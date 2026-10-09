"""
File Organizer - Downloads Organizer (Windows)
Author: Omar Khatab
Built to clean up my own cluttered Downloads, still use it myself.
Standalone - download one file and run it.
"""

import argparse
import shutil
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


DOWNLOADS_PATH = Path.home() / "Downloads"

def organize(dry_run: bool = False) -> None:
    if not DOWNLOADS_PATH.exists():
        print(f"[Error] Downloads not found: {DOWNLOADS_PATH}")
        return
    print(f"--- Organizing Downloads: {DOWNLOADS_PATH} ---")
    if dry_run:
        print(">>> DRY RUN - No folders/files will be created or moved <<<\n")
    moved = 0
    preview_folders: set[str] = set()
    for item in DOWNLOADS_PATH.iterdir():
        if item.name == Path(__file__).name:
            continue
        if item.is_dir():
            continue
        ext = item.suffix.lower()
        target_folder = UNKNOWN_FOLDER
        for folder, exts in CATEGORIES.items():
            if ext in exts:
                target_folder = folder
                break
        dest_dir = DOWNLOADS_PATH / target_folder
        dest_path = get_unique_path(dest_dir / item.name)
        if dry_run:
            preview_folders.add(target_folder)
            print(f"[DRY-RUN] Would move: {item.name} -> {target_folder}/{dest_path.name}")
            moved += 1
        else:
            try:
                dest_dir.mkdir(exist_ok=True)
                shutil.move(str(item), str(dest_path))
                print(f"Moved: {item.name} -> {target_folder}")
                moved += 1
            except OSError as e:
                print(f"[Failed] {item.name}: {e}")
    if dry_run and preview_folders:
        print(f"\n[DRY-RUN] Would use {len(preview_folders)} folders: {', '.join(sorted(preview_folders))}")
    print(f"\nDone. {moved} file(s) {'would be moved' if dry_run else 'moved'}.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Organize Downloads by file type.")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    args = parser.parse_args()
    organize(dry_run=args.dry_run)
