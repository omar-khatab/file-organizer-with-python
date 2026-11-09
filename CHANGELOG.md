# Changelog - File Organizer

كل النسخ هنا محفوظة كرحلة. النسخة الحالية المعتمدة هي **v3.2**.

---

## v3.2 - الحالية (PySide6 GUI) ✅
**الملف:** `Organize-PySide6.py`

- واجهة PySide6 Dark Theme + Drag & Drop
- Live Watch - بينظم الملفات الجديدة أول بأول
- Auto Organize كل X دقيقة - Watch + Auto شغالين مع بعض
- History بـ SQLite + Undo لآخر عملية
- Dry-run Preview
- System Tray + Start with Windows + Run in background
- Right-Click Integration: نظم أي فولدر من Explorer
- أمان: مفيش overwrite، بيتخطى الملفات المحمية والمخفية و `desktop.ini` و `Thumbs.db`
- Downloads/Desktop بيتجابوا من Windows Shell (شغال صح مع OneDrive)
- عربي / إنجليزي

**التفاصيل الكاملة لـ v3.2.4:**
- History فيه Type بدل ID: Watch / Auto / Manual
- قفل البرنامج بيقفل بجد (مفيش Zombie Process)
- Watch مش بيعمل صف فاضي كل دقيقة
- Undo مقفول طول ما Watch شغال
- زرار Right-Click بقى Toggle

---

## v2 - Organize-All (CLI - مرحلة التطور)
**الملف القديم:** `Organize-All.py` → دلوقتي في `legacy/v2-all/`

- قايمة تفاعلية: اختار Downloads / Desktop / Both / Custom Folder
- Preview بـ `--dry-run` قبل ما ينقل أي حاجة
- Right-Click Integration لأول مرة
- حماية: بيرفض `C:\` و Home و Windows و Program Files
- 11 تصنيف - 60+ امتداد
- مفيش overwrite: `file.txt` → `file (1).txt`

---

## v1 - البداية (CLI - ملفات منفصلة)
**الملفات القديمة:**
- `Organize-Downloads.py` → دلوقتي في `legacy/v1-downloads/`
- `Organize-Desktop.py` → دلوقتي في `legacy/v1-desktop/`

- كل ملف بينظم فولدر واحد بس
- أول نسخة اتعملت عشان تنضف Downloads و Desktop
- فكرة التصنيفات الـ 11 بدأت من هنا

---

## ملحوظة عن v3.3
كان فيه Release اتعمل باسم v3.3 بالغلط، واتلغى.
النسخة المعتمدة هي **v3.2**، ومفيش v3.3.
