import os
import time
import json
from typing import Optional
from playwright.async_api import async_playwright
from cryptography.fernet import Fernet
from app.config import settings
from app.services.ollama_client import OllamaClient
from app.services.stealth import apply_stealth
from app.services.vnc_manager import VNCManager
from app.services.broadcaster import Broadcaster
from app.prompts.form_analysis import FORM_ANALYSIS_PROMPT


class LoginAnalyzer:
    """Performs login on a page and then analyzes the target page for forms.

    Combines FormAnalyzer's Ollama analysis with VNC support for CAPTCHA/2FA
    during the login phase.
    """

    def __init__(self, ollama_model: str = None, vnc_manager: VNCManager = None):
        self.ollama = OllamaClient(model=ollama_model)
        self.vnc_manager = vnc_manager or VNCManager()
        self.broadcaster = Broadcaster.get_instance()

    async def perform_login_and_analyze_target(
        self,
        analysis_id: str,
        login_url: str,
        target_url: str,
        login_form_selector: str,
        login_submit_selector: str,
        login_fields: list[dict],
        needs_vnc: bool = False,
    ) -> dict:
        """Login to site and analyze the target page.

        Args:
            analysis_id: UUID for WebSocket broadcasting
            login_url: URL of the login page
            target_url: URL of the target page (behind login)
            login_form_selector: CSS selector for the login form
            login_submit_selector: CSS selector for the login submit button
            login_fields: List of dicts with field_selector, value, is_sensitive, encrypted
            needs_vnc: Whether to use headed browser for VNC (CAPTCHA/OAuth)

        Returns:
            dict with forms, session_cookies, login_successful
        """
        vnc_session_id = None
        vnc_display = None
        browser = None

        try:
            # Phase 1: Launch browser (headed if VNC needed)
            if needs_vnc:
                reserved = await self.vnc_manager.reserve_display(analysis_id)
                vnc_session_id = reserved["session_id"]
                vnc_display = reserved["display"]

            pw = await async_playwright().__aenter__()
            launch_args = ["--no-sandbox", "--disable-setuid-sandbox"]

            if needs_vnc and vnc_display:
                launch_env = {**os.environ, "DISPLAY": vnc_display}
                launch_options = {"headless": False, "args": launch_args, "env": launch_env}
            else:
                launch_options = {"headless": True, "args": launch_args}

            browser = await pw.chromium.launch(**launch_options)
            context = await browser.new_context()
            await apply_stealth(context)
            page = await context.new_page()

            # Phase 2: Navigate to login page
            self.broadcaster.trigger_analysis(analysis_id, "AiThinking", {
                "token": "Navigating to login page...\n",
                "done": False,
            })

            await page.goto(login_url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(1000)

            # Wait for login form
            try:
                await page.wait_for_selector(login_form_selector, timeout=10000)
            except Exception:
                return {
                    "forms": [],
                    "login_successful": False,
                    "error": f"Login form selector '{login_form_selector}' not found on {login_url}",
                }

            # Phase 3: Fill login fields
            self.broadcaster.trigger_analysis(analysis_id, "AiThinking", {
                "token": "Filling login credentials...\n",
                "done": False,
            })

            for field in login_fields:
                value = field["value"]

                # Decrypt sensitive values
                if field.get("encrypted") and settings.encryption_key:
                    try:
                        fernet = Fernet(settings.encryption_key.encode())
                        value = fernet.decrypt(value.encode()).decode()
                    except Exception:
                        pass

                try:
                    field_type = field.get("field_type", "text")
                    selector = field["field_selector"]

                    if field_type == "checkbox":
                        if value.lower() in ("true", "1", "yes", "on"):
                            await page.check(selector)
                        else:
                            await page.uncheck(selector)
                    elif field_type == "select":
                        await page.select_option(selector, value)
                    else:
                        await page.fill(selector, value)

                    await page.wait_for_timeout(200)
                except Exception as e:
                    self.broadcaster.trigger_analysis(analysis_id, "AiThinking", {
                        "token": f"Warning: Could not fill field {field.get('field_selector')}: {e}\n",
                        "done": False,
                    })

            # Phase 4: Handle CAPTCHA via VNC if needed
            if needs_vnc and vnc_session_id:
                # Check if there's a CAPTCHA on the page before submitting
                captcha_detected = await self._detect_captcha_on_page(page)

                if captcha_detected:
                    self.broadcaster.trigger_analysis(analysis_id, "AiThinking", {
                        "token": "CAPTCHA detected! Opening VNC viewer for manual intervention...\n",
                        "done": False,
                    })

                    vnc_result = await self.vnc_manager.activate_vnc(vnc_session_id)

                    # Broadcast VNC required event
                    self.broadcaster.trigger_analysis(analysis_id, "AnalysisVncRequired", {
                        "vnc_session_id": vnc_session_id,
                        "vnc_url": vnc_result.get("vnc_url"),
                        "ws_port": vnc_result.get("ws_port"),
                        "reason": "captcha",
                    })

                    # Wait for user to solve CAPTCHA and resume
                    resumed = await self.vnc_manager.wait_for_resume(vnc_session_id, timeout=3600)

                    if not resumed:
                        return {
                            "forms": [],
                            "login_successful": False,
                            "error": "VNC session timed out waiting for CAPTCHA resolution",
                        }

                    self.vnc_manager.deactivate_vnc(vnc_session_id)

                    self.broadcaster.trigger_analysis(analysis_id, "AiThinking", {
                        "token": "CAPTCHA resolved! Submitting login...\n",
                        "done": False,
                    })

            # Phase 5: Submit login
            self.broadcaster.trigger_analysis(analysis_id, "AiThinking", {
                "token": "Submitting login form...\n",
                "done": False,
            })

            await page.click(login_submit_selector)

            try:
                await page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            await page.wait_for_timeout(2000)

            # Phase 5b: Check for 2FA
            current_url = page.url
            two_fa_detected = await self._detect_2fa_on_page(page)

            if two_fa_detected and needs_vnc and vnc_session_id:
                self.broadcaster.trigger_analysis(analysis_id, "AiThinking", {
                    "token": "2FA detected! Opening VNC viewer for manual intervention...\n",
                    "done": False,
                })

                # Activate VNC if not already active
                session = self.vnc_manager.sessions.get(vnc_session_id)
                if session and session.get("status") != "active":
                    vnc_result = await self.vnc_manager.activate_vnc(vnc_session_id)
                else:
                    vnc_result = {"vnc_url": session.get("vnc_url"), "ws_port": self.vnc_manager._WS_PORT}

                self.broadcaster.trigger_analysis(analysis_id, "AnalysisVncRequired", {
                    "vnc_session_id": vnc_session_id,
                    "vnc_url": vnc_result.get("vnc_url"),
                    "ws_port": vnc_result.get("ws_port"),
                    "reason": "2fa",
                })

                # Reset resume event for second pause
                session = self.vnc_manager.sessions.get(vnc_session_id)
                if session:
                    import asyncio
                    session["resume_event"] = asyncio.Event()

                resumed = await self.vnc_manager.wait_for_resume(vnc_session_id, timeout=3600)

                if not resumed:
                    return {
                        "forms": [],
                        "login_successful": False,
                        "error": "VNC session timed out waiting for 2FA completion",
                    }

                self.vnc_manager.deactivate_vnc(vnc_session_id)
                await page.wait_for_timeout(2000)

            # Phase 6: Verify login succeeded (check if still on login page)
            post_login_url = page.url
            still_on_login = await self._is_still_on_login_page(page, login_form_selector)

            if still_on_login:
                return {
                    "forms": [],
                    "login_successful": False,
                    "error": "Login appears to have failed - still on login page after submit",
                }

            self.broadcaster.trigger_analysis(analysis_id, "AiThinking", {
                "token": "Login successful! Navigating to target page...\n",
                "done": False,
            })

            # Phase 7: Navigate to target page
            await page.goto(target_url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(2000)

            # Phase 8: Extract HTML and analyze with Ollama
            html_content = await page.content()
            if len(html_content) > 50000:
                html_content = html_content[:50000]

            self.broadcaster.trigger_analysis(analysis_id, "AiThinking", {
                "token": "Analyzing target page with AI...\n",
                "done": False,
            })

            prompt = FORM_ANALYSIS_PROMPT.replace("{html_content}", html_content)

            # Stream AI thinking tokens
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

            result = await self.ollama.parse_json_response_stream(prompt, on_token=on_token)

            # Flush remaining buffer
            if token_buffer:
                self.broadcaster.trigger_analysis(analysis_id, "AiThinking", {
                    "token": token_buffer,
                    "done": False,
                })

            # Signal AI thinking done
            self.broadcaster.trigger_analysis(analysis_id, "AiThinking", {
                "token": "",
                "done": True,
            })

            # Phase 9: Extract session cookies for potential reuse
            cookies = await context.cookies()
            session_cookies = [
                {"name": c["name"], "value": c["value"], "domain": c["domain"],
                 "path": c["path"], "secure": c.get("secure", False),
                 "httpOnly": c.get("httpOnly", False)}
                for c in cookies
            ]

            result["login_successful"] = True
            result["session_cookies"] = session_cookies

            return result

        except Exception as e:
            self.broadcaster.trigger_analysis(analysis_id, "AiThinking", {
                "token": f"\nError: {str(e)}",
                "done": True,
            })
            return {
                "forms": [],
                "login_successful": False,
                "error": str(e),
            }
        finally:
            if browser:
                await browser.close()
            try:
                await pw.__aexit__(None, None, None)
            except Exception:
                pass
            if vnc_session_id:
                try:
                    await self.vnc_manager.stop_session(vnc_session_id)
                except Exception:
                    pass

    async def _detect_captcha_on_page(self, page) -> bool:
        """Check if the current page has a CAPTCHA element."""
        captcha_selectors = [
            "iframe[src*='recaptcha']",
            "iframe[src*='hcaptcha']",
            ".g-recaptcha",
            ".h-captcha",
            "[data-sitekey]",
            "iframe[src*='turnstile']",
            ".cf-turnstile",
        ]
        for selector in captcha_selectors:
            try:
                el = await page.query_selector(selector)
                if el:
                    return True
            except Exception:
                pass
        return False

    async def _detect_2fa_on_page(self, page) -> bool:
        """Check if the current page appears to be a 2FA/OTP page."""
        indicators = [
            "input[name*='otp']",
            "input[name*='2fa']",
            "input[name*='totp']",
            "input[name*='verification']",
            "input[name*='code']",
            "input[autocomplete='one-time-code']",
        ]
        for selector in indicators:
            try:
                el = await page.query_selector(selector)
                if el:
                    return True
            except Exception:
                pass
        return False

    async def _is_still_on_login_page(self, page, login_form_selector: str) -> bool:
        """Check if we're still on the login page after submit."""
        try:
            el = await page.query_selector(login_form_selector)
            return el is not None
        except Exception:
            return False
