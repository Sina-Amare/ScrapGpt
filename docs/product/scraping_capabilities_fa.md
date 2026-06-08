# قابلیت‌های اسکریپینگ ScrapGPT — وضعیت فعلی و نقشه راه آینده

> این داکیومنت توضیح کاملی از نحوه کار سیستم اسکریپینگ، محدودیت‌های جاری، و اینکه در فازهای بعدی چه چیزی تغییر می‌کند، ارائه می‌دهد. اگر می‌خواهی بدانی این سیستم همان چیزی است که می‌خواهی یا نه، این سند را بخوان.

---

## ۱. چطور اسکریپینگ انجام می‌شود (pipeline فعلی — فاز ۱)

یک پروژه از ۵ مرحله عبور می‌کند:

```
URL ورودی
    ↓
[Fetch] صفحه HTML دریافت می‌شود
    ↓
[DOM Summary] ساختار صفحه فشرده می‌شود
    ↓
[AI Analysis] هوش مصنوعی فیلدها و سلکتورها را کشف می‌کند
    ↓
[User Review] کاربر فیلدها را انتخاب و ویرایش می‌کند
    ↓
[Seed Extraction] نمونه‌های AI به رکورد تبدیل می‌شوند
    ↓
Export (CSV / JSON)
```

### مرحله ۱ — Fetch (دریافت صفحه)

`fetch_url()` ابتدا صفحه را با **httpx** (static fetch) دریافت می‌کند. اگر محتوای HTML کمتر از ۵۰۰ کاراکتر باشد (صفحه‌ای که بدون JavaScript خالی است)، سیستم به‌صورت خودکار سراغ **Playwright/Chromium** می‌رود و صفحه را بعد از اجرای JavaScript دریافت می‌کند.

سه حالت وجود دارد:
- `AUTO` — static اول، browser اگر محتوا کم بود
- `STATIC` — فقط static (سریع‌تر، بدون Playwright)
- `BROWSER` — فقط browser rendering

محدودیت‌های این مرحله: صفحه در `MAX_FETCH_BYTES` bytes بریده می‌شود (برای صفحات خیلی بزرگ). redirect‌ها به IPs خصوصی (مثل `192.168.x.x` یا `10.x.x.x`) بلاک می‌شوند.

### مرحله ۲ — DOM Summary (فشرده‌سازی ساختار)

**مشکل مهم:** کل HTML صفحه به AI داده نمی‌شود. یک خلاصه ساختاری ساخته می‌شود تا توکن مصرفی کم باشد.

تابع `build_dom_summary()` اینها را استخراج می‌کند:
- عنوان و meta description
- حداکثر **۸ heading** (h1/h2/h3)
- داده‌های **JSON-LD** (structured data سایت)
- حداکثر **۵ کلاس CSS** که بیشترین تکرار دارند (احتمالاً container آیتم‌ها)
- حداکثر **۱۲ لینک** نمونه
- کنترل‌های احتمالی **pagination** (دکمه‌های next/prev)
- یک snippet کوتاه از text بدنه صفحه

همه این‌ها به حداکثر **۴۰۰۰ کاراکتر** محدود می‌شوند.

**این محدودیت چه مشکلی ایجاد می‌کند؟** ساختارهای عمیق‌تر صفحه، فیلدهایی که در داخل nested divها هستند، و سلکتورهای پیچیده ممکن است از دید AI پنهان بمانند. → **این باید در فاز ۲ بهبود پیدا کند (بخش ۵ را ببین).**

### مرحله ۳ — AI Analysis (تحلیل با هوش مصنوعی)

`analyze_page()` از LiteLLM برای تحلیل استفاده می‌کند. LiteLLM یک abstraction layer است که بیش از ۱۰۰ پروویدر (OpenAI، Anthropic، Gemini، Ollama، و غیره) را با یک API یکسان پشتیبانی می‌کند.

دو حالت تحلیل وجود دارد:

**STRUCTURED mode** — برای صفحات listing (محصولات، مقالات، جدول‌ها):
```json
{
  "page_type": "listing",
  "repeated_item_selector": ".product-card",
  "candidate_fields": [
    {
      "name": "price",
      "selector": ".price",
      "data_type": "number",
      "confidence": 0.95,
      "sample_values": ["$19.99", "$24.50"]
    }
  ],
  "pagination_selector": ".next-page",
  "estimated_pages": 34,
  "confidence": 0.87
}
```

