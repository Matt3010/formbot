import asyncio
from typing import Optional


class TaskEditingRegistry:
    """Singleton registry that tracks running asyncio tasks for task editing operations."""

    _instance: Optional["TaskEditingRegistry"] = None

    def __init__(self):
        self._tasks: dict[str, asyncio.Task] = {}

    @classmethod
    def get_instance(cls) -> "TaskEditingRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, task_id: str, task: asyncio.Task):
        self._tasks[task_id] = task

    def cancel(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if task and not task.done():
            task.cancel()
            return True
        return False

    def unregister(self, task_id: str):
        self._tasks.pop(task_id, None)

    def is_running(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        return task is not None and not task.done()
