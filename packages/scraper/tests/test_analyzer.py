"""Tests for app.services.form_analyzer.FormAnalyzer."""

import copy
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from tests.conftest import (
    SIMPLE_LOGIN_HTML,
    MULTI_FORM_HTML,
    CAPTCHA_FORM_HTML,
    TWO_FACTOR_HTML,
    NO_FORMS_HTML,
    SIMPLE_LOGIN_ANALYSIS,
    MULTI_FORM_ANALYSIS,
    CAPTCHA_ANALYSIS,
    TWO_FACTOR_ANALYSIS,
    NO_FORMS_ANALYSIS,
    _make_mock_page,
    _make_mock_context,
    _make_mock_browser,
    _make_mock_playwright,
)


# ---------------------------------------------------------------------------
# Helper to patch async_playwright + OllamaClient in one go
# ---------------------------------------------------------------------------

def _patch_analyzer(html: str, analysis_result: dict, has_password: bool = False):
    """Return a pair of context-manager patches for async_playwright and OllamaClient.

    The Playwright mock will return ``html`` from ``page.content()``.
    The OllamaClient mock will return ``analysis_result`` from ``parse_json_response``.
    If *has_password* is True the mock page will report a password field so that
    the login heuristic does not override ``page_requires_login``.
    """
    page = _make_mock_page(html, has_password=has_password)
    context = _make_mock_context(page)
    browser = _make_mock_browser(context)
    pw_cm = _make_mock_playwright(browser)

    pw_patch = patch(
        "app.services.form_analyzer.async_playwright",
        return_value=pw_cm,
    )

    ollama_mock = AsyncMock()
    ollama_mock.parse_json_response = AsyncMock(return_value=copy.deepcopy(analysis_result))

    ollama_patch = patch(
        "app.services.form_analyzer.OllamaClient",
        return_value=ollama_mock,
    )

    return pw_patch, ollama_patch, page, browser, ollama_mock


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analyze_simple_login_form():
    """analyze_url returns the expected login form analysis."""
    pw_patch, ollama_patch, page, browser, ollama_mock = _patch_analyzer(
        SIMPLE_LOGIN_HTML, SIMPLE_LOGIN_ANALYSIS, has_password=True
    )

    with pw_patch, ollama_patch:
        from app.services.form_analyzer import FormAnalyzer

        analyzer = FormAnalyzer(ollama_model="test-model")
        result = await analyzer.analyze_url("https://example.com/login")

    # Assertions on result structure
    assert "forms" in result
    assert len(result["forms"]) == 1
    form = result["forms"][0]
    assert form["form_type"] == "login"
    assert form["form_selector"] == "#login-form"
    assert form["captcha_detected"] is False
    assert len(form["fields"]) == 2
    assert result["page_requires_login"] is True
    assert result["two_factor_detected"] is False

    # Verify page.goto was called with the URL
    page.goto.assert_awaited_once()
    call_args = page.goto.call_args
    assert call_args[0][0] == "https://example.com/login"

    # Verify page.content was called
    page.content.assert_awaited_once()

    # Verify the Ollama client received a prompt containing the HTML
    ollama_mock.parse_json_response.assert_awaited_once()
    prompt_arg = ollama_mock.parse_json_response.call_args[0][0]
    assert "login-form" in prompt_arg  # HTML was substituted into the prompt

    # Verify browser was closed
    browser.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_analyze_multiple_forms():
    """analyze_url correctly relays multiple forms from the LLM analysis."""
    pw_patch, ollama_patch, page, browser, ollama_mock = _patch_analyzer(
        MULTI_FORM_HTML, MULTI_FORM_ANALYSIS
    )

    with pw_patch, ollama_patch:
        from app.services.form_analyzer import FormAnalyzer

        analyzer = FormAnalyzer()
        result = await analyzer.analyze_url("https://example.com/multi")

    assert len(result["forms"]) == 2
    form_types = [f["form_type"] for f in result["forms"]]
    assert "search" in form_types
    assert "other" in form_types
    assert result["page_requires_login"] is False


@pytest.mark.asyncio
async def test_analyze_captcha_detected():
    """analyze_url returns captcha_detected=True when LLM detects a CAPTCHA."""
    pw_patch, ollama_patch, *_ = _patch_analyzer(
        CAPTCHA_FORM_HTML, CAPTCHA_ANALYSIS
    )

    with pw_patch, ollama_patch:
        from app.services.form_analyzer import FormAnalyzer

        analyzer = FormAnalyzer()
        result = await analyzer.analyze_url("https://example.com/captcha")

    assert len(result["forms"]) == 1
    assert result["forms"][0]["captcha_detected"] is True
    assert result["forms"][0]["captcha_type"] == "recaptcha_v2"