**CONTENT mode** — برای صفحات مقاله/بلاگ/RAG:
```json
{
  "content_type": "article",
  "primary_content_selector": "article.main-content",
  "recommended_chunking": "paragraph",
  "metadata_fields": [...]
}
```

**Cache:** اگر همان صفحه با همان پروویدر/مدل قبلاً آنالیز شده باشد، AI دوباره فراخوانده نمی‌شود. کلید cache = `(content_hash, extraction_mode, provider, model, analyzer_version)`.

### مرحله ۴ — Seed Extraction (استخراج نمونه)

**این مهم‌ترین محدودیت فاز ۱ است:**

در حال حاضر، سیستم CSS selector را واقعاً اجرا نمی‌کند. به جای آن، `sample_values` که AI در مرحله ۳ برگرداند را مستقیماً به ExtractedRecord تبدیل می‌کند.

یعنی اگر AI برای فیلد `price` مقادیر `["$19.99", "$24.50"]` را به عنوان نمونه برگرداند، دقیقاً همین ۲ رکورد در پایگاه داده ذخیره می‌شوند — نه تمام ۸۴۷ قیمت روی سایت.

**این یعنی:** خروجی فاز ۱ همیشه ۲ تا ۵ رکورد نمونه است، نه کل داده‌های سایت.

---

## ۲. روی چه سایت‌هایی کار می‌کند؟

| نوع سایت | وضعیت فعلی | توضیح |
| -------- | ---------- | ----- |
| سایت‌های static HTML ساده | ✅ کامل | بهترین عملکرد |
| سایت‌های JS-rendered (React/Vue/Next.js) | ✅ با Playwright | نیاز به نصب `playwright install chromium` |
| سایت‌های listing (محصولات، اخبار، جداول) | ✅ STRUCTURED mode | |
| سایت‌های مقاله/بلاگ/دانشنامه | ✅ CONTENT mode | |
| سایت‌هایی با robots.txt | ✅ رعایت می‌شود | اگر مسیر disallow باشد، بلاک می‌شود |
| سایت‌هایی که HTTPS دارند | ✅ | |
| سایت‌های نیاز به لاگین/auth | ❌ پشتیبانی نمی‌شود | فاز ۶ |
| سایت‌هایی با CAPTCHA | ❌ bypass نمی‌شود | عمداً — non-goal |
| APIهای JSON (بدون HTML) | ❌ | content-type باید HTML باشد |
| فایل‌های PDF | ❌ بلاک می‌شود | content-type مجاز نیست |
| IPs خصوصی (`192.168.x.x`، `10.x.x.x`) | ❌ بلاک می‌شود | SSRF protection |
| سایت‌های با Cloudflare/bot detection | ⚠️ کار می‌کند اما ناقص | صفحه challenge برگشت داده می‌شود |
| سایت‌های چند-صفحه‌ای (pagination) | ⚠️ فاز ۱: فقط صفحه اول | فاز ۲: کل سایت |

---

## ۳. چقدر هوشمند است؟

### چه چیزهایی هوشمندانه انجام می‌شود:

- **Auto render detection:** سیستم خودش می‌فهمد صفحه نیاز به JavaScript دارد یا نه
- **CSS selector discovery:** AI سلکتورها را از روی ساختار DOM پیشنهاد می‌دهد، نه hardcode
- **Confidence scoring:** هر فیلد یک عدد بین ۰ تا ۱ دارد که نشان می‌دهد AI چقدر مطمئن است
- **Page type detection:** listing vs detail vs content به‌صورت خودکار تشخیص داده می‌شود
- **Pagination detection:** دکمه‌های next/prev خودکار کشف می‌شوند
- **Analysis cache:** همان صفحه دوباره تحلیل نمی‌شود
- **Structured + Content dual mode:** برای هر دو نوع داده (جدولی یا متن) بهینه شده

### محدودیت‌های هوشمندی:

- AI فقط DOM summary می‌بیند، نه کل صفحه — ساختارهای پیچیده ممکن است از دستش برود
- Sample values که AI می‌دهد لزوماً دقیق نیستند — نمونه هستند، نه داده‌های واقعی
- برای صفحات بسیار dynamic که ساختار DOM ندارند، سلکتورها اشتباه پیشنهاد می‌شوند
- هر بار که layout سایت عوض شود، سلکتورها باید دوباره آنالیز شوند (فاز ۲: selector repair خودکار)

