import os
import shutil
from pathlib import Path
from datetime import datetime

# --- الاعدادات ---
HOME = Path.home()

def find_folder(name):
    """بيدور على الفولدر في كذا مكان (عشان OneDrive)"""
    candidates = [
        HOME / name,
        HOME / "OneDrive" / name,
        HOME / "OneDrive" / "Desktop" if name == "Desktop" else None,
        Path.home() / "Desktop" if name == "Desktop" else None,
    ]
    # اضافة مسار OneDrive العربي احيانا
    candidates.append(HOME / "OneDrive" / "سطح المكتب")
    for p in candidates:
        if p and p.exists() and p.is_dir():
            return p
    return HOME / name

DOWNLOADS_PATH = find_folder("Downloads")
DESKTOP_PATH = find_folder("Desktop")

# تقسيمة محترمة - كل صيغة بتروح مكانها
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
IGNORE_FILES = [os.path.basename(__file__), "organize_both.py", "organize_desktop.py"]

def get_unique_path(destination: Path):
    """لو الملف موجود بيزود عليه رقم عشان ميعملش overwrite"""
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

def organize_folder(base_path: Path, mode="downloads", dry_run=False, move_shortcuts=False):
    if not base_path.exists():
        print(f"[!] مش لاقي الفولدر ده: {base_path}")
        return 0

    is_desktop = (mode == "desktop")
    organized_root = base_path / "00_Desktop_Organized" if is_desktop else base_path

    print(f"\n--- بنروق: {base_path} ({mode}) ---")
    if dry_run:
        print(">>> Dry Run بس <<<\n")

    if is_desktop:
        organized_root.mkdir(exist_ok=True)

    moved_count = 0
    
    for item in base_path.iterdir():
        if item.name in IGNORE_FILES or item.name == UNKNOWN_FOLDER or item.name in CATEGORIES or item.name.startswith("00_"):
            continue
        if item.name == organized_root.name:
            continue
        if item.is_dir():
            # متلمسش الفولدرات على الديسكتوب والداونلود - لم الملفات بس
            continue

        ext = item.suffix.lower()
        target_folder_name = None

        for folder, extensions in CATEGORIES.items():
            if ext in extensions:
                target_folder_name = folder
                break
        
        if not target_folder_name:
            target_folder_name = UNKNOWN_FOLDER

        # سيب الاختصارات على الديسكتوب لو مش عايز تنقلها
        if is_desktop and not move_shortcuts and target_folder_name == "10_Shortcuts":
            print(f"[سايبينه] {item.name} (اختصار)")
            continue

        target_folder = organized_root / target_folder_name if is_desktop else base_path / target_folder_name
        target_folder.mkdir(exist_ok=True)

        destination = target_folder / item.name
        destination = get_unique_path(destination)

        display = f"{organized_root.name}/{target_folder_name}" if is_desktop else target_folder_name

        if dry_run:
            print(f"[هيتنقل] {item.name}  ->  {display}/{destination.name}")
        else:
            try:
                shutil.move(str(item), str(destination))
                print(f"[اتنقل] {item.name}  ->  {display}/{destination.name}")
                moved_count += 1
            except Exception as e:
                print(f"[خطأ] مقدرتش انقل {item.name}: {e}")

    return moved_count

def organize(dry_run=False, downloads_only=False, desktop_only=False, move_shortcuts=False):
    total = 0
    if not desktop_only:
        if DOWNLOADS_PATH.exists():
            total += organize_folder(DOWNLOADS_PATH, mode="downloads", dry_run=dry_run, move_shortcuts=move_shortcuts)
        else:
            print(f"مش لاقي الداونلود: {DOWNLOADS_PATH}")
    
    if not downloads_only:
        print(f"\nبندور على الديسكتوب في: {DESKTOP_PATH}")
        if DESKTOP_PATH.exists():
            total += organize_folder(DESKTOP_PATH, mode="desktop", dry_run=dry_run, move_shortcuts=move_shortcuts)
        else:
            print(f"مش لاقي الديسكتوب: {DESKTOP_PATH}")

    if not dry_run:
        print(f"\n========================\nخلصنا! روقنا {total} ملف إجمالي.")
        if total == 0:
            print("جهازك نضيف أصلاً!")
    else:
        print(f"\nDry Run خلص - {total} ملف هيتنقلو")

if __name__ == "__main__":
    # --- تقدر تغير من هنا ---
    # False = هينقل بجد, True = تجربة بس
    DRY_RUN = False
    # لو عايز الداونلود بس خلي desktop_only = False و downloads_only = True
    organize(dry_run=DRY_RUN, downloads_only=False, desktop_only=False, move_shortcuts=False)
