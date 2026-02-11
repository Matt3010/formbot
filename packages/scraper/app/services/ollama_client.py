import httpx
import json
from typing import Callable, Optional
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

    async def generate_stream(self, prompt: str, model: str = None,
                              on_token: Optional[Callable[[str], None]] = None) -> str:
        """Send prompt to Ollama with streaming. Calls on_token for each chunk.
        Returns the complete accumulated response."""
        target_model = model or self.model
        accumulated = ""

        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/generate",
                json={
                    "model": target_model,
                    "prompt": prompt,
                    "stream": True,
                    "format": "json"
                }
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line)
                        token = chunk.get("response", "")
                        if token:
                            accumulated += token
                            if on_token:
                                on_token(token)
                        if chunk.get("done", False):
                            break
                    except json.JSONDecodeError:
                        continue

        return accumulated

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

    async def parse_json_response_stream(self, prompt: str, model: str = None,
                                         on_token: Optional[Callable[[str], None]] = None) -> dict:
        """Send prompt with streaming, parse JSON response. Calls on_token for each chunk."""
        raw = await self.generate_stream(prompt, model, on_token=on_token)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
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
