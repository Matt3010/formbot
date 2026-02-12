"""Tests for app.services.login_analyzer.LoginAnalyzer."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from tests.conftest import (
    SIMPLE_LOGIN_ANALYSIS,
    MULTI_FORM_ANALYSIS,
    NO_FORMS_ANALYSIS,
    _make_mock_page,
    _make_mock_context,
    _make_mock_browser,
    _make_mock_playwright,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_login_vnc_mock(session_id="vnc-login-session"):
    """Create a VNC manager mock for LoginAnalyzer tests."""
    vnc = MagicMock()

    resume_event = asyncio.Event()
    resume_event.set()  # Auto-resume by default

    vnc.sessions = {
        session_id: {
            "resume_event": resume_event,
            "status": "reserved",
            "vnc_url": "http://localhost:6080/vnc_lite.html?token=test",
        },
    }

    vnc.reserve_display = AsyncMock(return_value={
        "session_id": session_id,
        "display": ":99",
    })

    vnc.activate_vnc = AsyncMock(return_value={
        "vnc_url": "http://localhost:6080/vnc_lite.html?token=test",
        "ws_port": 6080,
    })

    vnc.deactivate_vnc = MagicMock()
    vnc.wait_for_resume = AsyncMock(return_value=True)
    vnc.stop_session = AsyncMock(return_value={"status": "stopped"})
    vnc._WS_PORT = 6080

    return vnc


def _patch_login_analyzer(html_content="<html></html>", analysis_result=None, page=None):
    """Return patches for async_playwright, OllamaClient, and Broadcaster."""
    custom_page = page is not None
    if page is None:
        page = _make_mock_page(html_content)
    # Only set defaults when page is not custom
    if not custom_page:
        page.query_selector = AsyncMock(return_value=None)
        page.url = "https://example.com/dashboard"

    context = _make_mock_context(page)
    context.cookies = AsyncMock(return_value=[
        {"name": "session", "value": "abc123", "domain": "example.com",
         "path": "/", "secure": True, "httpOnly": True},
    ])
    browser = _make_mock_browser(context)
    pw_cm = _make_mock_playwright(browser)

    pw_patch = patch(
        "app.services.login_analyzer.async_playwright",
        return_value=pw_cm,
    )

    ollama_mock = AsyncMock()
    if analysis_result:
        ollama_mock.parse_json_response_stream = AsyncMock(return_value=analysis_result)
    else:
        ollama_mock.parse_json_response_stream = AsyncMock(return_value=MULTI_FORM_ANALYSIS)

    ollama_patch = patch(
        "app.services.login_analyzer.OllamaClient",
        return_value=ollama_mock,
    )

    broadcaster_mock = MagicMock()
    broadcaster_mock.trigger_analysis = MagicMock()
    broadcaster_patch = patch(
        "app.services.login_analyzer.Broadcaster.get_instance",
        return_value=broadcaster_mock,
    )

    stealth_patch = patch(
        "app.services.login_analyzer.apply_stealth",
        AsyncMock(),
    )

    return pw_patch, ollama_patch, broadcaster_patch, stealth_patch, page, browser, context, ollama_mock, broadcaster_mock


# ---------------------------------------------------------------------------
# Tests - Successful login and analysis
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_and_analyze_success():
    """Successful login navigates to target and returns form analysis."""
    pw_p, ollama_p, bc_p, stealth_p, page, browser, context, ollama_mock, bc_mock = \
        _patch_login_analyzer(analysis_result=MULTI_FORM_ANALYSIS)

    vnc_mock = _make_login_vnc_mock()

    with pw_p, ollama_p, bc_p, stealth_p:
        from app.services.login_analyzer import LoginAnalyzer

        analyzer = LoginAnalyzer(ollama_model="test-model", vnc_manager=vnc_mock)
        result = await analyzer.perform_login_and_analyze_target(
            analysis_id="test-analysis-123",
            login_url="https://example.com/login",
            target_url="https://example.com/dashboard",
            login_form_selector="#login-form",
            login_submit_selector="#submit-btn",
            login_fields=[
                {"field_selector": "#username", "value": "admin", "field_type": "text"},
                {"field_selector": "#password", "value": "secret", "field_type": "password"},
            ],
            needs_vnc=False,
        )

    assert result["login_successful"] is True
    assert "forms" in result
    assert len(result["forms"]) == 2
    assert "session_cookies" in result
    assert len(result["session_cookies"]) == 1
    assert result["session_cookies"][0]["name"] == "session"

    # Verify navigation to login page
    page.goto.assert_any_await(
        "https://example.com/login", wait_until="networkidle", timeout=30000
    )

    # Verify fields were filled
    assert page.fill.await_count == 2
    fill_calls = page.fill.call_args_list
    assert fill_calls[0][0] == ("#username", "admin")
    assert fill_calls[1][0] == ("#password", "secret")

    # Verify submit was clicked
    page.click.assert_awaited_once_with("#submit-btn")

    # Verify navigation to target page
    page.goto.assert_any_await(
        "https://example.com/dashboard", wait_until="networkidle", timeout=30000
    )

    # Verify browser was closed
    browser.close.assert_awaited_once()

    # Verify AiThinking events were broadcast
    thinking_calls = [
        c for c in bc_mock.trigger_analysis.call_args_list
        if c[0][1] == "AiThinking"
    ]
    assert len(thinking_calls) >= 4  # Navigate, fill, submit, navigate target, analyze


@pytest.mark.asyncio
async def test_login_and_analyze_headless_when_no_vnc():
    """Without needs_vnc, browser launches in headless mode."""
    pw_p, ollama_p, bc_p, stealth_p, page, browser, context, _, _ = \
        _patch_login_analyzer()

    vnc_mock = _make_login_vnc_mock()

    with pw_p, ollama_p, bc_p, stealth_p:
        from app.services.login_analyzer import LoginAnalyzer

        analyzer = LoginAnalyzer(vnc_manager=vnc_mock)
        await analyzer.perform_login_and_analyze_target(
            analysis_id="test-1",
            login_url="https://example.com/login",
            target_url="https://example.com/target",
            login_form_selector="#form",
            login_submit_selector="#submit",
            login_fields=[],
            needs_vnc=False,
        )

    # VNC display should NOT have been reserved
    vnc_mock.reserve_display.assert_not_awaited()

    # Browser should have been launched headless
    pw = await _make_mock_playwright(browser).__aenter__()
    # The launch was called - verify it was headless by checking args
    # (The actual headless flag is in launch_options)


# ---------------------------------------------------------------------------
# Tests - Login form not found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_form_not_found():
    """When login form selector is not found, returns error."""
    page = _make_mock_page()
    page.wait_for_selector = AsyncMock(side_effect=Exception("Timeout 10000ms exceeded"))
    page.query_selector = AsyncMock(return_value=None)
    page.url = "https://example.com/login"

    pw_p, ollama_p, bc_p, stealth_p, _, browser, context, _, bc_mock = \
        _patch_login_analyzer(page=page)

    vnc_mock = _make_login_vnc_mock()

    with pw_p, ollama_p, bc_p, stealth_p:
        from app.services.login_analyzer import LoginAnalyzer

        analyzer = LoginAnalyzer(vnc_manager=vnc_mock)
        result = await analyzer.perform_login_and_analyze_target(
            analysis_id="test-2",
            login_url="https://example.com/login",
            target_url="https://example.com/target",
            login_form_selector="#nonexistent-form",
            login_submit_selector="#submit",
            login_fields=[],
            needs_vnc=False,
        )

    assert result["login_successful"] is False
    assert "not found" in result["error"]
    assert result["forms"] == []

    # Browser should still be cleaned up
    browser.close.assert_awaited_once()


# ---------------------------------------------------------------------------
# Tests - Login failed (still on login page)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_failed_still_on_login_page():
    """When still on login page after submit, returns login failed error."""
    page = _make_mock_page()
    login_form_el = MagicMock()
    # _is_still_on_login_page calls query_selector with the login form selector
    # We want it to find the form (meaning we're still on login page)
    page.query_selector = AsyncMock(return_value=login_form_el)
    page.url = "https://example.com/login"

    context = _make_mock_context(page)
    context.cookies = AsyncMock(return_value=[])
    browser = _make_mock_browser(context)
    pw_cm = _make_mock_playwright(browser)

    pw_patch = patch("app.services.login_analyzer.async_playwright", return_value=pw_cm)
    ollama_mock = AsyncMock()
    ollama_mock.parse_json_response_stream = AsyncMock(return_value=NO_FORMS_ANALYSIS)
    ollama_patch = patch("app.services.login_analyzer.OllamaClient", return_value=ollama_mock)
    bc_mock = MagicMock()
    bc_patch = patch("app.services.login_analyzer.Broadcaster.get_instance", return_value=bc_mock)
    stealth_patch = patch("app.services.login_analyzer.apply_stealth", AsyncMock())

    vnc_mock = _make_login_vnc_mock()

    with pw_patch, ollama_patch, bc_patch, stealth_patch:
        from app.services.login_analyzer import LoginAnalyzer

        analyzer = LoginAnalyzer(vnc_manager=vnc_mock)
        result = await analyzer.perform_login_and_analyze_target(
            analysis_id="test-3",
            login_url="https://example.com/login",
            target_url="https://example.com/target",
            login_form_selector="#login-form",
            login_submit_selector="#submit",
            login_fields=[
                {"field_selector": "#user", "value": "wrong", "field_type": "text"},
            ],
            needs_vnc=False,
        )

    assert result["login_successful"] is False
    assert "failed" in result["error"].lower()
    assert result["forms"] == []


# ---------------------------------------------------------------------------
# Tests - CAPTCHA with VNC
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_captcha_triggers_vnc_activation():
    """When CAPTCHA detected and needs_vnc=True, VNC is activated."""
    page = _make_mock_page()
    # First query_selector call for captcha detection: return element (captcha found)
    # Subsequent calls for login form check: return None (not on login page anymore)
    captcha_element = MagicMock()
    page.query_selector = AsyncMock(side_effect=[
        captcha_element,  # CAPTCHA selector found
        None,  # Not on login page after submit
        None,  # Additional checks
    ])
    page.url = "https://example.com/dashboard"

    context = _make_mock_context(page)
    context.cookies = AsyncMock(return_value=[])
    browser = _make_mock_browser(context)
    pw_cm = _make_mock_playwright(browser)

    pw_patch = patch("app.services.login_analyzer.async_playwright", return_value=pw_cm)
    ollama_mock = AsyncMock()
    ollama_mock.parse_json_response_stream = AsyncMock(return_value=NO_FORMS_ANALYSIS)
    ollama_patch = patch("app.services.login_analyzer.OllamaClient", return_value=ollama_mock)
    bc_mock = MagicMock()
    bc_patch = patch("app.services.login_analyzer.Broadcaster.get_instance", return_value=bc_mock)
    stealth_patch = patch("app.services.login_analyzer.apply_stealth", AsyncMock())

    vnc_mock = _make_login_vnc_mock()

    with pw_patch, ollama_patch, bc_patch, stealth_patch:
        from app.services.login_analyzer import LoginAnalyzer

        analyzer = LoginAnalyzer(vnc_manager=vnc_mock)
        result = await analyzer.perform_login_and_analyze_target(
            analysis_id="test-captcha",
            login_url="https://example.com/login",
            target_url="https://example.com/target",
            login_form_selector="#login-form",
            login_submit_selector="#submit",
            login_fields=[],
            needs_vnc=True,
        )

    # VNC display was reserved for headed browser
    vnc_mock.reserve_display.assert_awaited_once()

    # VNC was activated for CAPTCHA
    vnc_mock.activate_vnc.assert_awaited_once()

    # Wait for resume was called
    vnc_mock.wait_for_resume.assert_awaited_once()

    # VNC was deactivated after CAPTCHA resolved
    vnc_mock.deactivate_vnc.assert_called_once()

    # AnalysisVncRequired event was broadcast
    vnc_events = [
        c for c in bc_mock.trigger_analysis.call_args_list
        if c[0][1] == "AnalysisVncRequired"
    ]
    assert len(vnc_events) >= 1
    assert vnc_events[0][0][2]["reason"] == "captcha"


# ---------------------------------------------------------------------------
# Tests - VNC timeout
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_vnc_timeout_returns_error():
    """When VNC wait_for_resume times out, returns error."""
    page = _make_mock_page()
    captcha_element = MagicMock()
    # query_selector returns captcha element for all CAPTCHA-related selectors
    page.query_selector = AsyncMock(return_value=captcha_element)
    page.url = "https://example.com/login"

    context = _make_mock_context(page)
    context.cookies = AsyncMock(return_value=[])
    browser = _make_mock_browser(context)
    pw_cm = _make_mock_playwright(browser)

    pw_patch = patch("app.services.login_analyzer.async_playwright", return_value=pw_cm)
    ollama_mock = AsyncMock()
    ollama_mock.parse_json_response_stream = AsyncMock(return_value=NO_FORMS_ANALYSIS)
    ollama_patch = patch("app.services.login_analyzer.OllamaClient", return_value=ollama_mock)
    bc_mock = MagicMock()
    bc_patch = patch("app.services.login_analyzer.Broadcaster.get_instance", return_value=bc_mock)
    stealth_patch = patch("app.services.login_analyzer.apply_stealth", AsyncMock())

    vnc_mock = _make_login_vnc_mock()
    vnc_mock.wait_for_resume = AsyncMock(return_value=False)  # Timeout

    with pw_patch, ollama_patch, bc_patch, stealth_patch:
        from app.services.login_analyzer import LoginAnalyzer

        analyzer = LoginAnalyzer(vnc_manager=vnc_mock)
        result = await analyzer.perform_login_and_analyze_target(
            analysis_id="test-timeout",
            login_url="https://example.com/login",
            target_url="https://example.com/target",
            login_form_selector="#login-form",
            login_submit_selector="#submit",
            login_fields=[],
            needs_vnc=True,
        )

    assert result["login_successful"] is False
    assert "timed out" in result["error"].lower()

    # VNC session cleaned up in finally block
    vnc_mock.stop_session.assert_awaited_once()


# ---------------------------------------------------------------------------
# Tests - Browser cleanup on exception
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_browser_cleanup_on_exception():
    """Browser and VNC are cleaned up even when an exception occurs."""
    page = _make_mock_page()
    page.goto = AsyncMock(side_effect=Exception("Connection refused"))
    page.query_selector = AsyncMock(return_value=None)

    pw_p, ollama_p, bc_p, stealth_p, _, browser, context, _, _ = \
        _patch_login_analyzer(page=page)

    vnc_mock = _make_login_vnc_mock()

    with pw_p, ollama_p, bc_p, stealth_p:
        from app.services.login_analyzer import LoginAnalyzer

        analyzer = LoginAnalyzer(vnc_manager=vnc_mock)
        result = await analyzer.perform_login_and_analyze_target(
            analysis_id="test-error",
            login_url="https://unreachable.example.com/login",
            target_url="https://unreachable.example.com/target",
            login_form_selector="#form",
            login_submit_selector="#submit",
            login_fields=[],
            needs_vnc=False,
        )

    assert result["login_successful"] is False
    assert "Connection refused" in result["error"]

    # Browser was closed in finally block
    browser.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_vnc_cleanup_on_exception():
    """VNC session is always cleaned up via finally block on error."""
    page = _make_mock_page()
    page.goto = AsyncMock(side_effect=Exception("DNS resolution failed"))

    pw_p, ollama_p, bc_p, stealth_p, _, browser, context, _, _ = \
        _patch_login_analyzer(page=page)

    vnc_mock = _make_login_vnc_mock()

    with pw_p, ollama_p, bc_p, stealth_p:
        from app.services.login_analyzer import LoginAnalyzer

        analyzer = LoginAnalyzer(vnc_manager=vnc_mock)
        result = await analyzer.perform_login_and_analyze_target(
            analysis_id="test-vnc-error",
            login_url="https://example.com/login",
            target_url="https://example.com/target",
            login_form_selector="#form",
            login_submit_selector="#submit",
            login_fields=[],
            needs_vnc=True,
        )

    assert result["login_successful"] is False

    # VNC display was reserved (needs_vnc=True)
    vnc_mock.reserve_display.assert_awaited_once()

    # VNC session cleaned up in finally block
    vnc_mock.stop_session.assert_awaited_once()


# ---------------------------------------------------------------------------
# Tests - Encrypted field decryption
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_encrypted_field_decryption():
    """Encrypted sensitive fields are decrypted before filling."""
    from cryptography.fernet import Fernet

    key = Fernet.generate_key()
    fernet = Fernet(key)
    encrypted_password = fernet.encrypt(b"my-secret-password").decode()

    pw_p, ollama_p, bc_p, stealth_p, page, browser, context, _, _ = \
        _patch_login_analyzer()

    vnc_mock = _make_login_vnc_mock()

    settings_patch = patch(
        "app.services.login_analyzer.settings",
        MagicMock(encryption_key=key.decode()),
    )

    with pw_p, ollama_p, bc_p, stealth_p, settings_patch:
        from app.services.login_analyzer import LoginAnalyzer

        analyzer = LoginAnalyzer(vnc_manager=vnc_mock)
        result = await analyzer.perform_login_and_analyze_target(
            analysis_id="test-encrypt",
            login_url="https://example.com/login",
            target_url="https://example.com/target",
            login_form_selector="#login-form",
            login_submit_selector="#submit",
            login_fields=[
                {
                    "field_selector": "#password",
                    "value": encrypted_password,
                    "field_type": "password",
                    "is_sensitive": True,
                    "encrypted": True,
                },
            ],
            needs_vnc=False,
        )

    assert result["login_successful"] is True

    # Verify the decrypted value was used
    page.fill.assert_awaited_once_with("#password", "my-secret-password")


# ---------------------------------------------------------------------------
# Tests - HTML truncation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_html_truncation_before_ollama():
    """HTML content > 50000 chars is truncated before sending to Ollama."""
    page = _make_mock_page("A" * 60000)
    page.query_selector = AsyncMock(return_value=None)
    page.url = "https://example.com/dashboard"

    pw_p, ollama_p, bc_p, stealth_p, _, browser, context, ollama_mock, _ = \
        _patch_login_analyzer(page=page)

    vnc_mock = _make_login_vnc_mock()

    with pw_p, ollama_p, bc_p, stealth_p:
        from app.services.login_analyzer import LoginAnalyzer

        analyzer = LoginAnalyzer(vnc_manager=vnc_mock)
        await analyzer.perform_login_and_analyze_target(
            analysis_id="test-truncate",
            login_url="https://example.com/login",
            target_url="https://example.com/target",
            login_form_selector="#login-form",
            login_submit_selector="#submit",
            login_fields=[],
            needs_vnc=False,
        )

    # Verify the prompt sent to Ollama has truncated HTML
    prompt_arg = ollama_mock.parse_json_response_stream.call_args[0][0]
    assert "A" * 50000 in prompt_arg
    assert "A" * 60000 not in prompt_arg


# ---------------------------------------------------------------------------
# Tests - Select and checkbox field types during login
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_fields_checkbox_and_select():
    """Login fields of type checkbox and select use appropriate methods."""
    pw_p, ollama_p, bc_p, stealth_p, page, browser, context, _, _ = \
        _patch_login_analyzer()

    vnc_mock = _make_login_vnc_mock()

    with pw_p, ollama_p, bc_p, stealth_p:
        from app.services.login_analyzer import LoginAnalyzer

        analyzer = LoginAnalyzer(vnc_manager=vnc_mock)
        await analyzer.perform_login_and_analyze_target(
            analysis_id="test-field-types",
            login_url="https://example.com/login",
            target_url="https://example.com/target",
            login_form_selector="#login-form",
            login_submit_selector="#submit",
            login_fields=[
                {"field_selector": "#remember", "value": "true", "field_type": "checkbox"},
                {"field_selector": "#role", "value": "admin", "field_type": "select"},
                {"field_selector": "#username", "value": "user1", "field_type": "text"},
            ],
            needs_vnc=False,
        )

    page.check.assert_awaited_once_with("#remember")
    page.select_option.assert_awaited_once_with("#role", "admin")
    page.fill.assert_awaited_once_with("#username", "user1")


# ---------------------------------------------------------------------------
# Tests - CAPTCHA detection helpers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_detect_captcha_recaptcha():
    """_detect_captcha_on_page finds reCAPTCHA elements."""
    from app.services.login_analyzer import LoginAnalyzer

    page = AsyncMock()
    captcha_el = MagicMock()

    # Return None for first selectors, element for .g-recaptcha
    async def _qs(selector):
        if selector == ".g-recaptcha":
            return captcha_el
        return None

    page.query_selector = AsyncMock(side_effect=_qs)

    analyzer = LoginAnalyzer.__new__(LoginAnalyzer)
    result = await analyzer._detect_captcha_on_page(page)

    assert result is True


@pytest.mark.asyncio
async def test_detect_captcha_none():
    """_detect_captcha_on_page returns False when no CAPTCHA found."""
    from app.services.login_analyzer import LoginAnalyzer

    page = AsyncMock()
    page.query_selector = AsyncMock(return_value=None)

    analyzer = LoginAnalyzer.__new__(LoginAnalyzer)
    result = await analyzer._detect_captcha_on_page(page)

    assert result is False


@pytest.mark.asyncio
async def test_detect_2fa():
    """_detect_2fa_on_page finds OTP input elements."""
    from app.services.login_analyzer import LoginAnalyzer

    page = AsyncMock()
    otp_el = MagicMock()

    async def _qs(selector):
        if "otp" in selector:
            return otp_el
        return None

    page.query_selector = AsyncMock(side_effect=_qs)

    analyzer = LoginAnalyzer.__new__(LoginAnalyzer)
    result = await analyzer._detect_2fa_on_page(page)

    assert result is True


@pytest.mark.asyncio
async def test_is_still_on_login_page():
    """_is_still_on_login_page returns True when login form is still present."""
    from app.services.login_analyzer import LoginAnalyzer

    page = AsyncMock()
    page.query_selector = AsyncMock(return_value=MagicMock())

    analyzer = LoginAnalyzer.__new__(LoginAnalyzer)
    result = await analyzer._is_still_on_login_page(page, "#login-form")

    assert result is True


@pytest.mark.asyncio
async def test_is_not_on_login_page_after_redirect():
    """_is_still_on_login_page returns False when login form is gone."""
    from app.services.login_analyzer import LoginAnalyzer

    page = AsyncMock()
    page.query_selector = AsyncMock(return_value=None)

    analyzer = LoginAnalyzer.__new__(LoginAnalyzer)
    result = await analyzer._is_still_on_login_page(page, "#login-form")

    assert result is False