---

## ۴. مشکل داده‌های ناقص — دقیقاً کجاست؟

### مشکل ۱: Seed extraction = فقط نمونه AI، نه کل داده

**وضعیت فعلی:** خروجی extraction همان `sample_values` هستند که AI در prompt برگرداند. این ۲ تا ۵ نمونه هستند. برای یک dataset واقعی این کافی نیست.

**مثال:** سایت calories.info یک جدول بزرگ با صدها ردیف دارد، اما JavaScript آن را render می‌کند. در فاز ۱، فقط ۲ ردیفی که AI به عنوان نمونه پیشنهاد داد ذخیره می‌شوند — نه همه جدول.

**رفع در فاز ۲:** CSS selector واقعاً اجرا می‌شود روی تمام صفحات crawl شده.

---

### مشکل ۲: DOM Summary خیلی محدود است — کجاها باید بهتر شود

**وضعیت فعلی:** `build_dom_summary()` خیلی کوچک است:
- فقط ۸ heading
- فقط ۱۲ لینک
- فقط ۵ class CSS تکراری
- فقط ۶۰۰ کاراکتر متن
- کل چیزی که AI می‌بیند: ۴۰۰۰ کاراکتر

**نتیجه:** برای صفحات پیچیده:
1. سلکتورها اشتباه هستند چون AI ساختار واقعی DOM را ندیده
2. فیلدهایی که در عمق نستینگ هستند کشف نمی‌شوند
3. جداول بزرگ یا nested structures از دید AI پنهان می‌ماند

**پیشنهاد بهبود DOM Summary (باید پیاده‌سازی شود):**

| بهبود | توضیح |
| ----- | ----- |
| **نمونه‌برداری از ساختار جدول** | اگر `<table>` وجود دارد، ۲–۳ ردیف کامل به همراه header‌ها اضافه شود |
| **بیشتر repeated containers** | از ۵ به ۱۵ افزایش پیدا کند؛ تمام containerهایی که ۳+ بار تکرار می‌شوند مهم هستند |
| **نمونه‌برداری از nested items** | اگر `.product-card` یک container است، محتوای کامل یک نمونه از آن در summary باشد |
| **attribute scanning** | `data-*` attribute‌ها اغلب حاوی داده‌های مهم (ID، قیمت، دسته‌بندی) هستند |
| **افزایش حد کاراکتر** | از ۴۰۰۰ به ۸۰۰۰–۱۲۰۰۰ برسد — مدل‌های مدرن می‌توانند context بیشتری handle کنند |
| **chunk-based analysis** | برای صفحات خیلی پیچیده، DOM summary را بخش‌بخش کن و AI چندبار صدا بزن |

---

### مشکل ۳: فقط صفحه seed، نه کل سایت

وقتی URL می‌دهی، فقط همان صفحه آنالیز می‌شود. اگر سایت pagination دارد یا ۵۰ صفحه دارد، **هیچکدام از صفحات دیگر** fetch نمی‌شوند.

**رفع در فاز ۲:** BFS crawl — از صفحه اول شروع، تمام لینک‌ها کشف، هر صفحه extract می‌شود.

---

## ۵. تفاوت با Firecrawl و چرا ما می‌توانیم بهتر باشیم

| ویژگی | Firecrawl | ScrapGPT (فاز ۲) |
| ----- | --------- | ---------------- |
| روش extraction | هر صفحه → Markdown → LLM extract | AI یک‌بار ساختار را می‌فهمد، CSS همه صفحات را extract می‌کند |
| هزینه AI | برای هر صفحه یک LLM call | فقط برای آنالیز اولیه — نه per-page |
| داده خروجی | Markdown / unstructured text | فیلدهای typed و structured (number, string, url, date) |
| raw vs normalized | ندارد | raw_data همیشه حفظ می‌شود، normalized جدا |
| self-hosted | کد باز است، اما SaaS-first | کاملاً self-hosted، BYOK |
| field selection | ندارد — کل محتوا export می‌شود | کاربر دقیقاً انتخاب می‌کند چه فیلدهایی استخراج شوند |
| data quality | بسته به LLM، متغیر | سلکتور deterministic است — همیشه همان نتیجه |
| pagination | ✅ | ✅ (فاز ۲) |
| JS rendering | ✅ | ✅ (Playwright) |

