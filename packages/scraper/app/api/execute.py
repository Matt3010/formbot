import asyncio
import logging
from datetime import datetime
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from app.database import SessionLocal
from app.models.execution_log import ExecutionLog
from app.services.task_executor import TaskExecutor
from app.api.vnc import get_vnc_manager

router = APIRouter()
logger = logging.getLogger("formbot.execute")

# Store background execution results
_execution_results: dict[str, dict] = {}
# Track running background execution tasks by execution_id (fallback: task_id)
_running_executions: dict[str, asyncio.Task] = {}


class ExecuteRequest(BaseModel):
    task_id: str
    execution_id: Optional[str] = None
    is_dry_run: bool = False
    stealth_enabled: bool = True
    user_agent: Optional[str] = None
    action_delay_ms: int = 500


async def _run_execution(request: ExecuteRequest):
    """Run task execution in background with its own DB session."""
    run_key = request.execution_id or request.task_id
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
        # Keep task_id compatibility for legacy polling and add execution_id key for precision.
        _execution_results[request.task_id] = result
        if request.execution_id:
            _execution_results[request.execution_id] = result
    except asyncio.CancelledError:
        logger.info(f"Execution cancelled for task {request.task_id} (execution_id={request.execution_id})")
        cancelled_result = {
            "execution_id": request.execution_id,
            "status": "failed",
            "error": "Aborted by user",
        }
        _execution_results[request.task_id] = cancelled_result
        if request.execution_id:
            _execution_results[request.execution_id] = cancelled_result

            # Best-effort DB update in case cancellation happened mid-execution.
            try:
                execution = db.query(ExecutionLog).filter(
                    ExecutionLog.id == request.execution_id
                ).first()
                if execution:
                    execution.status = "failed"
                    execution.error_message = "Aborted by user"
                    execution.completed_at = datetime.utcnow()
                    execution.vnc_session_id = None
                    db.commit()
            except Exception:
                db.rollback()
        raise
    except Exception as e:
        logger.error(f"Execution failed for task {request.task_id}: {e}", exc_info=True)
        failure_result = {"execution_id": request.execution_id, "status": "failed", "error": str(e)}
        _execution_results[request.task_id] = failure_result
        if request.execution_id:
            _execution_results[request.execution_id] = failure_result
    finally:
        _running_executions.pop(run_key, None)
        db.close()


@router.post("/execute")
async def execute_task(request: ExecuteRequest):
    run_key = request.execution_id or request.task_id
    existing = _running_executions.get(run_key)
    if existing and not existing.done():
        return {
            "status": "already_running",
            "task_id": request.task_id,
            "execution_id": request.execution_id,
            "message": "Execution is already running",
        }

    # Run execution as a background asyncio task so the HTTP response returns immediately
    task = asyncio.create_task(_run_execution(request))
    _running_executions[run_key] = task

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


@router.post("/execute/{execution_id}/cancel")
async def cancel_execution(execution_id: str):
    """Cancel a running background execution by execution ID."""
    task = _running_executions.get(execution_id)
    if task and not task.done():
        task.cancel()
        return {"status": "cancelled", "execution_id": execution_id}
    return {"status": "not_found", "execution_id": execution_id}