@pytest.mark.asyncio
async def test_analyze_2fa_detected():
    """analyze_url returns two_factor_detected=True when LLM detects 2FA."""
    pw_patch, ollama_patch, *_ = _patch_analyzer(
        TWO_FACTOR_HTML, TWO_FACTOR_ANALYSIS
    )

    with pw_patch, ollama_patch:
        from app.services.form_analyzer import FormAnalyzer

        analyzer = FormAnalyzer()
        result = await analyzer.analyze_url("https://example.com/2fa")

    assert result["two_factor_detected"] is True
    assert len(result["forms"]) == 1
    assert result["forms"][0]["form_selector"] == "#otp-form"


@pytest.mark.asyncio
async def test_analyze_no_forms():
    """analyze_url returns empty forms list when page has no forms."""
    pw_patch, ollama_patch, *_ = _patch_analyzer(
        NO_FORMS_HTML, NO_FORMS_ANALYSIS
    )

    with pw_patch, ollama_patch:
        from app.services.form_analyzer import FormAnalyzer

        analyzer = FormAnalyzer()
        result = await analyzer.analyze_url("https://example.com/plain")

    assert result["forms"] == []
    assert result["page_requires_login"] is False


@pytest.mark.asyncio
async def test_analyze_navigation_error():
    """When Playwright fails to navigate, analyze_url returns an error dict."""
    page = _make_mock_page()
    page.goto = AsyncMock(side_effect=Exception("net::ERR_NAME_NOT_RESOLVED"))
    context = _make_mock_context(page)
    browser = _make_mock_browser(context)
    pw_cm = _make_mock_playwright(browser)

    pw_patch = patch(
        "app.services.form_analyzer.async_playwright",
        return_value=pw_cm,
    )

    ollama_mock = AsyncMock()
    ollama_patch = patch(
        "app.services.form_analyzer.OllamaClient",
        return_value=ollama_mock,
    )

    with pw_patch, ollama_patch:
        from app.services.form_analyzer import FormAnalyzer

        analyzer = FormAnalyzer()
        result = await analyzer.analyze_url("https://doesnotexist.example")

    assert result["forms"] == []
    assert "error" in result
    assert "ERR_NAME_NOT_RESOLVED" in result["error"]
    # Ollama should NOT have been called since navigation failed first
    ollama_mock.parse_json_response.assert_not_awaited()
    # Browser close is in the finally block, so it should still be called
    browser.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_analyze_ollama_invalid_json():
    """When Ollama returns un-parseable JSON, analyze_url returns an error."""
    page = _make_mock_page(SIMPLE_LOGIN_HTML)
    context = _make_mock_context(page)
    browser = _make_mock_browser(context)
    pw_cm = _make_mock_playwright(browser)

    pw_patch = patch(
        "app.services.form_analyzer.async_playwright",
        return_value=pw_cm,
    )

    ollama_mock = AsyncMock()
    ollama_mock.parse_json_response = AsyncMock(
        side_effect=ValueError("Could not parse JSON from Ollama response: garbage")
    )
    ollama_patch = patch(
        "app.services.form_analyzer.OllamaClient",
        return_value=ollama_mock,
    )

    with pw_patch, ollama_patch:
        from app.services.form_analyzer import FormAnalyzer

        analyzer = FormAnalyzer()
        result = await analyzer.analyze_url("https://example.com/login")

    assert result["forms"] == []
    assert "error" in result
    assert "Could not parse JSON" in result["error"]
    browser.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_analyze_html_truncation():
    """HTML content longer than 50000 chars is truncated before sending to Ollama."""
    long_html = "A" * 60000
    page = _make_mock_page(long_html)
    context = _make_mock_context(page)
    browser = _make_mock_browser(context)
    pw_cm = _make_mock_playwright(browser)

    pw_patch = patch(
        "app.services.form_analyzer.async_playwright",
        return_value=pw_cm,
    )

    ollama_mock = AsyncMock()
    ollama_mock.parse_json_response = AsyncMock(return_value=NO_FORMS_ANALYSIS)
    ollama_patch = patch(
        "app.services.form_analyzer.OllamaClient",
        return_value=ollama_mock,
    )

    with pw_patch, ollama_patch:
        from app.services.form_analyzer import FormAnalyzer

        analyzer = FormAnalyzer()
        await analyzer.analyze_url("https://example.com/long")

    # The prompt should contain at most 50000 chars of HTML
    prompt_arg = ollama_mock.parse_json_response.call_args[0][0]
    # The original "A"*60000 should have been truncated to "A"*50000
    assert "A" * 50000 in prompt_arg
    assert "A" * 60000 not in prompt_arg


