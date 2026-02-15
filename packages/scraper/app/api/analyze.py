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


class InteractiveAnalyzeRequest(BaseModel):
    url: str
    task_id: str
    user_corrections: Optional[dict] = None


@router.post("/analyze/interactive")
async def analyze_url_interactive(request: InteractiveAnalyzeRequest):
    """Start interactive task editing with VNC — keeps browser open for field editing."""
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
            await page.wait_for_timeout(1000)

            # Use existing user corrections or create empty structure
            if request.user_corrections:
                user_data = request.user_corrections
            else:
                user_data = {
                    "steps": [{
                        "step_order": 0,
                        "form_type": "target",
                        "form_selector": "",
                        "submit_selector": "",
                        "fields": [],
                        "page_url": request.url,
                    }],
                }

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
            broadcaster.trigger_task_editing(request.task_id, "TaskEditingError", {
                "error": "Cancelled by user",
            })
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

            broadcaster.trigger_task_editing(request.task_id, "TaskEditingError", {
                "error": str(e),
            })
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
