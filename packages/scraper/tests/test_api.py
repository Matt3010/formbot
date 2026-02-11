"""Tests for FastAPI endpoints (analyze, execute, validate, health)."""

import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

from tests.conftest import (
    SIMPLE_LOGIN_ANALYSIS,
    NO_FORMS_ANALYSIS,
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


# ---------------------------------------------------------------------------
# POST /analyze
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analyze_endpoint_success():
    """POST /analyze returns LLM form analysis for the given URL."""
    mock_analyzer = AsyncMock()
    mock_analyzer.analyze_url = AsyncMock(return_value=SIMPLE_LOGIN_ANALYSIS)

    with patch("app.api.analyze.FormAnalyzer", return_value=mock_analyzer):
        app = _get_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/analyze", json={
                "url": "https://example.com/login",
            })

    assert response.status_code == 200
    data = response.json()
    assert "forms" in data
    assert len(data["forms"]) == 1
    assert data["forms"][0]["form_type"] == "login"
    assert data["page_requires_login"] is True

    mock_analyzer.analyze_url.assert_awaited_once_with("https://example.com/login")


@pytest.mark.asyncio
async def test_analyze_endpoint_with_custom_model():
    """POST /analyze passes ollama_model to FormAnalyzer."""
    mock_analyzer = AsyncMock()
    mock_analyzer.analyze_url = AsyncMock(return_value=NO_FORMS_ANALYSIS)

    with patch("app.api.analyze.FormAnalyzer", return_value=mock_analyzer) as MockClass:
        app = _get_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/analyze", json={
                "url": "https://example.com",
                "ollama_model": "mistral:7b",
            })

    assert response.status_code == 200
    MockClass.assert_called_once_with(ollama_model="mistral:7b")


@pytest.mark.asyncio
async def test_analyze_endpoint_missing_url():
    """POST /analyze returns 422 when url is missing."""
    app = _get_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/analyze", json={})

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /analyze/dynamic
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analyze_dynamic_endpoint():
    """POST /analyze/dynamic returns analysis for dynamic page re-analysis."""
    mock_analyzer = AsyncMock()
    mock_analyzer.analyze_dynamic = AsyncMock(return_value=SIMPLE_LOGIN_ANALYSIS)

    with patch("app.api.analyze.FormAnalyzer", return_value=mock_analyzer):
        app = _get_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/analyze/dynamic", json={
                "url": "https://example.com/step2",
                "previous_state": {"forms": []},
                "interaction_performed": "clicked next",
            })

    assert response.status_code == 200
    data = response.json()
    assert "forms" in data

    mock_analyzer.analyze_dynamic.assert_awaited_once_with(
        "https://example.com/step2",
        {"forms": []},
        "clicked next",
    )


# ---------------------------------------------------------------------------
# POST /execute
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_endpoint_starts_background():
    """POST /execute returns immediately with status=started."""
    # We need to mock asyncio.create_task to prevent actual execution
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

    # Background task was created
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
        # Clean up in case of test failure
        _execution_results.pop(task_id, None)


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

    # Mock Playwright so all query_selector calls return a non-None element
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
async def test_health_check_ollama_available():
    """GET /health returns ok with ollama=connected."""
    mock_ollama = AsyncMock()
    mock_ollama.is_available = AsyncMock(return_value=True)

    with patch("app.main.OllamaClient", return_value=mock_ollama):
        app = _get_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["ollama"] == "connected"


@pytest.mark.asyncio
async def test_health_check_ollama_unavailable():
    """GET /health returns ok with ollama=unavailable when Ollama is down."""
    mock_ollama = AsyncMock()
    mock_ollama.is_available = AsyncMock(return_value=False)

    with patch("app.main.OllamaClient", return_value=mock_ollama):
        app = _get_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["ollama"] == "unavailable"


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
