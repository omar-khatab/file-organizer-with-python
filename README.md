# 📁 File Organizer with Python

[[Build](https://github.com/omar-khatab/file-organizer-with-python/actions/workflows/build.yml/badge.svg)](https://github.com/omar-khatab/file-organizer-with-python/actions/workflows/build.yml)
[[Release](https://img.shields.io/github/v/release/omar-khatab/file-organizer-with-python?color=blue)](https://github.com/omar-khatab/file-organizer-with-python/releases)
[[License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[[Windows](https://img.shields.io/badge/Platform-Windows-0078D6.svg)](https://github.com/omar-khatab/file-organizer-with-python)
[[Python](https://img.shields.io/badge/Python-3.8%2B-3776AB.svg)](https://www.python.org/)

> Windows-focused file automation that organizes Desktop, Downloads, and any folder into 11 clean categories. Built to clean up my own cluttered Downloads folder — and I still use it daily.

**One file, zero setup. Download and double-click.**

---

## ✨ Why this exists

I was tired of a messy Desktop and Downloads. So I built a tool I actually use every day:

- **No dependencies, no `common.py`, no `pip install`** — each `.py` is 100% standalone
- **Double-click friendly** — window stays open, shows what it did
- **Right-click any folder** → `Organize with File Organizer`
- **Safe** — never overwrites: `file.txt` → `file (1).txt`

---

## 🚀 Quick Start

### Option 1: EXE (no Python needed) — Recommended for most users

1. Go to [Releases](https://github.com/omar-khatab/file-organizer-with-python/releases)
2. Download `Organize-All.exe`
3. Double-click → Choose `[3] Both` or `[8] Install right-click menu`

> **SmartScreen warning?** The `.exe` is built with PyInstaller and not code-signed, so Windows shows "Unknown publisher". This is normal. Click `More info → Run anyway`. Source is fully open here.

### Option 2: Python (one file)

```bash
# Just download ONE file and run it
python Organize-All.py          # interactive menu
python Organize-Downloads.py    # Downloads only
python Organize-Desktop.py      # Desktop only
```

---

## 📸 Features

### 🧠 Smart path detection
- **Desktop:** checks `~/Desktop`, `~/OneDrive/Desktop`, and Registry via `winreg` — works even if OneDrive moved it
- **Downloads:** `Path.home() / "Downloads"`
- **Custom:** right-click any folder, or run `python Organize-All.py "C:\MyFolder"`

### 📂 11 Unified Categories — 60+ extensions

| Folder | Extensions |
|--------|------------|
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
- `get_unique_path()` → prevents overwrites: `file.txt` → `file (1).txt`
- Skips itself (works as `.py` and `.exe`)
- Skips already-organized folders (`00_*`, `01_*`...)
- Preserves all subfolders
- **Shortcuts are OFF by default** — Desktop icons stay where they are unless you use `--move-shortcuts`
- **Protected paths blocked** — refuses to organize drive roots (`C:\`), Home, `Windows`, `Program Files`
- **Right-click shows preview + asks for confirmation** before moving anything

---

## 🎮 Usage

### Interactive Menu (double-click)

```
==================================================
  File Organizer - Unified v2.4
  Omar Khatab
==================================================
Downloads: C:\Users\Omar\Downloads
Desktop:   C:\Users\Omar\OneDrive\Desktop

Choose what to organize:
  [1] Downloads only
  [2] Desktop only
  [3] Both (Downloads + Desktop)
  [4] Custom folder (enter path)
  [5] Preview Downloads (--dry-run)
  [6] Preview Desktop (--dry-run)
  [7] Preview Both (--dry-run)
  [8] Install right-click menu
  [9] Uninstall right-click menu
  [0] Exit
```

### Right-Click Integration ⭐

**Install once:**
```bash
python Organize-All.py --install-context-menu
# or from menu: [8]
```

Then right-click any folder in Explorer:
> `Organize with File Organizer`

**What happens when you right-click:**
1. Safety check → blocks `C:\`, `C:\Windows`, `Program Files`, Home
2. Dry-run preview → shows what would move
3. Confirmation → `Proceed? (y/n)`

**Registry details (safe, user-only):**
- Writes to `HKCU\Software\Classes\Directory\shell\FileOrganizer` (current user only, no admin needed)
- Stores full path to the exe/py
- No admin required because it's `HKEY_CURRENT_USER`, not `HKEY_LOCAL_MACHINE`

**Uninstall:**
```bash
python Organize-All.py --uninstall-context-menu
# or [9]
```

> ⚠️ **Important:** The right-click button saves the current exe path. Put the program in a permanent folder (e.g., `C:\Tools\FileOrganizer\`) **before** installing. If you move or delete the exe after install, the button will break — just reinstall from the new location.

### SmartScreen / Antivirus Note

The `.exe` files are built with PyInstaller and are **not code-signed**, so Windows may show:
> "Windows protected your PC" / "Unknown publisher"

This is normal for unsigned PyInstaller binaries. Click `More info → Run anyway` if you trust the source. Source code is fully open here for review. If flagged by antivirus, you can build the exe yourself (see below) — same code, built on your machine.

### Safety & Scope

This tool only organizes **files in the top level** of the target folder. It never deletes, never goes recursive into subfolders.

Protected locations (blocked automatically):
- Drive roots: `C:\`, `D:\`
- User home: `C:\Users\You`
- `C:\Windows`, `C:\Program Files`, `C:\Program Files (x86)`

If you right-click a project folder, you'll see a preview first and must confirm.

### Command Line Flags

```bash
# Preview without moving (always safe)
python Organize-All.py --dry-run --both
python Organize-Downloads.py --dry-run
python Organize-Desktop.py --dry-run

# Organize specific (shortcuts OFF by default = safe for Desktop)
python Organize-All.py --downloads
python Organize-All.py --desktop
python Organize-All.py --both

# Include shortcuts (.lnk, .url) -> 10_Shortcuts
python Organize-All.py --both --move-shortcuts
python Organize-All.py "D:\My Messy Folder" --move-shortcuts

# Any folder (right-click does this: preview + confirm)
python Organize-All.py "D:\My Messy Folder"
python Organize-All.py "D:\My Messy Folder" --dry-run
```

---

## 🛠️ Build EXE yourself

```bash
pip install pyinstaller

pyinstaller --onefile --name Organize-All Organize-All.py
pyinstaller --onefile --name Organize-Downloads Organize-Downloads.py
pyinstaller --onefile --name Organize-Desktop Organize-Desktop.py

# EXEs will be in dist/
```

GitHub Actions builds automatically on every tag `v*`:
- `.github/workflows/build.yml` → builds 3 EXEs → creates Release

---

## 📁 Project Structure

```
file-organizer-with-python/
├── Organize-All.py              # ⭐ Unified - menu + right-click + any folder
├── Organize-Desktop.py          # Desktop only - standalone
├── Organize-Downloads.py        # Downloads only - standalone
├── .github/
│   └── workflows/
│       └── build.yml            # Builds 3 EXEs on tag push
├── README.md
└── LICENSE
```

**Design principle:** Duplication of `CATEGORIES` across files is intentional. It avoids `ImportError: No module named common` for regular users who download a single file. Each file must work alone.

---

## 🤝 Contributing

PRs welcome! Ideas:
- [ ] Custom categories via `organizer.json`
- [ ] Undo feature
- [ ] Linux/macOS support
- [ ] File age filter (organize only files older than X days)

---

## 📄 License

MIT License — see [LICENSE](LICENSE)

Copyright (c) 2026 Omar Khatab

---

## 👨‍💻 Author

**Omar Khatab**

- GitHub: [@omar-khatab](https://github.com/omar-khatab)
- Project: [file-organizer-with-python](https://github.com/omar-khatab/file-organizer-with-python)

Built for myself, shared for everyone. If it saved you 5 minutes, give it a ⭐!

---

### Before / After

**Before:**
```
Desktop/
  report.pdf, IMG_1234.jpg, setup.exe, notes.txt, presentation.pptx,
  archive.zip, video.mp4, app.lnk, randomfile.xyz, ... (200+ files)
```

**After:**
```
Desktop/
  00_Desktop_Organized/
    01_PDFs/ report.pdf
    05_Images/ IMG_1234.jpg
    07_Programs/ setup.exe
    02_Documents/ notes.txt
    04_Presentations/ presentation.pptx
    06_Archives/ archive.zip
    08_Videos/ video.mp4
    10_Shortcuts/ app.lnk
    11_Others/ randomfile.xyz
```
