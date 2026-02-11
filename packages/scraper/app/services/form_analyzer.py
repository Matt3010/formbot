from playwright.async_api import async_playwright
from app.services.ollama_client import OllamaClient
from app.services.stealth import apply_stealth
from app.prompts.form_analysis import FORM_ANALYSIS_PROMPT


class FormAnalyzer:
    def __init__(self, ollama_model: str = None):
        self.ollama = OllamaClient(model=ollama_model)

    async def analyze_url(self, url: str, stealth: bool = True) -> dict:
        """Navigate to URL, extract HTML, analyze with Ollama."""
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
