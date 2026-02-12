import re
import time
from typing import Optional
from playwright.async_api import Page, async_playwright
from app.services.ollama_client import OllamaClient
from app.services.stealth import apply_stealth
from app.services.broadcaster import Broadcaster
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
