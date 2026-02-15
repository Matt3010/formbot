"""Editing API — endpoints for frontend → browser commands during VNC editing."""

import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.services.highlighter_registry import HighlighterRegistry
from app.services.broadcaster import Broadcaster
from app.services.field_highlighter import FieldHighlighter

router = APIRouter(prefix="/editing")


class SetModeRequest(BaseModel):
    task_id: str
    mode: str  # select | add | remove


class UpdateFieldsRequest(BaseModel):
    task_id: str
    fields: list[dict]


class FocusFieldRequest(BaseModel):
    task_id: str
    field_index: int


class TestSelectorRequest(BaseModel):
    task_id: str
    selector: str


class FillFieldRequest(BaseModel):
    task_id: str
    field_index: int
    value: str


class ReadFieldValueRequest(BaseModel):
    task_id: str
    field_index: int


class SessionRequest(BaseModel):
    task_id: str


class NavigateRequest(BaseModel):
    task_id: str
    url: str
    step: Optional[int] = None
    request_id: Optional[str] = None


def _get_session(task_id: str):
    registry = HighlighterRegistry.get_instance()
    session = registry.get(task_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"No active editing session for analysis {task_id}")
    return session


def _assert_session_command_ready(session) -> None:
    """Reject interactive commands while the session is busy."""
    if session.executing:
        raise HTTPException(status_code=409, detail="Login execution already in progress")
    if session.navigating:
        raise HTTPException(status_code=409, detail="Step navigation already in progress")


@router.post("/mode")
async def set_mode(request: SetModeRequest):
    """Set the interaction mode (select/add/remove)."""
    if request.mode not in ("select", "add", "remove"):
        raise HTTPException(status_code=400, detail="Invalid mode. Must be: select, add, remove")

    session = _get_session(request.task_id)
    _assert_session_command_ready(session)
    await session.highlighter.set_mode(request.mode)
    return {"status": "ok", "mode": request.mode}


@router.post("/update-fields")
async def update_fields(request: UpdateFieldsRequest):
    """Update the highlighted fields after panel edits."""
    session = _get_session(request.task_id)
    _assert_session_command_ready(session)
    session.fields = request.fields
    await session.highlighter.update_fields(request.fields)
    return {"status": "ok", "field_count": len(request.fields)}


@router.post("/focus-field")
async def focus_field(request: FocusFieldRequest):
    """Scroll to and flash-highlight a specific field."""
    session = _get_session(request.task_id)
    _assert_session_command_ready(session)
    await session.highlighter.focus_field(request.field_index)
    return {"status": "ok", "field_index": request.field_index}


@router.post("/test-selector")
async def test_selector(request: TestSelectorRequest):
    """Test a CSS selector — flash green if found, red if not."""
    session = _get_session(request.task_id)
    _assert_session_command_ready(session)
    result = await session.highlighter.test_selector(request.selector)
    return {"status": "ok", **result}


@router.post("/fill-field")
async def fill_field(request: FillFieldRequest):
    """Programmatically fill a field's value in the live page."""
    session = _get_session(request.task_id)
    _assert_session_command_ready(session)
    await session.highlighter.fill_field(request.field_index, request.value)
    return {"status": "ok"}


@router.post("/read-field-value")
async def read_field_value(request: ReadFieldValueRequest):
    """Read the current value of a field from the live page."""
    session = _get_session(request.task_id)
    # Allow reading even during login execution - it's a read-only operation
    value = await session.highlighter.read_field_value(request.field_index)
    return {"status": "ok", "value": value}


@router.post("/confirm")
async def confirm_editing(request: SessionRequest):
    """User confirmed all fields. Signal the session."""
    session = _get_session(request.task_id)
    session.confirmed_event.set()
    return {"status": "confirmed", "task_id": request.task_id}


