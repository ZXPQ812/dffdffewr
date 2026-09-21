# language: Python 3.11 | file: bot.py | target: TikTok Live via Playwright headless chromium

import asyncio
import threading
import logging
from playwright.async_api import async_playwright

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
)

ACCOUNTS = [
    {
        "name": "Invisible Account",
        "slot": "invisible",
        "message": "",  # dj fills this later via UI
    },
    {
        "name": "Share Account",
        "slot": "share",
        "message": "Negro a partagé ton live à 1000 personnes.",
    },
    {
        "name": "Welcome Account",
        "slot": "welcome",
        "message": "ntmrlp f2p a rejoint le live.",
    },
    {
        "name": "Notification Account",
        "slot": "notification",
        "message": "Ton live sera définitivement banni, si tu enfreints nos règles de sécurités.",
    },
]


def parse_cookies(cookie_str: str, domain: str = ".tiktok.com") -> list:
    """
    Parses raw browser cookie string into Playwright-compatible list.
    Input format: 'name=value; name2=value2; ...'
    """
    result = []
    if not cookie_str or not cookie_str.strip():
        return result
    for chunk in cookie_str.split(";"):
        chunk = chunk.strip()
        if "=" in chunk:
            name, _, value = chunk.partition("=")
            result.append({
                "name": name.strip(),
                "value": value.strip(),
                "domain": domain,
                "path": "/",
                "sameSite": "None",
                "secure": True,
            })
    return result


class AccountBot:
    def __init__(self, config: dict, live_url: str, cookie_str: str,
                 interval: int, status_map: dict):
        self.config = config
        self.live_url = live_url
        self.cookie_str = cookie_str
        self.interval = interval
        self.status_map = status_map
        self.running = False
        self._thread = None
        self.log = logging.getLogger(config["name"])

    def start(self):
        self.running = True
        self._thread = threading.Thread(target=self._loop_entry, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False

    def _loop_entry(self):
        asyncio.run(self._async_loop())

    async def _async_loop(self):
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-blink-features=AutomationControlled",
                    "--window-size=1280,720",
                ],
            )
            ctx = await browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )

            cookies = parse_cookies(self.cookie_str)
            if cookies:
                await ctx.add_cookies(cookies)

            page = await ctx.new_page()

            # mask automation signals
            await page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )

            try:
                self.log.info(f"Opening {self.live_url}")
                await page.goto(self.live_url, wait_until="domcontentloaded", timeout=40000)
                await asyncio.sleep(4)

                while self.running:
                    msg = self.config.get("message", "").strip()
                    if not msg:
                        self.status_map[self.config["name"]] = "⏸ No message set"
                        await asyncio.sleep(self.interval)
                        continue

                    try:
                        ok = await self._send(page, msg)
                        if ok:
                            self.status_map[self.config["name"]] = (
                                f"✅ Sent — {msg[:35]}{'...' if len(msg) > 35 else ''}"
                            )
                        else:
                            self.status_map[self.config["name"]] = "⚠ Input not found — reloading"
                            self.log.warning("Chat input not found, reloading page")
                            await page.reload(wait_until="domcontentloaded")
                            await asyncio.sleep(6)
                    except Exception as exc:
                        self.log.error(f"Send error: {exc}")
                        self.status_map[self.config["name"]] = f"❌ {str(exc)[:60]}"
                        try:
                            await page.goto(self.live_url, wait_until="domcontentloaded", timeout=40000)
                            await asyncio.sleep(6)
                        except Exception:
                            pass

                    await asyncio.sleep(self.interval)

            finally:
                await browser.close()

    async def _send(self, page, message: str) -> bool:
        """
        Tries a cascade of selectors to locate TikTok live chat input,
        types the message, and presses Enter.
        """
        selectors = [
            '[data-e2e="comment-input"]',
            '[data-e2e="live-comment-input"]',
            '[placeholder*="comment" i]',
            '[placeholder*="say something" i]',
            '[placeholder*="Chat" i]',
            'div[contenteditable="true"][class*="comment" i]',
            'div[contenteditable="true"][class*="input" i]',
            'div[contenteditable="true"]',
            'input[class*="comment" i]',
            'input[class*="chat" i]',
        ]

        for sel in selectors:
            try:
                el = page.locator(sel).first
                if await el.is_visible(timeout=2000):
                    await el.click()
                    await asyncio.sleep(0.4)
                    # clear existing text
                    await page.keyboard.press("Control+a")
                    await page.keyboard.press("Delete")
                    await el.type(message, delay=25)
                    await asyncio.sleep(0.3)
                    await page.keyboard.press("Enter")
                    await asyncio.sleep(1)
                    return True
            except Exception:
                continue

        return False


class BotManager:
    def __init__(self):
        self._bots: dict[str, AccountBot] = {}
        self.running = False
        self.status: dict[str, str] = {
            acc["name"]: "⏹ Stopped" for acc in ACCOUNTS
        }

    def start(self, live_url: str, cookies_map: dict,
              interval: int, custom_messages: dict = None):
        self.stop()
        self.running = True

        for acc in ACCOUNTS:
            cookie_str = cookies_map.get(acc["slot"], "").strip()
            if not cookie_str:
                self.status[acc["name"]] = "⚠ No cookie — skipped"
                continue

            cfg = dict(acc)
            # allow UI override for message (mainly Invisible Account)
            if custom_messages and acc["slot"] in custom_messages:
                override = custom_messages[acc["slot"]].strip()
                if override:
                    cfg["message"] = override

            bot = AccountBot(cfg, live_url, cookie_str, interval, self.status)
            self._bots[acc["name"]] = bot
            bot.start()
            self.status[acc["name"]] = "🚀 Starting..."

    def stop(self):
        for bot in self._bots.values():
            bot.stop()
        self._bots.clear()
        self.running = False
        for acc in ACCOUNTS:
            self.status[acc["name"]] = "⏹ Stopped"

    def get_status(self) -> dict:
        return {"running": self.running, "accounts": self.status}
