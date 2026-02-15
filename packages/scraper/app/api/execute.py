import asyncio
import logging
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from app.database import get_db, SessionLocal
from app.services.task_executor import TaskExecutor
from app.api.vnc import get_vnc_manager

router = APIRouter()
logger = logging.getLogger("formbot.execute")

# Store background execution results
_execution_results: dict[str, dict] = {}


class ExecuteRequest(BaseModel):
    task_id: str
    execution_id: Optional[str] = None
    is_dry_run: bool = False
    stealth_enabled: bool = True
    user_agent: Optional[str] = None
    action_delay_ms: int = 0  # No artificial delay


async def _run_execution(request: ExecuteRequest):
    """Run task execution in background with its own DB session."""
    db = SessionLocal()
    try:
        logger.info(f"Starting execution for task {request.task_id} (execution_id={request.execution_id})")
        vnc_manager = get_vnc_manager()
        executor = TaskExecutor(db, vnc_manager=vnc_manager)
        result = await executor.execute(
            task_id=request.task_id,
            execution_id=request.execution_id,
            is_dry_run=request.is_dry_run,
            stealth_enabled=request.stealth_enabled,
            user_agent=request.user_agent,
            action_delay_ms=request.action_delay_ms
        )
        logger.info(f"Execution completed for task {request.task_id}: {result.get('status')}")
        _execution_results[request.task_id] = result
    except Exception as e:
        logger.error(f"Execution failed for task {request.task_id}: {e}", exc_info=True)
        _execution_results[request.task_id] = {"status": "failed", "error": str(e)}
    finally:
        db.close()


@router.post("/execute")
async def execute_task(request: ExecuteRequest):
    # Run execution as a background asyncio task so the HTTP response returns immediately
    asyncio.create_task(_run_execution(request))

    return {
        "status": "started",
        "task_id": request.task_id,
        "execution_id": request.execution_id,
        "message": "Execution started in background"
    }


@router.get("/execute/status/{task_id}")
async def execution_status(task_id: str):
    """Check background execution status."""
    if task_id in _execution_results:
        return _execution_results.pop(task_id)
    return {"status": "running", "task_id": task_id}
