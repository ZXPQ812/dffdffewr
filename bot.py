import asyncio
import threading
import time
import logging
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

ACCOUNTS = [
    {
        "name": "Invisible Account",
        "message": None,  # TBD - set via UI
        "slot": "invisible",
    },
    {
        "name": "Share Account",
        "message": "Negro a partagé ton live à 1000 personnes.",
        "slot": "share",
    },
    {
        "name": "Welcome Account",
        "message": "ntmrlp f2p a rejoint le live.",
        "slot": "welcome",
    },
    {
        "name": "Notification Account",
        "message": "Ton live sera définitivement banni, si tu enfreints nos règles de sécurités.",
        "slot": "notification",
    },
]

def parse_cookie_string(cookie_str, domain=".tiktok.com"):
    """Parse browser cookie string into Playwright format."""
    cookies = []
    if not cookie_str or not cookie_str.strip():
        return cookies
    for part in cookie_str.split(";"):
        part = part.strip()
        if "=" in part:
            name, _, value = part.partition("=")
            cookies.append({
                "name": name.strip(),
                "value": value.strip(),
                "domain": domain,
                "path": "/",
            })
    return cookies


class AccountBot:
    def __init__(self, account_config, live_url, cookie_str, interval, status_dict):
        self.config = account_config
        self.live_url = live_url
        self.cookie_str = cookie_str
        self.interval = interval
        self.status_dict = status_dict
        self.running = False
        self.thread = None
        self.logger = logging.getLogger(account_config["name"])

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def _run_loop(self):
        asyncio.run(self._async_loop())

    async def _async_loop(self):
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--window-size=1280,720",
                ]
            )
            context = await browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            # Set cookies
            cookies = parse_cookie_string(self.cookie_str)
            if cookies:
                await context.add_cookies(cookies)
            
            page = await context.new_page()
            
            try:
                self.logger.info(f"Navigating to {self.live_url}")
                await page.goto(self.live_url, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(3)
                
                while self.running:
                    try:
                        message = self.config.get("message")
                        if message:
                            sent = await self._send_message(page, message)
                            if sent:
                                self.status_dict[self.config["name"]] = f"✅ Sent: {message[:30]}..."
                                self.logger.info(f"Sent message")
                            else:
                                self.status_dict[self.config["name"]] = "⚠️ Failed to find chat input"
                                self.logger.warning("Could not find chat input, refreshing...")
                                await page.reload(wait_until="networkidle")
                                await asyncio.sleep(5)
                        else:
                            self.status_dict[self.config["name"]] = "⏸️ No message set"
                    except Exception as e:
                        self.logger.error(f"Error: {e}")
                        self.status_dict[self.config["name"]] = f"❌ Error: {str(e)[:50]}"
                        try:
                            await page.goto(self.live_url, wait_until="networkidle", timeout=30000)
                            await asyncio.sleep(5)
                        except:
                            pass
                    
                    await asyncio.sleep(self.interval)
                    
            finally:
                await browser.close()

    async def _send_message(self, page, message):
        """Try multiple selectors to find TikTok live chat input."""
        selectors = [
            '[data-e2e="comment-input"]',
            '[placeholder*="comment" i]',
            '[placeholder*="Comment" i]',
            '[placeholder*="Say something" i]',
            '.comment-input',
            'div[contenteditable="true"]',
            'input[type="text"][class*="comment"]',
            '[class*="ReplyInput"]',
            '[class*="comment-input"]',
        ]
        
        input_el = None
        for sel in selectors:
            try:
                el = page.locator(sel).first
                if await el.is_visible(timeout=2000):
                    input_el = el
                    break
            except:
                continue
        
        if not input_el:
            return False
        
        try:
            await input_el.click()
            await asyncio.sleep(0.5)
            await input_el.fill("")
            await input_el.type(message, delay=30)
            await asyncio.sleep(0.3)
            await page.keyboard.press("Enter")
            await asyncio.sleep(1)
            return True
        except Exception as e:
            self.logger.error(f"Send failed: {e}")
            return False


class BotManager:
    def __init__(self):
        self.bots = {}
        self.running = False
        self.status = {acc["name"]: "⏹️ Stopped" for acc in ACCOUNTS}

    def start(self, live_url, cookies_map, interval, custom_messages=None):
        self.stop()
        self.running = True
        
        for acc in ACCOUNTS:
            cookie_str = cookies_map.get(acc["slot"], "")
            if not cookie_str:
                self.status[acc["name"]] = "⚠️ No cookie"
                continue
            
            config = dict(acc)
            if custom_messages and acc["slot"] in custom_messages:
                config["message"] = custom_messages[acc["slot"]]
            
            bot = AccountBot(config, live_url, cookie_str, interval, self.status)
            self.bots[acc["name"]] = bot
            bot.start()
            self.status[acc["name"]] = "🚀 Starting..."

    def stop(self):
        for bot in self.bots.values():
            bot.stop()
        self.bots = {}
        self.running = False
        for acc in ACCOUNTS:
            self.status[acc["name"]] = "⏹️ Stopped"

    def get_status(self):
        return {
            "running": self.running,
            "accounts": self.status,
        }
    
    def get_accounts(self):
        return ACCOUNTS
