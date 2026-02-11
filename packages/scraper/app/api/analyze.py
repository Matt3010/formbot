from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from app.services.form_analyzer import FormAnalyzer

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


@router.post("/analyze/dynamic")
async def analyze_dynamic(request: DynamicAnalyzeRequest):
    analyzer = FormAnalyzer()
    result = await analyzer.analyze_dynamic(
        request.url,
        request.previous_state or {},
        request.interaction_performed or ""
    )
    return result