@pytest.mark.asyncio
async def test_analyze_stealth_applied_by_default():
    """Stealth mode is applied when stealth=True (the default)."""
    page = _make_mock_page(SIMPLE_LOGIN_HTML)
    context = _make_mock_context(page)
    browser = _make_mock_browser(context)
    pw_cm = _make_mock_playwright(browser)

    pw_patch = patch(
        "app.services.form_analyzer.async_playwright",
        return_value=pw_cm,
    )
    ollama_mock = AsyncMock()
    ollama_mock.parse_json_response = AsyncMock(return_value=SIMPLE_LOGIN_ANALYSIS)
    ollama_patch = patch(
        "app.services.form_analyzer.OllamaClient",
        return_value=ollama_mock,
    )
    stealth_mock = AsyncMock()
    stealth_patch = patch(
        "app.services.form_analyzer.apply_stealth",
        stealth_mock,
    )

    with pw_patch, ollama_patch, stealth_patch:
        from app.services.form_analyzer import FormAnalyzer

        analyzer = FormAnalyzer()
        await analyzer.analyze_url("https://example.com/login", stealth=True)

    stealth_mock.assert_awaited_once_with(context)


@pytest.mark.asyncio
async def test_analyze_stealth_skipped():
    """Stealth mode is NOT applied when stealth=False."""
    page = _make_mock_page(SIMPLE_LOGIN_HTML)
    context = _make_mock_context(page)
    browser = _make_mock_browser(context)
    pw_cm = _make_mock_playwright(browser)

    pw_patch = patch(
        "app.services.form_analyzer.async_playwright",
        return_value=pw_cm,
    )
    ollama_mock = AsyncMock()
    ollama_mock.parse_json_response = AsyncMock(return_value=SIMPLE_LOGIN_ANALYSIS)
    ollama_patch = patch(
        "app.services.form_analyzer.OllamaClient",
        return_value=ollama_mock,
    )
    stealth_mock = AsyncMock()
    stealth_patch = patch(
        "app.services.form_analyzer.apply_stealth",
        stealth_mock,
    )

    with pw_patch, ollama_patch, stealth_patch:
        from app.services.form_analyzer import FormAnalyzer

        analyzer = FormAnalyzer()
        await analyzer.analyze_url("https://example.com/login", stealth=False)

    stealth_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_analyze_dynamic_returns_result():
    """analyze_dynamic navigates, extracts HTML, and returns LLM analysis."""
    pw_patch, ollama_patch, page, browser, ollama_mock = _patch_analyzer(
        SIMPLE_LOGIN_HTML, SIMPLE_LOGIN_ANALYSIS
    )

    with pw_patch, ollama_patch:
        from app.services.form_analyzer import FormAnalyzer

        analyzer = FormAnalyzer()
        result = await analyzer.analyze_dynamic(
            "https://example.com/login",
            previous_state={"forms": []},
            interaction="clicked next button",
        )

    assert "forms" in result
    assert len(result["forms"]) == 1
    page.goto.assert_awaited_once()
    browser.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_analyze_dynamic_error():
    """analyze_dynamic returns error dict when navigation fails."""
    page = _make_mock_page()
    page.goto = AsyncMock(side_effect=Exception("Timeout exceeded"))
    context = _make_mock_context(page)
    browser = _make_mock_browser(context)
    pw_cm = _make_mock_playwright(browser)

    pw_patch = patch(
        "app.services.form_analyzer.async_playwright",
        return_value=pw_cm,
    )
    ollama_mock = AsyncMock()
    ollama_patch = patch(
        "app.services.form_analyzer.OllamaClient",
        return_value=ollama_mock,
    )

    with pw_patch, ollama_patch:
        from app.services.form_analyzer import FormAnalyzer

        analyzer = FormAnalyzer()
        result = await analyzer.analyze_dynamic(
            "https://example.com/broken", {}, ""
        )

    assert result["forms"] == []
    assert "error" in result
    assert "Timeout" in result["error"]
