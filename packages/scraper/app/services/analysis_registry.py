import asyncio
from typing import Optional


class AnalysisRegistry:
    """Singleton registry that tracks running asyncio tasks for analysis operations."""

    _instance: Optional["AnalysisRegistry"] = None

    def __init__(self):
        self._tasks: dict[str, asyncio.Task] = {}

    @classmethod
    def get_instance(cls) -> "AnalysisRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, analysis_id: str, task: asyncio.Task):
        self._tasks[analysis_id] = task

    def cancel(self, analysis_id: str) -> bool:
        task = self._tasks.get(analysis_id)
        if task and not task.done():
            task.cancel()
            return True
        return False

    def unregister(self, analysis_id: str):
        self._tasks.pop(analysis_id, None)

    def is_running(self, analysis_id: str) -> bool:
        task = self._tasks.get(analysis_id)
        return task is not None and not task.done()
