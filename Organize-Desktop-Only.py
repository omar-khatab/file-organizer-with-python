import os
import shutil
from pathlib import Path

HOME = Path.home()

def find_desktop():
    candidates = [
        HOME / "Desktop",
        HOME / "OneDrive" / "Desktop",
        HOME / "OneDrive" / "سطح المكتب",
        Path(r"C:\Users") / os.getlogin() / "OneDrive" / "Desktop" if os.name == 'nt' else None,
    ]
    # دور كمان في كل اليوزرز لو معرفناش
    for p in candidates:
        if p and p.exists() and p.is_dir():
            return p
    # fallback: شوف Desktop الحقيقي من الـ registry لو ويندوز
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders")
        desktop_path = winreg.QueryValueEx(key, "Desktop")[0]
        p = Path(desktop_path)
        if p.exists():
            return p
    except:
        pass
    return HOME / "Desktop"

DESKTOP_PATH = find_desktop()
ORGANIZED_ROOT = DESKTOP_PATH / "00_Desktop_Organized"

CATEGORIES = {
    "01_PDFs": [".pdf"],
    "02_Documents": [".doc", ".docx", ".odt", ".rtf", ".txt"],
    "03_Sheets": [".xls", ".xlsx", ".csv", ".ods"],
    "04_Presentations": [".ppt", ".pptx", ".odp"],
    "05_Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".ico"],
    "06_Zip": [".zip", ".rar", ".7z", ".tar", ".gz"],
    "07_Programs": [".exe", ".msi", ".dmg", ".apk"],
    "08_Videos": [".mp4", ".mkv", ".mov", ".avi", ".wmv"],
    "09_Code": [".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".cpp", ".c", ".h", ".cs", ".go", ".php", ".html", ".css", ".json", ".xml", ".yml", ".yaml", ".sql", ".sh", ".bat", ".ipynb"],
    "10_Shortcuts": [".lnk", ".url"],
}

UNKNOWN_FOLDER = "11_Others"
IGNORE = [os.path.basename(__file__), "00_Desktop_Organized", "organize_both.py", "organize_downloads.py", "organize_desktop.py", "organize_desktop_only.py"]

def get_unique_path(dest: Path):
    if not dest.exists():
        return dest
    stem, suffix, parent = dest.stem, dest.suffix, dest.parent
    i = 1
    while True:
        new = parent / f"{stem} ({i}){suffix}"
        if not new.exists():
            return new
        i += 1

def organize_desktop(dry_run=False, move_shortcuts=False):
    print(f"بندور على الديسكتوب في: {DESKTOP_PATH}")
    if not DESKTOP_PATH.exists():
        print(f"[!] مش لاقي الديسكتوب! جربت: {DESKTOP_PATH}")
        return

    ORGANIZED_ROOT.mkdir(exist_ok=True)
    print(f"--- بنروق الديسكتوب: {DESKTOP_PATH} ---\n")
    if dry_run:
        print(">>> Dry Run بس - مش هننقل حاجة <<<\n")

    moved = 0
    for item in DESKTOP_PATH.iterdir():
        if item.name in IGNORE or item.name.startswith("00_") or item.name in CATEGORIES:
            continue
        if item.is_dir():
            continue  # سيب الفولدرات

        ext = item.suffix.lower()
        target = None
        for folder, exts in CATEGORIES.items():
            if ext in exts:
                target = folder
                break
        if not target:
            target = UNKNOWN_FOLDER

        if not move_shortcuts and target == "10_Shortcuts":
            print(f"[سايبينه] {item.name} (اختصار)")
            continue

        dest_folder = ORGANIZED_ROOT / target
        dest_folder.mkdir(exist_ok=True)

        dest = get_unique_path(dest_folder / item.name)

        if dry_run:
            print(f"[هيتنقل] {item.name} -> 00_Desktop_Organized/{target}/{dest.name}")
        else:
            try:
                shutil.move(str(item), str(dest))
                print(f"[اتنقل] {item.name} -> {target}/{dest.name}")
                moved += 1
            except Exception as e:
                print(f"[خطأ] {item.name}: {e}")

    if not dry_run:
        print(f"\nخلصنا! روقنا {moved} ملف من الديسكتوب.")
        print(f"هتلاقيهم في: {ORGANIZED_ROOT}")
    else:
        print(f"\nDry Run خلص - {moved} ملف هيتنقلو")

if __name__ == "__main__":
    # غير True لو عايز تجرب الاول
    organize_desktop(dry_run=False, move_shortcuts=False)
