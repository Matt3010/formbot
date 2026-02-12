from fastapi import APIRouter
from pydantic import BaseModel
from app.services.vnc_manager import VNCManager

router = APIRouter()

# Singleton VNC manager shared with execute endpoint
vnc_manager = VNCManager()


def get_vnc_manager() -> VNCManager:
    return vnc_manager


class VNCStartRequest(BaseModel):
    execution_id: str


class VNCStopRequest(BaseModel):
    session_id: str


class VNCResumeRequest(BaseModel):
    session_id: str
    execution_id: str


@router.post("/vnc/start")
async def start_vnc(request: VNCStartRequest):
    result = await vnc_manager.start_session(request.execution_id)
    return result


@router.post("/vnc/stop")
async def stop_vnc(request: VNCStopRequest):
    result = await vnc_manager.stop_session(request.session_id)
    return result


class VNCAnalysisResumeRequest(BaseModel):
    session_id: str
    analysis_id: str


@router.post("/vnc/resume")
async def resume_vnc(request: VNCResumeRequest):
    result = await vnc_manager.resume_session(request.session_id, request.execution_id)
    return result


@router.post("/vnc/resume-analysis")
async def resume_analysis_vnc(request: VNCAnalysisResumeRequest):
    """Resume a VNC session during login-aware analysis."""
    result = await vnc_manager.resume_session(request.session_id, request.analysis_id)
    return result
