"""Tests for FieldHighlighter service."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.field_highlighter import FieldHighlighter


SAMPLE_FIELDS = [
    {
        "field_selector": "#username",
        "field_name": "username",
        "field_type": "text",
        "field_purpose": "username",
    },
    {
        "field_selector": "#password",
        "field_name": "password",
        "field_type": "password",
        "field_purpose": "password",
    },
]


@pytest.fixture
def mock_page():
    page = AsyncMock()
    page.expose_function = AsyncMock()
    page.evaluate = AsyncMock()
    page.on = MagicMock()
    page.wait_for_timeout = AsyncMock()
    page.frames = [MagicMock()]  # just main frame
    page.main_frame = page.frames[0]
    return page


@pytest.fixture
def highlighter(mock_page):
    return FieldHighlighter(mock_page, analysis_id="test-analysis-123")


@pytest.mark.asyncio
async def test_setup_exposes_functions(highlighter, mock_page):
    """setup() should call expose_function for the 4 callbacks."""
    await highlighter.setup(SAMPLE_FIELDS)

    assert mock_page.expose_function.call_count == 4
    exposed_names = [call.args[0] for call in mock_page.expose_function.call_args_list]
    assert "__formbot_onFieldSelected" in exposed_names
    assert "__formbot_onFieldAdded" in exposed_names
    assert "__formbot_onFieldRemoved" in exposed_names
    assert "__formbot_onFieldValueChanged" in exposed_names


@pytest.mark.asyncio
async def test_setup_only_exposes_once(highlighter, mock_page):
    """Calling setup() twice should not re-expose functions."""
    await highlighter.setup(SAMPLE_FIELDS)
    await highlighter.setup(SAMPLE_FIELDS)

    assert mock_page.expose_function.call_count == 4  # not 8


@pytest.mark.asyncio
async def test_setup_registers_navigation_listeners(highlighter, mock_page):
    """setup() should register load and framenavigated event listeners."""
    await highlighter.setup(SAMPLE_FIELDS)

    events = [call.args[0] for call in mock_page.on.call_args_list]
    assert "load" in events
    assert "framenavigated" in events


@pytest.mark.asyncio
async def test_inject_evaluates_script_and_init(highlighter, mock_page):
    """inject() should evaluate the highlight.js script and call init()."""
    await highlighter.setup(SAMPLE_FIELDS)
    await highlighter.inject()

    # At least 2 evaluate calls: the script itself + init()
    assert mock_page.evaluate.call_count >= 2

    # Check init was called with the fields JSON
    init_calls = [
        c for c in mock_page.evaluate.call_args_list
        if "init(" in str(c)
    ]
    assert len(init_calls) == 1


@pytest.mark.asyncio
async def test_cleanup_evaluates_cleanup_command(highlighter, mock_page):
    """cleanup() should evaluate the cleanup command."""
    await highlighter.cleanup()

    mock_page.evaluate.assert_called_once()
    call_arg = mock_page.evaluate.call_args[0][0]
    assert "command_cleanup" in call_arg


@pytest.mark.asyncio
async def test_update_fields(highlighter, mock_page):
    """update_fields() should update internal state and call evaluate."""
    new_fields = [{"field_selector": "#email", "field_name": "email", "field_type": "email"}]
    await highlighter.update_fields(new_fields)

    assert highlighter._fields == new_fields
    call_arg = mock_page.evaluate.call_args[0][0]
    assert "command_updateFields" in call_arg


@pytest.mark.asyncio
async def test_set_mode(highlighter, mock_page):
    """set_mode() should evaluate setMode command."""
    await highlighter.set_mode("select")

    call_arg = mock_page.evaluate.call_args[0][0]
    assert "command_setMode" in call_arg
    assert "'select'" in call_arg


@pytest.mark.asyncio
async def test_focus_field(highlighter, mock_page):
    """focus_field() should evaluate focusField command with index."""
    await highlighter.focus_field(1)

    call_arg = mock_page.evaluate.call_args[0][0]
    assert "command_focusField" in call_arg
    assert "1" in call_arg


@pytest.mark.asyncio
async def test_test_selector(highlighter, mock_page):
    """test_selector() should evaluate and return result."""
    mock_page.evaluate = AsyncMock(return_value={"found": True, "matchCount": 1})

    result = await highlighter.test_selector("#username")

    assert result["found"] is True
    assert result["matchCount"] == 1


@pytest.mark.asyncio
async def test_test_selector_not_found(highlighter, mock_page):
    """test_selector() should handle not-found case."""
    mock_page.evaluate = AsyncMock(return_value={"found": False, "matchCount": 0})

    result = await highlighter.test_selector(".nonexistent")

    assert result["found"] is False
    assert result["matchCount"] == 0


@pytest.mark.asyncio
async def test_test_selector_returns_default_on_none(highlighter, mock_page):
    """test_selector() should return default dict if evaluate returns None."""
    mock_page.evaluate = AsyncMock(return_value=None)

    result = await highlighter.test_selector(".broken")

    assert result == {"found": False, "matchCount": 0}


@pytest.mark.asyncio
async def test_on_field_selected_broadcasts(highlighter):
    """_on_field_selected should broadcast FieldSelected event."""
    with patch.object(highlighter.broadcaster, "trigger_analysis") as mock_trigger:
        data = {"index": 0, "selector": "#username", "name": "username", "type": "text"}
        await highlighter._on_field_selected(json.dumps(data))

        mock_trigger.assert_called_once_with("test-analysis-123", "FieldSelected", data)


@pytest.mark.asyncio
async def test_on_field_added_broadcasts(highlighter):
    """_on_field_added should broadcast FieldAdded event."""
    with patch.object(highlighter.broadcaster, "trigger_analysis") as mock_trigger:
        data = {"selector": "#email", "tagName": "input", "type": "email", "name": "email"}
        await highlighter._on_field_added(json.dumps(data))

        mock_trigger.assert_called_once_with("test-analysis-123", "FieldAdded", data)


@pytest.mark.asyncio
async def test_on_field_removed_broadcasts(highlighter):
    """_on_field_removed should broadcast FieldRemoved event."""
    with patch.object(highlighter.broadcaster, "trigger_analysis") as mock_trigger:
        data = {"index": 1, "selector": "#password"}
        await highlighter._on_field_removed(json.dumps(data))

        mock_trigger.assert_called_once_with("test-analysis-123", "FieldRemoved", data)


@pytest.mark.asyncio
async def test_on_field_value_changed_broadcasts(highlighter):
    """_on_field_value_changed should broadcast FieldValueChanged event."""
    with patch.object(highlighter.broadcaster, "trigger_analysis") as mock_trigger:
        data = {"index": 0, "selector": "#username", "value": "testuser"}
        await highlighter._on_field_value_changed(json.dumps(data))

        mock_trigger.assert_called_once_with("test-analysis-123", "FieldValueChanged", data)


@pytest.mark.asyncio
async def test_fill_field(highlighter, mock_page):
    """fill_field() should evaluate command_fillField with index and value."""
    await highlighter.fill_field(0, "hello")

    call_arg = mock_page.evaluate.call_args[0][0]
    assert "command_fillField" in call_arg
    assert "0" in call_arg
    assert '"hello"' in call_arg


@pytest.mark.asyncio
async def test_read_field_value(highlighter, mock_page):
    """read_field_value() should evaluate command_readFieldValue and return result."""
    mock_page.evaluate = AsyncMock(return_value="current_val")

    result = await highlighter.read_field_value(1)

    assert result == "current_val"
    call_arg = mock_page.evaluate.call_args[0][0]
    assert "command_readFieldValue" in call_arg
    assert "1" in call_arg


@pytest.mark.asyncio
async def test_read_field_value_returns_empty_on_none(highlighter, mock_page):
    """read_field_value() should return empty string if evaluate returns None."""
    mock_page.evaluate = AsyncMock(return_value=None)

    result = await highlighter.read_field_value(0)

    assert result == ""
