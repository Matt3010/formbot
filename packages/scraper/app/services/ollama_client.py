import httpx
import json
from app.config import settings


class OllamaClient:
    def __init__(self, base_url: str = None, model: str = None):
        self.base_url = base_url or settings.ollama_url
        self.model = model or "llama3.2:1b"

    async def generate(self, prompt: str, model: str = None) -> str:
        """Send prompt to Ollama and get response."""
        target_model = model or self.model
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": target_model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json"
                }
            )
            response.raise_for_status()
            result = response.json()
            return result.get("response", "")

    async def parse_json_response(self, prompt: str, model: str = None) -> dict:
        """Send prompt and parse JSON response."""
        raw = await self.generate(prompt, model)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Try to extract JSON from the response
            start = raw.find('{')
            end = raw.rfind('}') + 1
            if start != -1 and end > start:
                return json.loads(raw[start:end])
            raise ValueError(f"Could not parse JSON from Ollama response: {raw[:200]}")

    async def is_available(self) -> bool:
        """Check if Ollama service is reachable."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except Exception:
            return False
