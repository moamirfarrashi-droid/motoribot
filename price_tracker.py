"""
ذخیره‌ی آماری از قیمت و برند آگهی‌هایی که هر روز بررسی می‌شن (چه پست بشن چه
به‌خاطر فیلتر رد بشن)، برای ساخت گزارش قیمت.

فایل price_stats.json کنار همین اسکریپت نگه‌داری میشه؛ فقط ۳۰ روز اخیر
نگه داشته میشه که بزرگ نشه.
"""

import json
import os
import re
from datetime import datetime, timedelta, timezone

STATS_FILE = os.path.join(os.path.dirname(__file__), "price_stats.json")
KEEP_DAYS = 30

BRAND_KEYWORDS = [
    "هوندا", "یاماها", "SYM", "سیم", "باجاج", "کویر", "سوزوکی", "کاوازاکی",
    "بنلی", "CFMOTO", "سی اف موتو", "KTM", "پیاجیو", "وسپا", "دوکاتی",
    "رویال انفیلد", "احسان موتور", "ماهیندرا",
]

FA_TO_EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


def _digits(text) -> int | None:
    d = re.sub(r"[^0-9]", "", str(text).translate(FA_TO_EN))
    return int(d) if d else None


def detect_brand(title: str) -> str:
    for b in BRAND_KEYWORDS:
        if b in title:
            return b
    first = title.strip().split()[0] if title and title.strip() else "نامشخص"
    return first


def _load() -> list:
    if not os.path.exists(STATS_FILE):
        return []
    try:
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _save(stats: list) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)
    trimmed = []
    for s in stats:
        try:
            if datetime.fromisoformat(s["date"]) >= cutoff:
                trimmed.append(s)
        except (KeyError, ValueError):
            continue
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(trimmed, f, ensure_ascii=False)


def record_stat(title: str, price_toman: int | None, mileage_km: int | None) -> None:
    """هر آگهی‌ای که قیمتش معلوم باشه رو ثبت می‌کنه."""
    if price_toman is None:
        return
    entry = {
        "date": datetime.now(timezone.utc).isoformat(),
        "brand": detect_brand(title or ""),
        "price": price_toman,
        "mileage": mileage_km,
        "title": title or "بدون عنوان",
    }
    stats = _load()
    stats.append(entry)
    _save(stats)


def load_recent(days: int = 7) -> list:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = []
    for s in _load():
        try:
            if datetime.fromisoformat(s["date"]) >= cutoff:
                result.append(s)
        except (KeyError, ValueError):
            continue
    return result
