import time
from typing import Optional
from playwright.async_api import async_playwright
from app.services.ollama_client import OllamaClient
from app.services.stealth import apply_stealth
from app.services.broadcaster import Broadcaster
from app.prompts.form_analysis import FORM_ANALYSIS_PROMPT


class FormAnalyzer:
    def __init__(self, ollama_model: str = None):
        self.ollama = OllamaClient(model=ollama_model)
        self.broadcaster = Broadcaster.get_instance()

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
                if len(html_content) > 50000:
                    html_content = html_content[:50000]

                prompt = FORM_ANALYSIS_PROMPT.replace("{html_content}", html_content)
                result = await self.ollama.parse_json_response(prompt)
                return result
            except Exception as e:
                return {"forms": [], "error": str(e)}
            finally:
                await browser.close()
