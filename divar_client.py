"""
کلاینت دیوار — لیست آگهی‌های تازه + جزئیات کامل هر آگهی (همه عکس‌ها و مشخصات).

⚠️ این ماژول از اندپوینت‌های داخلی و مستندنشده‌ی دیوار استفاده می‌کنه.
تاریخچه:
  - v8/search (POST قدیمی)      → بازنشسته شده، پیام «نیاز به بروزرسانی» میده
  - v8/web-search (GET)          → همین‌طور
  - v8/postlist/w/search (POST)  → اندپوینت فعلی که خود سایت divar.ir استفاده می‌کنه ← این نسخه
"""

import requests

POSTLIST_URL = "https://api.divar.ir/v8/postlist/w/search"
POST_V5_URL = "https://api.divar.ir/v5/posts/{token}"
POST_V8_URL = "https://api.divar.ir/v8/posts-v2/web/{token}"
POST_WEB_URL = "https://divar.ir/v/{token}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Origin": "https://divar.ir",
    "Referer": "https://divar.ir/",
}


# ---------------------------------------------------------------- ابزار عمومی

def _walk(obj):
    """پیمایش بازگشتی کل JSON (برای پیدا کردن فیلدها در هر ساختاری)."""
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)


def _find_first_str(d: dict, *keys: str) -> str:
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _extract_images(data) -> list[str]:
    """همه‌ی URLهای عکس رو از هر جای JSON پیدا می‌کنه."""
    urls, seen = [], set()
    for node in _walk(data):
        for key in ("image", "image_url", "url", "src"):
            val = node.get(key)
            if (
                isinstance(val, str)
                and "divarcdn" in val
                and ("post" in val or "picture" in val or val.endswith((".jpg", ".jpeg", ".webp", ".png")))
                and "thumbnail" not in val
                and val not in seen
            ):
                seen.add(val)
                urls.append(val)
    return urls


def _find_token(ad: dict) -> str:
    if isinstance(ad.get("token"), str):
        return ad["token"]
    for node in _walk(ad):
        t = node.get("token")
        if isinstance(t, str) and t:
            return t
        link = node.get("web_info", {}).get("web_url") if isinstance(node.get("web_info"), dict) else None
        if isinstance(link, str) and "/v/" in link:
            return link.rstrip("/").split("/")[-1]
    return ""


# ---------------------------------------------------------------- لیست آگهی‌ها

def fetch_listing_page(city_code: int, category: str) -> list[dict]:
    payload = {
        "city_ids": [str(city_code)] if city_code else [],
        "source_view": "CATEGORY",
        "disable_recommendation": False,
        "search_data": {
            "form_data": {
                "data": {
                    "category": {"str": {"value": category}},
                    "sort": {"str": {"value": "sort_date"}},
                }
            },
        },
    }

    resp = requests.post(POSTLIST_URL, json=payload, headers=HEADERS, timeout=20)

    print(f"[debug] POST {POSTLIST_URL}")
    print(f"[debug] HTTP status: {resp.status_code}")
    print(f"[debug] response length: {len(resp.content)} bytes")

    if resp.status_code != 200:
        print(f"[debug] پاسخ غیرمنتظره — اولین ۵۰۰ کاراکتر بدنه:\n{resp.text[:500]}")
        resp.raise_for_status()

    try:
        data = resp.json()
    except ValueError:
        print(f"[debug] پاسخ JSON نبود — اولین ۵۰۰ کاراکتر بدنه:\n{resp.text[:500]}")
        raise

    # آگهی‌ها معمولاً توی list_widgets با widget_type == POST_ROW هستن؛
    # ولی برای اطمینان کل JSON رو می‌گردیم.
    posts, seen_tokens = [], set()
    for node in _walk(data):
        if node.get("widget_type") != "POST_ROW":
            continue
        ad = node.get("data", {})
        token = _find_token(ad)
        if not token or token in seen_tokens:
            continue
        seen_tokens.add(token)
        posts.append({
            "token": token,
            "title": _find_first_str(ad, "title"),
            "thumb": _find_first_str(ad, "image_url", "image") or (_extract_images(ad) or [""])[0],
            "city": "",
            "district": "",
            "normal_text": _find_first_str(ad, "middle_description_text", "top_description_text", "bottom_description_text", "red_text"),
            "web_url": POST_WEB_URL.format(token=token),
        })

    if not posts:
        print(f"[debug] هیچ POST_ROW با token پیدا نشد. کلیدهای سطح اول جواب: {list(data.keys())}")
        print(f"[debug] نمونه از خود جواب (۱۰۰۰ کاراکتر اول):\n{str(data)[:1000]}")

    return posts


