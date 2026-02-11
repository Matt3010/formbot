"""Tests for app.services.ollama_client.OllamaClient."""

import json
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Tests for OllamaClient.generate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_success():
    """generate sends the prompt to Ollama and returns the response text."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "response": '{"forms": []}',
        "done": True,
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.ollama_client.httpx.AsyncClient", return_value=mock_client):
        from app.services.ollama_client import OllamaClient

        client = OllamaClient(base_url="http://test:11434", model="test-model")
        result = await client.generate("Analyze this HTML")

    assert result == '{"forms": []}'

    # Verify the request payload
    mock_client.post.assert_awaited_once()
    call_args = mock_client.post.call_args
    assert call_args[0][0] == "http://test:11434/api/generate"
    payload = call_args[1]["json"]
    assert payload["model"] == "test-model"
    assert payload["prompt"] == "Analyze this HTML"
    assert payload["stream"] is False
    assert payload["format"] == "json"


@pytest.mark.asyncio
async def test_generate_with_custom_model():
    """generate uses the model parameter when provided."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"response": "{}"}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.ollama_client.httpx.AsyncClient", return_value=mock_client):
        from app.services.ollama_client import OllamaClient

        client = OllamaClient(base_url="http://test:11434", model="default-model")
        await client.generate("test", model="override-model")

    payload = mock_client.post.call_args[1]["json"]
    assert payload["model"] == "override-model"


@pytest.mark.asyncio
async def test_generate_empty_response():
    """generate returns empty string when 'response' key is missing."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"done": True}  # no "response" key
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.ollama_client.httpx.AsyncClient", return_value=mock_client):
        from app.services.ollama_client import OllamaClient

        client = OllamaClient(base_url="http://test:11434")
        result = await client.generate("test prompt")

    assert result == ""


@pytest.mark.asyncio
async def test_generate_connection_error():
    """generate raises an exception when Ollama is unreachable."""
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.ollama_client.httpx.AsyncClient", return_value=mock_client):
        from app.services.ollama_client import OllamaClient

        client = OllamaClient(base_url="http://unreachable:11434")

        with pytest.raises(httpx.ConnectError):
            await client.generate("test")


@pytest.mark.asyncio
async def test_generate_http_error():
    """generate raises for non-200 status codes (via raise_for_status)."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "500 Internal Server Error",
            request=MagicMock(),
            response=MagicMock(status_code=500),
        )
    )

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.ollama_client.httpx.AsyncClient", return_value=mock_client):
        from app.services.ollama_client import OllamaClient

        client = OllamaClient(base_url="http://test:11434")

        with pytest.raises(httpx.HTTPStatusError):
            await client.generate("test")


# ---------------------------------------------------------------------------
# Tests for OllamaClient.parse_json_response
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_parse_json_response_valid():
    """parse_json_response correctly parses valid JSON from Ollama."""
    expected = {"forms": [{"type": "login"}], "page_requires_login": True}

    mock_response = MagicMock()
    mock_response.json.return_value = {"response": json.dumps(expected)}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.ollama_client.httpx.AsyncClient", return_value=mock_client):
        from app.services.ollama_client import OllamaClient

        client = OllamaClient(base_url="http://test:11434")
        result = await client.parse_json_response("Analyze this")

    assert result == expected
    assert result["forms"][0]["type"] == "login"


@pytest.mark.asyncio
async def test_parse_json_response_extracts_json_from_text():
    """parse_json_response extracts JSON when it is embedded in surrounding text."""
    embedded = 'Here is the analysis:\n{"forms": [], "page_requires_login": false}\nDone.'

    mock_response = MagicMock()
    mock_response.json.return_value = {"response": embedded}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.ollama_client.httpx.AsyncClient", return_value=mock_client):
        from app.services.ollama_client import OllamaClient

        client = OllamaClient(base_url="http://test:11434")
        result = await client.parse_json_response("test")

    assert result == {"forms": [], "page_requires_login": False}


@pytest.mark.asyncio
async def test_parse_json_response_no_json():
    """parse_json_response raises ValueError when no JSON can be found."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"response": "This is plain text with no JSON at all"}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.ollama_client.httpx.AsyncClient", return_value=mock_client):
        from app.services.ollama_client import OllamaClient

        client = OllamaClient(base_url="http://test:11434")

        with pytest.raises(ValueError, match="Could not parse JSON"):
            await client.parse_json_response("test")


@pytest.mark.asyncio
async def test_parse_json_response_invalid_json():
    """parse_json_response raises ValueError for malformed JSON even with braces."""
    # Contains braces but is not valid JSON
    broken_json = '{forms: [not valid json]}'

    mock_response = MagicMock()
    mock_response.json.return_value = {"response": broken_json}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.ollama_client.httpx.AsyncClient", return_value=mock_client):
        from app.services.ollama_client import OllamaClient

        client = OllamaClient(base_url="http://test:11434")

        with pytest.raises((ValueError, json.JSONDecodeError)):
            await client.parse_json_response("test")


# ---------------------------------------------------------------------------
# Tests for OllamaClient.is_available
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_is_available_true():
    """is_available returns True when Ollama responds with 200."""
    mock_response = MagicMock()
    mock_response.status_code = 200

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.ollama_client.httpx.AsyncClient", return_value=mock_client):
        from app.services.ollama_client import OllamaClient

        client = OllamaClient(base_url="http://test:11434")
        result = await client.is_available()

    assert result is True
    mock_client.get.assert_awaited_once_with("http://test:11434/api/tags")


@pytest.mark.asyncio
async def test_is_available_false_on_error():
    """is_available returns False when Ollama is unreachable."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.ollama_client.httpx.AsyncClient", return_value=mock_client):
        from app.services.ollama_client import OllamaClient

        client = OllamaClient(base_url="http://unreachable:11434")
        result = await client.is_available()

    assert result is False


@pytest.mark.asyncio
async def test_is_available_false_on_non_200():
    """is_available returns False when Ollama returns non-200 status."""
    mock_response = MagicMock()
    mock_response.status_code = 503

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.ollama_client.httpx.AsyncClient", return_value=mock_client):
        from app.services.ollama_client import OllamaClient

        client = OllamaClient(base_url="http://test:11434")
        result = await client.is_available()

    assert result is False


@pytest.mark.asyncio
async def test_default_model():
    """OllamaClient uses default model llama3.2:1b when none specified."""
    from app.services.ollama_client import OllamaClient

    client = OllamaClient(base_url="http://test:11434")
    assert client.model == "llama3.2:1b"


@pytest.mark.asyncio
async def test_custom_model():
    """OllamaClient stores a custom model name."""
    from app.services.ollama_client import OllamaClient

    client = OllamaClient(base_url="http://test:11434", model="mistral:7b")
    assert client.model == "mistral:7b"
