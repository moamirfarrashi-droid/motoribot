"""
ساخت کپشن دقیقاً با همون قالبی که در کانالت استفاده می‌کنی:

🏍 SYM Galaxy J200 – جی ۲۰۰ گالکسی

📅 سال ساخت: ۱۴۰۳
🛣 کارکرد: ۱۰,۰۰۰ کیلومتر
📍 محل بازدید: تهران، آبشار
💰 قیمت: ۲۴۵ میلیون تومان

🔧 مشخصات و وضعیت:
- فنی سالم و آماده سواری
- مدارک کامل و آماده انتقال

📢 کانال ما: https://t.me/motoritoo

هیچ API هوش مصنوعی‌ای لازم نیست — همه چیز از خود داده‌های آگهی ساخته میشه.
بولت‌های «مشخصات و وضعیت» از خطوط توضیحاتِ خود آگهی‌گذار درمیاد.
"""

import re

CAPTION_LIMIT = 1024  # محدودیت تلگرام برای کپشن عکس/آلبوم

# لینک کانال — انتهای هر کپشن اضافه میشه
CHANNEL_LINK = "https://t.me/motoritoo"

FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
EN_TO_FA = str.maketrans("0123456789", FA_DIGITS)
FA_TO_EN = str.maketrans(FA_DIGITS + "٬،,", "0123456789" + "   ")


def fa_num(text: str) -> str:
    """اعداد انگلیسی رو فارسی می‌کنه."""
    return str(text).translate(EN_TO_FA)


def humanize_price(price_text: str) -> str:
    """«۲۴۵٬۰۰۰٬۰۰۰ تومان» → «۲۴۵ میلیون تومان». اگه قابل‌تبدیل نبود، همون متن اصلی."""
    if not price_text:
        return ""
    if "توافق" in price_text:
        return "توافقی"
    digits = re.sub(r"[^0-9]", "", price_text.translate(FA_TO_EN))
    if not digits:
        return price_text
    n = int(digits)
    if n >= 1_000_000_000:
        whole, frac = divmod(n, 1_000_000_000)
        frac_100m = frac // 100_000_000  # یک رقم اعشار
        s = f"{whole}.{frac_100m}" if frac_100m else str(whole)
        return f"{fa_num(s)} میلیارد تومان"
    if n >= 1_000_000:
        whole, frac = divmod(n, 1_000_000)
        frac_100k = frac // 100_000
        s = f"{whole}.{frac_100k}" if frac_100k else str(whole)
        return f"{fa_num(s)} میلیون تومان"
    return f"{fa_num(f'{n:,}')} تومان"


def _find_spec(specs: dict, *keywords: str) -> str:
    """اولین مقداری از specs که کلیدش شامل یکی از این کلمه‌ها باشه."""
    for key, value in specs.items():
        for kw in keywords:
            if kw in key:
                return value
    return ""


def _description_bullets(description: str, max_bullets: int = 6, max_len: int = 60) -> list[str]:
    """خطوط توضیحات آگهی رو به بولت تبدیل می‌کنه (خطوط خیلی بلند/شماره‌تلفن حذف)."""
    bullets = []
    for raw_line in description.splitlines():
        line = raw_line.strip().strip("•-–—*").strip()
        if not line:
            continue
        # خطوطی که عمدتاً شماره تلفن هستن رو نمی‌ذاریم (بیننده باید از دکمه پشتیبانی بیاد)
        digit_count = len(re.findall(r"[0-9۰-۹]", line))
        if digit_count >= 8 and digit_count / max(len(line), 1) > 0.5:
            continue
        if len(line) > max_len:
            line = line[: max_len - 1].rstrip() + "…"
        bullets.append(line)
        if len(bullets) >= max_bullets:
            break
    return bullets


def build_caption(detail: dict, listing: dict) -> str:
    """detail: خروجی fetch_post_detail — listing: آیتم لیست جستجو (برای fallback)."""
    title = detail.get("title") or listing.get("title") or "آگهی موتورسیکلت"
    specs = detail.get("specs", {})

    year = _find_spec(specs, "مدل", "سال")
    mileage = _find_spec(specs, "کارکرد")
    price_raw = detail.get("price_text") or _find_spec(specs, "قیمت") or listing.get("normal_text", "")

    city = detail.get("city") or listing.get("city", "")
    district = detail.get("district") or listing.get("district", "")
    location = "، ".join([p for p in (city, district) if p])

    lines = [f"🏍 {title}", ""]

    if year:
        lines.append(f"📅 سال ساخت: {fa_num(year)}")
    if mileage:
        m = fa_num(mileage)
        if "کیلومتر" not in m:
            m += " کیلومتر"
        lines.append(f"🛣 کارکرد: {m}")
    if location:
        lines.append(f"📍 محل بازدید: {location}")
    if price_raw:
        lines.append(f"💰 قیمت: {humanize_price(price_raw)}")

    bullets = _description_bullets(detail.get("description", ""))
    if bullets:
        lines.append("")
        lines.append("🔧 مشخصات و وضعیت:")
        lines.extend(f"• {b}" for b in bullets)

    footer = f"\n\n📢 کانال ما: {CHANNEL_LINK}"

    caption = "\n".join(lines).strip()
    # اول متن اصلی رو (در صورت نیاز) کوتاه می‌کنیم که جا برای لینک کانال بمونه
    body_limit = CAPTION_LIMIT - len(footer)
    if len(caption) > body_limit:
        caption = caption[: body_limit - 1].rstrip() + "…"
    return caption + footer
