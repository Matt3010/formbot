"""Shared fixtures for FormBot scraper tests."""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Sample HTML fixtures
# ---------------------------------------------------------------------------

SIMPLE_LOGIN_HTML = """
<html>
<body>
<form id="login-form" action="/login" method="post">
    <input id="username" name="username" type="text" required />
    <input id="password" name="password" type="password" required />
    <button id="submit-btn" type="submit">Log in</button>
</form>
</body>
</html>
"""

MULTI_FORM_HTML = """
<html>
<body>
<form id="search-form" action="/search" method="get">
    <input id="q" name="q" type="text" />
    <button type="submit">Search</button>
</form>
<form id="newsletter-form" action="/subscribe" method="post">
    <input id="email" name="email" type="email" required />
    <button type="submit">Subscribe</button>
</form>
</body>
</html>
"""

CAPTCHA_FORM_HTML = """
<html>
<body>
<form id="captcha-form" action="/submit" method="post">
    <input id="name" name="name" type="text" />
    <div class="g-recaptcha" data-sitekey="xxxx"></div>
    <button type="submit">Submit</button>
</form>
</body>
</html>
"""

TWO_FACTOR_HTML = """
<html>
<body>
<form id="otp-form" action="/verify" method="post">
    <label>Enter your 6-digit code</label>
    <input id="otp" name="otp" type="text" maxlength="6" />
    <button type="submit">Verify</button>
</form>
</body>
</html>
"""

