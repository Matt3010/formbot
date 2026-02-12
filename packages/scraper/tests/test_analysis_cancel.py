"""Tests for AnalysisRegistry singleton and the POST /analyze/{id}/cancel endpoint."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

from app.services.analysis_registry import AnalysisRegistry


# ---------------------------------------------------------------------------
# Fixture: reset singleton between tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_registry():
    """Reset the AnalysisRegistry singleton before and after each test."""
    AnalysisRegistry._instance = None
    yield
    AnalysisRegistry._instance = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_app():
    """Import and return the FastAPI app, lazily to let patches take effect."""
    from app.main import app
    return app


def _make_fake_task(done: bool = False, cancelled: bool = False) -> MagicMock:
    """Create a MagicMock that behaves like an asyncio.Task."""
    task = MagicMock(spec=asyncio.Task)
    task.done.return_value = done
    task.cancel.return_value = True
    task.cancelled.return_value = cancelled
    return task


# ---------------------------------------------------------------------------
# AnalysisRegistry unit tests
# ---------------------------------------------------------------------------


class TestAnalysisRegistry:
    """Unit tests for the AnalysisRegistry singleton."""

    def test_register_and_is_running(self):
        """Registering a task makes is_running return True for that analysis_id."""
        registry = AnalysisRegistry.get_instance()
        task = _make_fake_task(done=False)

        registry.register("analysis-001", task)

        assert registry.is_running("analysis-001") is True

    def test_cancel_existing_task(self):
        """Cancelling an existing running task returns True and calls task.cancel()."""
        registry = AnalysisRegistry.get_instance()
        task = _make_fake_task(done=False)

        registry.register("analysis-002", task)
        result = registry.cancel("analysis-002")

        assert result is True
        task.cancel.assert_called_once()

    def test_cancel_nonexistent(self):
        """Cancelling a non-existent analysis_id returns False."""
        registry = AnalysisRegistry.get_instance()

        result = registry.cancel("does-not-exist")

        assert result is False

    def test_unregister(self):
        """Unregistering a task makes is_running return False."""
        registry = AnalysisRegistry.get_instance()
        task = _make_fake_task(done=False)

        registry.register("analysis-003", task)
        assert registry.is_running("analysis-003") is True

        registry.unregister("analysis-003")
        assert registry.is_running("analysis-003") is False

    def test_cancel_already_done_task(self):
        """Cancelling a task that is already done returns False."""
        registry = AnalysisRegistry.get_instance()
        task = _make_fake_task(done=True)

        registry.register("analysis-004", task)
        result = registry.cancel("analysis-004")

        assert result is False
        task.cancel.assert_not_called()

    def test_is_running_false_when_task_done(self):
        """is_running returns False when the registered task is already done."""
        registry = AnalysisRegistry.get_instance()
        task = _make_fake_task(done=True)

        registry.register("analysis-005", task)

        assert registry.is_running("analysis-005") is False

    def test_is_running_false_for_unknown_id(self):
        """is_running returns False for an analysis_id that was never registered."""
        registry = AnalysisRegistry.get_instance()

        assert registry.is_running("unknown-id") is False

    def test_singleton_returns_same_instance(self):
        """get_instance always returns the same AnalysisRegistry object."""
        instance_a = AnalysisRegistry.get_instance()
        instance_b = AnalysisRegistry.get_instance()

        assert instance_a is instance_b


# ---------------------------------------------------------------------------
# Cancel endpoint tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_running_analysis():
    """POST /analyze/{id}/cancel returns {"status": "cancelled"} when the task exists."""
    registry = AnalysisRegistry.get_instance()
    task = _make_fake_task(done=False)
    registry.register("running-analysis", task)

    app = _get_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/analyze/running-analysis/cancel")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "cancelled"
    task.cancel.assert_called_once()


@pytest.mark.asyncio
async def test_cancel_not_found():
    """POST /analyze/{id}/cancel returns {"status": "not_found"} when no task exists."""
    app = _get_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/analyze/nonexistent-id/cancel")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "not_found"
