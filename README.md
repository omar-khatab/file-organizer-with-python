# File Organizer with Python

> A clean, automated Python utility to organize cluttered Desktop and Downloads folders.

[[Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://python.org)
[[License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

**GitHub:** [github.com/omar-khatab/file-organizer-with-python](https://github.com/omar-khatab/file-organizer-with-python)

---

## 🚀 Overview

Simple Python scripts to automatically organize messy Desktop and Downloads folders into 11 categorized directories.

No dependencies - uses only Python standard library (`pathlib`, `shutil`, `os`).

---

## ✨ Features

- **11 Categories** - 40+ file extensions (PDFs, Images, Code, Shortcuts, Others)
- **Duplicate Handling** - Never overwrites: `report.pdf` → `report (1).pdf`
- **Dry-Run Mode** - Preview before moving
- **Preserves Folders** - Only moves files
- **Clean Desktop** - Organizes into `00_Desktop_Organized` to keep desktop clean
- **Unknown Files** - Goes to `11_Others_Unknown`

---

## 📁 Project Structure

```
file-organizer-with-python/
├── Organize-Desktop.py        # Desktop organizer
├── Organize-Downloads.py      # Downloads organizer
├── README.md
└── LICENSE
```

---

## 📦 Installation

```bash
git clone https://github.com/omar-khatab/file-organizer-with-python.git
cd file-organizer-with-python
```

Requires Python 3.8+

---

## 🎯 Usage

### 1. Desktop Organizer

```bash
python Organize-Desktop.py
```

**Before:**
```
Desktop/
├── report.pdf
├── photo.jpg
└── script.py
```

**After:**
```
Desktop/
└── 00_Desktop_Organized/
    ├── 01_PDFs/report.pdf
    ├── 05_Images/photo.jpg
    └── 09_Code/script.py
```

Enable dry-run:
```python
organize_desktop(dry_run=True, move_shortcuts=False)
```

### 2. Downloads Organizer

```bash
python Organize-Downloads.py
```

```
Downloads/
├── 01_PDFs/
├── 05_Images/
├── 09_Code/
├── 10_Shortcuts/
└── 11_Others_Unknown/
```

Enable dry-run:
```python
organize(dry_run=True)
```

---

## 🗂️ Categories

| Folder | Extensions |
|--------|------------|
| `01_PDFs` | `.pdf` |
| `02_Word_Docs` | `.doc`, `.docx`, `.txt` |
| `03_Excel_Sheets` | `.xls`, `.xlsx`, `.csv` |
| `04_PowerPoint` | `.ppt`, `.pptx` |
| `05_Images` | `.jpg`, `.png`, `.gif`, `.svg`, `.webp`, `.ico` |
| `06_Zip_Files` | `.zip`, `.rar`, `.7z`, `.tar`, `.gz` |
| `07_Programs` | `.exe`, `.msi`, `.dmg`, `.apk` |
| `08_Videos` | `.mp4`, `.mkv`, `.mov`, `.avi`, `.wmv` |
| `09_Code` | `.py`, `.js`, `.ts`, `.java`, `.cpp`, `.html`, `.css`, `.json`, `.xml`, `.yml`, `.sql`, `.ipynb` + more |
| `10_Shortcuts` | `.lnk`, `.url` |
| `11_Others_Unknown` | Any other extension |

---

## 🧠 How It Works

**1. Collision Handling**
```python
def get_unique_path(dest):
    # report.pdf -> report (1).pdf
```

**2. Organization Logic**
```python
for item in DOWNLOADS_PATH.iterdir():
    if item.is_dir():
        continue
    target = CATEGORIES.get(ext) or UNKNOWN_FOLDER
    shutil.move(item, target)
```

---

## 🛡️ Safety

- Dry-run preview
- Skips the script itself
- Preserves all folders
- No overwrite
- Try/except for errors

---

## 👨‍💻 Author

**Omar Khatab** - [GitHub](https://github.com/omar-khatab)

Mechanical Power Engineering (Ain Shams University)

---

## ⭐ Support

If this helped you, give it a ⭐ on GitHub!