NO_FORMS_HTML = """
<html>
<body>
<h1>Welcome</h1>
<p>No forms here.</p>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Mock Playwright helpers
# ---------------------------------------------------------------------------

def _make_mock_page(html_content: str = SIMPLE_LOGIN_HTML, has_password: bool = False) -> AsyncMock:
    """Return an AsyncMock that behaves like a Playwright Page.

    If *has_password* is True, ``page.locator(selector).count()`` returns 1 for
    password-related selectors so that ``_detect_login_heuristic`` sees a login page.
    """
    page = AsyncMock()
    page.goto = AsyncMock()
    page.wait_for_timeout = AsyncMock()
    page.wait_for_load_state = AsyncMock()
    page.content = AsyncMock(return_value=html_content)
    page.screenshot = AsyncMock()
    page.fill = AsyncMock()
    page.click = AsyncMock()
    page.check = AsyncMock()
    page.uncheck = AsyncMock()
    page.select_option = AsyncMock()
    page.set_input_files = AsyncMock()
    page.eval_on_selector = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.query_selector = AsyncMock(return_value=MagicMock())  # non-None element
    page.add_init_script = AsyncMock()

    # Mock locator().count() for _detect_login_heuristic
    locator_mock = AsyncMock()
    locator_mock.count = AsyncMock(return_value=1 if has_password else 0)
    page.locator = MagicMock(return_value=locator_mock)

    return page


def _make_mock_context(page: AsyncMock) -> AsyncMock:
    """Return an AsyncMock that behaves like a Playwright BrowserContext."""
    context = AsyncMock()
    context.new_page = AsyncMock(return_value=page)
    context.pages = []
    context.on = MagicMock()
    return context


def _make_mock_browser(context: AsyncMock) -> AsyncMock:
    """Return an AsyncMock that behaves like a Playwright Browser."""
    browser = AsyncMock()
    browser.new_context = AsyncMock(return_value=context)
    browser.close = AsyncMock()
    return browser


def _make_mock_playwright(browser: AsyncMock) -> AsyncMock:
    """Return an AsyncMock that mimics the async_playwright() context manager.

    Usage in production code:
        async with async_playwright() as p:
            browser = await p.chromium.launch(...)

    The returned mock supports ``async with`` via __aenter__/__aexit__
    and exposes ``p.chromium.launch`` as an AsyncMock that returns *browser*.
    """
    pw = AsyncMock()
    pw.chromium.launch = AsyncMock(return_value=browser)

    # Make it work as an async context manager
    pw_cm = AsyncMock()
    pw_cm.__aenter__ = AsyncMock(return_value=pw)
    pw_cm.__aexit__ = AsyncMock(return_value=False)
    return pw_cm


@pytest.fixture
def mock_page():
    """A mock Playwright page pre-configured with simple login HTML."""
    return _make_mock_page(SIMPLE_LOGIN_HTML)


@pytest.fixture
def mock_context(mock_page):
    return _make_mock_context(mock_page)


@pytest.fixture
def mock_browser(mock_context):
    return _make_mock_browser(mock_context)


@pytest.fixture
def mock_playwright(mock_browser):
    return _make_mock_playwright(mock_browser)


# ---------------------------------------------------------------------------
# Mock database session
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    """Return a MagicMock that behaves like a SQLAlchemy Session."""
    db = MagicMock()
    db.add = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock()
    db.close = MagicMock()
    # query().filter().first() and query().filter().order_by().all()
    # are set up per-test because return values vary.
    return db


# ---------------------------------------------------------------------------
# Model factory helpers
# ---------------------------------------------------------------------------

def make_task(**overrides):
    """Create a Task-like MagicMock with sensible defaults."""
    defaults = {
        "id": uuid.uuid4(),
        "user_id": 1,
        "name": "Test Task",
        "target_url": "https://example.com/login",
        "schedule_type": "once",
        "schedule_cron": None,
        "schedule_at": None,
        "status": "draft",
        "is_dry_run": False,
        "max_retries": 3,
        "max_parallel": 1,
        "stealth_enabled": True,
        "custom_user_agent": None,
        "action_delay_ms": 500,
        "cloned_from": None,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    defaults.update(overrides)
    obj = MagicMock()
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def make_form_definition(**overrides):
    """Create a FormDefinition-like MagicMock with sensible defaults."""
    defaults = {
        "id": uuid.uuid4(),
        "task_id": uuid.uuid4(),
        "step_order": 1,
        "page_url": "https://example.com/login",
        "form_type": "login",
        "form_selector": "#login-form",
        "submit_selector": "#submit-btn",
        "human_breakpoint": False,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    defaults.update(overrides)
    obj = MagicMock()
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def make_form_field(**overrides):
    """Create a FormField-like MagicMock with sensible defaults."""
    defaults = {
        "id": uuid.uuid4(),
        "form_definition_id": uuid.uuid4(),
        "field_name": "username",
        "field_type": "text",
        "field_selector": "#username",
        "field_purpose": "username",
        "preset_value": "testuser",
        "is_sensitive": False,
        "is_file_upload": False,
        "is_required": True,
        "options": None,
        "sort_order": 0,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    defaults.update(overrides)
    obj = MagicMock()
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def make_execution_log(**overrides):
    """Create an ExecutionLog-like MagicMock with sensible defaults."""
    defaults = {
        "id": uuid.uuid4(),
        "task_id": uuid.uuid4(),
        "started_at": datetime.utcnow(),
        "completed_at": None,
        "status": "running",
        "is_dry_run": False,
        "retry_count": 0,
        "error_message": None,
        "screenshot_path": None,
        "steps_log": [],
        "vnc_session_id": None,
        "created_at": datetime.utcnow(),
    }
    defaults.update(overrides)
    obj = MagicMock()
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


# ---------------------------------------------------------------------------
# Mock VNC manager
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_vnc_manager():
    """Return a mock VNCManager that always succeeds."""
    vnc = AsyncMock()
    vnc.start_session = AsyncMock(return_value={
        "session_id": "vnc-session-123",
        "vnc_url": "http://localhost:6080/vnc_lite.html?autoconnect=true",
    })
    vnc.wait_for_resume = AsyncMock(return_value=True)
    vnc.stop_session = AsyncMock(return_value={"status": "stopped"})
    vnc.resume_session = AsyncMock(return_value={"status": "resumed"})
    vnc._start_xvfb = MagicMock()
    vnc.get_display = MagicMock(return_value=":99")
    vnc.cleanup = MagicMock()
    return vnc