**مزیت اصلی ما:** AI فقط برای درک ساختار استفاده می‌شود. استخراج واقعی با CSS selector انجام می‌شود — سریع، ارزان، و deterministic. Firecrawl و Crawl4AI برای هر صفحه LLM صدا می‌زنند. این در مقیاس بزرگ خیلی گران‌تر و کندتر است.

---

## ۶. فازهای بعدی — چه چیزی تغییر می‌کند

### فاز ۲ — Real Extraction Engine (مهم‌ترین فاز)

این فازی است که سیستم را از "نمونه‌نمایی" به "استخراج واقعی" تبدیل می‌کند.

**چه چیزی build می‌شود:**

- **BFS crawl:** از صفحه seed شروع، تمام لینک‌های هم‌دامنه را کشف می‌کند تا `MAX_PAGES_PER_JOB` (پیش‌فرض ۵۰۰) صفحه
- **CSS execution واقعی:** `lxml` + `cssselect` — سلکتوری که AI پیشنهاد داد روی همه صفحات اجرا می‌شود
- **Per-page crash recovery:** هر صفحه یک ردیف در دیتابیس است با `lease_expires_at`. اگر سرور کرش کند، watchdog صفحات stuck را reset می‌کند
- **Per-page failure isolation:** یک صفحه blocked → بقیه ادامه می‌دهند. یک job با ۱۰۰۰ صفحه که ۵ تا block شد، ۹۹۵ رکورد تحویل می‌دهد
- **Challenge detection:**
  - HTTP 429 → `RATE_LIMITED` — auto retry با exponential backoff
  - Cloudflare/CAPTCHA → `CHALLENGE_REQUIRED` — job pause، کاربر باید دستی resolve کند
  - 401/403 → `AUTH_REQUIRED`
  - Permanent block → `BLOCKED`
- **Selector repair:** اگر یک سلکتور N صفحه پشت‌هم چیزی برنگرداند، AI دوباره صدا زده می‌شود

**نتیجه:** برای یک سایت با ۵۰۰ محصول، فاز ۲ همه ۵۰۰ محصول را extract می‌کند، نه ۳ نمونه.

---

### بهبود DOM Summary (باید در فاز ۲ پیاده‌سازی شود)

این موردی است که تو مستقیماً اشاره کردی: "سیستم سامری هم باید تغییر بدیم تا اطلاعات ناقص نشه"

**پیشنهاد implementation برای `build_dom_summary()`:**

```python
# اضافه کردن به build_dom_summary:

# 1. نمونه کامل از repeated containers
containers = _repeated_containers(soup)
for cls in containers[:3]:
    sample_el = soup.find(class_=cls)
    if sample_el and isinstance(sample_el, Tag):
        # یک نمونه کامل از محتوای container
        parts.append(f"Sample item in .{cls}:\n{str(sample_el)[:500]}")

# 2. جداول — header + 2 ردیف نمونه
for table in soup.find_all("table")[:2]:
    headers = [th.get_text(strip=True) for th in table.find_all("th")]
    rows = table.find_all("tr")
    sample_rows = [
        [td.get_text(strip=True)[:50] for td in row.find_all("td")]
        for row in rows[1:3]  # 2 ردیف نمونه
    ]
    if headers:
        parts.append(f"Table headers: {headers}\nSample rows: {sample_rows}")

# 3. data-* attributes مهم
data_attrs = {}
for tag in soup.find_all(True):
    for attr, val in tag.attrs.items():
        if isinstance(attr, str) and attr.startswith("data-"):
            data_attrs[attr] = str(val)[:50]
if data_attrs:
    parts.append(f"Data attributes: {dict(list(data_attrs.items())[:10])}")

# 4. افزایش حد از 4000 به 10000
_MAX_SUMMARY_CHARS = 10000
```

---

### فاز ۴ — AI Normalization

بعد از extraction، یک مرحله اختیاری:
- تاریخ‌ها به فرمت یکسان تبدیل می‌شوند
- قیمت‌ها parse می‌شوند (حذف `$`, `,`)
- آدرس‌ها normalize می‌شوند
- `raw_data` هرگز تغییر نمی‌کند — normalization جدا ذخیره می‌شود

