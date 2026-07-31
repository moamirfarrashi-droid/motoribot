"""
کلاینت دیوار — لیست آگهی‌های تازه + جزئیات کامل هر آگهی (همه عکس‌ها و مشخصات).

⚠️ توجه: این ماژول از اندپوینت‌های داخلی و مستندنشده‌ی دیوار استفاده می‌کنه
(همون‌هایی که خود سایت/اپ دیوار صدا می‌زنه). ممکنه بدون اطلاع تغییر کنن.
جزئیات و توصیه‌ها در README.md.
"""

import requests

SEARCH_URL = "https://api.divar.ir/v8/search/{city_code}/{category}"
POST_V5_URL = "https://api.divar.ir/v5/posts/{token}"
POST_V8_URL = "https://api.divar.ir/v8/posts-v2/web/{token}"
POST_WEB_URL = "https://divar.ir/v/{token}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Content-Type": "application/json",
}


# ---------------------------------------------------------------- لیست آگهی‌ها

def fetch_listing_page(city_code: int, category: str, last_post_date: int = 0) -> dict:
    url = SEARCH_URL.format(city_code=city_code, category=category)
    payload = {
        "json_schema": {"category": {"value": category}},
        "last-post-date": last_post_date,
    }
    resp = requests.post(url, json=payload, headers=HEADERS, timeout=20)

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

    if "widget_list" not in data:
        print(f"[debug] کلید widget_list توی جواب نبود. کلیدهای موجود: {list(data.keys())}")
        print(f"[debug] نمونه از خود جواب (۸۰۰ کاراکتر اول):\n{str(data)[:800]}")

    posts = []
    for widget in data.get("widget_list", []):
        d = widget.get("data", {})
        token = d.get("token")
        if not token:
            continue
        posts.append({
            "token": token,
            "title": (d.get("title") or "").strip(),
            "thumb": d.get("image", ""),
            "city": d.get("city", ""),
            "district": d.get("district", ""),
            "normal_text": d.get("normal_text", ""),
            "web_url": POST_WEB_URL.format(token=token),
        })

    if data.get("widget_list") and not posts:
        print(f"[debug] {len(data['widget_list'])} ویجت اومد ولی هیچ‌کدوم token نداشتن.")
        print(f"[debug] نمونه‌ی اولین ویجت:\n{str(data['widget_list'][0])[:800]}")

    return {"last_post_date": data.get("last_post_date", 0), "posts": posts}


def fetch_new_listings(city_code: int, category: str, max_pages: int = 2) -> list[dict]:
    """چند صفحه از نتایج رو می‌خونه (جدیدترین‌ها اول)."""
    all_posts, last_post_date = [], 0
    for _ in range(max_pages):
        page = fetch_listing_page(city_code, category, last_post_date)
        if not page["posts"]:
            break
        all_posts.extend(page["posts"])
        if page["last_post_date"] in (0, -1, last_post_date):
            break
        last_post_date = page["last_post_date"]
    return all_posts


# ------------------------------------------------------------- جزئیات آگهی

def _walk(obj):
    """پیمایش بازگشتی کل JSON (برای پیدا کردن فیلدها در هر ساختاری)."""
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)


def _extract_images(data: dict) -> list[str]:
    """همه‌ی URLهای عکس آگهی رو از هر جای JSON پیدا می‌کنه."""
    urls, seen = [], set()
    for node in _walk(data):
        for key in ("image", "url", "src"):
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
