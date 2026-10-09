"""
File Organizer - Desktop Organizer (Windows)
Author: Omar Khatab
Description: Built to clean up my own cluttered Desktop, and I still use it myself.
Design: Each script is standalone by design: download one file and run it, no setup.
"""

import argparse
import os
import shutil
import sys
from pathlib import Path

CATEGORIES = {
    "01_PDFs": [".pdf"],
    "02_Documents": [".doc", ".docx", ".odt", ".rtf", ".txt"],
    "03_Sheets": [".xls", ".xlsx", ".csv", ".ods"],
    "04_Presentations": [".ppt", ".pptx", ".odp"],
    "05_Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".ico"],
    "06_Archives": [".zip", ".rar", ".7z", ".tar", ".gz"],
    "07_Programs": [".exe", ".msi", ".dmg", ".apk"],
    "08_Videos": [".mp4", ".mkv", ".mov", ".avi", ".wmv"],
    "09_Code": [
        ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".cpp", ".c", ".h", ".hpp",
        ".cs", ".go", ".rb", ".php", ".html", ".css", ".scss", ".json", ".xml",
        ".yml", ".yaml", ".sql", ".sh", ".bat", ".ps1", ".ipynb", ".dart",
        ".kt", ".swift", ".rs"
    ],
    "10_Shortcuts": [".lnk", ".url"],
}

UNKNOWN_FOLDER = "11_Others"

def get_unique_path(destination: Path) -> Path:
    if not destination.exists():
        return destination
    stem, suffix, parent = destination.stem, destination.suffix, destination.parent
    counter = 1
    while True:
        new_path = parent / f"{stem} ({counter}){suffix}"
        if not new_path.exists():
            return new_path
        counter += 1


HOME = Path.home()

def find_desktop() -> Path:
    candidates = [
        HOME / "Desktop",
        HOME / "OneDrive" / "Desktop",
        Path(r"C:\Users") / os.getlogin() / "OneDrive" / "Desktop" if os.name == "nt" else None,
    ]
    for path in candidates:
        if path and path.exists() and path.is_dir():
            return path
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders")
        desktop_path = winreg.QueryValueEx(key, "Desktop")[0]
        path = Path(desktop_path)
        if path.exists():
            return path
    except (ImportError, OSError):
        pass
    return HOME / "Desktop"

DESKTOP_PATH = find_desktop()
ORGANIZED_ROOT = DESKTOP_PATH / "00_Desktop_Organized"
# Include .exe names to avoid self-move when running as exe
IGNORE = [
    "00_Desktop_Organized",
    "Organize-Desktop.py",
    "Organize-Downloads.py",
    "Organize-Desktop.exe",
    "Organize-Downloads.exe",
]

# Fix for .exe self-detection
SELF_NAME = Path(sys.executable).name if getattr(sys, "frozen", False) else Path(__file__).name

def organize_desktop(dry_run: bool = False, move_shortcuts: bool = True) -> None:
    print(f"Desktop location: {DESKTOP_PATH}")
    if not DESKTOP_PATH.exists():
        print(f"[Error] Desktop not found: {DESKTOP_PATH}")
        return
    if dry_run:
        print(">>> DRY RUN MODE - No folders/files will be created or moved <<<\n")
    else:
        ORGANIZED_ROOT.mkdir(exist_ok=True)
        print(f"--- Organizing Desktop: {DESKTOP_PATH} ---\n")
    moved = 0
    preview_folders: set[str] = set()
    for item in DESKTOP_PATH.iterdir():
        if item.name == SELF_NAME or item.name in IGNORE or item.name.startswith("00_") or item.name in CATEGORIES or item.name == UNKNOWN_FOLDER:
            continue
        if item.is_dir():
            continue
        ext = item.suffix.lower()
        target = UNKNOWN_FOLDER
        for folder, exts in CATEGORIES.items():
            if ext in exts:
                target = folder
                break
        dest_dir = ORGANIZED_ROOT / target
        dest_path = get_unique_path(dest_dir / item.name)
        if dry_run:
            preview_folders.add(target)
            print(f"[DRY-RUN] Would move: {item.name} -> {target}/{dest_path.name}")
            moved += 1
        else:
            try:
                dest_dir.mkdir(exist_ok=True)
                shutil.move(str(item), str(dest_path))
                print(f"Moved: {item.name} -> {target}")
                moved += 1
            except OSError as e:
                print(f"[Failed] {item.name}: {e}")
    print(f"\nDone. {moved} file(s) {'would be moved' if dry_run else 'moved'}.")
    if dry_run and preview_folders:
        print(f"[DRY-RUN] Would use folders: {', '.join(sorted(preview_folders))}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Organize Desktop files (Windows).")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no files moved")
    parser.add_argument("--move-shortcuts", action="store_true", help="Include .lnk and .url files")
    args = parser.parse_args()
    try:
        organize_desktop(dry_run=args.dry_run, move_shortcuts=args.move_shortcuts)
    except Exception as e:
        print(f"[Error] {e}")
        import traceback
        traceback.print_exc()
    
    try:
        input("\nPress Enter to exit...")
    except:
        pass
