"""HighlighterRegistry — singleton registry of active highlighting sessions.

Each session holds a reference to the browser, context, page, FieldHighlighter,
and VNC session so they can be cleaned up on confirm/cancel/timeout.
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional

from playwright.async_api import Browser, BrowserContext, Page

from app.services.field_highlighter import FieldHighlighter


@dataclass
class HighlighterSession:
    task_id: str
    highlighter: FieldHighlighter
    browser: Browser
    context: BrowserContext
    page: Page
    pw: object  # async_playwright instance
    vnc_session_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    confirmed_event: asyncio.Event = field(default_factory=asyncio.Event)
    cancelled_event: asyncio.Event = field(default_factory=asyncio.Event)
    fields: list = field(default_factory=list)
    resume_event: asyncio.Event = field(default_factory=asyncio.Event)
    executing: bool = False
    navigating: bool = False


class HighlighterRegistry:
    """Thread-safe singleton registry for active highlighting sessions."""

    _instance: Optional["HighlighterRegistry"] = None

    def __init__(self):
        self._sessions: dict[str, HighlighterSession] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None

    @classmethod
    def get_instance(cls) -> "HighlighterRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def register(self, session: HighlighterSession) -> None:
        async with self._lock:
            self._sessions[session.task_id] = session

    def get(self, task_id: str) -> Optional[HighlighterSession]:
        return self._sessions.get(task_id)

    async def remove(self, task_id: str) -> Optional[HighlighterSession]:
        async with self._lock:
            return self._sessions.pop(task_id, None)

    async def cleanup_session(self, task_id: str) -> None:
        """Cleanup overlay, close browser, remove from registry."""
        session = await self.remove(task_id)
        if not session:
            return

        try:
            await session.highlighter.cleanup()
        except Exception:
            pass

        try:
            await session.browser.close()
        except Exception:
            pass

        try:
            await session.pw.__aexit__(None, None, None)
        except Exception:
            pass

    async def start_cleanup_loop(self, timeout_seconds: int = 1800) -> None:
        """Background task that cleans up sessions older than timeout_seconds."""
        while True:
            await asyncio.sleep(60)
            now = time.time()
            stale = []
            async with self._lock:
                for aid, session in self._sessions.items():
                    if now - session.created_at > timeout_seconds:
                        stale.append(aid)

            for aid in stale:
                await self.cleanup_session(aid)

    def start_background_cleanup(self, timeout_seconds: int = 1800) -> None:
        """Start the cleanup loop as a background task."""
        if self._cleanup_task is None or self._cleanup_task.done():
            loop = asyncio.get_event_loop()
            self._cleanup_task = loop.create_task(
                self.start_cleanup_loop(timeout_seconds)
            )

    @property
    def active_count(self) -> int:
        return len(self._sessions)
