"""
File Organizer - Desktop Organizer
Author: Omar Khatab
GitHub: https://github.com/omar-khatab/file-organizer-with-python

Description:
    Dedicated desktop organizer that cleans up desktop files
    into categorized subfolders inside 00_Desktop_Organized.

Features:
    - Automatic desktop path detection (standard, OneDrive, registry)
    - 11 categories covering 40+ file extensions
    - Duplicate file handling with unique naming
    - Preserves folders - only moves files
    - Dry-run preview mode

Usage:
    python Organize-Desktop.py
"""

import os
import shutil
from pathlib import Path

# --- Configuration ---
HOME = Path.home()

def find_desktop():
    """
    Locate desktop folder across different Windows configurations.
    
    Checks:
    - Standard desktop path (C:/Users/Name/Desktop)
    - OneDrive synced desktop
    - Windows registry for custom desktop location
    
    Returns:
        Path: Desktop folder path
    """
    candidates = [
        HOME / "Desktop",
        HOME / "OneDrive" / "Desktop",
        Path(r"C:\Users") / os.getlogin() / "OneDrive" / "Desktop" if os.name == 'nt' else None,
    ]
    
    for path in candidates:
        if path and path.exists() and path.is_dir():
            return path
    
    # Fallback: Try to get desktop path from Windows registry
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, 
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
        )
        desktop_path = winreg.QueryValueEx(key, "Desktop")[0]
        path = Path(desktop_path)
        if path.exists():
            return path
    except:
        pass
    
    return HOME / "Desktop"

# Resolve paths
DESKTOP_PATH = find_desktop()
ORGANIZED_ROOT = DESKTOP_PATH / "00_Desktop_Organized"

# File categorization mapping - extension to folder
CATEGORIES = {
    "01_PDFs": [".pdf"],
    "02_Documents": [".doc", ".docx", ".odt", ".rtf", ".txt"],
    "03_Sheets": [".xls", ".xlsx", ".csv", ".ods"],
    "04_Presentations": [".ppt", ".pptx", ".odp"],
    "05_Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".ico"],
    "06_Zip": [".zip", ".rar", ".7z", ".tar", ".gz"],
    "07_Programs": [".exe", ".msi", ".dmg", ".apk"],
    "08_Videos": [".mp4", ".mkv", ".mov", ".avi", ".wmv"],
    "09_Code": [
        ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".cpp", ".c", ".h", 
        ".cs", ".go", ".php", ".html", ".css", ".json", ".xml", ".yml", 
        ".yaml", ".sql", ".sh", ".bat", ".ipynb"
    ],
    "10_Shortcuts": [".lnk", ".url"],
}

UNKNOWN_FOLDER = "11_Others"
# Files and folders to ignore during organization
IGNORE = [
    os.path.basename(__file__), 
    "00_Desktop_Organized",  
    "Organize-Downloads.py", 
]

def get_unique_path(dest: Path):
    """
    Generate unique path to avoid file overwrites.
    
    Creates incremented filename if destination exists:
    file.txt -> file (1).txt -> file (2).txt
    
    Args:
        dest (Path): Desired destination path
    
    Returns:
        Path: Unique available path
    """
    if not dest.exists():
        return dest
    
    stem, suffix, parent = dest.stem, dest.suffix, dest.parent
    counter = 1
    
    while True:
        new_path = parent / f"{stem} ({counter}){suffix}"
        if not new_path.exists():
            return new_path
        counter += 1

def organize_desktop(dry_run=False, move_shortcuts=False):
    """
    Organize desktop files into categorized folders.
    
    Creates 00_Desktop_Organized folder containing subfolders
    for each category. Only moves files, preserves all folders.
    
    Args:
        dry_run (bool): Preview mode without moving files
        move_shortcuts (bool): Whether to move shortcut files
    """
    print(f"Searching Desktop at: {DESKTOP_PATH}")
    
    if not DESKTOP_PATH.exists():
        print(f"[!] Desktop not found! Tried: {DESKTOP_PATH}")
        return

    # Create organized root folder
    ORGANIZED_ROOT.mkdir(exist_ok=True)
    print(f"--- Organizing Desktop: {DESKTOP_PATH} ---\n")
    
    if dry_run:
        print(">>> DRY RUN - Preview only, no files will be moved <<<\n")

    moved = 0
    
    # Iterate through desktop items
    for item in DESKTOP_PATH.iterdir():
        # Skip ignored files and already-organized folders
        if item.name in IGNORE or item.name.startswith("00_") or item.name in CATEGORIES:
            continue
        # Skip all directories - preserve folder structure
        if item.is_dir():
            continue

        # Determine target category by file extension
        ext = item.suffix.lower()
        target = None
        
        for folder, extensions in CATEGORIES.items():
            if ext in extensions:
                target = folder
                break
        
        # Unknown file types go to Others folder
        if not target:
            target = UNKNOWN_FOLDER

        # Skip shortcuts if not requested
        if not move_shortcuts and target == "10_Shortcuts":
            print(f"[Skipped] {item.name} (shortcut)")
            continue

        # Create category folder
        dest_folder = ORGANIZED_ROOT / target
        dest_folder.mkdir(exist_ok=True)

        # Handle duplicate filenames
        dest = get_unique_path(dest_folder / item.name)

        if dry_run:
            print(f"[Will move] {item.name} -> 00_Desktop_Organized/{target}/{dest.name}")
        else:
            try:
                shutil.move(str(item), str(dest))
                print(f"[Moved] {item.name} -> {target}/{dest.name}")
                moved += 1
            except Exception as e:
                print(f"[Error] {item.name}: {e}")

    # Final summary
    if not dry_run:
        print(f"\nDone! Organized {moved} files from Desktop.")
        print(f"Files located at: {ORGANIZED_ROOT}")
    else:
        print(f"\nDry run complete - {moved} files would be moved")

if __name__ == "__main__":
    # Set dry_run=True to preview, False to actually organize
    organize_desktop(dry_run=False, move_shortcuts=False)
