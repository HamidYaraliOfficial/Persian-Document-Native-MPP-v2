# Persian Document → Native MPP v2

نسخه ۲ بدون نیاز به Microsoft Project فایل **Native Microsoft Project `.mpp`** تولید می‌کند.

## معماری

- Python/FastAPI: دریافت فایل، استخراج PDF/DOCX، تحلیل فارسی و WBS
- OfficeIMO.Project 3.4.4: موتور managed برای authoring فایل‌های MPP
- .NET 8: اجرای موتور Native MPP
- Frontend: رابط فارسی RTL مستقل، Drag & Drop، پیش‌نمایش WBS، Timeline و JSON

## نیازمندی‌ها

- Windows
- Python 3.11+
- .NET 8 SDK
- اینترنت در اولین `dotnet build` برای دریافت بسته OfficeIMO.Project

**Microsoft Project لازم نیست.**

## اجرا

ابتدا:

```powershell
pip install -r requirements.txt
```

سپس ساده‌ترین روش:

```text
run_v2.bat
```

یا دستی:

```powershell
dotnet build native_writer/native_mpp_writer.csproj -c Release
python -m uvicorn persian_doc_to_mpp.api:app --host 127.0.0.1 --port 8080
```

مرورگر:

`http://127.0.0.1:8080`

## استفاده به‌عنوان ماژول

```python
from persian_doc_to_mpp.module import convert

result = convert(
    "project.docx",
    "project.mpp",
    project_name="پروژه توسعه سامانه",
)
print(result.output)
```

## فرمت ورودی

PDF متنی و DOCX پشتیبانی می‌شوند. عددهای فارسی/عربی، تاریخ شمسی، تیترها، لیست‌ها و جدول‌های دارای ستون‌هایی مثل `فعالیت، مدت، شروع، پایان، پیش‌نیاز، مسئول، توضیحات` تحلیل می‌شوند.

فایل‌های PDF اسکن‌شده بدون لایه متن در این نسخه نیاز به OCR جداگانه دارند. فایل `.doc` قدیمی نیز بدون Microsoft Word عمداً پردازش نمی‌شود؛ آن را به `.docx` تبدیل کنید.

## خروجی

خروجی با پسوند `.mpp` و generation مدرن MPP14 ساخته می‌شود. موتور OfficeIMO.Project در مستندات خود authoring نسل‌های MPP 8/9/12/14 را بدون COM و بدون Microsoft Project اعلام کرده است.
