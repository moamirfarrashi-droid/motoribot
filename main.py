"""
اسکریپت اصلی. هر بار اجرا:
  ۱. لیست آگهی‌های تازه موتورسیکلت رو از دیوار می‌گیره
  ۲. تکراری‌ها رو (با seen_posts.json) فیلتر می‌کنه
  ۳. برای هر آگهی جدید، جزئیات کامل (همه عکس‌ها + مشخصات) رو می‌گیره
  ۴. کپشن با قالب کانالت می‌سازه و پست می‌کنه (آلبوم عکس + دکمه پشتیبانی)

حالت تست (بدون پست کردن چیزی، فقط نمایش خروجی):
    python3 main.py --test
تست یک آگهی خاص با توکن:
    python3 main.py --test-token gaqZf69e
"""

import os
import sys
import time

from dotenv import load_dotenv

from divar_client import fetch_new_listings, fetch_post_detail
from formatter import build_caption
from storage import load_seen, save_seen, mark_seen
from telegram_poster import TelegramPoster

load_dotenv()


def get_config(need_telegram: bool = True):
    if need_telegram:
        required = ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHANNEL_ID", "SUPPORT_TELEGRAM_URL"]
        missing = [k for k in required if not os.getenv(k)]
        if missing:
            print(f"[config] این متغیرها در فایل .env تنظیم نشدن: {', '.join(missing)}")
            sys.exit(1)
    return {
        "bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
        "channel_id": os.getenv("TELEGRAM_CHANNEL_ID", ""),
        "support_url": os.getenv("SUPPORT_TELEGRAM_URL", ""),
        "proxy": os.getenv("TELEGRAM_PROXY", ""),
        "post_mode": os.getenv("POST_MODE", "album"),
        "max_images": int(os.getenv("MAX_IMAGES_PER_POST", "6")),
        "city_code": int(os.getenv("DIVAR_CITY_CODE", "1")),
        "category": os.getenv("DIVAR_CATEGORY", "motorcycles"),
        "max_posts": int(os.getenv("MAX_POSTS_PER_RUN", "10")),
        "delay": int(os.getenv("DELAY_BETWEEN_POSTS_SECONDS", "30")),
    }


def run_test_token(token: str):
    """جزئیات و کپشن یک آگهی خاص رو نشون میده — بدون پست کردن."""
    detail = fetch_post_detail(token)
    print("=" * 50)
    print("عنوان:", detail["title"])
    print("تعداد عکس:", len(detail["images"]))
    for img in detail["images"]:
        print("  🖼", img)
    print("مشخصات پیدا شده:", detail["specs"])
    print("=" * 50)
    print("کپشن نهایی:")
    print(build_caption(detail, {}))


def run_test():
    """چند آگهی اول رو می‌گیره و کپشن‌ها رو نشون میده — بدون پست کردن."""
    config = get_config(need_telegram=False)
    listings = fetch_new_listings(config["city_code"], config["category"], max_pages=1)
    print(f"{len(listings)} آگهی دریافت شد. نمایش ۳ تای اول:\n")
    for listing in listings[:3]:
        detail = fetch_post_detail(listing["token"])
        print("=" * 50)
        print(f"لینک: {listing['web_url']}")
        print(f"تعداد عکس: {len(detail['images'])}")
        print("-" * 50)
        print(build_caption(detail, listing))
        print()
        time.sleep(2)


def main():
    config = get_config()
    seen = load_seen()

    print(f"[divar] دریافت آگهی‌ها (شهر={config['city_code']}, دسته={config['category']})...")
    listings = fetch_new_listings(config["city_code"], config["category"])
    new_listings = [p for p in listings if p["token"] not in seen]
    print(f"[divar] {len(listings)} آگهی دریافت شد، {len(new_listings)} تاش جدیده.")

    to_post = new_listings[: config["max_posts"]]
    if not to_post:
        print("[main] آگهی جدیدی برای پست نیست.")
        return

    poster = TelegramPoster(
        config["bot_token"], config["channel_id"], config["support_url"],
        proxy=config["proxy"], post_mode=config["post_mode"],
        max_images=config["max_images"],
    )

    posted = 0
    for i, listing in enumerate(to_post):
        try:
            detail = fetch_post_detail(listing["token"])
            caption = build_caption(detail, listing)
            images = detail["images"] or ([listing["thumb"]] if listing["thumb"] else [])
            ok = poster.send_post(caption, images, listing["web_url"])
        except Exception as e:  # noqa: BLE001 — یک آگهی خراب نباید کل اجرا رو متوقف کنه
            print(f"[main] خطا روی آگهی {listing['token']}: {e}")
            ok = False

        mark_seen(seen, listing["token"])
        save_seen(seen)
        if ok:
            posted += 1
            print(f"[main] ✅ پست شد: {listing['title']}")
        else:
            print(f"[main] ❌ پست نشد: {listing['title']}")

        if i < len(to_post) - 1:
            time.sleep(config["delay"])

    print(f"[main] پایان — {posted} از {len(to_post)} آگهی پست شد.")


if __name__ == "__main__":
    if "--test" in sys.argv:
        run_test()
    elif "--test-token" in sys.argv:
        idx = sys.argv.index("--test-token")
        run_test_token(sys.argv[idx + 1])
    else:
        main()
