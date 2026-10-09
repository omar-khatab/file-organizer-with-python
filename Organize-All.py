"""
File Organizer - Unified Organizer (Windows)
Author: Omar Khatab
GitHub: https://github.com/omar-khatab/file-organizer-with-python
Description: Built to clean up my own cluttered Downloads and Desktop - still in daily use.
Design: One file to rule them all. Download and run, no setup.
Right-click: Right-click any folder -> Organize with File Organizer
"""
from __future__ import annotations

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
    stem = destination.stem
    suffix = destination.suffix
    parent = destination.parent
    counter = 1
    while True:
        new_path = parent / f"{stem} ({counter}){suffix}"
        if not new_path.exists():
            return new_path
        counter += 1

HOME = Path.home()
DOWNLOADS_PATH = HOME / "Downloads"

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

SELF_NAMES = {
    "Organize-All.py", "Organize-All.exe",
    "Organize-Desktop.py", "Organize-Desktop.exe",
    "Organize-Downloads.py", "Organize-Downloads.exe",
    "FileOrganizer.exe", "Organize.py", "Organize.exe"
}
CURRENT_SELF = Path(sys.executable).name if getattr(sys, "frozen", False) else Path(__file__).name
IGNORE_DESKTOP = ["00_Desktop_Organized"] + list(SELF_NAMES)

# --- Safety: protected paths ---

def get_protected_roots() -> list[Path]:
    roots: list[Path] = []
    try:
        # Drive roots: C:\, D:\ etc
        # HOME itself
        roots.append(HOME.resolve())
        # Windows dir
        windir = os.environ.get("WINDIR", r"C:\Windows")
        roots.append(Path(windir).resolve())
        # Program Files
        for env_var in ["ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"]:
            pf = os.environ.get(env_var)
            if pf:
                roots.append(Path(pf).resolve())
        # System drive root
        system_drive = os.environ.get("SystemDrive", "C:")
        roots.append(Path(f"{system_drive}\\").resolve())
    except (OSError, RuntimeError):
        pass
    # Deduplicate
    seen = set()
    uniq = []
    for p in roots:
        try:
            rp = p.resolve()
            if str(rp).lower() not in seen:
                seen.add(str(rp).lower())
                uniq.append(rp)
        except (OSError, RuntimeError):
            continue
    return uniq

PROTECTED_ROOTS = get_protected_roots()

def is_protected_path(folder: Path) -> str | None:
    """Return reason if folder is protected, else None."""
    try:
        resolved = folder.resolve()
    except (OSError, RuntimeError):
        return "Cannot resolve path"

    # Block drive root: C:\, D:\, /
    if resolved == Path(resolved.anchor).resolve() or str(resolved).lower() == resolved.anchor.lower().strip("\\").lower() + "\\":
        # Check if anchor is root
        if len(resolved.parts) <= 1 or resolved.parent == resolved:
            return f"Drive root is protected: {resolved}"
    # Direct check for anchor equality (Windows: C:\ -> anchor C:\)
    try:
        if resolved == Path(resolved.anchor) or (os.name == "nt" and str(resolved).lower() == f"{resolved.drive.lower()}\\"):
            return f"Drive root is protected: {resolved}"
    except (OSError, ValueError):
        pass

    # Check against protected roots
    for protected in PROTECTED_ROOTS:
        try:
            # Exact match
            if resolved == protected:
                return f"Protected location: {protected}"
            # Inside protected (e.g., C:\Windows\System32)
            # Use is_relative_to for Python 3.9+ (we have 3.9, but use try)
            try:
                if resolved.is_relative_to(protected):
                    return f"Inside protected location: {protected}"
            except AttributeError:
                # Python <3.9 fallback
                try:
                    resolved.relative_to(protected)
                    return f"Inside protected location: {protected}"
                except ValueError:
                    pass
        except (OSError, ValueError, RuntimeError):
            continue

    # Block HOME directly, but allow subfolders like Downloads, Desktop (they are handled separately)
    # Actually HOME itself should be blocked to avoid organizing entire home
    try:
        if resolved == HOME.resolve():
            return f"Home folder is protected, organize a subfolder instead: {HOME}"
    except (OSError, RuntimeError):
        pass

    return None

