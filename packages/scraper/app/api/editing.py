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


class FillFieldRequest(BaseModel):
    analysis_id: str
    field_index: int
    value: str


class ReadFieldValueRequest(BaseModel):
    analysis_id: str
    field_index: int


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


@router.post("/fill-field")
async def fill_field(request: FillFieldRequest):
    """Programmatically fill a field's value in the live page."""
    session = _get_session(request.analysis_id)
    await session.highlighter.fill_field(request.field_index, request.value)
    return {"status": "ok"}


@router.post("/read-field-value")
async def read_field_value(request: ReadFieldValueRequest):
    """Read the current value of a field from the live page."""
    session = _get_session(request.analysis_id)
    value = await session.highlighter.read_field_value(request.field_index)
    return {"status": "ok", "value": value}


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
        return {"status": "ok", "url": request.url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Navigation failed: {str(e)}")


class LoginFieldPayload(BaseModel):
    field_selector: str
    value: Optional[str] = ""
    field_type: Optional[str] = "text"
    is_sensitive: Optional[bool] = False


class ExecuteLoginRequest(BaseModel):
    analysis_id: str
    login_fields: list[LoginFieldPayload]
    target_url: str
    submit_selector: Optional[str] = ""
    captcha_detected: bool = False
    two_factor_expected: bool = False
    human_breakpoint: bool = False


@router.post("/execute-login")
async def execute_login(request: ExecuteLoginRequest):
    """Execute login in the existing VNC session, then navigate to target and analyze."""
    session = _get_session(request.analysis_id)

    if session.executing:
        raise HTTPException(status_code=409, detail="Login execution already in progress")

    session.executing = True

    async def _run():
        broadcaster = Broadcaster.get_instance()
        page = session.page
        analysis_id = request.analysis_id

        # Helper function to DRY up manual intervention pauses
        async def _pause_for_human(phase_name: str, message_text: str):
            broadcaster.trigger_analysis(analysis_id, "LoginExecutionProgress", {
                "phase": phase_name,
                "message": message_text,
                "needs_vnc": True,
            })
            session.resume_event.clear()
            await session.resume_event.wait()
            try:
                await page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                await page.wait_for_timeout(3000)

        try:
            # Phase: filling
            broadcaster.trigger_analysis(analysis_id, "LoginExecutionProgress", {
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
            broadcaster.trigger_analysis(analysis_id, "LoginExecutionProgress", {
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
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
                await page.wait_for_timeout(5000)
            except Exception:
                await page.wait_for_timeout(6000)

            # Manual Interventions
            if request.captcha_detected:
                await _pause_for_human("captcha", "CAPTCHA expected — please solve it in the VNC viewer, then click Resume.")

            if request.two_factor_expected:
                await _pause_for_human("2fa", "2FA expected — complete verification in the VNC viewer, then click Resume.")

            if request.human_breakpoint:
                await _pause_for_human("human_breakpoint", "Human breakpoint — complete any manual steps in the VNC viewer, then click Resume.")

            # Phase: navigating to target
            broadcaster.trigger_analysis(analysis_id, "LoginExecutionProgress", {
                "phase": "navigating",
                "message": "Navigating to target page...",
            })

            await page.goto(request.target_url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(3000)

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

            broadcaster.trigger_analysis(analysis_id, "LoginExecutionComplete", {
                "success": True,
                "target_result": target_result,
                "target_fields": target_fields,
            })

        except Exception as e:
            broadcaster.trigger_analysis(analysis_id, "LoginExecutionComplete", {
                "success": False,
                "error": str(e),
            })
        finally:
            session.executing = False

    asyncio.create_task(_run())
    return {"status": "started", "analysis_id": request.analysis_id}


@router.post("/resume-login")
async def resume_login(request: SessionRequest):
    """Signal that manual CAPTCHA/2FA intervention is complete."""
    session = _get_session(request.analysis_id)
    session.resume_event.set()
    return {"status": "resumed", "analysis_id": request.analysis_id}