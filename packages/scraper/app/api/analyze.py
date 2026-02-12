import asyncio
import httpx
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from app.services.form_analyzer import FormAnalyzer
from app.services.login_analyzer import LoginAnalyzer
from app.services.broadcaster import Broadcaster
from app.services.analysis_registry import AnalysisRegistry
from app.api.vnc import get_vnc_manager
from app.config import settings

router = APIRouter()


class AnalyzeRequest(BaseModel):
    url: str
    ollama_model: Optional[str] = None
    analysis_id: Optional[str] = None


class DynamicAnalyzeRequest(BaseModel):
    url: str
    previous_state: Optional[dict] = None
    interaction_performed: Optional[str] = None


@router.post("/analyze")
async def analyze_url(request: AnalyzeRequest):
    analyzer = FormAnalyzer(ollama_model=request.ollama_model)
    result = await analyzer.analyze_url(
        request.url,
        analysis_id=request.analysis_id,
    )
    return result


class LoginFieldRequest(BaseModel):
    field_selector: str
    value: str
    field_type: Optional[str] = "text"
    is_sensitive: Optional[bool] = False
    encrypted: Optional[bool] = False


class LoginAndAnalyzeTargetRequest(BaseModel):
    analysis_id: str
    login_url: str
    target_url: str
    login_form_selector: str
    login_submit_selector: str
    login_fields: list[LoginFieldRequest]
    needs_vnc: bool = False
    ollama_model: Optional[str] = None


class InteractiveAnalyzeRequest(BaseModel):
    url: str
    analysis_id: str
    ollama_model: Optional[str] = None


@router.post("/analyze/interactive")
async def analyze_url_interactive(request: InteractiveAnalyzeRequest):
    """Start interactive analysis with VNC — keeps browser open for field editing."""
    vnc_manager = get_vnc_manager()
    analyzer = FormAnalyzer(ollama_model=request.ollama_model)
    registry = AnalysisRegistry.get_instance()

    async def _run():
        broadcaster = Broadcaster.get_instance()
        try:
            result = await analyzer.analyze_url_interactive(
                url=request.url,
                analysis_id=request.analysis_id,
                vnc_manager=vnc_manager,
            )
            broadcaster.trigger_analysis(request.analysis_id, "AnalysisCompleted", {
                "result": result,
                "error": result.get("error"),
            })
            await _notify_backend_result(request.analysis_id, result, result.get("error"))
        except asyncio.CancelledError:
            broadcaster.trigger_analysis(request.analysis_id, "AnalysisCompleted", {
                "result": {},
                "error": "Cancelled by user",
            })
            await _notify_backend_result(request.analysis_id, {}, "Cancelled by user")
        except Exception as e:
            import traceback
            print(f"[INTERACTIVE_ANALYSIS] EXCEPTION: {e}\n{traceback.format_exc()}", flush=True)
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


@router.post("/analyze/dynamic")
async def analyze_dynamic(request: DynamicAnalyzeRequest):
    analyzer = FormAnalyzer()
    result = await analyzer.analyze_dynamic(
        request.url,
        request.previous_state or {},
        request.interaction_performed or ""
    )
    return result


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
        print(f"[LOGIN_ANALYSIS] Failed to notify backend: {e}", flush=True)


async def _run_login_analysis(analyzer: LoginAnalyzer, request: LoginAndAnalyzeTargetRequest):
    """Background task to perform login and analyze target page."""
    registry = AnalysisRegistry.get_instance()
    broadcaster = Broadcaster.get_instance()
    try:
        result = await analyzer.perform_login_and_analyze_target(
            analysis_id=request.analysis_id,
            login_url=request.login_url,
            target_url=request.target_url,
            login_form_selector=request.login_form_selector,
            login_submit_selector=request.login_submit_selector,
            login_fields=[f.model_dump() for f in request.login_fields],
            needs_vnc=request.needs_vnc,
        )

        broadcaster.trigger_analysis(request.analysis_id, "AnalysisCompleted", {
            "result": result,
            "error": result.get("error"),
        })

        await _notify_backend_result(request.analysis_id, result, result.get("error"))
    except asyncio.CancelledError:
        print(f"[LOGIN_ANALYSIS] Cancelled: {request.analysis_id}", flush=True)
        broadcaster.trigger_analysis(request.analysis_id, "AnalysisCompleted", {
            "result": {},
            "error": "Cancelled by user",
        })
        await _notify_backend_result(request.analysis_id, {}, "Cancelled by user")
    except Exception as e:
        import traceback
        print(f"[LOGIN_ANALYSIS] EXCEPTION: {e}\n{traceback.format_exc()}", flush=True)
        broadcaster.trigger_analysis(request.analysis_id, "AnalysisCompleted", {
            "result": {},
            "error": str(e),
        })
        await _notify_backend_result(request.analysis_id, {}, str(e))
    finally:
        registry.unregister(request.analysis_id)


@router.post("/analyze/login-and-target")
async def analyze_login_and_target(request: LoginAndAnalyzeTargetRequest):
    """Start login-aware analysis in background."""
    registry = AnalysisRegistry.get_instance()
    vnc_manager = get_vnc_manager()
    analyzer = LoginAnalyzer(ollama_model=request.ollama_model, vnc_manager=vnc_manager)
    task = asyncio.create_task(_run_login_analysis(analyzer, request))
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
