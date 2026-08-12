"""
گزارش قیمت (میانگین به تفکیک برند + ارزون‌ترین/گرون‌ترین) — یک روز در میون
به‌عنوان آخرین پست روز فرستاده میشه.

برای دقیق نگه داشتن فاصله‌ی «هر ۲ روز» (حتی سر تغییر ماه)، یه فایل کوچیک
(report_state.json) تاریخ آخرین ارسال رو نگه می‌داره.

داده‌های گزارش از یه پنجره‌ی ۷روزه‌ی چرخشی (price_stats.json) ساخته میشه.
"""

import json
import os
import sys
from collections import defaultdict
from datetime import date

from dotenv import load_dotenv

from formatter import humanize_price, fa_num
from price_tracker import load_recent
from telegram_poster import TelegramPoster

load_dotenv()

STATE_FILE = os.path.join(os.path.dirname(__file__), "report_state.json")
SEND_EVERY_DAYS = 2


def _load_state() -> dict:
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False)


def is_report_due() -> bool:
    state = _load_state()
    last_sent = state.get("last_sent_date")
    if not last_sent:
        return True
    days_since = (date.today() - date.fromisoformat(last_sent)).days
    return days_since >= SEND_EVERY_DAYS


def mark_report_sent() -> None:
    _save_state({"last_sent_date": date.today().isoformat()})


def build_report_text() -> str | None:
    stats = load_recent(days=7)
    if not stats:
        return None

    by_brand = defaultdict(list)
    for s in stats:
        by_brand[s["brand"]].append(s["price"])

    lines = ["📊 گزارش قیمت موتورسیکلت", ""]

    sorted_brands = sorted(by_brand.items(), key=lambda kv: -len(kv[1]))
    brand_lines = []
    for brand, prices in sorted_brands:
        if len(prices) < 2:
            continue
        avg = sum(prices) // len(prices)
        brand_lines.append(f"🏍 {brand}: میانگین {humanize_price(str(avg))} ({fa_num(len(prices))} آگهی)")

    if brand_lines:
        lines.extend(brand_lines[:8])
    else:
        lines.append("داده‌ی کافی برای میانگین‌گیری برندها هنوز جمع نشده.")

    cheapest = min(stats, key=lambda s: s["price"])
    priciest = max(stats, key=lambda s: s["price"])

    lines.append("")
    lines.append(f"🔻 ارزون‌ترین این چند روز: {cheapest['title']} — {humanize_price(str(cheapest['price']))}")
    lines.append(f"🔺 گرون‌ترین این چند روز: {priciest['title']} — {humanize_price(str(priciest['price']))}")
    lines.append("")
    lines.append(f"📦 مجموع آگهی‌های بررسی‌شده: {fa_num(len(stats))}")
    lines.append("")
    lines.append("📢 کانال ما: https://t.me/motoritoo")

    return "\n".join(lines)


def main():
    if not is_report_due():
        print("[report] هنوز ۲ روز از آخرین گزارش نگذشته — این نوبت رد میشه.")
        return

    text = build_report_text()
    if not text:
        print("[report] داده‌ی کافی برای گزارش نیست — ارسال نمیشه (نوبت مصرف نمیشه).")
        return

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    channel_id = os.getenv("TELEGRAM_CHANNEL_ID")
    support_url = os.getenv("SUPPORT_TELEGRAM_URL", "")
    proxy = os.getenv("TELEGRAM_PROXY", "")

    if not bot_token or not channel_id:
        print("[config] TELEGRAM_BOT_TOKEN یا TELEGRAM_CHANNEL_ID تنظیم نشده.")
        sys.exit(1)

    poster = TelegramPoster(bot_token, channel_id, support_url, proxy=proxy)
    ok = poster.send_post(text, images=[])
    if ok:
        mark_report_sent()
        print("[report] گزارش ارسال شد.")
    else:
        print("[report] ارسال گزارش شکست خورد (نوبت مصرف نشد، دوباره امتحان میشه).")
    print(text)


if __name__ == "__main__":
    main()