---

### فاز ۶ — Authenticated Crawling (پیچیده‌ترین)

- کاربر session cookie‌های مرورگر خودش را paste می‌کند
- سیستم از آن‌ها برای authenticated requests استفاده می‌کند
- CAPTCHA **خودکار حل نمی‌شود** (این عمداً non-goal است)
- Scheduled jobs: هر X ساعت/روز سایت دوباره scrape شود (site monitoring)

---

## ۷. خلاصه: الان چه می‌تواند و چه نمی‌تواند

### می‌تواند (Phase 1 — همین الان):
- ✅ هر URL عمومی را آنالیز کند و فیلدهای قابل استخراج پیشنهاد دهد
- ✅ ساختار صفحه، نوع محتوا، و pagination را خودکار تشخیص دهد
- ✅ صفحات JavaScript-rendered را با Playwright بخواند
- ✅ ۲–۵ رکورد نمونه به عنوان preview نشان دهد
- ✅ به‌عنوان proof-of-concept یا validation tool عالی است
- ✅ Cache کند تا برای URL یکسان دوباره AI فراخوانده نشود
- ✅ داده را به CSV/JSON export کند

### نمی‌تواند (فاز ۱):
- ❌ همه محصولات/ردیف‌های یک سایت را extract کند (فقط ۲–۵ نمونه)
- ❌ از صفحه ۱ به صفحه ۲، ۳، ... برود (multi-page crawl نیست)
- ❌ وارد سایت‌های نیاز به login شود
- ❌ CAPTCHA حل کند
- ❌ PDF یا محتوای غیر HTML بخواند
- ❌ برای ساخت dataset کامل استفاده شود

### می‌تواند (Phase 2 — باید build شود):
- ✅ کل سایت را crawl کند (BFS، صفحه‌بندی را دنبال کند)
- ✅ CSS selector واقعی روی همه صفحات اجرا کند
- ✅ هزاران رکورد extract کند
- ✅ در صورت crash از آخرین صفحه ادامه دهد
- ✅ صفحات blocked را مدیریت کند بدون اینکه کل job شکست بخورد
- ✅ برای dataset collection واقعی استفاده شود

---

## ۸. آیا API key رایگان برای اسکریپینگ کافی است؟

این سوال مهمی است — چون سیستم ما BYOK است و کاربر باید خودش key بدهد. پاسخ واضح است: **Google AI Studio بله، OpenRouter رایگان خیر.**

---

### Google AI Studio — Gemini (رایگان)

| معیار | مشخصات |
| ----- | ------- |
| مدل پیشنهادی | Gemini 2.0 Flash / Gemini 2.5 Flash |
| RPM (درخواست در دقیقه) | ۱۵ |
| RPD (درخواست در روز) | ۱,۵۰۰ |
| TPM (توکن در دقیقه) | ۱,۰۰۰,۰۰۰ |
| Context window | ۱,۰۰۰,۰۰۰ توکن |
| JSON / Structured output | ✅ کاملاً پشتیبانی می‌شود — schema enforced |
| قابلیت اطمینان | بسیار بالا — مستقیم از Google، بدون queue |
| نیاز به کارت بانکی | ❌ ندارد |

**آیا ۱۵ RPM و ۱,۵۰۰ RPD برای اسکریپینگ کافی است؟**

ما **AI را فقط برای آنالیز اولیه** صدا می‌زنیم، نه هر صفحه. یک سایت با ۵۰۰ صفحه = **۱ تا ۳ بار AI call** (یک‌بار برای seed page، شاید یک‌بار برای template دیگر).

حساب:
- ۱۵ RPM = می‌توانی ۱۵ پروژه در ۱ دقیقه استارت بزنی
- ۱,۵۰۰ RPD = می‌توانی ۱,۵۰۰ پروژه در روز آنالیز کنی
- Selector repair (اگر فعال) = چند call اضافه در حین crawl

**نتیجه: برای استفاده شخصی و حتی تیم‌های کوچک، Google AI Studio رایگان کاملاً کافی است.**

⚠️ نقطه ضعف: اگر سرعت رو بخوای زیاد کنی و بخوای ۵۰+ پروژه همزمان استارت بزنی، به پلن پولی نیاز داری. اما برای معمول‌ترین use case ها، رایگان کار می‌کند.

