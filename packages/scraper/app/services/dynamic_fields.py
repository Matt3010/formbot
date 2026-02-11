from playwright.async_api import Page
from app.services.ollama_client import OllamaClient
from app.prompts.form_analysis import FORM_ANALYSIS_PROMPT


class DynamicFieldAnalyzer:
    def __init__(self, ollama_model: str = None):
        self.ollama = OllamaClient(model=ollama_model)

    async def reanalyze_after_interaction(self, page: Page) -> dict:
        """Re-analyze page DOM after an interaction to detect dynamic fields."""
        html_content = await page.content()

        if len(html_content) > 50000:
            html_content = html_content[:50000]

        prompt = FORM_ANALYSIS_PROMPT.replace("{html_content}", html_content)
        result = await self.ollama.parse_json_response(prompt)

        return result

    async def detect_new_fields(self, previous_fields: list, current_fields: list) -> list:
        """Compare previous and current fields to find newly appeared ones."""
        previous_selectors = {f.get("field_selector") for f in previous_fields}
        new_fields = [f for f in current_fields if f.get("field_selector") not in previous_selectors]
        return new_fields
