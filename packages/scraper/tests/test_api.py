"""Tests for FastAPI endpoints (execute, health, VNC)."""

import uuid
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_app():
    """Import and return the FastAPI app, lazily to let patches take effect."""
    from app.main import app
    return app


# ---------------------------------------------------------------------------
# POST /execute
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_endpoint_starts_background():
    """POST /execute returns immediately with status=started."""
    with patch("app.api.execute.asyncio.create_task") as mock_create_task:
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
    with patch("app.api.execute.asyncio.create_task"):
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
async def test_vnc_resume_task_editing_endpoint():
    """POST /vnc/resume-task-editing signals a VNC session to resume during task editing."""
    mock_vnc = AsyncMock()
    mock_vnc.resume_session = AsyncMock(return_value={
        "status": "resumed",
        "execution_id": "task-123",
    })

    with patch("app.api.vnc.vnc_manager", mock_vnc):
        app = _get_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/vnc/resume-task-editing", json={
                "session_id": "vnc-session-abc",
                "task_id": "task-123",
            })

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "resumed"
    mock_vnc.resume_session.assert_awaited_once_with("vnc-session-abc", "task-123")
