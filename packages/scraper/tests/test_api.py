"""Tests for FastAPI endpoints (execute, validate, health, VNC)."""

import asyncio
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

from tests.conftest import (
    make_task,
    make_form_definition,
    make_form_field,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_app():
    """Import and return the FastAPI app, lazily to let patches take effect."""
    from app.main import app
    return app


@pytest.fixture(autouse=True)
def _clear_execute_state():
    """Keep execute endpoint globals isolated between tests."""
    from app.api.execute import _execution_results, _running_executions
    _execution_results.clear()
    _running_executions.clear()
    yield
    _execution_results.clear()
    _running_executions.clear()


# ---------------------------------------------------------------------------
# POST /execute
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_endpoint_starts_background():
    """POST /execute returns immediately with status=started."""
    def _fake_create_task(coro):
        coro.close()
        return MagicMock()

    with patch("app.api.execute.asyncio.create_task", side_effect=_fake_create_task) as mock_create_task:
        app = _get_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/execute", json={
                "task_id": str(uuid.uuid4()),
                "is_dry_run": False,
            })

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "started"
    assert "task_id" in data
    assert "message" in data

    mock_create_task.assert_called_once()


@pytest.mark.asyncio
async def test_execute_endpoint_with_all_options():
    """POST /execute accepts all optional parameters."""
    def _fake_create_task(coro):
        coro.close()
        return MagicMock()

    with patch("app.api.execute.asyncio.create_task", side_effect=_fake_create_task):
        app = _get_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/execute", json={
                "task_id": str(uuid.uuid4()),
                "is_dry_run": True,
                "stealth_enabled": False,
                "user_agent": "CustomBot/1.0",
                "action_delay_ms": 1000,
            })

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "started"


