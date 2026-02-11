try:
    from playwright_stealth import stealth_async as _stealth_async
    HAS_STEALTH = True
except (ImportError, ModuleNotFoundError):
    HAS_STEALTH = False

    async def _stealth_async(page):
        """Fallback stealth: inject minimal anti-detection scripts."""
        await page.add_init_script("""
            // Override navigator.webdriver
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

            // Override chrome runtime
            window.chrome = { runtime: {} };

            // Override permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) =>
                parameters.name === 'notifications'
                    ? Promise.resolve({ state: Notification.permission })
                    : originalQuery(parameters);

            // Override plugins length
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });

            // Override languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });
        """)


async def apply_stealth(context):
    """Apply stealth settings to a browser context."""
    context.on("page", lambda page: _stealth_async(page))

    for page in context.pages:
        await _stealth_async(page)
