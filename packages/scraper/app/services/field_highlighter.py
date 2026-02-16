"""FieldHighlighter — manages injection of highlight.js into a Playwright page.

Exposes bridge functions (exposeFunction) for browser → Python callbacks,
and provides commands (Python → browser via page.evaluate).
"""

import json
import os
from typing import Optional

from playwright.async_api import Page

from app.services.broadcaster import Broadcaster


# Load the highlight.js script once at module level
_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "..", "injection", "highlight.js")
with open(_SCRIPT_PATH, "r") as _f:
    _HIGHLIGHT_JS = _f.read()


class FieldHighlighter:
    """Injects visual overlays on form fields in a Playwright Page."""

    def __init__(self, page: Page, task_id: str):
        self.page = page
        self.task_id = task_id
        self.broadcaster = Broadcaster.get_instance()
        self._exposed = False
        self._fields: list[dict] = []
        self._mode: str = "select"

    async def setup(self, fields: list[dict]) -> None:
        """Register exposeFunction callbacks and store initial fields."""
        self._fields = fields

        if not self._exposed:
            await self.page.expose_function(
                "__formbot_onFieldSelected", self._on_field_selected
            )
            await self.page.expose_function(
                "__formbot_onFieldAdded", self._on_field_added
            )
            await self.page.expose_function(
                "__formbot_onFieldRemoved", self._on_field_removed
            )
            await self.page.expose_function(
                "__formbot_onFieldValueChanged", self._on_field_value_changed
            )
            self._exposed = True

        # Auto re-inject on navigation
        self.page.on("load", lambda _: self._safe_reinject())
        self.page.on("framenavigated", lambda _: self._safe_reinject())

    async def inject(self) -> None:
        """Inject highlight.js into the page and initialize with current fields."""
        fields_json = json.dumps(self._fields)

        # Inject into main frame
        await self.page.evaluate(_HIGHLIGHT_JS)
        await self.page.evaluate(
            f"window.__FORMBOT_HIGHLIGHT.init({fields_json})"
        )
        await self.page.evaluate(
            f"window.__FORMBOT_HIGHLIGHT.command_setMode({json.dumps(self._mode)})"
        )

        # Try injecting into iframes too
        for frame in self.page.frames:
            if frame == self.page.main_frame:
                continue
            try:
                await frame.evaluate(_HIGHLIGHT_JS)
                await frame.evaluate(
                    f"window.__FORMBOT_HIGHLIGHT.init({fields_json})"
                )
                await frame.evaluate(
                    f"window.__FORMBOT_HIGHLIGHT.command_setMode({json.dumps(self._mode)})"
                )
            except Exception:
                pass  # frame may be detached or cross-origin

    async def cleanup(self) -> None:
        """Remove all overlays and event listeners from the page."""
        try:
            await self.page.evaluate(
                "if(window.__FORMBOT_HIGHLIGHT) window.__FORMBOT_HIGHLIGHT.command_cleanup()"
            )
        except Exception:
            pass

    # ----- Commands: frontend → browser via page.evaluate -----

    async def update_fields(self, fields: list[dict]) -> None:
        """Update the highlighted fields."""
        self._fields = fields
        fields_json = json.dumps(fields)
        await self.page.evaluate(
            f"window.__FORMBOT_HIGHLIGHT.command_updateFields({fields_json})"
        )

    async def set_mode(self, mode: str) -> None:
        """Set interaction mode: 'select' | 'add' | 'remove'."""
        self._mode = mode
        await self.page.evaluate(
            f"window.__FORMBOT_HIGHLIGHT.command_setMode({json.dumps(mode)})"
        )

    async def focus_field(self, field_index: int) -> None:
        """Scroll to and flash-highlight a specific field."""
        await self.page.evaluate(
            f"window.__FORMBOT_HIGHLIGHT.command_focusField({field_index})"
        )

    async def test_selector(self, selector: str) -> dict:
        """Test a CSS selector: flash green/red, return {found, matchCount}."""
        result = await self.page.evaluate(
            f"window.__FORMBOT_HIGHLIGHT.command_testSelector({json.dumps(selector)})"
        )
        return result or {"found": False, "matchCount": 0}

    async def fill_field(self, field_index: int, value: str) -> None:
        """Programmatically fill a field's value in the live page."""
        await self.page.evaluate(
            f"window.__FORMBOT_HIGHLIGHT.command_fillField({field_index}, {json.dumps(value)})"
        )

    async def read_field_value(self, field_index: int) -> str:
        """Read the current value of a field from the live page."""
        result = await self.page.evaluate(
            f"window.__FORMBOT_HIGHLIGHT.command_readFieldValue({field_index})"
        )
        return result or ""

    # ----- Callbacks: browser → Python via exposeFunction → Pusher -----

    async def _on_field_selected(self, data_json: str) -> None:
        """Called when user clicks a field in 'select' mode."""
        data = json.loads(data_json)
        self.broadcaster.trigger_task_editing(self.task_id, "FieldSelected", data)

    async def _on_field_added(self, data_json: str) -> None:
        """Called when user clicks an element in 'add' mode."""
        data = json.loads(data_json)
        self.broadcaster.trigger_task_editing(self.task_id, "FieldAdded", data)

    async def _on_field_removed(self, data_json: str) -> None:
        """Called when user clicks a field in 'remove' mode."""
        data = json.loads(data_json)
        self.broadcaster.trigger_task_editing(self.task_id, "FieldRemoved", data)

    async def _on_field_value_changed(self, data_json: str) -> None:
        """Called when user types in a tracked field on the live page."""
        data = json.loads(data_json)
        self.broadcaster.trigger_task_editing(self.task_id, "FieldValueChanged", data)

    # ----- Re-injection on navigation -----

    def _safe_reinject(self) -> None:
        """Schedule re-injection (fire-and-forget on navigation)."""
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self._reinject())
        except RuntimeError:
            pass

    async def _reinject(self) -> None:
        """Re-inject highlight.js after a page navigation."""
        try:
            try:
                await self.page.wait_for_load_state("domcontentloaded", timeout=3000)
            except Exception:
                pass
            await self.inject()
        except Exception:
            pass