@router.post("/cancel")
async def cancel_editing(request: SessionRequest):
    """User cancelled editing. Signal the session."""
    session = _get_session(request.task_id)
    session.cancelled_event.set()
    return {"status": "cancelled", "task_id": request.task_id}


@router.post("/cleanup")
async def cleanup_editing(request: SessionRequest):
    """Force cleanup an editing session (close browser, remove overlays)."""
    registry = HighlighterRegistry.get_instance()
    session = registry.get(request.task_id)
    if not session:
        return {"status": "not_found"}

    await registry.cleanup_session(request.task_id)
    return {"status": "cleaned_up", "task_id": request.task_id}


@router.post("/navigate")
async def navigate_step(request: NavigateRequest):
    """Navigate the browser to a different URL (for multi-step flows)."""
    session = _get_session(request.task_id)
    broadcaster = Broadcaster.get_instance()
    if session.executing:
        raise HTTPException(status_code=409, detail="Login execution already in progress")
    if session.navigating:
        raise HTTPException(status_code=409, detail="Step navigation already in progress")

    session.navigating = True
    broadcaster.trigger_task_editing(request.task_id, "StepNavigationState", {
        "status": "started",
        "step": request.step,
        "url": request.url,
        "request_id": request.request_id,
        "message": f"Navigating to {request.url}...",
    })

    try:
        # Avoid strict network-idle waits: modern apps can keep long-lived
        # connections open and never become "idle" even when ready.
        await session.page.goto(request.url, wait_until="domcontentloaded", timeout=45000)
        try:
            await session.page.wait_for_load_state("load", timeout=15000)
        except Exception:
            # Best effort only: some pages never reach "load" cleanly.
            pass
        await session.page.wait_for_timeout(800)

        final_url = getattr(session.page, "url", None)
        if not isinstance(final_url, str) or not final_url:
            final_url = request.url
        broadcaster.trigger_task_editing(request.task_id, "StepNavigationState", {
            "status": "completed",
            "step": request.step,
            "url": request.url,
            "final_url": final_url,
            "request_id": request.request_id,
            "message": "Target page ready",
        })
        return {"status": "ok", "url": request.url, "final_url": final_url}
    except Exception as e:
        broadcaster.trigger_task_editing(request.task_id, "StepNavigationState", {
            "status": "failed",
            "step": request.step,
            "url": request.url,
            "request_id": request.request_id,
            "message": "Navigation failed",
            "error": str(e),
        })
        raise HTTPException(status_code=500, detail=f"Navigation failed: {str(e)}")
    finally:
        session.navigating = False


class LoginFieldPayload(BaseModel):
    field_selector: str
    value: Optional[str] = ""
    field_type: Optional[str] = "text"
    is_sensitive: Optional[bool] = False


class ExecuteLoginRequest(BaseModel):
    task_id: str
    login_fields: list[LoginFieldPayload]
    target_url: str
    submit_selector: Optional[str] = ""
    human_breakpoint: bool = False


