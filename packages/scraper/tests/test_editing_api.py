"""Tests for the editing API endpoints."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.services.highlighter_registry import HighlighterRegistry, HighlighterSession
from app.services.field_highlighter import FieldHighlighter


client = TestClient(app)

ANALYSIS_ID = "test-analysis-edit-001"

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


def _make_mock_session(task_id: str = ANALYSIS_ID) -> HighlighterSession:
    """Create a mock HighlighterSession."""
    page = AsyncMock()
    page.evaluate = AsyncMock(return_value={"found": True, "matchCount": 1})
    page.goto = AsyncMock()
    page.wait_for_timeout = AsyncMock()

    highlighter = AsyncMock(spec=FieldHighlighter)
    highlighter.set_mode = AsyncMock()
    highlighter.update_fields = AsyncMock()
    highlighter.focus_field = AsyncMock()
    highlighter.test_selector = AsyncMock(return_value={"found": True, "matchCount": 1})
    highlighter.fill_field = AsyncMock()
    highlighter.read_field_value = AsyncMock(return_value="")
    highlighter.cleanup = AsyncMock()

    browser = AsyncMock()
    context = AsyncMock()
    pw = AsyncMock()

    session = HighlighterSession(
        task_id=task_id,
        highlighter=highlighter,
        browser=browser,
        context=context,
        page=page,
        pw=pw,
        vnc_session_id="vnc-sess-001",
        fields=SAMPLE_FIELDS.copy(),
    )
    return session


@pytest.fixture(autouse=True)
def clean_registry():
    """Reset the registry before each test."""
    registry = HighlighterRegistry.get_instance()
    registry._sessions.clear()
    yield
    registry._sessions.clear()


def _register_session(session=None):
    """Helper to register a mock session synchronously."""
    registry = HighlighterRegistry.get_instance()
    session = session or _make_mock_session()
    registry._sessions[session.task_id] = session
    return session


# ----- Test /editing/mode -----

def test_set_mode_success():
    session = _register_session()
    resp = client.post("/editing/mode", json={
        "task_id": ANALYSIS_ID,
        "mode": "select",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.json()["mode"] == "select"
    session.highlighter.set_mode.assert_called_once_with("select")


def test_set_mode_invalid_mode():
    _register_session()
    resp = client.post("/editing/mode", json={
        "task_id": ANALYSIS_ID,
        "mode": "invalid",
    })
    assert resp.status_code == 400


def test_set_mode_session_not_found():
    resp = client.post("/editing/mode", json={
        "task_id": "nonexistent",
        "mode": "select",
    })
    assert resp.status_code == 404


def test_set_mode_blocked_while_navigating():
    session = _register_session()
    session.navigating = True
    resp = client.post("/editing/mode", json={
        "task_id": ANALYSIS_ID,
        "mode": "add",
    })
    assert resp.status_code == 409


# ----- Test /editing/update-fields -----

def test_update_fields_success():
    session = _register_session()
    new_fields = [{"field_selector": "#email", "field_name": "email", "field_type": "email"}]
    resp = client.post("/editing/update-fields", json={
        "task_id": ANALYSIS_ID,
        "fields": new_fields,
    })
    assert resp.status_code == 200
    assert resp.json()["field_count"] == 1
    session.highlighter.update_fields.assert_called_once_with(new_fields)


def test_update_fields_session_not_found():
    resp = client.post("/editing/update-fields", json={
        "task_id": "nonexistent",
        "fields": [],
    })
    assert resp.status_code == 404


# ----- Test /editing/focus-field -----

def test_focus_field_success():
    session = _register_session()
    resp = client.post("/editing/focus-field", json={
        "task_id": ANALYSIS_ID,
        "field_index": 0,
    })
    assert resp.status_code == 200
    session.highlighter.focus_field.assert_called_once_with(0)


def test_focus_field_session_not_found():
    resp = client.post("/editing/focus-field", json={
        "task_id": "nonexistent",
        "field_index": 0,
    })
    assert resp.status_code == 404


# ----- Test /editing/test-selector -----

def test_test_selector_found():
    session = _register_session()
    resp = client.post("/editing/test-selector", json={
        "task_id": ANALYSIS_ID,
        "selector": "#username",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["found"] is True
    assert data["matchCount"] == 1


def test_test_selector_not_found():
    session = _register_session()
    session.highlighter.test_selector = AsyncMock(return_value={"found": False, "matchCount": 0})
    resp = client.post("/editing/test-selector", json={
        "task_id": ANALYSIS_ID,
        "selector": ".nonexistent",
    })
    assert resp.status_code == 200
    assert resp.json()["found"] is False


# ----- Test /editing/fill-field -----

def test_fill_field_success():
    session = _register_session()
    resp = client.post("/editing/fill-field", json={
        "task_id": ANALYSIS_ID,
        "field_index": 0,
        "value": "testuser",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    session.highlighter.fill_field.assert_called_once_with(0, "testuser")


def test_fill_field_session_not_found():
    resp = client.post("/editing/fill-field", json={
        "task_id": "nonexistent",
        "field_index": 0,
        "value": "test",
    })
    assert resp.status_code == 404


# ----- Test /editing/read-field-value -----

def test_read_field_value_success():
    session = _register_session()
    session.highlighter.read_field_value = AsyncMock(return_value="current_value")
    resp = client.post("/editing/read-field-value", json={
        "task_id": ANALYSIS_ID,
        "field_index": 0,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["value"] == "current_value"
    session.highlighter.read_field_value.assert_called_once_with(0)


def test_read_field_value_session_not_found():
    resp = client.post("/editing/read-field-value", json={
        "task_id": "nonexistent",
        "field_index": 0,
    })
    assert resp.status_code == 404


# ----- Test /editing/confirm -----

def test_confirm_success():
    session = _register_session()
    resp = client.post("/editing/confirm", json={"task_id": ANALYSIS_ID})
    assert resp.status_code == 200
    assert resp.json()["status"] == "confirmed"
    assert session.confirmed_event.is_set()


def test_confirm_session_not_found():
    resp = client.post("/editing/confirm", json={"task_id": "nonexistent"})
    assert resp.status_code == 404


# ----- Test /editing/cancel -----

def test_cancel_success():
    session = _register_session()
    resp = client.post("/editing/cancel", json={"task_id": ANALYSIS_ID})
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"
    assert session.cancelled_event.is_set()


# ----- Test /editing/cleanup -----

def test_cleanup_success():
    session = _register_session()
    resp = client.post("/editing/cleanup", json={"task_id": ANALYSIS_ID})
    assert resp.status_code == 200
    assert resp.json()["status"] == "cleaned_up"

    # Session should be removed
    registry = HighlighterRegistry.get_instance()
    assert registry.get(ANALYSIS_ID) is None


def test_cleanup_not_found():
    resp = client.post("/editing/cleanup", json={"task_id": "nonexistent"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "not_found"


# ----- Test /editing/navigate -----

def test_navigate_success():
    session = _register_session()
    resp = client.post("/editing/navigate", json={
        "task_id": ANALYSIS_ID,
        "url": "https://example.com/target",
    })
    assert resp.status_code == 200
    assert resp.json()["url"] == "https://example.com/target"
    session.page.goto.assert_called_once()


def test_navigate_broadcasts_started_and_completed_events():
    _register_session()
    with patch("app.api.editing.Broadcaster.get_instance") as mock_get:
        mock_broadcaster = MagicMock()
        mock_get.return_value = mock_broadcaster

        resp = client.post("/editing/navigate", json={
            "task_id": ANALYSIS_ID,
            "url": "https://example.com/target",
            "step": 2,
            "request_id": "nav-req-001",
        })

    assert resp.status_code == 200
    calls = [
        c for c in mock_broadcaster.trigger_task_editing.call_args_list
        if c.args[1] == "StepNavigationState"
    ]
    statuses = [c.args[2]["status"] for c in calls]
    assert "started" in statuses
    assert "completed" in statuses


def test_navigate_blocked_when_already_navigating():
    session = _register_session()
    session.navigating = True
    resp = client.post("/editing/navigate", json={
        "task_id": ANALYSIS_ID,
        "url": "https://example.com/target",
    })
    assert resp.status_code == 409


def test_navigate_blocked_when_executing():
    session = _register_session()
    session.executing = True
    resp = client.post("/editing/navigate", json={
        "task_id": ANALYSIS_ID,
        "url": "https://example.com/target",
    })
    assert resp.status_code == 409


def test_navigate_sets_busy_flag_and_clears_after_success():
    session = _register_session()

    async def _goto(*args, **kwargs):
        assert session.navigating is True

    session.page.goto = AsyncMock(side_effect=_goto)
    session.page.wait_for_timeout = AsyncMock()

    resp = client.post("/editing/navigate", json={
        "task_id": ANALYSIS_ID,
        "url": "https://example.com/target",
    })
    assert resp.status_code == 200
    assert session.navigating is False


def test_navigate_clears_busy_flag_on_failure():
    session = _register_session()

    async def _goto(*args, **kwargs):
        assert session.navigating is True
        raise RuntimeError("goto failed")

    session.page.goto = AsyncMock(side_effect=_goto)

    resp = client.post("/editing/navigate", json={
        "task_id": ANALYSIS_ID,
        "url": "https://example.com/target",
    })
    assert resp.status_code == 500
    assert session.navigating is False


def test_navigate_broadcasts_failed_event():
    session = _register_session()
    session.page.goto = AsyncMock(side_effect=RuntimeError("goto failed"))
    with patch("app.api.editing.Broadcaster.get_instance") as mock_get:
        mock_broadcaster = MagicMock()
        mock_get.return_value = mock_broadcaster

        resp = client.post("/editing/navigate", json={
            "task_id": ANALYSIS_ID,
            "url": "https://example.com/target",
            "request_id": "nav-req-fail",
        })

    assert resp.status_code == 500
    calls = [
        c for c in mock_broadcaster.trigger_task_editing.call_args_list
        if c.args[1] == "StepNavigationState"
    ]
    statuses = [c.args[2]["status"] for c in calls]
    assert "started" in statuses
    assert "failed" in statuses


def test_navigate_session_not_found():
    resp = client.post("/editing/navigate", json={
        "task_id": "nonexistent",
        "url": "https://example.com",
    })
    assert resp.status_code == 404


# ----- Test HighlighterRegistry -----

def test_registry_singleton():
    r1 = HighlighterRegistry.get_instance()
    r2 = HighlighterRegistry.get_instance()
    assert r1 is r2


@pytest.mark.asyncio
async def test_registry_register_and_get():
    registry = HighlighterRegistry.get_instance()
    session = _make_mock_session("reg-test-001")
    await registry.register(session)

    found = registry.get("reg-test-001")
    assert found is session

    # Cleanup
    await registry.remove("reg-test-001")


@pytest.mark.asyncio
async def test_registry_remove():
    registry = HighlighterRegistry.get_instance()
    session = _make_mock_session("reg-test-002")
    await registry.register(session)

    removed = await registry.remove("reg-test-002")
    assert removed is session
    assert registry.get("reg-test-002") is None


@pytest.mark.asyncio
async def test_registry_remove_nonexistent():
    registry = HighlighterRegistry.get_instance()
    removed = await registry.remove("nonexistent-id")
    assert removed is None


@pytest.mark.asyncio
async def test_registry_cleanup_session():
    registry = HighlighterRegistry.get_instance()
    session = _make_mock_session("cleanup-test")
    await registry.register(session)

    await registry.cleanup_session("cleanup-test")

    assert registry.get("cleanup-test") is None
    session.highlighter.cleanup.assert_called_once()
    session.browser.close.assert_called_once()


@pytest.mark.asyncio
async def test_registry_active_count():
    registry = HighlighterRegistry.get_instance()
    assert registry.active_count == 0

    s1 = _make_mock_session("count-1")
    s2 = _make_mock_session("count-2")
    await registry.register(s1)
    await registry.register(s2)
    assert registry.active_count == 2

    await registry.remove("count-1")
    assert registry.active_count == 1

    await registry.remove("count-2")
    assert registry.active_count == 0


# ----- Test /editing/execute-login -----

def test_execute_login_success():
    session = _register_session()
    resp = client.post("/editing/execute-login", json={
        "task_id": ANALYSIS_ID,
        "login_fields": [
            {"field_selector": "#username", "value": "user1"},
            {"field_selector": "#password", "value": "pass1", "field_type": "password", "is_sensitive": True},
        ],
        "target_url": "https://example.com/dashboard",
        "submit_selector": "button[type=submit]",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "started"


def test_execute_login_session_not_found():
    resp = client.post("/editing/execute-login", json={
        "task_id": "nonexistent",
        "login_fields": [],
        "target_url": "https://example.com",
    })
    assert resp.status_code == 404


def test_execute_login_already_executing():
    session = _register_session()
    session.executing = True
    resp = client.post("/editing/execute-login", json={
        "task_id": ANALYSIS_ID,
        "login_fields": [],
        "target_url": "https://example.com",
    })
    assert resp.status_code == 409


def test_execute_login_blocked_while_navigating():
    session = _register_session()
    session.navigating = True
    resp = client.post("/editing/execute-login", json={
        "task_id": ANALYSIS_ID,
        "login_fields": [],
        "target_url": "https://example.com",
    })
    assert resp.status_code == 409


# ----- Test /editing/resume-login -----

def test_resume_login_success():
    session = _register_session()
    resp = client.post("/editing/resume-login", json={"task_id": ANALYSIS_ID})
    assert resp.status_code == 200
    assert resp.json()["status"] == "resumed"
    assert session.resume_event.is_set()


def test_resume_login_session_not_found():
    resp = client.post("/editing/resume-login", json={"task_id": "nonexistent"})
    assert resp.status_code == 404


# ----- Test HighlighterSession resume_event and executing -----

def test_session_has_resume_event():
    session = _make_mock_session()
    assert hasattr(session, 'resume_event')
    assert isinstance(session.resume_event, asyncio.Event)
    assert not session.resume_event.is_set()


def test_session_has_executing_flag():
    session = _make_mock_session()
    assert hasattr(session, 'executing')
    assert session.executing is False


def test_session_has_navigating_flag():
    session = _make_mock_session()
    assert hasattr(session, 'navigating')
    assert session.navigating is False


# ----- Test /editing/execute-login always creates empty result -----

def test_execute_login_creates_empty_result():
    """After login, execute-login always creates an empty result for the
    target page (no AI analysis)."""
    session = _register_session()
    resp = client.post("/editing/execute-login", json={
        "task_id": ANALYSIS_ID,
        "login_fields": [],
        "target_url": "https://example.com/dashboard",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "started"
