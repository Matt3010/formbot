"""Analyze API — interactive VNC session setup for manual field editing."""

import os
import asyncio
import httpx
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from playwright.async_api import async_playwright

from app.services.stealth import apply_stealth
from app.services.broadcaster import Broadcaster
from app.services.task_editing_registry import TaskEditingRegistry
from app.services.field_highlighter import FieldHighlighter
from app.services.highlighter_registry import HighlighterRegistry, HighlighterSession
from app.api.vnc import get_vnc_manager
from app.config import settings

router = APIRouter()


async def _wait_for_render_ready(page, timeout_ms: int = 3000) -> None:
    """Wait for paint-ready DOM; timeout acts only as a guardrail."""
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


class InteractiveAnalyzeRequest(BaseModel):
    url: str
    task_id: str
    user_corrections: Optional[dict] = None
    is_login_step: Optional[bool] = False


@router.post("/analyze/interactive")
async def analyze_url_interactive(request: InteractiveAnalyzeRequest):
    """Start interactive task editing with VNC — keeps browser open for field editing."""
    print(f"[ANALYZE] Starting VNC session - URL: {request.url}, is_login_step: {request.is_login_step}", flush=True)
    vnc_manager = get_vnc_manager()
    registry = TaskEditingRegistry.get_instance()

    async def _run():
        broadcaster = Broadcaster.get_instance()
        vnc_session_id = None
        browser = None
        pw = None

        try:
            # Reserve display for headed browser
            reserved = await vnc_manager.reserve_display(request.task_id)
            vnc_session_id = reserved["session_id"]
            vnc_display = reserved["display"]

            # Launch headed browser on Xvfb
            pw = await async_playwright().__aenter__()
            launch_env = {**os.environ, "DISPLAY": vnc_display}
            browser = await pw.chromium.launch(
                headless=False,
                args=["--no-sandbox", "--disable-setuid-sandbox"],
                env=launch_env,
            )
            context = await browser.new_context()
            await apply_stealth(context)
            page = await context.new_page()

            # Navigate using resilient waits. "networkidle" can hang on pages
            # with long-lived connections (analytics, websockets, etc.).
            await page.goto(request.url, wait_until="domcontentloaded", timeout=45000)
            try:
                await page.wait_for_load_state("load", timeout=15000)
            except Exception:
                # Best effort only.
                pass
            await _wait_for_render_ready(page, timeout_ms=3000)

            # Use existing user corrections or create empty structure
            if request.user_corrections:
                user_data = request.user_corrections
                print(f"[ANALYZE] Using existing user_corrections with {len(user_data.get('steps', []))} steps", flush=True)

                # IMPORTANT: If this is a login step, override the first step's form_type and page_url
                if request.is_login_step and user_data.get("steps"):
                    first_step = user_data["steps"][0]
                    if first_step.get("form_type") != "login" or first_step.get("page_url") != request.url:
                        print(f"[ANALYZE] Fixing first step: form_type={first_step.get('form_type')} -> login, page_url={first_step.get('page_url')} -> {request.url}", flush=True)
                        first_step["form_type"] = "login"
                        first_step["page_url"] = request.url
            else:
                # For new sessions, set form_type based on whether this is a login step
                form_type = "login" if request.is_login_step else "target"
                user_data = {
                    "steps": [{
                        "step_order": 0,
                        "form_type": form_type,
                        "form_selector": "",
                        "submit_selector": "",
                        "fields": [],
                        "page_url": request.url,
                    }],
                }
                print(f"[ANALYZE] Created new step with form_type={form_type}, page_url={request.url}", flush=True)

            # Build fields list from steps
            fields = []
            for step in user_data.get("steps", []):
                for field in step.get("fields", []):
                    fields.append(field)

            # Create FieldHighlighter and inject
            highlighter = FieldHighlighter(page, request.task_id)
            await highlighter.setup(fields)
            await highlighter.inject()

            # Activate VNC
            vnc_result = await vnc_manager.activate_vnc(vnc_session_id)

            # Register session in HighlighterRegistry
            session = HighlighterSession(
                task_id=request.task_id,
                highlighter=highlighter,
                browser=browser,
                context=context,
                page=page,
                pw=pw,
                vnc_session_id=vnc_session_id,
                fields=fields,
            )
            h_registry = HighlighterRegistry.get_instance()
            await h_registry.register(session)

            # Broadcast HighlightingReady
            broadcaster.trigger_task_editing(request.task_id, "HighlightingReady", {
                "vnc_url": vnc_result.get("vnc_url"),
                "vnc_session_id": vnc_session_id,
                "fields": fields,
                "user_corrections": user_data,
            })

            return user_data

        except asyncio.CancelledError:
            print(f"[INTERACTIVE_EDITING] Cancelled by user for task {request.task_id}", flush=True)
        except Exception as e:
            import traceback
            print(f"[INTERACTIVE_EDITING] EXCEPTION: {e}\n{traceback.format_exc()}", flush=True)

            # On error, clean up browser
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass
            if pw:
                try:
                    await pw.__aexit__(None, None, None)
                except Exception:
                    pass
            if vnc_session_id and vnc_manager:
                try:
                    await vnc_manager.stop_session(vnc_session_id)
                except Exception:
                    pass

            # Error already logged above in traceback
        finally:
            registry.unregister(request.task_id)

    task = asyncio.create_task(_run())
    registry.register(request.task_id, task)
    return {"status": "started", "task_id": request.task_id}


@router.post("/analyze/{task_id}/cancel")
async def cancel_task(task_id: str):
    """Cancel a running task editing session."""
    registry = TaskEditingRegistry.get_instance()
    cancelled = registry.cancel(task_id)
    if cancelled:
        return {"status": "cancelled"}
    return {"status": "not_found"}