def fetch_new_listings(city_code: int, category: str, max_pages: int = 1) -> list[dict]:
    """صفحه‌ی اول نتایج (معمولاً ۲۰-۲۴ آگهی جدیدترین) — برای این حجم کار کافیه."""
    return fetch_listing_page(city_code, category)


def _extract_spec_pairs(data: dict) -> dict:
    """جفت‌های عنوان/مقدار (مثل کارکرد، مدل، برند) رو از ویجت‌های آگهی درمیاره."""
    specs = {}
    for node in _walk(data):
        title = node.get("title")
        value = node.get("value")
        if isinstance(title, str) and isinstance(value, str) and title and value:
            specs.setdefault(title.strip(), value.strip())
        items = node.get("items")
        if isinstance(items, list):
            for it in items:
                if isinstance(it, dict):
                    t, v = it.get("title") or it.get("label"), it.get("value")
                    if isinstance(t, str) and isinstance(v, str) and t and v:
                        specs.setdefault(t.strip(), v.strip())
    return specs


def fetch_post_detail(token: str) -> dict:
    """جزئیات کامل یک آگهی: عنوان، توضیحات، همه عکس‌ها، مشخصات (سال/کارکرد/...)، قیمت."""
    result = {
        "token": token,
        "title": "",
        "description": "",
        "images": [],
        "specs": {},
        "price_text": "",
        "city": "",
        "district": "",
        "web_url": POST_WEB_URL.format(token=token),
    }

    data = None
    for url in (POST_V8_URL.format(token=token), POST_V5_URL.format(token=token)):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            if resp.status_code == 200:
                data = resp.json()
                break
        except (requests.RequestException, ValueError):
            continue
    if data is None:
        print(f"[debug] جزئیات آگهی {token} از هیچ‌کدوم از اندپوینت‌ها نیومد.")
        return result

    try:
        result["title"] = data["data"]["share"]["title"]
    except (KeyError, TypeError):
        pass
    try:
        result["description"] = data["data"]["description"]
    except (KeyError, TypeError):
        pass
    try:
        result["city"] = data["data"].get("city", "")
        result["district"] = data["data"].get("district", "")
    except (KeyError, TypeError, AttributeError):
        pass
    try:
        imgs = data["widgets"]["images"]
        if isinstance(imgs, list):
            result["images"] = [i for i in imgs if isinstance(i, str)]
    except (KeyError, TypeError):
        pass

    if not result["images"]:
        result["images"] = _extract_images(data)

    specs = _extract_spec_pairs(data)
    result["specs"] = specs

    if not result["title"]:
        for node in _walk(data):
            if node.get("widget_type") == "POST_TITLE" or "post_title" in str(node.get("widget_type", "")).lower():
                t = node.get("data", {}).get("title") or node.get("title")
                if isinstance(t, str):
                    result["title"] = t.strip()
                    break
    if not result["description"]:
        for node in _walk(data):
            wt = str(node.get("widget_type", "")).upper()
            if "DESCRIPTION" in wt:
                d = node.get("data", {}).get("text") or node.get("text")
                if isinstance(d, str) and len(d) > 20:
                    result["description"] = d.strip()
                    break

    for key in ("قیمت", "قیمت پایه", "قیمت کل"):
        if key in specs:
            result["price_text"] = specs[key]
            break

    return result
