# File Organizer with Python

Windows-focused file automation that organizes Desktop and Downloads into 11 clean categories. Built to clean up my own cluttered Downloads folder, and I still use it daily.

## Why standalone?

**Each script is standalone by design: download one file and run it, no setup.**

No `common.py`, no dependencies. Duplication of categories is intentional to avoid `ImportError` for regular users.

## Features

- **Smart path detection**
  - Desktop: `~/Desktop`, `~/OneDrive/Desktop`, Registry fallback via `winreg`
  - Downloads: `Path.home() / "Downloads"`
- **11 unified categories, 60+ extensions**
  - `01_PDFs`, `02_Documents`, `03_Sheets`, `04_Presentations`, `05_Images`, `06_Archives`, `07_Programs`, `08_Videos`, `09_Code`, `10_Shortcuts`, `11_Others`
- **Safe**
  - `get_unique_path()`: `file.txt` → `file (1).txt`
  - True `--dry-run` with `argparse`
  - Skips itself (works as .py and .exe), preserves folders

## Usage

### Python version
```bash
python Organize-Downloads.py --dry-run
python Organize-Downloads.py
python Organize-Desktop.py --dry-run --move-shortcuts
```

### EXE version (no Python needed)

1. Download `Organize-Downloads.exe` or `Organize-Desktop.exe` from [Releases](https://github.com/omar-khatab/file-organizer-with-python/releases)
2. Place it in Downloads/Desktop folder and double-click
3. Or run from terminal with `--dry-run` flag

> **Note on Windows SmartScreen / Antivirus:** The `.exe` files are built with PyInstaller and are not code-signed, so Windows may show a SmartScreen warning ("Unknown publisher") or your antivirus may flag it. This is normal for unsigned PyInstaller binaries. You can click "More info" → "Run anyway" if you trust the source. Source code is fully available here for review.

## Flags

- `--dry-run`: preview only
- `--move-shortcuts`: include `.lnk`, `.url` (Desktop only)

## Build EXE yourself

```bash
pip install pyinstaller
pyinstaller --onefile --name Organize-Downloads Organize-Downloads.py
pyinstaller --onefile --name Organize-Desktop Organize-Desktop.py
```

## Structure

```
├── Organize-Desktop.py
├── Organize-Downloads.py
├── .github/workflows/build.yml
└── README.md
```
