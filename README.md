# 📁 File Organizer with Python

> Windows-focused file automation that organizes Desktop, Downloads, and any folder into 11 clean categories. Built to clean up my own cluttered Downloads folder — and I still use it daily.

**Current Version: v3.2 - PySide6 GUI ✅**

One file, zero setup. Download and double-click.

---

## 🚀 Quick Start - النسخة الحالية v3.2

### Option 1: Python (GUI)

```bash
pip install PySide6
python Organize-PySide6.py
```

### CLI (نفس الملف)

```bash
python Organize-PySide6.py --watch
python Organize-PySide6.py --auto 60
python Organize-PySide6.py --downloads
python Organize-PySide6.py --desktop
python Organize-PySide6.py --both
```

---

## ✨ Features - v3.2

- **Dark GUI + Drag & Drop** - اسحب أي فولدر ونظمه
- **Live Watch** - بينظم الملفات الجديدة لوحده
- **Auto Organize** - كل X دقيقة، وشغال مع Watch مع بعض
- **History + Undo** - كل عملية متسجلة في SQLite وتقدر ترجعها
- **Dry-run Preview** - شوف هيعمل إيه قبل ما ينقل
- **System Tray + Start with Windows**
- **Right-Click** - كليك يمين على أي فولدر → Organize
- **Safe** - مفيش overwrite، بيتخطى الملفات المحمية والمخفية
- **Smart Paths** - شغال صح مع OneDrive والفولدرات المنقولة
- **عربي / إنجليزي**

### 📂 11 Categories - 60+ extensions

| Folder | Extensions |
| --- | --- |
| `01_PDFs` | `.pdf` |
| `02_Documents` | `.doc`, `.docx`, `.odt`, `.rtf`, `.txt` |
| `03_Sheets` | `.xls`, `.xlsx`, `.csv`, `.ods` |
| `04_Presentations` | `.ppt`, `.pptx`, `.odp` |
| `05_Images` | `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.svg`, `.webp`, `.ico` |
| `06_Archives` | `.zip`, `.rar`, `.7z`, `.tar`, `.gz` |
| `07_Programs` | `.exe`, `.msi`, `.dmg`, `.apk` |
| `08_Videos` | `.mp4`, `.mkv`, `.mov`, `.avi`, `.wmv` |
| `09_Code` | `.py`, `.js`, `.ts`, `.java`, `.cpp`, `.html`, `.css`, `.json`, `.yml`, `.sql`, `.sh`, `.ipynb` + 20 more |
| `10_Shortcuts` | `.lnk`, `.url` |
| `11_Others` | everything else |

### 🛡️ Safe by design

- `get_unique_path()` → `file.txt` → `file (1).txt` - مفيش overwrite
- Skips itself, skips already-organized folders (`00_*`, `01_*`...)
- Protected paths blocked: `C:\`, Home, `Windows`, `Program Files`
- Skips `desktop.ini`, `Thumbs.db`, hidden+system files

---

## 🛤️ My Journey - الرحلة

البرنامج ده اتبنى على مراحل، وكل مرحلة محفوظة في `legacy/`:

### v1 - البداية
- `legacy/v1-downloads/Organize-Downloads.py` - بينظم Downloads بس
- `legacy/v1-desktop/Organize-Desktop.py` - بينظم Desktop بس

### v2 - التطور
- `legacy/v2-all/Organize-All.py` - قايمة تفاعلية، بتختار الفولدر، Preview، Right-Click لأول مرة

### v3.2 - الحالية ✅
- `Organize-PySide6.py` - GUI كامل، Watch، Auto، History، Undo

شوف `CHANGELOG.md` للتفاصيل الكاملة.

---

## 📁 Project Structure

```
file-organizer-with-python/
├── Organize-PySide6.py      # ⭐ v3.2 - Current - GUI
├── README.md
├── CHANGELOG.md
├── LICENSE
└── legacy/
    ├── v1-downloads/
    │   └── Organize-Downloads.py  # v1 - Downloads only
    ├── v1-desktop/
    │   └── Organize-Desktop.py    # v1 - Desktop only
    └── v2-all/
        └── Organize-All.py        # v2 - Interactive menu
```

---

## 📄 License
MIT License — see LICENSE
Copyright (c) 2026 Omar Khatab

## 👨‍💻 Author
**Omar Khatab**
- GitHub: @omar-khatab

Built for myself, shared for everyone. If it saved you 5 minutes, give it a ⭐!