@router.post("/execute-login")
async def execute_login(request: ExecuteLoginRequest):
    """Execute login in the existing VNC session, then navigate to target and analyze."""
    session = _get_session(request.task_id)

    if session.executing:
        raise HTTPException(status_code=409, detail="Login execution already in progress")
    if session.navigating:
        raise HTTPException(status_code=409, detail="Step navigation already in progress")

    session.executing = True

    async def _run():
        broadcaster = Broadcaster.get_instance()
        page = session.page
        task_id = request.task_id

        # Helper function to DRY up manual intervention pauses
        async def _pause_for_human(phase_name: str, message_text: str):
            broadcaster.trigger_task_editing(task_id, "LoginExecutionProgress", {
                "phase": phase_name,
                "message": message_text,
                "needs_vnc": True,
            })
            session.resume_event.clear()
            await session.resume_event.wait()
            try:
                await page.wait_for_load_state("load", timeout=12000)
            except Exception:
                await page.wait_for_timeout(3000)

        try:
            # Phase: filling
            broadcaster.trigger_task_editing(task_id, "LoginExecutionProgress", {
                "phase": "filling",
                "message": "Filling login form fields...",
            })

            submit_field_selector = None
            for field in request.login_fields:
                if field.field_type in ("submit", "button"):
                    submit_field_selector = field.field_selector
                    continue
                try:
                    el = page.locator(field.field_selector).first
                    field_value = field.value or ""

                    if field.field_type == "checkbox":
                        if str(field_value).lower() in ("true", "1", "yes", "on"):
                            await el.check()
                        else:
                            await el.uncheck()
                    elif field.field_type == "select":
                        await el.select_option(value=field_value)
                    else:
                        await el.click()
                        await el.fill(field_value)

                    await page.wait_for_timeout(200)
                except Exception:
                    pass  # Silently skip fields that fail to fill

            # Phase: submitting
            broadcaster.trigger_task_editing(task_id, "LoginExecutionProgress", {
                "phase": "submitting",
                "message": "Submitting login form...",
            })

            effective_submit = request.submit_selector or submit_field_selector

            try:
                await page.evaluate("if(window.__FORMBOT_HIGHLIGHT) window.__FORMBOT_HIGHLIGHT.command_cleanup()")
            except Exception:
                pass

            if effective_submit:
                try:
                    await page.locator(effective_submit).first.click(timeout=5000)
                except Exception:
                    try:
                        await page.locator(effective_submit).first.click(force=True, timeout=5000)
                    except Exception:
                        await page.evaluate(f"document.querySelector('{effective_submit}').click()")
            else:
                await page.keyboard.press("Enter")

            # Allow time for cookies and redirects
            broadcaster.trigger_task_editing(task_id, "LoginExecutionProgress", {
                "phase": "waiting_redirect",
                "message": "Waiting for page redirect...",
            })
            try:
                await page.wait_for_load_state("load", timeout=15000)
            except Exception:
                pass
            await page.wait_for_timeout(800)

            # Manual Interventions
            if request.human_breakpoint:
                await _pause_for_human("human_breakpoint", "Human breakpoint — complete any manual steps in the VNC viewer, then click Resume.")

            # Phase: navigating to target
            broadcaster.trigger_task_editing(task_id, "LoginExecutionProgress", {
                "phase": "navigating",
                "message": "Navigating to target page...",
            })

            await page.goto(request.target_url, wait_until="domcontentloaded", timeout=45000)

            # Wait for target page to be fully loaded
            try:
                await page.wait_for_load_state("load", timeout=15000)
            except Exception:
                pass
            await page.wait_for_timeout(800)

            broadcaster.trigger_task_editing(task_id, "LoginExecutionProgress", {
                "phase": "loading_target",
                "message": "Target page loaded, preparing editor...",
            })

            # Prepare Target Phase
            target_result = {
                "url": request.target_url,
                "page_requires_login": False,
                "forms": [{
                    "form_type": "target",
                    "form_selector": "",
                    "submit_selector": "",
                    "fields": [],
                    "page_url": request.target_url,
                }],
            }
            target_fields = []

            # Re-inject highlighter with empty fields
            session.highlighter._fields = target_fields
            await session.highlighter.inject()
            session.fields = target_fields

            broadcaster.trigger_task_editing(task_id, "LoginExecutionComplete", {
                "success": True,
                "target_result": target_result,
                "target_fields": target_fields,
            })

        except Exception as e:
            broadcaster.trigger_task_editing(task_id, "LoginExecutionComplete", {
                "success": False,
                "error": str(e),
            })
        finally:
            session.executing = False

    asyncio.create_task(_run())
    return {"status": "started", "task_id": request.task_id}


@router.post("/resume-login")
async def resume_login(request: SessionRequest):
    """Signal that manual intervention is complete."""
    session = _get_session(request.task_id)
    session.resume_event.set()
    return {"status": "resumed", "task_id": request.task_id}