@pytest.mark.asyncio
async def test_execute_endpoint_already_running():
    """POST /execute returns already_running when same execution is in progress."""
    from app.api.execute import _running_executions

    execution_id = "exec-already-running"
    blocker = asyncio.Event()
    running_task = asyncio.create_task(blocker.wait())
    _running_executions[execution_id] = running_task

    try:
        with patch("app.api.execute.asyncio.create_task") as mock_create_task:
            app = _get_app()
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.post("/execute", json={
                    "task_id": str(uuid.uuid4()),
                    "execution_id": execution_id,
                })

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "already_running"
        mock_create_task.assert_not_called()
    finally:
        running_task.cancel()
        try:
            await running_task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_execute_status_running():
    """GET /execute/status/{task_id} returns running when no result yet."""
    task_id = str(uuid.uuid4())

    app = _get_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(f"/execute/status/{task_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"
    assert data["task_id"] == task_id


@pytest.mark.asyncio
async def test_execute_status_completed():
    """GET /execute/status/{task_id} returns result when execution completed."""
    from app.api.execute import _execution_results

    task_id = str(uuid.uuid4())
    _execution_results[task_id] = {
        "execution_id": "exec-123",
        "status": "success",
        "screenshot": "exec-123_final.png",
    }

    try:
        app = _get_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get(f"/execute/status/{task_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["execution_id"] == "exec-123"

        # Result is consumed (popped)
        assert task_id not in _execution_results
    finally:
        _execution_results.pop(task_id, None)


@pytest.mark.asyncio
async def test_execute_cancel_running_execution():
    """POST /execute/{execution_id}/cancel cancels a running execution task."""
    from app.api.execute import _running_executions

    execution_id = "exec-cancel-123"
    blocker = asyncio.Event()
    running_task = asyncio.create_task(blocker.wait())
    _running_executions[execution_id] = running_task

    app = _get_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(f"/execute/{execution_id}/cancel")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "cancelled"
    assert data["execution_id"] == execution_id

    try:
        await running_task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_execute_cancel_not_found():
    """POST /execute/{execution_id}/cancel returns not_found when missing."""
    app = _get_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/execute/nonexistent-exec/cancel")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "not_found"
    assert data["execution_id"] == "nonexistent-exec"


# ---------------------------------------------------------------------------
# POST /validate-selectors
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_selectors_task_not_found():
    """POST /validate-selectors returns error when task not found."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    def override_get_db():
        yield mock_db

    app = _get_app()
    app.dependency_overrides = {}
    from app.database import get_db
    app.dependency_overrides[get_db] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/validate-selectors", json={
                "task_id": str(uuid.uuid4()),
            })

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["error"] == "Task not found"
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_validate_selectors_all_valid():
    """POST /validate-selectors returns valid=True when all selectors exist."""
    task_id = uuid.uuid4()
    fd_id = uuid.uuid4()

    task = make_task(id=task_id, stealth_enabled=True)
    form_def = make_form_definition(
        id=fd_id, task_id=task_id, step_order=1,
        page_url="https://example.com/form",
        form_selector="#form", submit_selector="#submit",
    )
    field = make_form_field(
        form_definition_id=fd_id, field_name="name",
        field_selector="#name",
    )

    mock_db = MagicMock()

    def _query_side_effect(model):
        q = MagicMock()
        model_name = getattr(model, "__name__", "")
        if model_name == "Task":
            q.filter.return_value.first.return_value = task
        elif model_name == "FormDefinition":
            q.filter.return_value.order_by.return_value.all.return_value = [form_def]
        elif model_name == "FormField":
            q.filter.return_value.all.return_value = [field]
        return q

    mock_db.query = MagicMock(side_effect=_query_side_effect)

    def override_get_db():
        yield mock_db

    from tests.conftest import _make_mock_page, _make_mock_context, _make_mock_browser, _make_mock_playwright

    page = _make_mock_page()
    page.query_selector = AsyncMock(return_value=MagicMock())  # element found
    context = _make_mock_context(page)
    browser = _make_mock_browser(context)
    pw_cm = _make_mock_playwright(browser)

    pw_patch = patch("app.api.validate.async_playwright", return_value=pw_cm)
    stealth_patch = patch("app.api.validate.apply_stealth", AsyncMock())

    app = _get_app()
    from app.database import get_db
    app.dependency_overrides[get_db] = override_get_db

    try:
        with pw_patch, stealth_patch:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.post("/validate-selectors", json={
                    "task_id": str(task_id),
                })

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["invalid_selectors"] == []
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_validate_selectors_invalid_found():
    """POST /validate-selectors detects invalid selectors."""
    task_id = uuid.uuid4()
    fd_id = uuid.uuid4()

    task = make_task(id=task_id, stealth_enabled=False)
    form_def = make_form_definition(
        id=fd_id, task_id=task_id, step_order=1,
        page_url="https://example.com/form",
        form_selector="#missing-form", submit_selector="#missing-submit",
    )

    mock_db = MagicMock()

    def _query_side_effect(model):
        q = MagicMock()
        model_name = getattr(model, "__name__", "")
        if model_name == "Task":
            q.filter.return_value.first.return_value = task
        elif model_name == "FormDefinition":
            q.filter.return_value.order_by.return_value.all.return_value = [form_def]
        elif model_name == "FormField":
            q.filter.return_value.all.return_value = []
        return q

    mock_db.query = MagicMock(side_effect=_query_side_effect)

    def override_get_db():
        yield mock_db

    from tests.conftest import _make_mock_page, _make_mock_context, _make_mock_browser, _make_mock_playwright

    page = _make_mock_page()
    page.query_selector = AsyncMock(return_value=None)  # element NOT found
    context = _make_mock_context(page)
    browser = _make_mock_browser(context)
    pw_cm = _make_mock_playwright(browser)

    pw_patch = patch("app.api.validate.async_playwright", return_value=pw_cm)
    stealth_patch = patch("app.api.validate.apply_stealth", AsyncMock())

    app = _get_app()
    from app.database import get_db
    app.dependency_overrides[get_db] = override_get_db

    try:
        with pw_patch, stealth_patch:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.post("/validate-selectors", json={
                    "task_id": str(task_id),
                })

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert len(data["invalid_selectors"]) == 2  # form + submit
        types_found = [s["type"] for s in data["invalid_selectors"]]
        assert "form" in types_found
        assert "submit" in types_found
    finally:
        app.dependency_overrides = {}


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_check():
    """GET /health returns ok."""
    app = _get_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


# ---------------------------------------------------------------------------
# VNC endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_vnc_start_endpoint():
    """POST /vnc/start creates a VNC session."""
    mock_vnc = AsyncMock()
    mock_vnc.start_session = AsyncMock(return_value={
        "session_id": "vnc-abc",
        "vnc_url": "http://localhost:6080/vnc_lite.html",
    })

    with patch("app.api.vnc.vnc_manager", mock_vnc):
        app = _get_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/vnc/start", json={
                "execution_id": "exec-123",
            })

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "vnc-abc"
    assert "vnc_url" in data
    mock_vnc.start_session.assert_awaited_once_with("exec-123")


@pytest.mark.asyncio
async def test_vnc_resume_endpoint():
    """POST /vnc/resume signals a VNC session to resume."""
    mock_vnc = AsyncMock()
    mock_vnc.resume_session = AsyncMock(return_value={
        "status": "resumed",
        "execution_id": "exec-123",
    })

    with patch("app.api.vnc.vnc_manager", mock_vnc):
        app = _get_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/vnc/resume", json={
                "session_id": "vnc-abc",
                "execution_id": "exec-123",
            })

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "resumed"


@pytest.mark.asyncio
async def test_vnc_stop_endpoint():
    """POST /vnc/stop terminates a VNC session."""
    mock_vnc = AsyncMock()
    mock_vnc.stop_session = AsyncMock(return_value={"status": "stopped"})

    with patch("app.api.vnc.vnc_manager", mock_vnc):
        app = _get_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/vnc/stop", json={
                "session_id": "vnc-abc",
            })

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "stopped"


@pytest.mark.asyncio
async def test_vnc_resume_analysis_endpoint():
    """POST /vnc/resume-analysis signals a VNC session to resume during analysis."""
    mock_vnc = AsyncMock()
    mock_vnc.resume_session = AsyncMock(return_value={
        "status": "resumed",
        "execution_id": "analysis-123",
    })

    with patch("app.api.vnc.vnc_manager", mock_vnc):
        app = _get_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/vnc/resume-analysis", json={
                "session_id": "vnc-session-abc",
                "analysis_id": "analysis-123",
            })

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "resumed"
    mock_vnc.resume_session.assert_awaited_once_with("vnc-session-abc", "analysis-123")
