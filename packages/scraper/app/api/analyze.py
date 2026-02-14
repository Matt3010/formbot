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
from app.services.analysis_registry import AnalysisRegistry
from app.services.field_highlighter import FieldHighlighter
from app.services.highlighter_registry import HighlighterRegistry, HighlighterSession
from app.api.vnc import get_vnc_manager
from app.config import settings

router = APIRouter()


class InteractiveAnalyzeRequest(BaseModel):
    url: str
    analysis_id: str
    analysis_result: Optional[dict] = None


@router.post("/analyze/interactive")
async def analyze_url_interactive(request: InteractiveAnalyzeRequest):
    """Start interactive analysis with VNC — keeps browser open for field editing."""
    vnc_manager = get_vnc_manager()
    registry = AnalysisRegistry.get_instance()

    async def _run():
        broadcaster = Broadcaster.get_instance()
        vnc_session_id = None
        browser = None
        pw = None

        try:
            # Reserve display for headed browser
            reserved = await vnc_manager.reserve_display(request.analysis_id)
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

            # Use existing result or create empty one
            if request.analysis_result:
                result = request.analysis_result
            else:
                result = {
                    "forms": [{
                        "form_type": "target",
                        "form_selector": "",
                        "submit_selector": "",
                        "fields": [],
                        "page_url": request.url,
                    }],
                    "page_requires_login": False,
                }

            # Build fields list from result
            fields = []
            for form in result.get("forms", []):
                for field in form.get("fields", []):
                    fields.append(field)

            # Create FieldHighlighter and inject
            highlighter = FieldHighlighter(page, request.analysis_id)
            await highlighter.setup(fields)
            await highlighter.inject()

            # Activate VNC
            vnc_result = await vnc_manager.activate_vnc(vnc_session_id)

            # Register session in HighlighterRegistry
            session = HighlighterSession(
                analysis_id=request.analysis_id,
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
            broadcaster.trigger_analysis(request.analysis_id, "HighlightingReady", {
                "vnc_url": vnc_result.get("vnc_url"),
                "vnc_session_id": vnc_session_id,
                "fields": fields,
                "analysis_result": result,
            })

            return result

        except asyncio.CancelledError:
            broadcaster.trigger_analysis(request.analysis_id, "AnalysisCompleted", {
                "result": {},
                "error": "Cancelled by user",
            })
            await _notify_backend_result(request.analysis_id, {}, "Cancelled by user")
        except Exception as e:
            import traceback
            print(f"[INTERACTIVE_ANALYSIS] EXCEPTION: {e}\n{traceback.format_exc()}", flush=True)

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

            broadcaster.trigger_analysis(request.analysis_id, "AnalysisCompleted", {
                "result": {},
                "error": str(e),
            })
            await _notify_backend_result(request.analysis_id, {}, str(e))
        finally:
            registry.unregister(request.analysis_id)

    task = asyncio.create_task(_run())
    registry.register(request.analysis_id, task)
    return {"status": "started", "analysis_id": request.analysis_id}


@router.post("/analyze/{analysis_id}/cancel")
async def cancel_analysis(analysis_id: str):
    """Cancel a running analysis."""
    registry = AnalysisRegistry.get_instance()
    cancelled = registry.cancel(analysis_id)
    if cancelled:
        return {"status": "cancelled"}
    return {"status": "not_found"}


async def _notify_backend_result(analysis_id: str, result: dict, error: Optional[str]):
    """Call backend internal endpoint to store the analysis result."""
    try:
        url = f"{settings.backend_url}/api/internal/analyses/{analysis_id}/result"
        async with httpx.AsyncClient(timeout=30) as client:
            await client.post(url, json={
                "result": result,
                "error": error,
            }, headers={
                "X-Internal-Key": settings.internal_api_key,
            })
    except Exception as e:
        print(f"[INTERACTIVE_ANALYSIS] Failed to notify backend: {e}", flush=True)
