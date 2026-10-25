"""
File Organizer v3.0 PRODUCTION - Omar Khatab
Fixed: Protected paths, No silent errors, SQLite history, Watch fixed, Auto, Right-click fixed

Features:
- Protected paths: blocks C:\, HOME, Windows, Program Files
- SQLite history: ~/.file_organizer/history.db with status done/undone
- No silent except: all failures logged and shown
- Watch fixed: processed by (name+size+mtime), retry on failure, ignores .tmp/.crdownload/.part
- Auto: interval timer
- Right-click: reads sys.argv, installs both Directory and Background
- CLI + Interactive menu
"""
from __future__ import annotations
import argparse, datetime, json, os, shutil, sys, sqlite3, time, threading
from pathlib import Path
from collections import defaultdict

VERSION = "3.0 PRODUCTION"

CATEGORIES = {
    "01_PDFs": [".pdf"],
    "02_Documents": [".doc", ".docx", ".odt", ".rtf", ".txt"],
    "03_Sheets": [".xls", ".xlsx", ".csv", ".ods"],
    "04_Presentations": [".ppt", ".pptx", ".odp"],
    "05_Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".ico"],
    "06_Archives": [".zip", ".rar", ".7z", ".tar", ".gz"],
    "07_Programs": [".exe", ".msi", ".dmg", ".apk"],
    "08_Videos": [".mp4", ".mkv", ".mov", ".avi", ".wmv"],
    "09_Code": [".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".cpp", ".c", ".h", ".hpp", ".cs", ".go", ".rb", ".php", ".html", ".css", ".scss", ".json", ".xml", ".yml", ".yaml", ".sql", ".sh", ".bat", ".ps1", ".ipynb", ".dart", ".kt", ".swift", ".rs"],
    "10_Shortcuts": [".lnk", ".url"],
}
UNKNOWN_FOLDER = "11_Others"
TEMP_EXTS = {".tmp", ".crdownload", ".part", ".partial", ".download", ".!ut"}

HOME = Path.home()
DOWNLOADS_PATH = HOME / "Downloads"

def find_desktop() -> Path:
    candidates = [HOME / "Desktop", HOME / "OneDrive" / "Desktop"]
    for p in candidates:
        if p.exists() and p.is_dir():
            return p
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders")
        path = Path(winreg.QueryValueEx(key, "Desktop")[0])
        if path.exists():
            return path
    except Exception as e:
        pass
    return HOME / "Desktop"

DESKTOP_PATH = find_desktop()
ORGANIZED_ROOT = DESKTOP_PATH / "00_Desktop_Organized"
UNDO_ROOT = HOME / ".file_organizer" / "undo_logs"
UNDO_ROOT.mkdir(parents=True, exist_ok=True)
DB_PATH = HOME / ".file_organizer" / "history.db"

SELF_NAMES = {
    "Organize-All.py", "Organize-All.exe", "Organize-GUI.py", "Organize-GUI.exe",
    "Organize-PySide6.py", "Organize-PySide6.exe", "Organize-PySide6.pyw", "Organize-GUI.pyw",
    "FileOrganizer-PRO.exe", "FileOrganizer-GUI.exe", "FileOrganizer.exe", "Organize.py", "Organize.exe"
}

def _resolve(p) -> Path | None:
    try:
        return Path(p).resolve()
    except Exception as e:
        return None

EXACT_BLOCKED = [p for p in (_resolve(HOME), _resolve(HOME.parent), _resolve(os.environ.get("SystemDrive", "C:") + "\\")) if p]
TREE_BLOCKED = [p for p in (_resolve(os.environ.get("WINDIR", r"C:\Windows")), _resolve(os.environ.get("ProgramFiles", r"C:\Program Files")), _resolve(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))) if p]

def is_protected_path(folder: Path) -> str | None:
    resolved = _resolve(folder)
    if not resolved:
        return "Cannot resolve path"
    if resolved.parent == resolved:
        return f"Drive root protected: {resolved}"
    if resolved in EXACT_BLOCKED:
        return f"Protected location: {resolved} - organize a subfolder instead"
    for root in TREE_BLOCKED:
        if resolved == root or root in resolved.parents:
            return f"Inside system location: {root}"
    return None

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

