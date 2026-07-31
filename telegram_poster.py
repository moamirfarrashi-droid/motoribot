"""
ارسال پست به کانال تلگرام.

دکمه‌های زیر هر پست:
  💬 ارتباط با پشتیبانی   → آیدی تلگرام پشتیبانی
  🛠 درخواست کارشناسی      → همون آیدی تلگرام
  🛡 راهنمای خرید امن      → پست راهنما در کانال

نکته: تلگرام اجازه نمیده روی آلبوم (چند عکس) دکمه گذاشت؛ به همین خاطر در حالت
آلبوم، دکمه‌ها در یک پیام کوتاه مستقل (بدون ریپلای) بلافاصله بعد از آلبوم میان.
در حالت single (تک‌عکس) دکمه‌ها مستقیم روی خود پست هستن.
"""

import requests

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"
MAX_ALBUM_SIZE = 10  # محدودیت تلگرام

SAFE_BUYING_GUIDE_URL = "https://t.me/motoritoo/7"


class TelegramPoster:
    def __init__(self, bot_token: str, channel_id: str, support_url: str,
                 proxy: str = "", post_mode: str = "album", max_images: int = 6):
        self.bot_token = bot_token
        self.channel_id = channel_id
        self.support_url = support_url
        self.post_mode = post_mode
        self.max_images = min(max_images, MAX_ALBUM_SIZE)
        self.session = requests.Session()
        if proxy:
            self.session.proxies = {"http": proxy, "https": proxy}

    # ------------------------------------------------------------- ابزارها

    def _url(self, method: str) -> str:
        return TELEGRAM_API.format(token=self.bot_token, method=method)

    def _call(self, method: str, payload: dict) -> dict | None:
        resp = self.session.post(self._url(method), json=payload, timeout=60)
        data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        if resp.status_code != 200 or not data.get("ok"):
            print(f"[telegram] {method} خطا: {resp.status_code} - {resp.text[:300]}")
            return None
        return data.get("result")

    def _keyboard(self) -> dict:
        return {
            "inline_keyboard": [
                [{"text": "💬 ارتباط با پشتیبانی", "url": self.support_url}],
                [{"text": "🛠 درخواست کارشناسی", "url": self.support_url}],
                [{"text": "🛡 راهنمای خرید امن", "url": SAFE_BUYING_GUIDE_URL}],
            ]
        }

    # -------------------------------------------------------------- ارسال

    def send_post(self, caption: str, images: list[str], post_web_url: str = "") -> bool:
        images = [i for i in images if i][: self.max_images]

        if not images:
            return self._call("sendMessage", {
                "chat_id": self.channel_id,
                "text": caption,
                "reply_markup": self._keyboard(),
            }) is not None

        if self.post_mode == "single" or len(images) == 1:
            return self._call("sendPhoto", {
                "chat_id": self.channel_id,
                "photo": images[0],
                "caption": caption,
                "reply_markup": self._keyboard(),
            }) is not None

        # --- حالت آلبوم ---
        media = [{"type": "photo", "media": url} for url in images]
        media[0]["caption"] = caption
        result = self._call("sendMediaGroup", {
            "chat_id": self.channel_id,
            "media": media,
        })
        if result is None:
            return self._call("sendPhoto", {
                "chat_id": self.channel_id,
                "photo": images[0],
                "caption": caption,
                "reply_markup": self._keyboard(),
            }) is not None

        # پیام دکمه‌ها — مستقل، بدون ریپلای
        self._call("sendMessage", {
            "chat_id": self.channel_id,
            "text": "👇 برای خرید، کارشناسی یا سوال:",
            "reply_markup": self._keyboard(),
        })
        return True
