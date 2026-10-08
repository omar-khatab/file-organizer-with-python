"""
File Organizer - Downloads Organizer
Author: Omar Khatab
GitHub: https://github.com/omar-khatab/file-organizer-with-python

Description:
    Organizes Downloads folder into categorized subfolders based on file extensions.

Features:
    - Automatic Downloads path detection
    - 11 categories covering 40+ file extensions (including Code, Shortcuts, Others)
    - Duplicate file handling with unique naming (file (1), file (2))
    - Dry-run mode for safe preview
    - Preserves existing folders

Usage:
    python Organize-Downloads.py
    # To preview without moving: set dry_run=True
"""

import os
import shutil
from pathlib import Path
from datetime import datetime

# --- Configuration ---
# Automatically detect Downloads folder for Windows/Mac/Linux
DOWNLOADS_PATH = Path.home() / "Downloads"

# File categorization - maps folder names to file extensions
CATEGORIES = {
    "01_PDFs": [".pdf"],
    "02_Word_Docs": [".doc", ".docx", ".odt", ".rtf", ".txt"],
    "03_Excel_Sheets": [".xls", ".xlsx", ".csv", ".ods"],
    "04_PowerPoint": [".ppt", ".pptx", ".odp"],
    "05_Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".ico"],
    "06_Zip_Files": [".zip", ".rar", ".7z", ".tar", ".gz"],
    "07_Programs": [".exe", ".msi", ".dmg", ".apk"],
    "08_Videos": [".mp4", ".mkv", ".mov", ".avi", ".wmv"],
    "09_Code": [
        ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".cpp", ".c", ".h",
        ".hpp", ".cs", ".go", ".rb", ".php", ".html", ".css", ".scss",
        ".json", ".xml", ".yml", ".yaml", ".sql", ".sh", ".bat", ".ps1",
        ".ipynb", ".dart", ".kt", ".swift", ".rs"
    ],
    "10_Shortcuts": [".lnk", ".url"],
}

UNKNOWN_FOLDER = "11_Others_Unknown"

def get_unique_path(destination: Path):
    """
    Generate unique path to prevent file overwrites.
    
    If file exists, creates incremented version:
    Example: report.pdf -> report (1).pdf -> report (2).pdf
    
    Args:
        destination (Path): Desired destination path
    
    Returns:
        Path: Unique available path
    """
    if not destination.exists():
        return destination
    
    stem = destination.stem
    suffix = destination.suffix
    parent = destination.parent
    counter = 1
    
    while True:
        new_name = f"{stem} ({counter}){suffix}"
        new_path = parent / new_name
        if not new_path.exists():
            return new_path
        counter += 1

def organize(dry_run=False):
    """
    Organize Downloads folder by file type.
    
    Workflow:
    1. Check if Downloads folder exists
    2. Iterate through files
    3. Categorize by extension
    4. Move to appropriate folder with duplicate handling
    
    Args:
        dry_run (bool): If True, preview only without moving files
    """
    if not DOWNLOADS_PATH.exists():
        print(f"Downloads folder not found at: {DOWNLOADS_PATH}")
        return

    print(f"--- Starting organization: {DOWNLOADS_PATH} ---")
    if dry_run:
        print(">>> DRY RUN MODE - No files will be moved <<<\n")

    moved_count = 0
    
    for item in DOWNLOADS_PATH.iterdir():
        # Skip category folders we created and the script itself
        if item.is_dir() and (item.name in CATEGORIES or item.name == UNKNOWN_FOLDER):
            continue
        if item.name == os.path.basename(__file__):
            continue
        # Skip all directories - only organize files
        if item.is_dir():
            continue

        # Determine target folder by file extension
        ext = item.suffix.lower()
        target_folder_name = None

        for folder, extensions in CATEGORIES.items():
            if ext in extensions:
                target_folder_name = folder
                break
        
        # Unknown extensions go to Others folder
        if not target_folder_name:
            target_folder_name = UNKNOWN_FOLDER

        # Create target folder if it doesn't exist
        target_folder = DOWNLOADS_PATH / target_folder_name
        target_folder.mkdir(exist_ok=True)

        # Handle duplicate filenames
        destination = target_folder / item.name
        destination = get_unique_path(destination)

        if dry_run:
            print(f"[Will move] {item.name}  ->  {target_folder_name}/{destination.name}")
        else:
            try:
                shutil.move(str(item), str(destination))
                print(f"[Moved] {item.name}  ->  {target_folder_name}/{destination.name}")
                moved_count += 1
            except Exception as e:
                print(f"[Error] Failed to move {item.name}: {e}")

    # Final summary
    if not dry_run:
        print(f"\nDone! Organized {moved_count} files.")
        print(f"Check folder: {DOWNLOADS_PATH}")
    else:
        print("\nDry run complete. Remove dry_run=True to apply changes")

if __name__ == "__main__":
    # Set dry_run=True to preview, False to actually move files
    organize(dry_run=False)
