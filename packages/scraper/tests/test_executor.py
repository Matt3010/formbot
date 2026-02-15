"""Tests for app.services.task_executor.TaskExecutor."""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

from tests.conftest import (
    make_task,
    make_form_definition,
    make_form_field,
    _make_mock_page,
    _make_mock_context,
    _make_mock_browser,
    _make_mock_playwright,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _setup_db_for_task(mock_db, task, form_defs, fields_by_form_def_id):
    """Wire up mock_db.query(...).filter(...).first()/.all() chains.

    ``fields_by_form_def_id`` maps form_def.id -> list of FormField mocks.
    """

    def _query_side_effect(model):
        q = MagicMock()

        model_name = getattr(model, "__name__", "") or str(model)

        if model_name == "Task":
            q.filter.return_value.first.return_value = task
            return q
        elif model_name == "FormDefinition":
            q.filter.return_value.order_by.return_value.all.return_value = form_defs
            return q
        elif model_name == "FormField":
            # Called once per form_def during field filling
            def _filter_side_effect(*args, **kwargs):
                inner = MagicMock()
                # We need to figure out which form_def_id was requested.
                # The executor calls FormField.form_definition_id == form_def.id
                # We'll match based on call order.
                return inner

            # Simpler approach: return fields in sequence via side_effect
            q.filter.return_value.order_by.return_value.all = MagicMock(
                side_effect=[
                    fields_by_form_def_id.get(fd.id, []) for fd in form_defs
                ]
            )
            return q

        return q

    mock_db.query = MagicMock(side_effect=_query_side_effect)


def _build_executor_patches(page, browser):
    """Return patches for async_playwright, apply_stealth, and ScreenshotStorage."""
    context = _make_mock_context(page)
    browser_mock = browser
    browser_mock.new_context = AsyncMock(return_value=context)
    pw_cm = _make_mock_playwright(browser_mock)

    pw_patch = patch(
        "app.services.task_executor.async_playwright",
        return_value=pw_cm,
    )
    stealth_patch = patch(
        "app.services.task_executor.apply_stealth",
        AsyncMock(),
    )
    screenshot_storage_mock = MagicMock()
    screenshot_storage_mock.upload_screenshot = MagicMock(return_value=("test-key", 12345))
    screenshot_storage_patch = patch(
        "app.services.task_executor.ScreenshotStorage.get_instance",
        return_value=screenshot_storage_mock,
    )
    return pw_patch, stealth_patch, screenshot_storage_patch, context


def _make_two_phase_vnc_mock(session_id="vnc-test-session"):
    """Create a VNC manager mock supporting the two-phase approach
    (reserve_display + activate_vnc) used by the task executor."""
    vnc = MagicMock()

    resume_event = MagicMock()
    vnc.sessions = {
        session_id: {"resume_event": resume_event},
    }

    vnc.reserve_display = AsyncMock(return_value={
        "session_id": session_id,
        "display": ":99",
    })

    vnc.activate_vnc = AsyncMock(return_value={
        "vnc_url": "http://localhost:6080/vnc_lite.html?token=test",
        "ws_port": 6080,
    })

    vnc.deactivate_vnc = MagicMock()
    vnc.wait_for_resume = AsyncMock(return_value=True)
    vnc.stop_session = AsyncMock(return_value={"status": "stopped"})

    return vnc


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_simple_single_form(mock_db, mock_vnc_manager):
    """Successful execution of a single login form with two text fields."""
    task_id = uuid.uuid4()
    form_def_id = uuid.uuid4()

    task = make_task(id=task_id)
    form_def = make_form_definition(
        id=form_def_id, task_id=task_id, step_order=1,
        page_url="https://example.com/login",
        form_selector="#login-form", submit_selector="#submit-btn",
        human_breakpoint=False,
    )
    username_field = make_form_field(
        form_definition_id=form_def_id, field_name="username",
        field_type="text", field_selector="#username",
        preset_value="testuser", is_sensitive=False, is_file_upload=False,
        sort_order=0,
    )
    password_field = make_form_field(
        form_definition_id=form_def_id, field_name="password",
        field_type="password", field_selector="#password",
        preset_value="secret", is_sensitive=False, is_file_upload=False,
        sort_order=1,
    )

    _setup_db_for_task(mock_db, task, [form_def], {
        form_def_id: [username_field, password_field],
    })

    page = _make_mock_page()
    browser = _make_mock_browser(_make_mock_context(page))
    pw_patch, stealth_patch, screenshot_patch, context = _build_executor_patches(page, browser)

    with pw_patch, stealth_patch, screenshot_patch:
        from app.services.task_executor import TaskExecutor

        executor = TaskExecutor(db=mock_db, vnc_manager=mock_vnc_manager)
        result = await executor.execute(str(task_id))

    assert result["status"] == "success"
    assert "execution_id" in result
    assert "screenshot" in result

    # Verify navigation
    page.goto.assert_awaited_once()
    assert page.goto.call_args[0][0] == "https://example.com/login"

    # Verify form selector was waited for
    page.wait_for_selector.assert_awaited_once_with("#login-form", timeout=10000)

    # Verify fields were filled
    assert page.fill.await_count == 2
    fill_calls = page.fill.call_args_list
    assert fill_calls[0][0] == ("#username", "testuser")
    assert fill_calls[1][0] == ("#password", "secret")

    # Verify submit was clicked
    page.click.assert_awaited_once_with("#submit-btn")

    # Verify screenshot taken
    page.screenshot.assert_awaited_once()

    # Verify browser closed
    browser.close.assert_awaited_once()

    # Verify DB commit was called (execution log updates)
    assert mock_db.commit.call_count >= 2


@pytest.mark.asyncio
async def test_execute_multi_step(mock_db, mock_vnc_manager):
    """Execution with two form steps: login -> target form."""
    task_id = uuid.uuid4()
    fd1_id = uuid.uuid4()
    fd2_id = uuid.uuid4()

    task = make_task(id=task_id)
    form_def_1 = make_form_definition(
        id=fd1_id, task_id=task_id, step_order=1,
        page_url="https://example.com/login",
        form_selector="#login-form", submit_selector="#login-submit",
        human_breakpoint=False,
    )
    form_def_2 = make_form_definition(
        id=fd2_id, task_id=task_id, step_order=2,
        page_url="https://example.com/dashboard/form",
        form_selector="#data-form", submit_selector="#data-submit",
        human_breakpoint=False,
    )
    login_field = make_form_field(
        form_definition_id=fd1_id, field_name="user",
        field_type="text", field_selector="#user",
        preset_value="admin", sort_order=0,
    )
    data_field = make_form_field(
        form_definition_id=fd2_id, field_name="amount",
        field_type="number", field_selector="#amount",
        preset_value="100", sort_order=0,
    )

    _setup_db_for_task(mock_db, task, [form_def_1, form_def_2], {
        fd1_id: [login_field],
        fd2_id: [data_field],
    })

    page = _make_mock_page()
    browser = _make_mock_browser(_make_mock_context(page))
    pw_patch, stealth_patch, screenshot_patch, context = _build_executor_patches(page, browser)

    with pw_patch, stealth_patch, screenshot_patch:
        from app.services.task_executor import TaskExecutor

        executor = TaskExecutor(db=mock_db, vnc_manager=mock_vnc_manager)
        result = await executor.execute(str(task_id))

    assert result["status"] == "success"

    # Two navigations (one per step)
    assert page.goto.await_count == 2
    urls_navigated = [c[0][0] for c in page.goto.call_args_list]
    assert urls_navigated[0] == "https://example.com/login"
    assert urls_navigated[1] == "https://example.com/dashboard/form"

    # Two submits
    assert page.click.await_count == 2
    submit_selectors = [c[0][0] for c in page.click.call_args_list]
    assert "#login-submit" in submit_selectors
    assert "#data-submit" in submit_selectors

    # Two form selectors waited for
    assert page.wait_for_selector.await_count == 2


@pytest.mark.asyncio
async def test_execute_multi_step_uses_dependency_graph_order(mock_db, mock_vnc_manager):
    """Steps are executed in dependency order, not only by step_order."""
    task_id = uuid.uuid4()
    root_id = uuid.uuid4()
    late_child_id = uuid.uuid4()
    middle_child_id = uuid.uuid4()

    task = make_task(id=task_id)
    root_step = make_form_definition(
        id=root_id, task_id=task_id, step_order=1,
        depends_on_step_order=None,
        page_url="https://example.com/root",
        form_selector="#root-form", submit_selector="#root-submit",
        human_breakpoint=False,
    )
    # This one has a lower step_order but depends on step 3.
    late_child_step = make_form_definition(
        id=late_child_id, task_id=task_id, step_order=2,
        depends_on_step_order=3,
        page_url="https://example.com/late-child",
        form_selector="#late-form", submit_selector="#late-submit",
        human_breakpoint=False,
    )
    middle_child_step = make_form_definition(
        id=middle_child_id, task_id=task_id, step_order=3,
        depends_on_step_order=1,
        page_url="https://example.com/middle-child",
        form_selector="#middle-form", submit_selector="#middle-submit",
        human_breakpoint=False,
    )

    _setup_db_for_task(mock_db, task, [root_step, late_child_step, middle_child_step], {
        root_id: [],
        late_child_id: [],
        middle_child_id: [],
    })

    page = _make_mock_page()
    browser = _make_mock_browser(_make_mock_context(page))
    pw_patch, stealth_patch, screenshot_patch, context = _build_executor_patches(page, browser)

    with pw_patch, stealth_patch, screenshot_patch:
        from app.services.task_executor import TaskExecutor

        executor = TaskExecutor(db=mock_db, vnc_manager=mock_vnc_manager)
        result = await executor.execute(str(task_id))

    assert result["status"] == "success"

    visited_urls = [call[0][0] for call in page.goto.call_args_list]
    assert visited_urls == [
        "https://example.com/root",
        "https://example.com/middle-child",
        "https://example.com/late-child",
    ]


@pytest.mark.asyncio
async def test_execute_dry_run(mock_db, mock_vnc_manager):
    """Dry run stops before final submit and returns dry_run_ok."""
    task_id = uuid.uuid4()
    fd_id = uuid.uuid4()

    task = make_task(id=task_id)
    form_def = make_form_definition(
        id=fd_id, task_id=task_id, step_order=1,
        page_url="https://example.com/form",
        form_selector="#form", submit_selector="#submit",
        human_breakpoint=False,
    )
    field = make_form_field(
        form_definition_id=fd_id, field_name="name",
        field_type="text", field_selector="#name",
        preset_value="John", sort_order=0,
    )

    _setup_db_for_task(mock_db, task, [form_def], {fd_id: [field]})

    page = _make_mock_page()
    browser = _make_mock_browser(_make_mock_context(page))
    pw_patch, stealth_patch, screenshot_patch, context = _build_executor_patches(page, browser)

    with pw_patch, stealth_patch, screenshot_patch:
        from app.services.task_executor import TaskExecutor

        executor = TaskExecutor(db=mock_db, vnc_manager=mock_vnc_manager)
        result = await executor.execute(str(task_id), is_dry_run=True)

    assert result["status"] == "dry_run_ok"
    assert "screenshot" in result

    # Field was filled
    page.fill.assert_awaited_once_with("#name", "John")

    # Submit was NOT clicked (dry run)
    page.click.assert_not_awaited()

    # Screenshot was taken
    page.screenshot.assert_awaited_once()
    screenshot_kwargs = page.screenshot.call_args[1]
    assert screenshot_kwargs["full_page"] is True

    # Browser was closed
    browser.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_with_human_breakpoint_triggers_vnc_pause(mock_db):
    """When human_breakpoint=True, a VNC pause is triggered for manual intervention."""
    task_id = uuid.uuid4()
    fd_id = uuid.uuid4()

    task = make_task(id=task_id)
    form_def = make_form_definition(
        id=fd_id, task_id=task_id, step_order=1,
        page_url="https://example.com/test",
        form_selector="#test-form", submit_selector="#submit",
        human_breakpoint=True,
    )
    field = make_form_field(
        form_definition_id=fd_id, field_name="name",
        field_type="text", field_selector="#name",
        preset_value="Test", sort_order=0,
    )

    _setup_db_for_task(mock_db, task, [form_def], {fd_id: [field]})

    page = _make_mock_page()
    browser = _make_mock_browser(_make_mock_context(page))
    pw_patch, stealth_patch, screenshot_patch, context = _build_executor_patches(page, browser)

    vnc_mock = _make_two_phase_vnc_mock()

    broadcaster_patch = patch(
        "app.services.task_executor.Broadcaster.get_instance",
        return_value=MagicMock(),
    )

    with pw_patch, stealth_patch, screenshot_patch, broadcaster_patch:
        from app.services.task_executor import TaskExecutor

        executor = TaskExecutor(db=mock_db, vnc_manager=vnc_mock)
        result = await executor.execute(str(task_id))

    assert result["status"] == "success"

    # VNC display was reserved
    vnc_mock.reserve_display.assert_awaited_once()

    # VNC was activated for manual intervention
    vnc_mock.activate_vnc.assert_awaited_once()

    # VNC was waited on
    vnc_mock.wait_for_resume.assert_awaited_once()

    # VNC was stopped after execution
    vnc_mock.stop_session.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_with_breakpoint_triggers_post_submit_vnc(mock_db):
    """When human_breakpoint=True, VNC pause is triggered for manual intervention during execution."""
    task_id = uuid.uuid4()
    fd_id = uuid.uuid4()

    task = make_task(id=task_id)
    form_def = make_form_definition(
        id=fd_id, task_id=task_id, step_order=1,
        page_url="https://example.com/login",
        form_selector="#login-form", submit_selector="#submit",
        human_breakpoint=True,
    )
    field = make_form_field(
        form_definition_id=fd_id, field_name="user",
        field_type="text", field_selector="#user",
        preset_value="admin", sort_order=0,
    )

    _setup_db_for_task(mock_db, task, [form_def], {fd_id: [field]})

    page = _make_mock_page()
    browser = _make_mock_browser(_make_mock_context(page))
    pw_patch, stealth_patch, screenshot_patch, context = _build_executor_patches(page, browser)

    vnc_mock = _make_two_phase_vnc_mock()

    broadcaster_patch = patch(
        "app.services.task_executor.Broadcaster.get_instance",
        return_value=MagicMock(),
    )

    with pw_patch, stealth_patch, screenshot_patch, broadcaster_patch:
        from app.services.task_executor import TaskExecutor

        executor = TaskExecutor(db=mock_db, vnc_manager=vnc_mock)
        result = await executor.execute(str(task_id))

    assert result["status"] == "success"

    # Submit was clicked (manual intervention pause is POST-submit)
    page.click.assert_awaited_once_with("#submit")

    # VNC display was reserved and activated for manual intervention
    vnc_mock.reserve_display.assert_awaited_once()
    vnc_mock.activate_vnc.assert_awaited_once()
    vnc_mock.wait_for_resume.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_vnc_timeout_fails(mock_db):
    """When VNC wait_for_resume times out, execution fails."""
    task_id = uuid.uuid4()
    fd_id = uuid.uuid4()

    task = make_task(id=task_id)
    form_def = make_form_definition(
        id=fd_id, task_id=task_id, step_order=1,
        page_url="https://example.com/test",
        form_selector="#form", submit_selector="#submit",
        human_breakpoint=True,
    )

    _setup_db_for_task(mock_db, task, [form_def], {fd_id: []})

    page = _make_mock_page()
    browser = _make_mock_browser(_make_mock_context(page))
    pw_patch, stealth_patch, screenshot_patch, context = _build_executor_patches(page, browser)

    # VNC times out
    vnc_mock = _make_two_phase_vnc_mock()
    vnc_mock.wait_for_resume = AsyncMock(return_value=False)

    broadcaster_patch = patch(
        "app.services.task_executor.Broadcaster.get_instance",
        return_value=MagicMock(),
    )

    with pw_patch, stealth_patch, screenshot_patch, broadcaster_patch:
        from app.services.task_executor import TaskExecutor

        executor = TaskExecutor(db=mock_db, vnc_manager=vnc_mock)
        result = await executor.execute(str(task_id))

    assert result["status"] == "failed"
    assert "VNC timeout" in result["error"]

    # VNC session cleaned up via finally block
    vnc_mock.stop_session.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_task_not_found(mock_db, mock_vnc_manager):
    """execute raises ValueError when the task does not exist."""
    mock_db.query.return_value.filter.return_value.first.return_value = None

    screenshot_storage_mock = MagicMock()
    screenshot_storage_mock.upload_screenshot = MagicMock(return_value=("test-key", 12345))

    with patch("app.services.task_executor.ScreenshotStorage.get_instance", return_value=screenshot_storage_mock):
        from app.services.task_executor import TaskExecutor

        executor = TaskExecutor(db=mock_db, vnc_manager=mock_vnc_manager)

        with pytest.raises(ValueError, match="not found"):
            await executor.execute("nonexistent-task-id")


@pytest.mark.asyncio
async def test_execute_form_selector_not_found(mock_db, mock_vnc_manager):
    """When the form selector is not found on the page, execution fails."""
    task_id = uuid.uuid4()
    fd_id = uuid.uuid4()

    task = make_task(id=task_id)
    form_def = make_form_definition(
        id=fd_id, task_id=task_id, step_order=1,
        page_url="https://example.com/form",
        form_selector="#nonexistent-form", submit_selector="#submit",
        human_breakpoint=False,
    )

    _setup_db_for_task(mock_db, task, [form_def], {fd_id: []})

    page = _make_mock_page()
    page.wait_for_selector = AsyncMock(side_effect=Exception("Timeout 10000ms exceeded"))
    browser = _make_mock_browser(_make_mock_context(page))
    pw_patch, stealth_patch, screenshot_patch, context = _build_executor_patches(page, browser)

    with pw_patch, stealth_patch, screenshot_patch:
        from app.services.task_executor import TaskExecutor

        executor = TaskExecutor(db=mock_db, vnc_manager=mock_vnc_manager)
        result = await executor.execute(str(task_id))

    assert result["status"] == "failed"
    assert "not found" in result["error"]


@pytest.mark.asyncio
async def test_execute_stealth_mode(mock_db, mock_vnc_manager):
    """Stealth is applied when stealth_enabled=True."""
    task_id = uuid.uuid4()
    fd_id = uuid.uuid4()

    task = make_task(id=task_id)
    form_def = make_form_definition(
        id=fd_id, task_id=task_id, step_order=1,
        page_url="https://example.com/form",
        form_selector="#form", submit_selector="#submit",
        human_breakpoint=False,
    )

    _setup_db_for_task(mock_db, task, [form_def], {fd_id: []})

    page = _make_mock_page()
    browser = _make_mock_browser(_make_mock_context(page))
    stealth_mock = AsyncMock()
    context = _make_mock_context(page)
    browser.new_context = AsyncMock(return_value=context)
    pw_cm = _make_mock_playwright(browser)

    pw_patch = patch(
        "app.services.task_executor.async_playwright",
        return_value=pw_cm,
    )
    stealth_patch = patch(
        "app.services.task_executor.apply_stealth",
        stealth_mock,
    )
    screenshot_storage_mock = MagicMock()
    screenshot_storage_mock.upload_screenshot = MagicMock(return_value=("test-key", 12345))
    screenshot_patch = patch(
        "app.services.task_executor.ScreenshotStorage.get_instance",
        return_value=screenshot_storage_mock,
    )

    with pw_patch, stealth_patch, screenshot_patch:
        from app.services.task_executor import TaskExecutor

        executor = TaskExecutor(db=mock_db, vnc_manager=mock_vnc_manager)
        await executor.execute(str(task_id), stealth_enabled=True)

    stealth_mock.assert_awaited_once_with(context)


@pytest.mark.asyncio
async def test_execute_field_filling_select(mock_db, mock_vnc_manager):
    """Select fields use page.select_option."""
    task_id = uuid.uuid4()
    fd_id = uuid.uuid4()

    task = make_task(id=task_id)
    form_def = make_form_definition(
        id=fd_id, task_id=task_id, step_order=1,
        form_selector="#form", submit_selector="#submit",
        human_breakpoint=False,
    )
    select_field = make_form_field(
        form_definition_id=fd_id, field_name="country",
        field_type="select", field_selector="#country",
        preset_value="US", sort_order=0,
    )

    _setup_db_for_task(mock_db, task, [form_def], {fd_id: [select_field]})

    page = _make_mock_page()
    browser = _make_mock_browser(_make_mock_context(page))
    pw_patch, stealth_patch, screenshot_patch, context = _build_executor_patches(page, browser)

    with pw_patch, stealth_patch, screenshot_patch:
        from app.services.task_executor import TaskExecutor

        executor = TaskExecutor(db=mock_db, vnc_manager=mock_vnc_manager)
        result = await executor.execute(str(task_id))

    assert result["status"] == "success"
    page.select_option.assert_awaited_once_with("#country", "US")


@pytest.mark.asyncio
async def test_execute_field_filling_checkbox(mock_db, mock_vnc_manager):
    """Checkbox fields use page.check / page.uncheck based on value."""
    task_id = uuid.uuid4()
    fd_id = uuid.uuid4()

    task = make_task(id=task_id)
    form_def = make_form_definition(
        id=fd_id, task_id=task_id, step_order=1,
        form_selector="#form", submit_selector="#submit",
        human_breakpoint=False,
    )
    checkbox_on = make_form_field(
        form_definition_id=fd_id, field_name="agree",
        field_type="checkbox", field_selector="#agree",
        preset_value="true", sort_order=0,
    )
    checkbox_off = make_form_field(
        form_definition_id=fd_id, field_name="newsletter",
        field_type="checkbox", field_selector="#newsletter",
        preset_value="false", sort_order=1,
    )

    _setup_db_for_task(mock_db, task, [form_def], {
        fd_id: [checkbox_on, checkbox_off],
    })

    page = _make_mock_page()
    browser = _make_mock_browser(_make_mock_context(page))
    pw_patch, stealth_patch, screenshot_patch, context = _build_executor_patches(page, browser)

    with pw_patch, stealth_patch, screenshot_patch:
        from app.services.task_executor import TaskExecutor

        executor = TaskExecutor(db=mock_db, vnc_manager=mock_vnc_manager)
        result = await executor.execute(str(task_id))

    assert result["status"] == "success"
    page.check.assert_awaited_once_with("#agree")
    page.uncheck.assert_awaited_once_with("#newsletter")


@pytest.mark.asyncio
async def test_execute_field_filling_file_upload(mock_db, mock_vnc_manager):
    """File upload fields use page.set_input_files."""
    task_id = uuid.uuid4()
    fd_id = uuid.uuid4()

    task = make_task(id=task_id)
    form_def = make_form_definition(
        id=fd_id, task_id=task_id, step_order=1,
        form_selector="#form", submit_selector="#submit",
        human_breakpoint=False,
    )
    file_field = make_form_field(
        form_definition_id=fd_id, field_name="document",
        field_type="file", field_selector="#document",
        preset_value="report.pdf", is_file_upload=True, sort_order=0,
    )

    _setup_db_for_task(mock_db, task, [form_def], {fd_id: [file_field]})

    page = _make_mock_page()
    browser = _make_mock_browser(_make_mock_context(page))
    pw_patch, stealth_patch, screenshot_patch, context = _build_executor_patches(page, browser)

    with pw_patch, stealth_patch, screenshot_patch:
        from app.services.task_executor import TaskExecutor

        executor = TaskExecutor(db=mock_db, vnc_manager=mock_vnc_manager)
        result = await executor.execute(str(task_id))

    assert result["status"] == "success"
    page.set_input_files.assert_awaited_once()
    call_args = page.set_input_files.call_args[0]
    assert call_args[0] == "#document"
    assert "report.pdf" in call_args[1]


@pytest.mark.asyncio
async def test_execute_field_filling_hidden(mock_db, mock_vnc_manager):
    """Hidden fields use page.eval_on_selector to set value."""
    task_id = uuid.uuid4()
    fd_id = uuid.uuid4()

    task = make_task(id=task_id)
    form_def = make_form_definition(
        id=fd_id, task_id=task_id, step_order=1,
        form_selector="#form", submit_selector="#submit",
        human_breakpoint=False,
    )
    hidden_field = make_form_field(
        form_definition_id=fd_id, field_name="token",
        field_type="hidden", field_selector="#token",
        preset_value="abc123", sort_order=0,
    )

    _setup_db_for_task(mock_db, task, [form_def], {fd_id: [hidden_field]})

    page = _make_mock_page()
    browser = _make_mock_browser(_make_mock_context(page))
    pw_patch, stealth_patch, screenshot_patch, context = _build_executor_patches(page, browser)

    with pw_patch, stealth_patch, screenshot_patch:
        from app.services.task_executor import TaskExecutor

        executor = TaskExecutor(db=mock_db, vnc_manager=mock_vnc_manager)
        result = await executor.execute(str(task_id))

    assert result["status"] == "success"
    page.eval_on_selector.assert_awaited_once()
    call_args = page.eval_on_selector.call_args[0]
    assert call_args[0] == "#token"
    assert call_args[2] == "abc123"


@pytest.mark.asyncio
async def test_execute_skips_field_with_no_preset(mock_db, mock_vnc_manager):
    """Fields with preset_value=None are skipped during filling."""
    task_id = uuid.uuid4()
    fd_id = uuid.uuid4()

    task = make_task(id=task_id)
    form_def = make_form_definition(
        id=fd_id, task_id=task_id, step_order=1,
        form_selector="#form", submit_selector="#submit",
        human_breakpoint=False,
    )
    no_value_field = make_form_field(
        form_definition_id=fd_id, field_name="optional",
        field_type="text", field_selector="#optional",
        preset_value=None, sort_order=0,
    )

    _setup_db_for_task(mock_db, task, [form_def], {fd_id: [no_value_field]})

    page = _make_mock_page()
    browser = _make_mock_browser(_make_mock_context(page))
    pw_patch, stealth_patch, screenshot_patch, context = _build_executor_patches(page, browser)

    with pw_patch, stealth_patch, screenshot_patch:
        from app.services.task_executor import TaskExecutor

        executor = TaskExecutor(db=mock_db, vnc_manager=mock_vnc_manager)
        result = await executor.execute(str(task_id))

    assert result["status"] == "success"
    # No fill/select/check methods should have been called
    page.fill.assert_not_awaited()
    page.select_option.assert_not_awaited()
    page.check.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_field_error_continues(mock_db, mock_vnc_manager):
    """If a field fill fails, the error is logged but execution continues."""
    task_id = uuid.uuid4()
    fd_id = uuid.uuid4()

    task = make_task(id=task_id)
    form_def = make_form_definition(
        id=fd_id, task_id=task_id, step_order=1,
        form_selector="#form", submit_selector="#submit",
        human_breakpoint=False,
    )
    bad_field = make_form_field(
        form_definition_id=fd_id, field_name="broken",
        field_type="text", field_selector="#broken",
        preset_value="value", sort_order=0,
    )
    good_field = make_form_field(
        form_definition_id=fd_id, field_name="working",
        field_type="text", field_selector="#working",
        preset_value="ok", sort_order=1,
    )

    _setup_db_for_task(mock_db, task, [form_def], {fd_id: [bad_field, good_field]})

    page = _make_mock_page()
    # First fill call fails, second succeeds
    page.fill = AsyncMock(side_effect=[Exception("Element not found"), None])
    browser = _make_mock_browser(_make_mock_context(page))
    pw_patch, stealth_patch, screenshot_patch, context = _build_executor_patches(page, browser)

    with pw_patch, stealth_patch, screenshot_patch:
        from app.services.task_executor import TaskExecutor

        executor = TaskExecutor(db=mock_db, vnc_manager=mock_vnc_manager)
        result = await executor.execute(str(task_id))

    # Execution still succeeds (field errors are non-fatal)
    assert result["status"] == "success"
    # Both fills were attempted
    assert page.fill.await_count == 2


@pytest.mark.asyncio
async def test_execute_dry_run_multi_step(mock_db, mock_vnc_manager):
    """In a multi-step dry run, only the LAST step skips submit."""
    task_id = uuid.uuid4()
    fd1_id = uuid.uuid4()
    fd2_id = uuid.uuid4()

    task = make_task(id=task_id)
    form_def_1 = make_form_definition(
        id=fd1_id, task_id=task_id, step_order=1,
        page_url="https://example.com/login",
        form_selector="#login", submit_selector="#login-btn",
        human_breakpoint=False,
    )
    form_def_2 = make_form_definition(
        id=fd2_id, task_id=task_id, step_order=2,
        page_url="https://example.com/form",
        form_selector="#form", submit_selector="#submit-btn",
        human_breakpoint=False,
    )

    _setup_db_for_task(mock_db, task, [form_def_1, form_def_2], {
        fd1_id: [],
        fd2_id: [],
    })

    page = _make_mock_page()
    browser = _make_mock_browser(_make_mock_context(page))
    pw_patch, stealth_patch, screenshot_patch, context = _build_executor_patches(page, browser)

    with pw_patch, stealth_patch, screenshot_patch:
        from app.services.task_executor import TaskExecutor

        executor = TaskExecutor(db=mock_db, vnc_manager=mock_vnc_manager)
        result = await executor.execute(str(task_id), is_dry_run=True)

    assert result["status"] == "dry_run_ok"

    # First step's submit WAS clicked (dry run only skips the last step)
    page.click.assert_awaited_once_with("#login-btn")

    # Screenshot was taken
    page.screenshot.assert_awaited_once()


# ---------------------------------------------------------------------------
# Bug fix regression tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_duplicate_step_in_steps_log_after_manual_intervention(mock_db):
    """After manual intervention is resolved, steps_log should contain exactly one entry
    per step — no duplicates from _vnc_pause + main loop both appending.

    Regression test for: _vnc_pause appended step_info to steps_log, then
    the main loop appended it again after submit, causing duplicate entries.
    """
    task_id = uuid.uuid4()
    fd_id = uuid.uuid4()

    task = make_task(id=task_id)
    form_def = make_form_definition(
        id=fd_id, task_id=task_id, step_order=1,
        page_url="https://example.com/test",
        form_selector="#test-form", submit_selector="button[type='submit']",
        human_breakpoint=True,
    )
    field = make_form_field(
        form_definition_id=fd_id, field_name="name",
        field_type="text", field_selector="#name",
        preset_value="Test", sort_order=0,
    )

    _setup_db_for_task(mock_db, task, [form_def], {fd_id: [field]})

    page = _make_mock_page()
    browser = _make_mock_browser(_make_mock_context(page))
    pw_patch, stealth_patch, screenshot_patch, _ = _build_executor_patches(page, browser)

    vnc_mock = _make_two_phase_vnc_mock()

    broadcaster_patch = patch(
        "app.services.task_executor.Broadcaster.get_instance",
        return_value=MagicMock(),
    )

    # Capture the execution object to inspect steps_log
    added_objects = []
    mock_db.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

    with pw_patch, stealth_patch, screenshot_patch, broadcaster_patch:
        from app.services.task_executor import TaskExecutor

        executor = TaskExecutor(db=mock_db, vnc_manager=vnc_mock)
        result = await executor.execute(str(task_id))

    assert result["status"] == "success"

    # Get the execution log object that was created
    assert len(added_objects) == 1
    execution = added_objects[0]

    # steps_log should have exactly 1 entry (one form step)
    assert len(execution.steps_log) == 1, (
        f"Expected 1 step in steps_log, got {len(execution.steps_log)}"
    )

    # The single entry should have status "submitted" (final state)
    assert execution.steps_log[0]["status"] == "submitted"


@pytest.mark.asyncio
async def test_vnc_cleanup_on_execution_exception(mock_db):
    """VNC session is always cleaned up via finally, even when an unexpected
    exception occurs during execution (e.g., navigation fails).

    Regression test for: stop_session was only called in the success path,
    leaving Xvfb/x11vnc processes running on failure or exception.
    """
    task_id = uuid.uuid4()
    fd_id = uuid.uuid4()

    task = make_task(id=task_id)
    form_def = make_form_definition(
        id=fd_id, task_id=task_id, step_order=1,
        page_url="https://example.com/test",
        form_selector="#form", submit_selector="#submit",
        human_breakpoint=True,
    )

    _setup_db_for_task(mock_db, task, [form_def], {fd_id: []})

    # Navigation throws an unexpected exception
    page = _make_mock_page()
    page.goto = AsyncMock(side_effect=Exception("DNS resolution failed"))
    browser = _make_mock_browser(_make_mock_context(page))
    pw_patch, stealth_patch, screenshot_patch, _ = _build_executor_patches(page, browser)

    vnc_mock = _make_two_phase_vnc_mock()

    broadcaster_patch = patch(
        "app.services.task_executor.Broadcaster.get_instance",
        return_value=MagicMock(),
    )

    with pw_patch, stealth_patch, screenshot_patch, broadcaster_patch:
        from app.services.task_executor import TaskExecutor

        executor = TaskExecutor(db=mock_db, vnc_manager=vnc_mock)
        result = await executor.execute(str(task_id))

    assert result["status"] == "failed"
    assert "DNS resolution failed" in result["error"]

    # VNC display was reserved (needs_vnc=True due to human_breakpoint)
    vnc_mock.reserve_display.assert_awaited_once()

    # VNC session is cleaned up by the finally block
    vnc_mock.stop_session.assert_awaited_once()


@pytest.mark.asyncio
async def test_vnc_cleanup_on_timeout_failure(mock_db):
    """VNC session is cleaned up when _vnc_pause times out.

    Regression test for: early return from execute() after _vnc_pause
    returned False would skip the stop_session call.
    """
    task_id = uuid.uuid4()
    fd_id = uuid.uuid4()

    task = make_task(id=task_id)
    form_def = make_form_definition(
        id=fd_id, task_id=task_id, step_order=1,
        page_url="https://example.com/test",
        form_selector="#form", submit_selector="#submit",
        human_breakpoint=True,
    )

    _setup_db_for_task(mock_db, task, [form_def], {fd_id: []})

    page = _make_mock_page()
    browser = _make_mock_browser(_make_mock_context(page))
    pw_patch, stealth_patch, screenshot_patch, _ = _build_executor_patches(page, browser)

    # VNC times out
    vnc_mock = _make_two_phase_vnc_mock()
    vnc_mock.wait_for_resume = AsyncMock(return_value=False)

    broadcaster_patch = patch(
        "app.services.task_executor.Broadcaster.get_instance",
        return_value=MagicMock(),
    )

    with pw_patch, stealth_patch, screenshot_patch, broadcaster_patch:
        from app.services.task_executor import TaskExecutor

        executor = TaskExecutor(db=mock_db, vnc_manager=vnc_mock)
        result = await executor.execute(str(task_id))

    assert result["status"] == "failed"

    # VNC session is cleaned up by the finally block even on timeout
    vnc_mock.stop_session.assert_awaited_once()