---

### OpenRouter (رایگان — tier بدون شارژ)

| معیار | مشخصات |
| ----- | ------- |
| RPM (روی کاغذ) | ۲۰ |
| RPD (بدون شارژ حساب) | **۵۰ در روز** |
| RPD (بعد از ۱۰ دلار شارژ) | ۱,۰۰۰ در روز |
| JSON / Structured output | ⚠️ وابسته به مدل — ضمانت ندارد |
| خطای ۴۲۹ در عمل | 🔴 بسیار زیاد — حتی برای کاربران پولی |
| قابلیت اطمینان | ضعیف |

**مشکل اصلی OpenRouter رایگان:**
- ۵۰ RPD بیشتر از ۵۰ پروژه در روز نمی‌توانی آنالیز کنی
- خطاهای ۴۲۹ حتی در ساعات غیر شلوغ گزارش می‌شوند
- یک retry loop می‌تواند کل سهمیه روزانه را ظرف چند دقیقه تمام کند (چون حتی درخواست‌های failed هم از quota کم می‌شوند)
- مدل‌های رایگان دائماً deprecate می‌شوند (`gemini-2.0-flash-exp:free` در فوریه ۲۰۲۶ deprecated شد)
- Structured JSON output روی مدل‌های رایگان OpenRouter ناپایدار است

**نتیجه: OpenRouter رایگان برای تست و prototype مناسب است. برای هر چیزی که واقعاً بخواهی کار کند، استفاده نکن.**

---

### جدول مقایسه سریع

| معیار | Google AI Studio (رایگان) | OpenRouter (رایگان) |
| ----- | ------------------------- | ------------------- |
| مناسب production | ✅ بله | ❌ خیر |
| Structured output مطمئن | ✅ | ⚠️ ناپایدار |
| ۵۰ پروژه در روز | ✅ آسان | ❌ حد سقف |
| خطای ۴۲۹ | نادر | بسیار رایج |
| model stability | ✅ | ⚠️ مدل‌ها deprecate می‌شوند |
| توصیه | **اول انتخاب کن** | فقط برای تست |

---

### چه provider ای برای کاربران جدی توصیه می‌شود؟

| بودجه | توصیه |
| ----- | ----- |
| رایگان | **Google AI Studio** با Gemini 2.0 Flash |
| پولی کم | **OpenRouter** با ۱۰ دلار شارژ + مدل‌های paid (مثل `google/gemini-2.0-flash`) |
| پولی جدی | مستقیم از **OpenAI** یا **Anthropic** یا **Google Vertex AI** |
| محلی (بدون API) | **Ollama** با مدل‌های local مثل `llama3.2` یا `qwen2.5-coder` — رایگان اما کندتر |

> **نکته مهم برای تو:** چون می‌خواهی یک سیستم متمایز بسازی، کاربران target تو احتمالاً developer هستند که API key دارند یا می‌توانند بگیرند. Google AI Studio برای آن‌ها کاملاً رایگان و کافی است — هیچ مانعی وجود ندارد.

---

## ۹. نتیجه‌گیری: آیا این همان چیزی است که می‌خواهی؟

**اگر می‌خواهی داده‌های واقعی در مقیاس بزرگ جمع‌آوری کنی:**
→ فاز ۱ به تنهایی کافی نیست. فاز ۲ (Real Extraction Engine) باید build شود.

**اگر می‌خواهی بهتر از Firecrawl باشی:**
→ مزیت اصلی ما AI-once + CSS-everywhere است. این را باید در UI و README به وضوح توضیح دهیم.

**اگر می‌خواهی داده‌ها کامل و با کیفیت بالا باشند:**
→ باید DOM Summary بهبود پیدا کند (جداول، nested containers، data attributes). این یک تغییر نسبتاً کوچک در `dom_summary.py` است اما تأثیر بزرگی روی کیفیت تحلیل AI دارد.

**پیشنهاد ترتیب اولویت‌ها:**
1. بهبود `build_dom_summary()` (سریع، تأثیر فوری روی کیفیت)
2. فاز ۲ — Real CSS extraction + BFS crawl (اصلی‌ترین feature)
3. بهبود UI برای نشان دادن تفاوت Phase 1 (preview/sample) vs Phase 2 (real extraction)