def organize_folder(source: Path, dest_root: Path | None, dry_run: bool, move_shortcuts: bool = False, label: str = "") -> int:
    if not source.exists():
        print(f"[Error] {label} not found: {source}")
        return 0

    is_desktop = dest_root is not None
    actual_dest_root = dest_root if is_desktop else source

    if not is_desktop:
        print(f"--- Organizing {label}: {source} ---")
    else:
        print(f"--- Organizing {label}: {source} -> {actual_dest_root} ---")

    if dry_run:
        print(">>> DRY RUN - No changes <<<\n")

    if not dry_run and is_desktop:
        actual_dest_root.mkdir(exist_ok=True)

    moved = 0
    preview_folders: set[str] = set()

    for item in source.iterdir():
        if item.name == CURRENT_SELF or item.name in SELF_NAMES:
            continue
        if is_desktop and (item.name in IGNORE_DESKTOP or item.name.startswith("00_") or item.name in CATEGORIES or item.name == UNKNOWN_FOLDER):
            continue
        if item.is_dir():
            continue

        ext = item.suffix.lower()
        target = UNKNOWN_FOLDER
        for folder, exts in CATEGORIES.items():
            if ext in exts:
                target = folder
                break

        # CRITICAL: respect move_shortcuts flag
        if not move_shortcuts and target == "10_Shortcuts":
            continue

        dest_dir = actual_dest_root / target
        dest_path = get_unique_path(dest_dir / item.name)

        if dry_run:
            preview_folders.add(target)
            print(f"[DRY-RUN] {label}: {item.name} -> {target}/{dest_path.name}")
            moved += 1
        else:
            try:
                dest_dir.mkdir(exist_ok=True)
                shutil.move(str(item), str(dest_path))
                print(f"Moved: {item.name} -> {target}")
                moved += 1
            except OSError as e:
                print(f"[Failed] {item.name}: {e}")

    print(f"\n{label} Done. {moved} file(s) {'would be moved' if dry_run else 'moved'}.")
    if dry_run and preview_folders:
        print(f"Would use: {', '.join(sorted(preview_folders))}\n")
    else:
        print()
    return moved

def organize_downloads(dry_run: bool = False, move_shortcuts: bool = False) -> int:
    return organize_folder(DOWNLOADS_PATH, None, dry_run, move_shortcuts, "Downloads")

def organize_desktop(dry_run: bool = False, move_shortcuts: bool = False) -> int:
    return organize_folder(DESKTOP_PATH, ORGANIZED_ROOT, dry_run, move_shortcuts, "Desktop")

def organize_custom_folder(folder: Path, dry_run: bool = False, move_shortcuts: bool = False) -> int:
    folder = folder.resolve()
    if not folder.exists() or not folder.is_dir():
        print(f"[Error] Not a folder: {folder}")
        return 0

    protected_reason = is_protected_path(folder)
    if protected_reason:
        print(f"[Blocked] {protected_reason}")
        print("Refusing to organize this location for safety.")
        return 0

    return organize_folder(folder, None, dry_run, move_shortcuts, f"Folder {folder.name}")

def install_context_menu():
    if os.name != "nt":
        print("Context menu only works on Windows")
        return
    try:
        import winreg
        exe_path = Path(sys.executable).resolve() if getattr(sys, "frozen", False) else Path(__file__).resolve()
        if exe_path.suffix == ".py":
            python_exe = Path(sys.executable).resolve()
            command = f'"{python_exe}" "{exe_path}" "%V"'
        else:
            command = f'"{exe_path}" "%V"'

        for reg_path in [r"Directory\shell\FileOrganizer", r"Directory\Background\shell\FileOrganizer"]:
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"Software\Classes\{reg_path}")
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "Organize with File Organizer")
            winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, str(exe_path))
            cmd_key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"Software\Classes\{reg_path}\command")
            winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ, command)
            winreg.CloseKey(cmd_key)
            winreg.CloseKey(key)

        print(f"[OK] Context menu installed! Command: {command}")
        print("Now right-click any folder -> Organize with File Organizer")
        print("\nNote: The button stores the current exe path.")
        print("Place the program in a permanent folder before installing.")
        print("Registry: HKCU\\Software\\Classes\\Directory\\shell\\FileOrganizer")
    except (OSError, ImportError) as e:
        print(f"[Failed] Could not install context menu: {e}")

def uninstall_context_menu():
    if os.name != "nt":
        return
    try:
        import winreg
        for reg_path in [
            r"Directory\shell\FileOrganizer", r"Directory\Background\shell\FileOrganizer",
            r"Directory\shell\FileOrganizerWithShortcuts", r"Directory\Background\shell\FileOrganizerWithShortcuts"
        ]:
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, f"Software\Classes\{reg_path}\command")
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, f"Software\Classes\{reg_path}")
            except FileNotFoundError:
                pass
        print("[OK] Context menu removed")
        print("Removed from HKCU\\Software\\Classes\\Directory\\shell\\FileOrganizer")
    except (OSError, ImportError) as e:
        print(f"[Failed] {e}")

def pause():
    try:
        input("\nPress Enter to exit...")
    except (EOFError, OSError):
        pass

