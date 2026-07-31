"""
ارسال پست به کانال تلگرام.

دو حالت پست (POST_MODE در .env):
  single : یک عکس + کپشن + دکمه‌ها روی همون پست (تمیزترین حالت)
  album  : همه عکس‌های آگهی به صورت آلبوم + کپشن روی عکس اول،
           و چون تلگرام اجازه نمیده روی آلبوم دکمه بذاریم، یک پیام کوتاه
           بلافاصله بعد از آلبوم (به صورت ریپلای روی آلبوم) با دکمه‌ها میاد.

اگه از داخل ایران اجراش می‌کنی، api.telegram.org مسدوده — متغیر TELEGRAM_PROXY
رو در .env تنظیم کن (مثلاً socks5h://127.0.0.1:1080).
"""

import requests

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"
MAX_ALBUM_SIZE = 10  # محدودیت تلگرام


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

    def _keyboard(self, post_web_url: str) -> dict:
        return {
            "inline_keyboard": [
                [{"text": "💬 ارتباط با پشتیبانی", "url": self.support_url}],
                [{"text": "🔗 مشاهده آگهی در دیوار", "url": post_web_url}],
            ]
        }

    # -------------------------------------------------------------- ارسال

    def send_post(self, caption: str, images: list[str], post_web_url: str) -> bool:
        images = [i for i in images if i][: self.max_images]

        if not images:
            return self._call("sendMessage", {
                "chat_id": self.channel_id,
                "text": caption,
                "reply_markup": self._keyboard(post_web_url),
            }) is not None

        if self.post_mode == "single" or len(images) == 1:
            return self._call("sendPhoto", {
                "chat_id": self.channel_id,
                "photo": images[0],
                "caption": caption,
                "reply_markup": self._keyboard(post_web_url),
            }) is not None

        # --- حالت آلبوم ---
        media = [{"type": "photo", "media": url} for url in images]
        media[0]["caption"] = caption
        result = self._call("sendMediaGroup", {
            "chat_id": self.channel_id,
            "media": media,
        })
        if result is None:
            # اگه آلبوم شکست خورد (مثلاً یکی از عکس‌ها خراب بود)، با یک عکس دوباره امتحان کن
            return self._call("sendPhoto", {
                "chat_id": self.channel_id,
                "photo": images[0],
                "caption": caption,
                "reply_markup": self._keyboard(post_web_url),
            }) is not None

        # پیام دکمه‌ها، ریپلای روی اولین عکس آلبوم
        first_msg_id = result[0]["message_id"] if isinstance(result, list) and result else None
        payload = {
            "chat_id": self.channel_id,
            "text": "برای خرید یا سوال 👇",
            "reply_markup": self._keyboard(post_web_url),
        }
        if first_msg_id:
            payload["reply_to_message_id"] = first_msg_id
        self._call("sendMessage", payload)
        return True
