import os
import re
import time
from typing import Optional
from playwright.async_api import Page, async_playwright
from app.services.ollama_client import OllamaClient
from app.services.stealth import apply_stealth
from app.services.broadcaster import Broadcaster
from app.services.field_highlighter import FieldHighlighter
from app.services.highlighter_registry import HighlighterRegistry, HighlighterSession
from app.prompts.form_analysis import FORM_ANALYSIS_PROMPT

# Attributes to keep when cleaning HTML
KEEP_ATTRS = {
    "id", "name", "class", "type", "value", "placeholder",
    "action", "method", "for", "href", "src", "required",
    "autocomplete", "pattern", "min", "max", "step",
    "checked", "selected", "disabled", "readonly", "multiple", "accept",
}

LOGIN_SIGNALS = [
    'input[type="password"]',
    'input[name*="password"]',
    'input[autocomplete="current-password"]',
    'input[autocomplete="new-password"]',
]


class FormAnalyzer:
    def __init__(self, ollama_model: str = None):
        self.ollama = OllamaClient(model=ollama_model)
        self.broadcaster = Broadcaster.get_instance()

    @staticmethod
    def _clean_html(html: str) -> str:
        """Remove noisy/irrelevant parts of HTML before sending to the AI."""
        # Remove <script>...</script>
        html = re.sub(r"<script[\s\S]*?</script>", "", html, flags=re.IGNORECASE)
        # Remove <style>...</style>
        html = re.sub(r"<style[\s\S]*?</style>", "", html, flags=re.IGNORECASE)
        # Remove HTML comments
        html = re.sub(r"<!--[\s\S]*?-->", "", html)
        # Remove <svg>...</svg>
        html = re.sub(r"<svg[\s\S]*?</svg>", "", html, flags=re.IGNORECASE)
        # Remove <path ... /> or <path ...>...</path>
        html = re.sub(r"<path[\s\S]*?(?:/>|</path>)", "", html, flags=re.IGNORECASE)
        # Remove <noscript>...</noscript>
        html = re.sub(r"<noscript[\s\S]*?</noscript>", "", html, flags=re.IGNORECASE)

        # Remove non-relevant attributes, keeping only KEEP_ATTRS
        def _strip_attrs(match: re.Match) -> str:
            tag_start = match.group(1)  # e.g. "<input"
            attrs_str = match.group(2)  # everything between tag name and >
            closing = match.group(3)    # ">" or "/>"
            kept = []
            for attr_match in re.finditer(
                r"""([\w-]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|(\S+))|([\w-]+)(?=\s|/?>)""",
                attrs_str,
            ):
                attr_name = (attr_match.group(1) or attr_match.group(5) or "").lower()
                if attr_name in KEEP_ATTRS:
                    kept.append(attr_match.group(0))
            if kept:
                return f"{tag_start} {' '.join(kept)}{closing}"
            return f"{tag_start}{closing}"

        html = re.sub(
            r"(<\w+)((?:\s+[^>]*?)?)(\s*/?>)",
            _strip_attrs,
            html,
        )

        # Collapse multiple whitespace into single space
        html = re.sub(r"\s{2,}", " ", html)

        return html.strip()

    @staticmethod
    async def _detect_login_heuristic(page: Page) -> bool:
        """Check if the page contains password-related inputs (login signal)."""
        for selector in LOGIN_SIGNALS:
            try:
                count = await page.locator(selector).count()
                if count > 0:
                    return True
            except Exception:
                continue
        return False

    async def analyze_url(self, url: str, stealth: bool = True,
                          analysis_id: Optional[str] = None) -> dict:
        """Navigate to URL, extract HTML, analyze with Ollama.
        If analysis_id is provided, streams AI thinking tokens via WebSocket."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()

            if stealth:
                await apply_stealth(context)

            page = await context.new_page()

            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
                # Wait a bit for dynamic content
                await page.wait_for_timeout(2000)

                # Get page HTML
                html_content = await page.content()

                # Clean HTML before truncation
                html_content = self._clean_html(html_content)

                # Truncate HTML if too long (keep first 50K chars)
                if len(html_content) > 50000:
                    html_content = html_content[:50000]

                # Analyze with Ollama
                prompt = FORM_ANALYSIS_PROMPT.replace("{html_content}", html_content)

                if analysis_id:
                    # Use streaming with AI thinking broadcast
                    token_buffer = ""
                    last_flush = time.time()

                    def on_token(token: str):
                        nonlocal token_buffer, last_flush
                        token_buffer += token
                        now = time.time()
                        # Flush every 100ms to avoid too many broadcasts
                        if now - last_flush >= 0.1:
                            self.broadcaster.trigger_analysis(analysis_id, "AiThinking", {
                                "token": token_buffer,
                                "done": False,
                            })
                            token_buffer = ""
                            last_flush = now

                    result = await self.ollama.parse_json_response_stream(
                        prompt, on_token=on_token
                    )

                    # Flush remaining buffer
                    if token_buffer:
                        self.broadcaster.trigger_analysis(analysis_id, "AiThinking", {
                            "token": token_buffer,
                            "done": False,
                        })

                    # Signal done
                    self.broadcaster.trigger_analysis(analysis_id, "AiThinking", {
                        "token": "",
                        "done": True,
                    })
                else:
                    result = await self.ollama.parse_json_response(prompt)

                # Heuristic override: no password field → not a login page
                has_password = await self._detect_login_heuristic(page)
                if not has_password:
                    result["page_requires_login"] = False

                return result
            except Exception as e:
                return {
                    "forms": [],
                    "page_requires_login": False,
                    "error": str(e)
                }
            finally:
                await browser.close()

    async def analyze_url_interactive(
        self,
        url: str,
        analysis_id: str,
        vnc_manager=None,
        stealth: bool = True,
        existing_result: dict | None = None,
    ) -> dict:
        """Analyze URL interactively: keep browser open for VNC editing.

        If existing_result is provided, skips the Ollama AI analysis and uses
        the pre-existing result to set up field highlights directly.
        """
        from app.services.vnc_manager import VNCManager

        vnc_mgr = vnc_manager or VNCManager()
        vnc_session_id = None
        browser = None
        pw = None

        try:
            # Reserve display for headed browser
            reserved = await vnc_mgr.reserve_display(analysis_id)
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
            if stealth:
                await apply_stealth(context)
            page = await context.new_page()

            # Navigate
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(2000)

            if existing_result:
                # Skip AI — use the result from the previous analysis
                result = existing_result
            else:
                # Full AI analysis (only when no previous result available)
                html_content = await page.content()
                html_content = self._clean_html(html_content)
                if len(html_content) > 50000:
                    html_content = html_content[:50000]

                prompt = FORM_ANALYSIS_PROMPT.replace("{html_content}", html_content)

                # Stream AI thinking
                token_buffer = ""
                last_flush = time.time()

                def on_token(token: str):
                    nonlocal token_buffer, last_flush
                    token_buffer += token
                    now = time.time()
                    if now - last_flush >= 0.1:
                        self.broadcaster.trigger_analysis(analysis_id, "AiThinking", {
                            "token": token_buffer,
                            "done": False,
                        })
                        token_buffer = ""
                        last_flush = now

                result = await self.ollama.parse_json_response_stream(
                    prompt, on_token=on_token
                )

                if token_buffer:
                    self.broadcaster.trigger_analysis(analysis_id, "AiThinking", {
                        "token": token_buffer,
                        "done": False,
                    })

                self.broadcaster.trigger_analysis(analysis_id, "AiThinking", {
                    "token": "",
                    "done": True,
                })

                # Heuristic override
                has_password = await self._detect_login_heuristic(page)
                if not has_password:
                    result["page_requires_login"] = False

            # Build fields list from analysis result
            fields = []
            for form in result.get("forms", []):
                for field in form.get("fields", []):
                    fields.append(field)

            # Create FieldHighlighter and inject
            highlighter = FieldHighlighter(page, analysis_id)
            await highlighter.setup(fields)
            await highlighter.inject()

            # Activate VNC
            vnc_result = await vnc_mgr.activate_vnc(vnc_session_id)

            # Register session in HighlighterRegistry
            session = HighlighterSession(
                analysis_id=analysis_id,
                highlighter=highlighter,
                browser=browser,
                context=context,
                page=page,
                pw=pw,
                vnc_session_id=vnc_session_id,
                fields=fields,
            )
            registry = HighlighterRegistry.get_instance()
            await registry.register(session)

            # Broadcast HighlightingReady
            self.broadcaster.trigger_analysis(analysis_id, "HighlightingReady", {
                "vnc_url": vnc_result.get("vnc_url"),
                "vnc_session_id": vnc_session_id,
                "fields": fields,
                "analysis_result": result,
            })

            return result

        except Exception as e:
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
            if vnc_session_id and vnc_mgr:
                try:
                    await vnc_mgr.stop_session(vnc_session_id)
                except Exception:
                    pass

            self.broadcaster.trigger_analysis(analysis_id, "AiThinking", {
                "token": f"\nError: {str(e)}",
                "done": True,
            })
            return {
                "forms": [],
                "page_requires_login": False,
                "error": str(e),
            }

    async def analyze_dynamic(self, url: str, previous_state: dict, interaction: str) -> dict:
        """Re-analyze page after an interaction for dynamic fields."""
        # Similar to analyze_url but with interaction context
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(2000)

                html_content = await page.content()

                # Clean HTML before truncation
                html_content = self._clean_html(html_content)

                if len(html_content) > 50000:
                    html_content = html_content[:50000]

                prompt = FORM_ANALYSIS_PROMPT.replace("{html_content}", html_content)
                result = await self.ollama.parse_json_response(prompt)

                # Heuristic override: no password field → not a login page
                has_password = await self._detect_login_heuristic(page)
                if not has_password:
                    result["page_requires_login"] = False

                return result
            except Exception as e:
                return {"forms": [], "error": str(e)}
            finally:
                await browser.close()
