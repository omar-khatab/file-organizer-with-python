# 📁 File Organizer with Python

> Windows-focused file automation that organizes Desktop, Downloads, and any folder into 11 clean categories. Built to clean up my own cluttered Downloads folder — and I still use it daily.

**Current Version: v3.2 - PySide6 GUI**

One file, zero setup. Download and double-click.

---

## 🚀 Quick Start - v3.2

### Option 1: Python (GUI)

```bash
pip install PySide6
python Organize-PySide6.py
```

### CLI (same file)

```bash
python Organize-PySide6.py --watch
python Organize-PySide6.py --auto 60
python Organize-PySide6.py --downloads
python Organize-PySide6.py --desktop
python Organize-PySide6.py --both
```

---

## ✨ Features - v3.2

- **Dark GUI + Drag & Drop** - Drop any folder to organize it
- **Live Watch** - Organizes new files automatically
- **Auto Organize** - Every X minutes, works together with Watch
- **History + Undo** - Every operation is logged in SQLite and can be undone
- **Dry-run Preview** - See what will happen before moving anything
- **System Tray + Start with Windows**
- **Right-Click Integration** - Right-click any folder -> Organize
- **Safe** - No overwrite, skips protected and hidden files
- **Smart Paths** - Works correctly with OneDrive and moved folders
- **English / Arabic**

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

- `get_unique_path()` -> `file.txt` -> `file (1).txt` - No overwrite
- Skips itself, skips already-organized folders (`00_*`, `01_*`...)
- Protected paths blocked: `C:\`, Home, `Windows`, `Program Files`
- Skips `desktop.ini`, `Thumbs.db`, hidden + system files

---

## 🛤️ My Journey

This project was built in stages. Every stage is preserved in `legacy/`:

### v1 - The Beginning
- `legacy/v1-downloads/Organize-Downloads.py` - Organizes Downloads only
- `legacy/v1-desktop/Organize-Desktop.py` - Organizes Desktop only

### v2 - Evolution
- `legacy/v2-all/Organize-All.py` - Interactive menu, choose the folder, Preview, Right-Click for the first time

### v3.2 - Current
- `Organize-PySide6.py` - Full GUI, Watch, Auto, History, Undo

See `CHANGELOG.md` for full details.

---

## 📁 Project Structure

```
file-organizer-with-python/
├── Organize-PySide6.py      # v3.2 - Current - GUI
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
MIT License - see LICENSE
Copyright (c) 2026 Omar Khatab

## 👨‍💻 Author
**Omar Khatab**
- GitHub: @omar-khatab

Built for myself, shared for everyone. If it saved you 5 minutes, give it a star!
