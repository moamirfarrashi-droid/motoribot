"""
نگهداری لیست آگهی‌هایی که قبلاً پست شدن، تا دوباره تکراری پست نشن.
یک فایل JSON ساده کنار اسکریپت (seen_posts.json). برای این حجم کار
نیازی به دیتابیس نیست.
"""

import json
import os

STORAGE_FILE = os.path.join(os.path.dirname(__file__), "seen_posts.json")
MAX_KEEP = 5000  # برای اینکه فایل بی‌نهایت بزرگ نشه، فقط آخرین N تا رو نگه می‌داریم


def load_seen() -> set:
    if not os.path.exists(STORAGE_FILE):
        return set()
    try:
        with open(STORAGE_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except (json.JSONDecodeError, OSError):
        return set()


def save_seen(seen: set) -> None:
    trimmed = list(seen)[-MAX_KEEP:]
    with open(STORAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(trimmed, f, ensure_ascii=False)


def mark_seen(seen: set, token: str) -> None:
    seen.add(token)