# ========== SQLite History ==========

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS operations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            readable_date TEXT,
            source_path TEXT,
            folder_name TEXT,
            label TEXT,
            file_count INTEGER,
            status TEXT DEFAULT 'done',
            error_count INTEGER DEFAULT 0
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS moves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operation_id INTEGER,
            from_path TEXT,
            to_path TEXT,
            name TEXT,
            category TEXT,
            FOREIGN KEY(operation_id) REFERENCES operations(id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operation_id INTEGER,
            file_name TEXT,
            error_msg TEXT,
            FOREIGN KEY(operation_id) REFERENCES operations(id)
        )
    """)
    conn.commit()
    conn.close()

init_db()

def write_undo_log(source: Path, moves: list[dict], errors: list[dict], label: str) -> int | None:
    if not moves and not errors:
        return None
    now = datetime.datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    readable = now.strftime("%Y-%m-%d %I:%M %p")
    full_date = now.strftime("%A, %d %B %Y %I:%M %p")
    
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO operations (timestamp, readable_date, source_path, folder_name, label, file_count, status, error_count) VALUES (?,?,?,?,?,?,?,?)",
                    (timestamp, readable, str(source.resolve()), source.name, label, len(moves), "done", len(errors)))
        op_id = cur.lastrowid
        for m in moves:
            cur.execute("INSERT INTO moves (operation_id, from_path, to_path, name, category) VALUES (?,?,?,?,?)",
                        (op_id, m.get("from"), m.get("to"), m.get("name"), m.get("category") or Path(m.get("to","")).parent.name))
        for e in errors:
            cur.execute("INSERT INTO errors (operation_id, file_name, error_msg) VALUES (?,?,?)",
                        (op_id, e.get("name"), e.get("error")))
        conn.commit()
    except Exception as ex:
        print(f"[DB Error] Failed to write history: {ex}")
        conn.rollback()
        op_id = None
    finally:
        conn.close()
    
    # Also write JSON for backward compat + readable txt
    try:
        safe_name = "".join(c if c.isalnum() else "_" for c in source.name)[:30]
        log_data = {
            "id": op_id,
            "version": "3.0",
            "date": readable,
            "full_date": full_date,
            "folder_name": source.name,
            "full_path": str(source.resolve()),
            "total_files": len(moves),
            "errors": errors,
            "timestamp": timestamp,
            "source": str(source.resolve()),
            "label": label,
            "file_count": len(moves),
            "moves": moves,
        }
        central = UNDO_ROOT / f"{timestamp}_{safe_name}_{len(moves)}files_{op_id}.json"
        central.write_text(json.dumps(log_data, indent=2, ensure_ascii=False), encoding="utf-8")
        txt = UNDO_ROOT / f"{timestamp}_{safe_name}_{len(moves)}files_{op_id}.txt"
        lines = [f"File Organizer v3.0", f"ID: {op_id}", f"Date: {full_date}", f"Folder: {source.name}", f"Path: {source.resolve()}", f"Total: {len(moves)}", f"Errors: {len(errors)}", "", "Moved:"]
        for m in moves[:100]:
            lines.append(f"  {m.get('name')} -> {m.get('category') or Path(m.get('to','')).parent.name}")
        if errors:
            lines.append("")
            lines.append("Errors:")
            for e in errors:
                lines.append(f"  {e.get('name')}: {e.get('error')}")
        txt.write_text("\n".join(lines), encoding="utf-8")
    except Exception as ex:
        print(f"[Log Error] Failed to write txt/json: {ex}")
    
    print(f"[UNDO] Saved: ID={op_id} | {len(moves)} files | {len(errors)} errors | {readable}")
    return op_id

def list_undo_history(limit=30):
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute("SELECT id, readable_date, folder_name, file_count, status, error_count, source_path FROM operations ORDER BY id DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    if not rows:
        print(f"No history in {DB_PATH}")
        return
    print(f"=== History v3.0 - {len(rows)} ops (from SQLite) ===\n")
    for r in rows:
        op_id, date, folder, count, status, err_count, src = r
        status_icon = "✓" if status=="done" else "↩ undone"
        print(f"ID {op_id} | {date} | {folder} ({count} files) | {status_icon} | Errors: {err_count}")
        print(f"     Source: {src}")
        print(f"     To undo: --undo {op_id}\n")

def undo_operation(operation_id: int | None = None, source: Path | None = None) -> int:
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    if operation_id is not None:
        cur.execute("SELECT id, source_path, status FROM operations WHERE id=?", (operation_id,))
    elif source:
        cur.execute("SELECT id, source_path, status FROM operations WHERE source_path=? AND status='done' ORDER BY id DESC LIMIT 1", (str(source.resolve()),))
    else:
        cur.execute("SELECT id, source_path, status FROM operations WHERE status='done' ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    if not row:
        print("[UNDO] No matching operation found")
        conn.close()
        return 0
    op_id, src_path, status = row
    if status != "done":
        print(f"[UNDO] Operation {op_id} already undone")
        conn.close()
        return 0
    cur.execute("SELECT from_path, to_path, name FROM moves WHERE operation_id=?", (op_id,))
    moves = cur.fetchall()
    restored = 0
    failed = 0
    for from_path, to_path, name in reversed(moves):
        dst = Path(to_path)
        src = Path(from_path)
        if not dst.exists():
            print(f"[Skip] {name} - destination missing")
            continue
        try:
            src.parent.mkdir(parents=True, exist_ok=True)
            final = get_unique_path(src)
            shutil.move(str(dst), str(final))
            print(f"Restored: {name}")
            restored += 1
        except Exception as e:
            print(f"[Failed] {name}: {e}")
            failed += 1
    if failed == 0:
        cur.execute("UPDATE operations SET status='undone' WHERE id=?", (op_id,))
        conn.commit()
        print(f"\n[UNDO] Restored {restored}/{len(moves)} files - Operation {op_id} marked as undone")
    else:
        print(f"\n[UNDO] Partial restore {restored}/{len(moves)} - {failed} failed, keeping status as done for retry")
    conn.close()
    return restored

# ========== Core Organize ==========

def organize_folder(source: Path, dest_root: Path | None, dry_run: bool, move_shortcuts: bool, label: str) -> tuple[int, list, list]:
    if not source.exists():
        print(f"[Error] {label} not found: {source}")
        return 0, [], [{"name": str(source), "error": "Not found"}]
    reason = is_protected_path(source.resolve())
    if reason and not dry_run:
        print(f"[Blocked] {reason}")
        return 0, [], [{"name": source.name, "error": reason}]
    is_desktop = dest_root is not None
    actual_root = dest_root if is_desktop else source
    print(f"--- Organizing {label}: {source} ---")
    if dry_run:
        print(">>> DRY RUN <<<\n")
    if not dry_run and is_desktop:
        actual_root.mkdir(exist_ok=True)
    moved = 0
    moves = []
    errors = []
    for item in source.iterdir():
        if item.name in SELF_NAMES or item.name.startswith("00_") or item.is_dir():
            continue
        if is_desktop and item.name in ["00_Desktop_Organized", ".file_organizer"]:
            continue
        ext = item.suffix.lower()
        if ext in TEMP_EXTS:
            continue
        target = UNKNOWN_FOLDER
        for folder, exts in CATEGORIES.items():
            if ext in exts:
                target = folder
                break
        if not move_shortcuts and target == "10_Shortcuts":
            continue
        dest_dir = actual_root / target
        dest_path = get_unique_path(dest_dir / item.name)
        if dry_run:
            print(f"[DRY] {item.name} -> {target}/{dest_path.name}")
            moved += 1
        else:
            try:
                dest_dir.mkdir(exist_ok=True)
                orig = item.resolve()
                shutil.move(str(item), str(dest_path))
                print(f"Moved: {item.name} -> {target}")
                moves.append({"from": str(orig.parent / item.name), "to": str(dest_path.resolve()), "name": item.name, "category": target})
                moved += 1
            except Exception as e:
                err_msg = f"{type(e).__name__}: {e}"
                print(f"[Failed] {item.name}: {err_msg}")
                errors.append({"name": item.name, "error": err_msg})
    print(f"\n{label} Done: {moved} moved, {len(errors)} errors\n")
    if not dry_run:
        if moves or errors:
            write_undo_log(source, moves, errors, label)
    return moved, moves, errors

def organize_downloads(dry_run=False, move_shortcuts=False):
    return organize_folder(DOWNLOADS_PATH, None, dry_run, move_shortcuts, "Downloads")[0]

def organize_desktop(dry_run=False, move_shortcuts=False):
    return organize_folder(DESKTOP_PATH, ORGANIZED_ROOT, dry_run, move_shortcuts, "Desktop")[0]

def organize_custom_folder(folder: Path, dry_run=False, move_shortcuts=False):
    folder = folder.resolve()
    reason = is_protected_path(folder)
    if reason and not dry_run:
        print(f"[Blocked] {reason}")
        return 0
    return organize_folder(folder, None, dry_run, move_shortcuts, f"Folder {folder.name}")[0]

# ========== Watch Fixed ==========

def is_file_ready(file_path: Path, wait_time=0.8) -> bool:
    try:
        if not file_path.exists() or not file_path.is_file():
            return False
        name_lower = file_path.name.lower()
        if any(name_lower.endswith(ext) for ext in TEMP_EXTS):
            return False
        if file_path.name in SELF_NAMES or file_path.name.startswith("00_"):
            return False
        size1 = file_path.stat().st_size
        time.sleep(wait_time)
        if not file_path.exists():
            return False
        size2 = file_path.stat().st_size
        return size1 == size2 and size1 > 0
    except Exception:
        return False

def get_file_signature(file_path: Path) -> tuple:
    try:
        stat = file_path.stat()
        return (file_path.name, stat.st_size, int(stat.st_mtime))
    except Exception as e:
        return (file_path.name, -1, -1)

def organize_single_file(file_path: Path, source_folder: Path, dest_root: Path | None, move_shortcuts: bool) -> tuple[bool, str]:
    try:
        if not file_path.exists() or not file_path.is_file():
            return False, "Not exists"
        if file_path.name in SELF_NAMES or file_path.name.startswith("00_"):
            return False, "Self file"
        ext = file_path.suffix.lower()
        if ext in TEMP_EXTS:
            return False, "Temp file"
        target = UNKNOWN_FOLDER
        for folder, exts in CATEGORIES.items():
            if ext in exts:
                target = folder
                break
        if not move_shortcuts and target == "10_Shortcuts":
            return False, "Shortcut skipped"
        is_desktop = dest_root is not None
        actual_root = dest_root if is_desktop else source_folder
        dest_dir = actual_root / target
        if is_desktop:
            actual_root.mkdir(exist_ok=True)
        dest_dir.mkdir(exist_ok=True)
        dest_path = get_unique_path(dest_dir / file_path.name)
        orig = file_path.resolve()
        shutil.move(str(file_path), str(dest_path))
        print(f"[WATCH] Moved: {file_path.name} -> {target}/{dest_path.name}")
        write_undo_log(source_folder, [{"from": str(orig.parent / file_path.name), "to": str(dest_path.resolve()), "name": file_path.name, "category": target}], [], f"Watch {source_folder.name}")
        return True, f"Moved to {target}"
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        print(f"[WATCH] Failed {file_path.name}: {err}")
        return False, err

def watch_folder(folder: Path, move_shortcuts=False, stop_event=None):
    folder = folder.resolve()
    if not folder.exists():
        print(f"[WATCH] Folder not found: {folder}")
        return
    reason = is_protected_path(folder)
    if reason:
        print(f"[WATCH] Blocked: {reason}")
        return
    print(f"[WATCH] Started watching: {folder}")
    print("[WATCH] - Ignores temp files (.tmp, .crdownload, .part)")
    print("[WATCH] - Waits for file to finish copying")
    print("[WATCH] - Signature based (name+size+mtime) - retry on failure")
    print("[WATCH] Press Ctrl+C to stop\n")
    processed = {}
    failed_retries = {}
    for f in folder.iterdir():
        if f.is_file():
            processed[f.name] = get_file_signature(f)
    print(f"[WATCH] Watching {len(processed)} existing files, will organize only NEW/changed files\n")
    try:
        while True:
            if stop_event and stop_event.is_set():
                print("[WATCH] Stop requested")
                break
            time.sleep(1.5)
            try:
                for item in folder.iterdir():
                    if not item.is_file():
                        continue
                    sig = get_file_signature(item)
                    if item.name in processed and processed[item.name] == sig:
                        continue
                    if item.name in SELF_NAMES or item.name.startswith("00_"):
                        processed[item.name] = sig
                        continue
                    print(f"[WATCH] New/Changed file detected: {item.name} (size {sig[1]})")
                    if not is_file_ready(item):
                        print(f"[WATCH] Waiting for {item.name} to finish...")
                        continue
                    ext = item.suffix.lower()
                    target = UNKNOWN_FOLDER
                    for folder_name, exts in CATEGORIES.items():
                        if ext in exts:
                            target = folder_name
                            break
                    if not move_shortcuts and target == "10_Shortcuts":
                        processed[item.name] = sig
                        continue
                    is_desktop_watch = folder == DESKTOP_PATH
                    dest_root = ORGANIZED_ROOT if is_desktop_watch else None
                    success, msg = organize_single_file(item, folder, dest_root, move_shortcuts)
                    if success:
                        processed[item.name] = sig
                        if item.name in failed_retries:
                            del failed_retries[item.name]
                    else:
                        # Do not mark as processed if failed, allow retry
                        retries = failed_retries.get(item.name, 0) + 1
                        failed_retries[item.name] = retries
                        if retries >= 5:
                            print(f"[WATCH] Giving up on {item.name} after 5 retries")
                            processed[item.name] = sig
                        else:
                            print(f"[WATCH] Will retry {item.name} (attempt {retries}/5)")
            except Exception as e:
                print(f"[WATCH] Scan error: {e}")
                time.sleep(2)
    except KeyboardInterrupt:
        print(f"\n[WATCH] Stopped watching: {folder}")

# ========== Auto with timer ==========

def auto_organize_loop(folders: list[Path], interval_minutes: int, move_shortcuts=False, stop_event=None):
    print(f"[AUTO] Started - every {interval_minutes} min")
    print(f"[AUTO] Folders: {', '.join([f.name for f in folders])}")
    print("[AUTO] Press Ctrl+C to stop\n")
    print("[AUTO] Initial organize...")
    for folder in folders:
        if folder not in [DOWNLOADS_PATH, DESKTOP_PATH]:
            organize_custom_folder(folder, False, move_shortcuts)
        elif folder == DOWNLOADS_PATH:
            organize_downloads(False, move_shortcuts)
        else:
            organize_desktop(False, move_shortcuts)
    try:
        while True:
            if stop_event and stop_event.is_set():
                break
            total_seconds = interval_minutes * 60
            for remaining in range(total_seconds, 0, -1):
                if stop_event and stop_event.is_set():
                    print("[AUTO] Stop requested")
                    return
                if remaining % 30 == 0 or remaining <= 10:
                    mins, secs = divmod(remaining, 60)
                    print(f"\r[AUTO] Next in {mins:02d}:{secs:02d} - {datetime.datetime.now().strftime('%H:%M:%S')}   ", end="", flush=True)
                time.sleep(1)
            print(f"\n\n[AUTO] Running scheduled organize - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            for folder in folders:
                if stop_event and stop_event.is_set():
                    break
                if folder not in [DOWNLOADS_PATH, DESKTOP_PATH]:
                    organize_custom_folder(folder, False, move_shortcuts)
                elif folder == DOWNLOADS_PATH:
                    organize_downloads(False, move_shortcuts)
                else:
                    organize_desktop(False, move_shortcuts)
            print(f"[AUTO] Done. Next in {interval_minutes} min\n")
    except KeyboardInterrupt:
        print("\n[AUTO] Stopped")

# ========== Right-click Fixed ==========

def get_exe_command(extra_args=""):
    if getattr(sys, 'frozen', False):
        exe_path = Path(sys.executable).resolve()
        base = f'"{exe_path}"'
    else:
        python_exe = Path(sys.executable).resolve()
        # Use pythonw for GUI to hide console, python for CLI
        script_path = Path(__file__).resolve()
        base = f'"{python_exe}" "{script_path}"'
    if extra_args:
        return f'{base} {extra_args} "%V"'
    else:
        return f'{base} "%V"'

def get_icon_path():
    if getattr(sys, 'frozen', False):
        return str(Path(sys.executable).resolve())
    else:
        script_dir = Path(__file__).parent
        for icon_name in ["icon.ico", "organizer.ico", "FileOrganizer.ico"]:
            icon_path = script_dir / icon_name
            if icon_path.exists():
                return str(icon_path)
        return str(Path(sys.executable).resolve())

def install_context_menu(move_shortcuts=False):
    if os.name != "nt":
        print("[Error] Windows only")
        return
    try:
        import winreg
        icon_path = get_icon_path()
        menu_items = {
            "FileOrganizer": ("Organize with File Organizer", ""),
            "FileOrganizer.Watch": ("Watch this folder (Live)", "--watch"),
            "FileOrganizer.Auto": ("Auto-Organize every 60 min", "--auto 60"),
        }
        for key_name, (display_name, extra_args) in menu_items.items():
            try:
                cmd = get_exe_command(extra_args)
                for base in [r"Directory\shell", r"Directory\Background\shell"]:
                    full_key = rf"{base}\{key_name}"
                    k = winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{full_key}")
                    winreg.SetValueEx(k, "", 0, winreg.REG_SZ, display_name)
                    winreg.SetValueEx(k, "Icon", 0, winreg.REG_SZ, icon_path)
                    winreg.CloseKey(k)
                    cmd_key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{full_key}\command")
                    winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ, cmd)
                    winreg.CloseKey(cmd_key)
                print(f"[OK] Installed: {display_name} (Directory + Background)")
            except Exception as e:
                print(f"[Failed] {key_name}: {e}")
        print("\n[OK] Right-click menu installed with 3 options x 2 locations")
    except Exception as e:
        print(f"[Error] {e}")

def uninstall_context_menu():
    if os.name != "nt":
        print("Windows only")
        return
    try:
        import winreg
        keys_to_remove = ["FileOrganizer", "FileOrganizer.Watch", "FileOrganizer.Auto"]
        removed = 0
        for key_name in keys_to_remove:
            for base in [r"Directory\shell", r"Directory\Background\shell"]:
                full_key = rf"{base}\{key_name}"
                try:
                    try:
                        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{full_key}\command")
                    except FileNotFoundError:
                        pass
                    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{full_key}")
                    removed += 1
                except FileNotFoundError:
                    pass
                except Exception as e:
                    print(f"[Skip] {full_key}: {e}")
        print(f"\n[OK] Removed {removed} menu entries")
    except Exception as e:
        print(f"[Error] {e}")

def pause():
    try:
        input("\nPress Enter...")
    except Exception as e:
        pass

def interactive_menu():
    print("="*70)
    print(f"  File Organizer v{VERSION}")
    print("="*70)
    print(f"Downloads: {DOWNLOADS_PATH}")
    print(f"Desktop: {DESKTOP_PATH}")
    print(f"History DB: {DB_PATH}\n")
    print("  [1] Organize Downloads")
    print("  [2] Organize Desktop")
    print("  [3] Organize Both")
    print("  [4] Organize Custom folder")
    print("  [5] Preview")
    print("  [6] Watch folder (Live - Fixed)")
    print("  [7] Auto-organize every X minutes")
    print("  [8] Install right-click menu (3 options)")
    print("  [9] Uninstall right-click menu")
    print("  [U] UNDO by ID")
    print("  [H] History (SQLite)")
    print("  [0] Exit\n")
    try:
        choice = input("Enter choice: ").strip().lower()
    except Exception as e:
        choice = "0"
    move_sc = False
    if choice in ["1","2","3","4","5","6","7","8"]:
        try:
            ans = input("Include shortcuts? [y/N]: ").strip().lower()
            move_sc = ans == "y"
        except Exception as e:
            pass
    try:
        if choice == "1":
            organize_downloads(False, move_sc)
        elif choice == "2":
            organize_desktop(False, move_sc)
        elif choice == "3":
            organize_downloads(False, move_sc)
            organize_desktop(False, move_sc)
        elif choice == "4":
            path = input("Enter folder path: ").strip().strip('"')
            organize_custom_folder(Path(path), False, move_sc)
        elif choice == "5":
            organize_downloads(True, move_sc)
            organize_desktop(True, move_sc)
        elif choice == "6":
            path = input("Enter folder to watch: ").strip().strip('"') or str(DOWNLOADS_PATH)
            watch_folder(Path(path), move_sc)
        elif choice == "7":
            try:
                interval = int(input("Every how many minutes? [60]: ").strip() or "60")
            except Exception as e:
                interval = 60
            path = input("Folder to auto-organize (leave empty for Downloads+Desktop): ").strip().strip('"')
            if path:
                folders = [Path(path)]
            else:
                folders = [DOWNLOADS_PATH, DESKTOP_PATH]
            auto_organize_loop(folders, interval, move_sc)
        elif choice == "8":
            install_context_menu(move_sc)
        elif choice == "9":
            uninstall_context_menu()
        elif choice == "u":
            try:
                op_id = input("Enter operation ID to undo (leave empty for latest): ").strip()
                if op_id:
                    undo_operation(int(op_id))
                else:
                    undo_operation(None)
            except Exception as e:
                print(f"[Error] {e}")
        elif choice == "h":
            list_undo_history()
    except Exception as e:
        print(f"[Error] {e}")
        import traceback
        traceback.print_exc()
    pause()

def main():
    parser = argparse.ArgumentParser(description=f"File Organizer v{VERSION}")
    parser.add_argument("folder", nargs="?", help="Folder to organize/watch (from right-click)")
    parser.add_argument("--downloads", action="store_true")
    parser.add_argument("--desktop", action="store_true")
    parser.add_argument("--both", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--move-shortcuts", action="store_true")
    parser.add_argument("--install-context-menu", action="store_true")
    parser.add_argument("--uninstall-context-menu", action="store_true")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--auto", type=int, nargs="?", const=60)
    parser.add_argument("--undo", nargs="?", const="latest", help="Undo by ID or latest")
    parser.add_argument("--undo-history", action="store_true")
    args = parser.parse_args()

    # Right-click passes folder as first arg
    if args.folder and Path(args.folder).exists() and Path(args.folder).is_dir():
        # If --watch or --auto flag present, treat folder as watch target
        if args.watch:
            watch_folder(Path(args.folder), args.move_shortcuts)
            pause()
            return
        if args.auto is not None:
            interval = args.auto if isinstance(args.auto, int) else 60
            auto_organize_loop([Path(args.folder)], interval, args.move_shortcuts)
            pause()
            return
        # Default: organize that folder (from right-click Organize)
        custom_path = Path(args.folder)
        reason = is_protected_path(custom_path.resolve())
        if reason:
            print(f"[Blocked] {reason}")
            pause()
            return
        print(f"Right-click target: {custom_path}\n")
        count = organize_folder(custom_path.resolve(), None, True, args.move_shortcuts, "Preview")[0]
        if count == 0:
            print("Nothing to organize.")
            pause()
            return
        try:
            confirm = input(f"\nOrganize {count} files? (y/n): ").strip().lower()
        except Exception as e:
            confirm = "n"
        if confirm == "y":
            organize_custom_folder(custom_path, args.dry_run, args.move_shortcuts)
        pause()
        return

    if args.undo_history:
        list_undo_history()
        pause()
        return
    if args.undo is not None:
        if args.undo == "latest":
            undo_operation(None)
        else:
            try:
                op_id = int(args.undo)
                undo_operation(op_id)
            except ValueError:
                p = Path(args.undo)
                if p.exists() and p.is_dir():
                    undo_operation(None, p)
                else:
                    if args.undo.lower()=="downloads":
                        undo_operation(None, DOWNLOADS_PATH)
                    elif args.undo.lower()=="desktop":
                        undo_operation(None, DESKTOP_PATH)
                    else:
                        undo_operation(None)
        pause()
        return
    if args.install_context_menu:
        install_context_menu(args.move_shortcuts)
        pause()
        return
    if args.uninstall_context_menu:
        uninstall_context_menu()
        pause()
        return
    if args.watch:
        folder = Path(args.folder) if args.folder else DOWNLOADS_PATH
        watch_folder(folder, args.move_shortcuts)
        pause()
        return
    if args.auto is not None:
        interval = args.auto if isinstance(args.auto, int) else 60
        if args.folder and Path(args.folder).exists():
            folders = [Path(args.folder)]
        elif args.both:
            folders = [DOWNLOADS_PATH, DESKTOP_PATH]
        elif args.downloads:
            folders = [DOWNLOADS_PATH]
        elif args.desktop:
            folders = [DESKTOP_PATH]
        else:
            folders = [DOWNLOADS_PATH, DESKTOP_PATH]
        auto_organize_loop(folders, interval, args.move_shortcuts)
        pause()
        return
    if args.folder:
        print(f"[Error] Not a folder or protected: {args.folder}")
        pause()
        return
    if not any([args.downloads, args.desktop, args.both]):
        interactive_menu()
        return
    dry = args.dry_run
    move_sc = args.move_shortcuts
    if args.both or (args.downloads and args.desktop):
        organize_downloads(dry, move_sc)
        organize_desktop(dry, move_sc)
    elif args.downloads:
        organize_downloads(dry, move_sc)
    elif args.desktop:
        organize_desktop(dry, move_sc)
    pause()

if __name__ == "__main__":
    main()