def interactive_menu():
    print("="*50)
    print("  File Organizer - Unified")
    print("  Omar Khatab")
    print("="*50)
    print(f"Downloads: {DOWNLOADS_PATH}")
    print(f"Desktop:   {DESKTOP_PATH}\n")
    print("Choose what to organize:")
    print("  [1] Downloads only")
    print("  [2] Desktop only")
    print("  [3] Both (Downloads + Desktop)")
    print("  [4] Custom folder (enter path)")
    print("  [5] Preview Downloads (--dry-run)")
    print("  [6] Preview Desktop (--dry-run)")
    print("  [7] Preview Both (--dry-run)")
    print("  [8] Install right-click menu")
    print("  [9] Uninstall right-click menu")
    print("  [0] Exit\n")

    try:
        choice = input("Enter choice [0-9]: ").strip()
    except (EOFError, OSError):
        choice = "0"

    try:
        if choice == "1":
            organize_downloads(dry_run=False, move_shortcuts=False)
        elif choice == "2":
            organize_desktop(dry_run=False, move_shortcuts=False)
        elif choice == "3":
            organize_downloads(dry_run=False, move_shortcuts=False)
            organize_desktop(dry_run=False, move_shortcuts=False)
        elif choice == "4":
            path = input("Enter folder path: ").strip().strip('"')
            organize_custom_folder(Path(path), dry_run=False, move_shortcuts=False)
        elif choice == "5":
            organize_downloads(dry_run=True, move_shortcuts=False)
        elif choice == "6":
            organize_desktop(dry_run=True, move_shortcuts=False)
        elif choice == "7":
            organize_downloads(dry_run=True, move_shortcuts=False)
            organize_desktop(dry_run=True, move_shortcuts=False)
        elif choice == "8":
            install_context_menu()
        elif choice == "9":
            uninstall_context_menu()
        else:
            print("Exited.")
    except (OSError, ValueError) as e:
        print(f"[Error] {e}")
        import traceback
        traceback.print_exc()

    pause()

def main():
    parser = argparse.ArgumentParser(description="Unified File Organizer - Desktop, Downloads, or any folder (Windows).")
    parser.add_argument("folder", nargs="?", help="Custom folder to organize (for right-click menu)")
    parser.add_argument("--downloads", action="store_true", help="Organize Downloads only")
    parser.add_argument("--desktop", action="store_true", help="Organize Desktop only")
    parser.add_argument("--both", action="store_true", help="Organize both Downloads and Desktop")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no files moved")
    parser.add_argument("--move-shortcuts", action="store_true", help="Include .lnk and .url files")
    parser.add_argument("--install-context-menu", action="store_true", help="Add right-click menu")
    parser.add_argument("--uninstall-context-menu", action="store_true", help="Remove right-click menu")
    args = parser.parse_args()

    # Install/uninstall context menu
    if args.install_context_menu:
        install_context_menu()
        pause()
        sys.exit(0)
    if args.uninstall_context_menu:
        uninstall_context_menu()
        pause()
        sys.exit(0)

    # Right-click: folder path passed as argument - WITH SAFETY CHECK + PREVIEW + CONFIRM
    if args.folder:
        custom_path = Path(args.folder)
        if not custom_path.exists() or not custom_path.is_dir():
            print(f"[Error] Not a folder: {args.folder}")
            pause()
            sys.exit(1)

        # Safety check
        protected_reason = is_protected_path(custom_path.resolve())
        if protected_reason:
            print(f"[Blocked] {protected_reason}")
            print("Refusing to organize this location for safety.")
            print("\nProtected locations: drive roots (C:\\), Home, Windows, Program Files")
            pause()
            sys.exit(1)

        try:
            # Preview first
            print(f"Right-click target: {custom_path}\n")
            count = organize_folder(custom_path.resolve(), None, True, args.move_shortcuts, label="Preview")
            if count == 0:
                print("Nothing to organize.")
                pause()
                sys.exit(0)

            try:
                confirm = input(f"\nProceed to organize {count} file(s) in '{custom_path.name}'? (y/n): ").strip().lower()
            except (EOFError, OSError):
                confirm = "n"

            if confirm == "y":
                organize_custom_folder(custom_path, dry_run=args.dry_run, move_shortcuts=args.move_shortcuts)
            else:
                print("Cancelled.")
        except (OSError, ValueError) as e:
            print(f"[Error] {e}")
            import traceback
            traceback.print_exc()
        pause()
        sys.exit(0)

    # No args = show menu (double-click case)
    no_flags = not any([args.downloads, args.desktop, args.both])
    if not args.folder and no_flags:
        interactive_menu()
        sys.exit(0)

    # Flags provided
    try:
        dry = args.dry_run
        move_sc = args.move_shortcuts
        if args.both:
            organize_downloads(dry_run=dry, move_shortcuts=move_sc)
            organize_desktop(dry_run=dry, move_shortcuts=move_sc)
        elif args.downloads and args.desktop:
            organize_downloads(dry_run=dry, move_shortcuts=move_sc)
            organize_desktop(dry_run=dry, move_shortcuts=move_sc)
        elif args.downloads:
            organize_downloads(dry_run=dry, move_shortcuts=move_sc)
        elif args.desktop:
            organize_desktop(dry_run=dry, move_shortcuts=move_sc)
    except (OSError, ValueError) as e:
        print(f"[Error] {e}")
        import traceback
        traceback.print_exc()
    
    pause()

if __name__ == "__main__":
    main()
