"""
اسکریپت اصلی. هر بار اجرا:
  ۱. لیست آگهی‌های تازه موتورسیکلت رو از دیوار می‌گیره
  ۲. تکراری‌ها رو (با seen_posts.json) فیلتر می‌کنه
  ۳. جزئیات هر آگهی رو می‌گیره، آمار قیمت/برند رو ثبت می‌کنه، و فیلتر می‌کنه
  ۴. کپشن با قالب کانال می‌سازه و پست می‌کنه
"""

import os
import re
import sys
import time

from dotenv import load_dotenv

from divar_client import fetch_new_listings, fetch_post_detail
from formatter import build_caption
from price_tracker import record_stat
from storage import load_seen, save_seen, mark_seen
from telegram_poster import TelegramPoster

load_dotenv()

MIN_MILEAGE_KM = 1000
MAX_MILEAGE_KM = 15000
MIN_PRICE_TOMAN = 400_000_000

FA_TO_EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


def _digits_of(text: str) -> int | None:
    digits = re.sub(r"[^0-9]", "", str(text).translate(FA_TO_EN))
    return int(digits) if digits else None


def get_mileage_km(detail: dict) -> int | None:
    for key, value in detail.get("specs", {}).items():
        if "کارکرد" in key:
            return _digits_of(value)
    return None


def get_price_toman(detail: dict) -> int | None:
    raw = detail.get("price_text", "")
    if not raw:
        for key, value in detail.get("specs", {}).items():
            if "قیمت" in key:
                raw = value
                break
    if not raw or "توافق" in raw:
        return None
    return _digits_of(raw)


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
    detail = fetch_post_detail(token)
    print("=" * 50)
    print("عنوان:", detail["title"])
    print("مکان:", detail["city"], "-", detail["district"])
    print("کارکرد (کیلومتر):", get_mileage_km(detail))
    print("قیمت (تومان):", get_price_toman(detail))
    print("تعداد عکس:", len(detail["images"]))
    for img in detail["images"]:
        print("  🖼", img)
    print("مشخصات پیدا شده:", detail["specs"])
    print("=" * 50)
    print("کپشن نهایی:")
    print(build_caption(detail, {}))


def run_test():
    config = get_config(need_telegram=False)
    listings = fetch_new_listings(config["city_code"], config["category"])
    print(f"{len(listings)} آگهی دریافت شد. نمایش ۳ تای اول:\n")
    for listing in listings[:3]:
        detail = fetch_post_detail(listing["token"])
        print("=" * 50)
        print(f"لینک: {listing['web_url']}")
        print(f"کارکرد: {get_mileage_km(detail)} | قیمت: {get_price_toman(detail)} | عکس: {len(detail['images'])}")
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

    if not new_listings:
        print("[main] آگهی جدیدی برای پست نیست.")
        return

    poster = TelegramPoster(
        config["bot_token"], config["channel_id"], config["support_url"],
        proxy=config["proxy"], post_mode=config["post_mode"],
        max_images=config["max_images"],
    )

    posted = 0
    for listing in new_listings:
        if posted >= config["max_posts"]:
            break
        try:
            detail = fetch_post_detail(listing["token"])

            mileage_for_stats = get_mileage_km(detail)
            price_for_stats = get_price_toman(detail)
            record_stat(detail.get("title") or listing["title"], price_for_stats, mileage_for_stats)

            mileage = mileage_for_stats
            if mileage is None or not (MIN_MILEAGE_KM <= mileage <= MAX_MILEAGE_KM):
                print(f"[main] ⏭ رد شد (کارکرد={mileage}): {listing['title']}")
                mark_seen(seen, listing["token"])
                save_seen(seen)
                continue

            price = price_for_stats
            if price is None or price < MIN_PRICE_TOMAN:
                print(f"[main] ⏭ رد شد (قیمت={price}): {listing['title']}")
                mark_seen(seen, listing["token"])
                save_seen(seen)
                continue

            caption = build_caption(detail, listing)
            images = detail["images"] or ([listing["thumb"]] if listing["thumb"] else [])
            ok = poster.send_post(caption, images)
        except Exception as e:
            print(f"[main] خطا روی آگهی {listing['token']}: {e}")
            ok = False

        mark_seen(seen, listing["token"])
        save_seen(seen)
        if ok:
            posted += 1
            print(f"[main] ✅ پست شد: {listing['title']}")
            time.sleep(config["delay"])
        else:
            print(f"[main] ❌ پست نشد: {listing['title']}")

    print(f"[main] پایان — {posted} آگهی پست شد.")


if __name__ == "__main__":
    if "--test" in sys.argv:
        run_test()
    elif "--test-token" in sys.argv:
        idx = sys.argv.index("--test-token")
        run_test_token(sys.argv[idx + 1])
    else:
        main()
