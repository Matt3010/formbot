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


async def _wait_for_next_paint(page) -> None:
    """Yield until at least one browser paint has happened."""
    try:
        await page.evaluate(
            "() => new Promise((resolve) => requestAnimationFrame(resolve))"
        )
    except Exception:
        pass


async def _wait_for_render_ready(page, timeout_ms: int = 3000) -> None:
    """Wait for a paint-ready DOM without relying on fixed sleeps."""
    try:
        await page.wait_for_function(
            """() => {
                if (!document.body) return false;
                const state = document.readyState;
                return state === 'interactive' || state === 'complete';
            }""",
            timeout=timeout_ms,
        )
    except Exception:
        return

    try:
        await page.evaluate(
            "() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))"
        )
    except Exception:
        pass


async def _capture_dom_marker(page) -> dict | None:
    """Capture a compact DOM marker used to detect same-URL transitions."""
    try:
        return await page.evaluate(
            """() => {
                const body = document.body;
                const text = body ? body.innerText.slice(0, 4000) : '';
                const htmlLength = body ? body.innerHTML.length : 0;
                return {
                    text,
                    htmlLength,
                    title: document.title || '',
                    path: window.location.pathname + window.location.search + window.location.hash,
                };
            }"""
        )
    except Exception:
        return None


async def _wait_for_post_submit(
    page,
    previous_url: str,
    previous_dom_marker: dict | None,
    timeout_ms: int = 10000,
) -> bool:
    """Wait for submit side-effects: URL/frame nav, or same-URL DOM transition."""
    navigation_detected = False
    try:
        await page.wait_for_url(
            lambda url: url != previous_url,
            timeout=timeout_ms,
        )
        navigation_detected = True
    except Exception:
        navigation_detected = False

    if not navigation_detected:
        try:
            await page.wait_for_event(
                "framenavigated",
                predicate=lambda frame: frame == page.main_frame,
                timeout=min(timeout_ms, 12000),
            )
            navigation_detected = True
        except Exception:
            navigation_detected = False

    if navigation_detected:
        try:
            await page.wait_for_load_state("load", timeout=15000)
        except Exception:
            pass
        await _wait_for_render_ready(page, timeout_ms=min(timeout_ms, 5000))
        return True

    if previous_dom_marker is not None:
        try:
            await page.wait_for_function(
                """(before) => {
                    const body = document.body;
                    const text = body ? body.innerText.slice(0, 4000) : '';
                    const htmlLength = body ? body.innerHTML.length : 0;
                    const title = document.title || '';
                    const path = window.location.pathname + window.location.search + window.location.hash;
                    return (
                        text !== before.text ||
                        htmlLength !== before.htmlLength ||
                        title !== before.title ||
                        path !== before.path
                    );
                }""",
                previous_dom_marker,
                timeout=min(timeout_ms, 12000),
            )
            await _wait_for_render_ready(page, timeout_ms=min(timeout_ms, 3000))
            return True
        except Exception:
            pass

    return False


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
        await _wait_for_render_ready(session.page, timeout_ms=3000)

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
    field_name: Optional[str] = ""
    value: Optional[str] = ""
    field_type: Optional[str] = "text"
    is_required: Optional[bool] = False
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
                try:
                    await page.wait_for_load_state("domcontentloaded", timeout=5000)
                except Exception:
                    pass
            await _wait_for_render_ready(page, timeout_ms=3000)

        try:
            # Phase: filling
            broadcaster.trigger_task_editing(task_id, "LoginExecutionProgress", {
                "phase": "filling",
                "message": "Filling login form fields...",
            })

            submit_field_selector = None
            fill_errors: list[str] = []
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

                    await _wait_for_next_paint(page)
                except Exception as e:
                    value_present = bool((field.value or "").strip())
                    if field.is_required or value_present:
                        field_label = field.field_name or field.field_selector
                        fill_errors.append(f"{field_label}: {str(e)}")

            if fill_errors:
                joined = "; ".join(fill_errors[:5])
                raise Exception(f"Failed to fill required login fields ({len(fill_errors)}): {joined}")

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

            submit_method = "keyboard_enter"
            navigation_detected = False
            previous_url = page.url
            previous_dom_marker = await _capture_dom_marker(page)
            if effective_submit:
                submit_method = "click"
                try:
                    await asyncio.wait_for(
                        page.locator(effective_submit).first.click(timeout=5000, no_wait_after=True),
                        timeout=8,
                    )
                except Exception:
                    submit_method = "click_force"
                    await asyncio.wait_for(
                        page.locator(effective_submit).first.click(force=True, timeout=5000, no_wait_after=True),
                        timeout=8,
                    )
                navigation_detected = await _wait_for_post_submit(
                    page,
                    previous_url,
                    previous_dom_marker,
                    timeout_ms=10000,
                )

                if not navigation_detected:
                    # Fallback to native submit path on the parent form.
                    submit_method = "click_then_request_submit"
                    submitted = await page.evaluate(
                        """(submitSelector) => {
                            const el = submitSelector ? document.querySelector(submitSelector) : null;
                            if (!el) return false;
                            const form = el.closest?.('form');
                            if (form && typeof form.requestSubmit === 'function') form.requestSubmit();
                            else if (form) form.submit();
                            else if (el.click) el.click();
                            return true;
                        }""",
                        effective_submit,
                    )
                    if submitted:
                        navigation_detected = await _wait_for_post_submit(
                            page,
                            previous_url,
                            previous_dom_marker,
                            timeout_ms=10000,
                        )
                    else:
                        submit_method = "click_then_enter"
                        await page.keyboard.press("Enter")
                        navigation_detected = await _wait_for_post_submit(
                            page,
                            previous_url,
                            previous_dom_marker,
                            timeout_ms=10000,
                        )
            else:
                await page.keyboard.press("Enter")
                navigation_detected = await _wait_for_post_submit(
                    page,
                    previous_url,
                    previous_dom_marker,
                    timeout_ms=10000,
                )

            # Allow time for cookies and redirects
            broadcaster.trigger_task_editing(task_id, "LoginExecutionProgress", {
                "phase": "waiting_redirect",
                "message": "Waiting for page redirect...",
                "submit_method": submit_method,
                "navigation_detected": navigation_detected,
            })

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
            await _wait_for_render_ready(page, timeout_ms=3000)

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
