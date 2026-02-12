"""Editing API — endpoints for frontend → browser commands during VNC editing."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.services.highlighter_registry import HighlighterRegistry

router = APIRouter(prefix="/editing")


class SetModeRequest(BaseModel):
    analysis_id: str
    mode: str  # view | select | add | remove


class UpdateFieldsRequest(BaseModel):
    analysis_id: str
    fields: list[dict]


class FocusFieldRequest(BaseModel):
    analysis_id: str
    field_index: int


class TestSelectorRequest(BaseModel):
    analysis_id: str
    selector: str


class SessionRequest(BaseModel):
    analysis_id: str


class NavigateRequest(BaseModel):
    analysis_id: str
    url: str


def _get_session(analysis_id: str):
    registry = HighlighterRegistry.get_instance()
    session = registry.get(analysis_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"No active editing session for analysis {analysis_id}")
    return session


@router.post("/mode")
async def set_mode(request: SetModeRequest):
    """Set the interaction mode (view/select/add/remove)."""
    if request.mode not in ("view", "select", "add", "remove"):
        raise HTTPException(status_code=400, detail="Invalid mode. Must be: view, select, add, remove")

    session = _get_session(request.analysis_id)
    await session.highlighter.set_mode(request.mode)
    return {"status": "ok", "mode": request.mode}


@router.post("/update-fields")
async def update_fields(request: UpdateFieldsRequest):
    """Update the highlighted fields after panel edits."""
    session = _get_session(request.analysis_id)
    session.fields = request.fields
    await session.highlighter.update_fields(request.fields)
    return {"status": "ok", "field_count": len(request.fields)}


@router.post("/focus-field")
async def focus_field(request: FocusFieldRequest):
    """Scroll to and flash-highlight a specific field."""
    session = _get_session(request.analysis_id)
    await session.highlighter.focus_field(request.field_index)
    return {"status": "ok", "field_index": request.field_index}


@router.post("/test-selector")
async def test_selector(request: TestSelectorRequest):
    """Test a CSS selector — flash green if found, red if not."""
    session = _get_session(request.analysis_id)
    result = await session.highlighter.test_selector(request.selector)
    return {"status": "ok", **result}


@router.post("/confirm")
async def confirm_editing(request: SessionRequest):
    """User confirmed all fields. Signal the session."""
    session = _get_session(request.analysis_id)
    session.confirmed_event.set()
    return {"status": "confirmed", "analysis_id": request.analysis_id}


@router.post("/cancel")
async def cancel_editing(request: SessionRequest):
    """User cancelled editing. Signal the session."""
    session = _get_session(request.analysis_id)
    session.cancelled_event.set()
    return {"status": "cancelled", "analysis_id": request.analysis_id}


@router.post("/cleanup")
async def cleanup_editing(request: SessionRequest):
    """Force cleanup an editing session (close browser, remove overlays)."""
    registry = HighlighterRegistry.get_instance()
    session = registry.get(request.analysis_id)
    if not session:
        return {"status": "not_found"}

    await registry.cleanup_session(request.analysis_id)
    return {"status": "cleaned_up", "analysis_id": request.analysis_id}


@router.post("/navigate")
async def navigate_step(request: NavigateRequest):
    """Navigate the browser to a different URL (for multi-step flows)."""
    session = _get_session(request.analysis_id)
    try:
        await session.page.goto(request.url, wait_until="networkidle", timeout=30000)
        await session.page.wait_for_timeout(1000)
        # Re-inject highlights will happen automatically via page load event
        return {"status": "ok", "url": request.url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Navigation failed: {str(e)}")
