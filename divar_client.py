"""
کلاینت دیوار — لیست آگهی‌ها (با صفحه‌بندی، چندین صفحه عمیق) + جزئیات کامل هر آگهی.

⚠️ این ماژول از اندپوینت‌های داخلی و مستندنشده‌ی دیوار استفاده می‌کنه.
اندپوینت فعلی: POST api.divar.ir/v8/postlist/w/search (همونی که خود سایت استفاده می‌کنه)

نکته: چون فیلترهای کانال سخت‌گیرانه‌ست (کارکرد + قیمت)، این نسخه به‌جای فقط
صفحه‌ی اول، چندین صفحه از نتایج رو ورق می‌زنه (قدیمی‌ترها هم بررسی میشن) تا
آگهی واجد شرایط بیشتری پیدا بشه.
"""

import time

import requests

POSTLIST_URL = "https://api.divar.ir/v8/postlist/w/search"
POST_V5_URL = "https://api.divar.ir/v5/posts/{token}"
POST_V8_URL = "https://api.divar.ir/v8/posts-v2/web/{token}"
POST_WEB_URL = "https://divar.ir/v/{token}"

# چند صفحه از نتایج دیوار در هر اجرا بررسی بشه (هر صفحه ≈ ۲۴ آگهی)
MAX_PAGES = 10
# مکث بین درخواست هر صفحه (ثانیه) — برای فشار نیاوردن به دیوار
PAGE_DELAY_SECONDS = 2

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


def _find_pagination(data: dict):
    """داده‌ی صفحه‌بندی برای درخواست صفحه‌ی بعد رو پیدا می‌کنه (اگه باشه)."""
    pag = data.get("pagination")
    if isinstance(pag, dict):
        pd = pag.get("data")
        if isinstance(pd, dict) and pd:
            return pd
    # جستجوی عمومی: هر dict که last_post_date داشته باشه و @type صفحه‌بندی
    for node in _walk(data):
        if isinstance(node, dict) and "last_post_date" in node and "@type" in str(node.get("@type", "")):
            if "Pagination" in str(node.get("@type", "")):
                return node
    return None


# ---------------------------------------------------------------- لیست آگهی‌ها

def _parse_posts(data: dict, seen_tokens: set) -> list[dict]:
    posts = []
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
    return posts


def fetch_new_listings(city_code: int, category: str, max_pages: int = MAX_PAGES) -> list[dict]:
    """چندین صفحه از نتایج رو ورق می‌زنه و همه‌ی آگهی‌ها رو یکجا برمی‌گردونه."""
    all_posts: list[dict] = []
    seen_tokens: set = set()
    pagination_data = None

    for page_num in range(1, max_pages + 1):
        payload = {
            "city_ids": [str(city_code)] if city_code else [],
            "source_view": "CATEGORY",
            "disable_recommendation": True,
            "search_data": {
                "form_data": {
                    "data": {
                        "category": {"str": {"value": category}},
                        "sort": {"str": {"value": "sort_date"}},
                    }
                },
            },
        }
        if pagination_data:
            payload["pagination_data"] = pagination_data

        try:
            resp = requests.post(POSTLIST_URL, json=payload, headers=HEADERS, timeout=20)
        except requests.RequestException as e:
            print(f"[divar] صفحه {page_num}: خطای شبکه: {e}")
            break

        if resp.status_code != 200:
            print(f"[divar] صفحه {page_num}: HTTP {resp.status_code} — {resp.text[:300]}")
            break

        try:
            data = resp.json()
        except ValueError:
            print(f"[divar] صفحه {page_num}: پاسخ JSON نبود — {resp.text[:300]}")
            break

        page_posts = _parse_posts(data, seen_tokens)
        all_posts.extend(page_posts)
        print(f"[divar] صفحه {page_num}: {len(page_posts)} آگهی (مجموع: {len(all_posts)})")

        if page_num == 1 and not page_posts:
            print(f"[debug] هیچ POST_ROW پیدا نشد. کلیدهای سطح اول: {list(data.keys())}")
            print(f"[debug] نمونه از جواب:\n{str(data)[:800]}")

        pagination_data = _find_pagination(data)
        if not pagination_data or not page_posts:
            break  # صفحه‌ی بعدی وجود نداره

        time.sleep(PAGE_DELAY_SECONDS)

    return all_posts


# ------------------------------------------------------------- جزئیات آگهی

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

    # مکان: کلیدهای city_persian / district_persian هر جای JSON که باشن
    if not result["city"] or not result["district"]:
        for node in _walk(data):
            c = node.get("city_persian")
            d = node.get("district_persian")
            if isinstance(c, str) and c and not result["city"]:
                result["city"] = c.strip()
            if isinstance(d, str) and d and not result["district"]:
                result["district"] = d.strip()
            if result["city"] and result["district"]:
                break

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
