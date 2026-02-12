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


def _make_mock_session(analysis_id: str = ANALYSIS_ID) -> HighlighterSession:
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
    highlighter.cleanup = AsyncMock()

    browser = AsyncMock()
    context = AsyncMock()
    pw = AsyncMock()

    session = HighlighterSession(
        analysis_id=analysis_id,
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
    registry._sessions[session.analysis_id] = session
    return session


# ----- Test /editing/mode -----

def test_set_mode_success():
    session = _register_session()
    resp = client.post("/editing/mode", json={
        "analysis_id": ANALYSIS_ID,
        "mode": "select",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.json()["mode"] == "select"
    session.highlighter.set_mode.assert_called_once_with("select")


def test_set_mode_invalid_mode():
    _register_session()
    resp = client.post("/editing/mode", json={
        "analysis_id": ANALYSIS_ID,
        "mode": "invalid",
    })
    assert resp.status_code == 400


def test_set_mode_session_not_found():
    resp = client.post("/editing/mode", json={
        "analysis_id": "nonexistent",
        "mode": "view",
    })
    assert resp.status_code == 404


# ----- Test /editing/update-fields -----

def test_update_fields_success():
    session = _register_session()
    new_fields = [{"field_selector": "#email", "field_name": "email", "field_type": "email"}]
    resp = client.post("/editing/update-fields", json={
        "analysis_id": ANALYSIS_ID,
        "fields": new_fields,
    })
    assert resp.status_code == 200
    assert resp.json()["field_count"] == 1
    session.highlighter.update_fields.assert_called_once_with(new_fields)


def test_update_fields_session_not_found():
    resp = client.post("/editing/update-fields", json={
        "analysis_id": "nonexistent",
        "fields": [],
    })
    assert resp.status_code == 404


# ----- Test /editing/focus-field -----

def test_focus_field_success():
    session = _register_session()
    resp = client.post("/editing/focus-field", json={
        "analysis_id": ANALYSIS_ID,
        "field_index": 0,
    })
    assert resp.status_code == 200
    session.highlighter.focus_field.assert_called_once_with(0)


def test_focus_field_session_not_found():
    resp = client.post("/editing/focus-field", json={
        "analysis_id": "nonexistent",
        "field_index": 0,
    })
    assert resp.status_code == 404


# ----- Test /editing/test-selector -----

def test_test_selector_found():
    session = _register_session()
    resp = client.post("/editing/test-selector", json={
        "analysis_id": ANALYSIS_ID,
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
        "analysis_id": ANALYSIS_ID,
        "selector": ".nonexistent",
    })
    assert resp.status_code == 200
    assert resp.json()["found"] is False


# ----- Test /editing/confirm -----

def test_confirm_success():
    session = _register_session()
    resp = client.post("/editing/confirm", json={"analysis_id": ANALYSIS_ID})
    assert resp.status_code == 200
    assert resp.json()["status"] == "confirmed"
    assert session.confirmed_event.is_set()


def test_confirm_session_not_found():
    resp = client.post("/editing/confirm", json={"analysis_id": "nonexistent"})
    assert resp.status_code == 404


# ----- Test /editing/cancel -----

def test_cancel_success():
    session = _register_session()
    resp = client.post("/editing/cancel", json={"analysis_id": ANALYSIS_ID})
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"
    assert session.cancelled_event.is_set()


# ----- Test /editing/cleanup -----

def test_cleanup_success():
    session = _register_session()
    resp = client.post("/editing/cleanup", json={"analysis_id": ANALYSIS_ID})
    assert resp.status_code == 200
    assert resp.json()["status"] == "cleaned_up"

    # Session should be removed
    registry = HighlighterRegistry.get_instance()
    assert registry.get(ANALYSIS_ID) is None


def test_cleanup_not_found():
    resp = client.post("/editing/cleanup", json={"analysis_id": "nonexistent"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "not_found"


# ----- Test /editing/navigate -----

def test_navigate_success():
    session = _register_session()
    resp = client.post("/editing/navigate", json={
        "analysis_id": ANALYSIS_ID,
        "url": "https://example.com/target",
    })
    assert resp.status_code == 200
    assert resp.json()["url"] == "https://example.com/target"
    session.page.goto.assert_called_once()


def test_navigate_session_not_found():
    resp = client.post("/editing/navigate", json={
        "analysis_id": "nonexistent",
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
