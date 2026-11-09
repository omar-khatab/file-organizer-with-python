"""
File Organizer FREE v3.2 - Omar Khatab
# FREE Edition: 12 categories incl. Audio, Watch + Auto, History + Undo
# PRO Edition adds: Editable Categories, Single Instance, Quiet Right-Click + Priority Support
Fixes v3.1 -> v3.2:
1. Watch batch in memory -> immediate DB insert under open session, flush every 60s, Quit stops worker then quits
2. Start with Windows: --background flag + QSettings/JSON persistence, restores Watch/Auto
3. Tray: app.setQuitOnLastWindowClosed(False)
4. Crash on startup: blockSignals for startup_check, isChecked() not state==2, log_text created earlier
5. argparse: parse_known_args, robust --auto handling, --downloads etc handled
6. closeEvent blocks batch_running
7. Undo missing counter
8. Packaging: get_resource_path for icon.ico via sys._MEIPASS

v3.2.1 (bug-fix release):
9.  Closing the window with nothing running now really exits (was a hidden zombie process); "No" on the tray prompt now quits
10. Watch no longer writes an empty history row every minute (sessions are created on the first move)
11. Skips desktop.ini / Thumbs.db / hidden+system files and the app's own exe
12. Undo is blocked while Watch is running
13. Downloads/Desktop resolved from Windows shell folders first (OneDrive / moved folders)
14. Log text is HTML-escaped
15. Install Right-Click is a toggle like Pro: the button reads "Remove Right-Click" once installed (and --uninstall-context-menu works from the command line)

v3.2.4: History no longer shows the internal ID (it has a Type column instead: Watch / Auto / Manual); Watch and Auto can run together
        (they take turns moving files, so they never fight over the same file)
v3.2.3: tray icon now appears even without icon.ico (PySide6 6.x broke SP_ComputerIcon); with no tray the window is never hidden
v3.2.2 (more bug fixes):
16. Target combo follows the folder shown in the path box (it always fell back to Downloads)
17. Browse / drag&drop no longer pop a second folder dialog; changing the folder stops a running Watch
18. Stats timer no longer shows a modal "Blocked" dialog every 10s
19. Right-click icon uses the exe itself (the _MEIPASS temp folder is deleted on exit)
20. Log is capped; --auto 0 is clamped to 1 minute; settings are merged instead of overwritten
21. Stale Watch sessions from a crash are closed at startup and empty Watch rows are cleaned up
"""

from __future__ import annotations
import sys, os, json, shutil, datetime, time, sqlite3, html, threading
from pathlib import Path
from collections import defaultdict

try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QLabel, QLineEdit, QFileDialog, QTextEdit, QCheckBox,
        QComboBox, QGroupBox, QFrame, QProgressBar, QMessageBox, QGraphicsDropShadowEffect,
        QDialog, QTableWidget, QTableWidgetItem, QHeaderView, QDialogButtonBox, QSystemTrayIcon, QMenu, QStyle
    )
    from PySide6.QtCore import Qt, QThread, Signal, QTimer, QMutex
    from PySide6.QtGui import QColor, QAction, QIcon
except ImportError:
    print("PySide6 not found. Install with: pip install PySide6")
    sys.exit(1)

def get_resource_path(relative: str) -> Path:
    """Handles PyInstaller --onefile with --add-data"""
    try:
        if hasattr(sys, '_MEIPASS'):
            return Path(sys._MEIPASS) / relative
    except Exception as e:
        print(f"get_resource_path MEIPASS check failed: {e}")
    return Path(__file__).parent / relative

def hide_black_console():
    if sys.platform == "win32":
        try:
            import ctypes
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 0)
        except Exception as e:
            print(f"hide console failed: {e}")

# Hide console only for GUI mode (no CLI flags)
CLI_FLAGS = {"--watch", "--auto", "--downloads", "--desktop", "--both", "--dry-run", "--install-context-menu", "--uninstall-context-menu", "--undo", "--undo-history", "--background", "--minimized"}
has_cli = any(arg in CLI_FLAGS for arg in sys.argv[1:])
is_folder_arg = len(sys.argv) == 2 and Path(sys.argv[1]).exists()
if not has_cli and (len(sys.argv) == 1 or is_folder_arg):
    hide_black_console()

HOME = Path.home()
SETTINGS_PATH = HOME / ".file_organizer" / "settings.json"

def _make_guid(folder_id: str):
    """ctypes GUID with the exact memory layout Windows expects (same bytes as uuid.bytes_le)."""
    import ctypes, uuid
    class GUID(ctypes.Structure):
        _fields_ = [("Data1", ctypes.c_uint32), ("Data2", ctypes.c_uint16), ("Data3", ctypes.c_uint16), ("Data4", ctypes.c_ubyte * 8)]  # fixed sizes: c_ulong is 8 bytes on Linux
    u = uuid.UUID(folder_id)
    return GUID(u.time_low, u.time_mid, u.time_hi_version, (ctypes.c_ubyte * 8)(*u.bytes[8:]))

def _known_folder_path(folder_id: str):
    """SHGetKnownFolderPath: the one API that always knows about moved / OneDrive-redirected folders."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes
        guid = _make_guid(folder_id)
        fn = ctypes.windll.shell32.SHGetKnownFolderPath
        fn.argtypes = [ctypes.POINTER(type(guid)), wintypes.DWORD, wintypes.HANDLE, ctypes.POINTER(ctypes.c_void_p)]
        fn.restype = ctypes.c_long
        ptr = ctypes.c_void_p()
        if fn(ctypes.byref(guid), 0, None, ctypes.byref(ptr)) != 0:
            return None
        try:
            return ctypes.wstring_at(ptr.value)
        finally:
            ctypes.windll.ole32.CoTaskMemFree(ptr)
    except Exception as e:
        print(f"SHGetKnownFolderPath({folder_id}) failed: {e}")
        return None

def get_shell_folder(known_folder_id: str, reg_value: str, fallbacks: list) -> Path:
    """Where Windows really keeps a user folder: shell API, then User Shell Folders, then Shell Folders, then defaults."""
    candidates = [_known_folder_path(known_folder_id)]
    if sys.platform == "win32":
        try:
            import winreg
            for key_name in ("User Shell Folders", "Shell Folders"):
                try:
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf"Software\Microsoft\Windows\CurrentVersion\Explorer\{key_name}") as key:
                        candidates.append(os.path.expandvars(winreg.QueryValueEx(key, reg_value)[0]))  # REG_EXPAND_SZ has %VARS%
                except OSError:
                    continue
        except ImportError:
            pass
    for candidate in candidates:
        if candidate and Path(candidate).is_dir():
            return Path(candidate)
    for fb in fallbacks:
        if fb.is_dir():
            return fb
    return fallbacks[0]

DOWNLOADS_PATH = get_shell_folder("{374DE290-123F-4565-9164-39C4925E467B}", "{374DE290-123F-4565-9164-39C4925E467B}", [HOME / "Downloads"])

def find_desktop() -> Path:
    return get_shell_folder("{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}", "Desktop", [HOME / "Desktop", HOME / "OneDrive" / "Desktop"])

DESKTOP_PATH = find_desktop()
ORGANIZED_ROOT = DESKTOP_PATH / "00_Desktop_Organized"
UNDO_ROOT = HOME / ".file_organizer" / "undo_logs"
UNDO_ROOT.mkdir(parents=True, exist_ok=True)
DB_PATH = HOME / ".file_organizer" / "history.db"
SELF_NAMES = {"Organize-All.py", "Organize-PySide6.py", "Organize-GUI.py", "FileOrganizer-Modern.exe", "Organize-PySide6.pyw", "Organize-GUI.pyw"}
MENU_BASES = [r"Directory\shell", r"Directory\Background\shell"]
MENU_KEY_NAMES = ["FileOrganizer", "FileOrganizer.Watch", "FileOrganizer.Auto"]

def is_menu_installed() -> bool:
    try:
        import winreg
    except ImportError:
        return False
    for base in MENU_BASES:
        for name in MENU_KEY_NAMES:
            try:
                winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{base}\{name}"))
                return True
            except OSError:
                continue
    return False

def uninstall_context_menu():
    """Remove every right-click entry this app created. Returns (removed_count, errors)."""
    try:
        import winreg
    except ImportError:
        return 0, ["Windows registry is not available on this system"]
    removed, errors = 0, []
    for base in MENU_BASES:
        for name in MENU_KEY_NAMES:
            path = rf"Software\Classes\{base}\{name}"
            for sub_path in (path + r"\command", path):  # a key with sub-keys can't be deleted, so command goes first
                try:
                    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, sub_path)
                    if sub_path == path:
                        removed += 1
                except FileNotFoundError:
                    pass
                except OSError as e:
                    errors.append(f"{sub_path}: {e}")
    return removed, errors

FS_LOCK = threading.Lock()  # Watch and Organize/Auto take turns moving files, so they never fight over the same file
_SELF_LOWER = {n.lower() for n in SELF_NAMES}
if getattr(sys, "frozen", False):
    _SELF_LOWER.add(Path(sys.executable).name.lower())  # the packaged exe, whatever it is called
IGNORED_NAMES = {"desktop.ini", "thumbs.db"}

def should_skip(item: Path) -> bool:
    """Files the organizer must never touch: itself, shell metadata, hidden/system files."""
    if item.name.lower() in _SELF_LOWER or item.name.lower() in IGNORED_NAMES:
        return True
    try:
        attrs = getattr(item.stat(), "st_file_attributes", 0)
        if attrs & 0x2 or attrs & 0x4:  # FILE_ATTRIBUTE_HIDDEN / SYSTEM
            return True
    except OSError:
        pass
    return False

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
    "10_Audio": [".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma", ".opus", ".aiff"],
    "11_Shortcuts": [".lnk", ".url"],
}
UNKNOWN_FOLDER = "12_Others"
TEMP_EXTS = {".tmp", ".crdownload", ".part", ".partial", ".download", ".!ut"}

def _resolve(p) -> Path | None:
    try:
        return Path(p).resolve()
    except Exception as e:
        print(f"_resolve failed for {p}: {e}")
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
        return f"Protected location: {resolved}"
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

# ========== Settings ==========

def load_settings() -> dict:
    try:
        if SETTINGS_PATH.exists():
            return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"load_settings failed: {e}")
    return {}

def save_settings(data: dict):
    try:
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"save_settings failed: {e}")

def update_setting(key, value):
    try:
        s = load_settings()
        s[key] = value
        s["last_updated"] = datetime.datetime.now().isoformat()
        save_settings(s)
    except Exception as e:
        print(f"update_setting {key} failed: {e}")

# ========== DB ==========

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS operations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT, readable_date TEXT, source_path TEXT,
            folder_name TEXT, label TEXT, file_count INTEGER,
            status TEXT DEFAULT 'done', error_count INTEGER DEFAULT 0
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS moves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operation_id INTEGER, from_path TEXT, to_path TEXT, name TEXT, category TEXT,
            FOREIGN KEY(operation_id) REFERENCES operations(id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operation_id INTEGER, file_name TEXT, error_msg TEXT,
            FOREIGN KEY(operation_id) REFERENCES operations(id)
        )
    """)
    # Sessions left open by a crash/kill: drop empty ones (older versions wrote one every minute), close the rest so they can be undone
    cur.execute("DELETE FROM operations WHERE status IN ('watch_open','done') AND file_count=0 AND error_count=0 AND label LIKE 'Watch %'")
    cur.execute("UPDATE operations SET status='done' WHERE status='watch_open'")
    conn.commit()
    conn.close()

init_db()

def write_undo_log(source: Path, moves: list[dict], errors: list[dict], label: str) -> tuple[int | None, str | None]:
    if not moves and not errors:
        return None, None
    now = datetime.datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    readable = now.strftime("%Y-%m-%d %I:%M %p")
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        cur.execute("INSERT INTO operations (timestamp, readable_date, source_path, folder_name, label, file_count, status, error_count) VALUES (?,?,?,?,?,?,?,?)",
                    (timestamp, readable, str(source.resolve()), source.name, label, len(moves), "done", len(errors)))
        op_id = cur.lastrowid
        for m in moves:
            cur.execute("INSERT INTO moves (operation_id, from_path, to_path, name, category) VALUES (?,?,?,?,?)",
                        (op_id, m.get("from"), m.get("to"), m.get("name"), m.get("category")))
        for e in errors:
            cur.execute("INSERT INTO errors (operation_id, file_name, error_msg) VALUES (?,?,?)",
                        (op_id, e.get("name"), e.get("error")))
        conn.commit()
        conn.close()
        return op_id, None
    except Exception as e:
        try:
            conn.close()
        except Exception:
            pass
        err_msg = f"DB write failed: {type(e).__name__}: {e}"
        print(err_msg)
        return None, err_msg

# Watch session with immediate writes

def create_watch_session(folder: Path) -> int | None:
    now = datetime.datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    readable = now.strftime("%Y-%m-%d %I:%M %p") + " (Watch session)"
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        cur.execute("INSERT INTO operations (timestamp, readable_date, source_path, folder_name, label, file_count, status, error_count) VALUES (?,?,?,?,?,?,?,?)",
                    (timestamp, readable, str(folder.resolve()), folder.name, f"Watch {folder.name} (open session)", 0, "watch_open", 0))
        op_id = cur.lastrowid
        conn.commit()
        conn.close()
        return op_id
    except Exception as e:
        print(f"create_watch_session failed: {e}")
        return None

def add_move_to_session(op_id: int, move: dict):
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        cur.execute("INSERT INTO moves (operation_id, from_path, to_path, name, category) VALUES (?,?,?,?,?)",
                    (op_id, move.get("from"), move.get("to"), move.get("name"), move.get("category")))
        cur.execute("UPDATE operations SET file_count = file_count + 1 WHERE id=?", (op_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"add_move_to_session failed: {e}")

def add_error_to_session(op_id: int, error: dict):
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        cur.execute("INSERT INTO errors (operation_id, file_name, error_msg) VALUES (?,?,?)",
                    (op_id, error.get("name"), error.get("error")))
        cur.execute("UPDATE operations SET error_count = error_count + 1 WHERE id=?", (op_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"add_error_to_session failed: {e}")

def close_watch_session(op_id: int):
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        now = datetime.datetime.now().strftime("%Y-%m-%d %I:%M %p")
        cur.execute("UPDATE operations SET status='done', readable_date=?, label=label || ' - closed' WHERE id=? AND status='watch_open'", (now, op_id))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"close_watch_session failed: {e}")

def undo_operation(op_id: int) -> tuple[int, int, int, int, str | None]:
    """Returns restored, failed, missing, total, error_msg. Only marks undone if failed==0"""
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    try:
        cur.execute("SELECT status FROM operations WHERE id=?", (op_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return 0, 0, 0, 0, f"Operation {op_id} not found"
        if row[0] != "done":
            conn.close()
            return 0, 0, 0, 0, f"Operation {op_id} already {row[0]}"
        cur.execute("SELECT from_path, to_path, name FROM moves WHERE operation_id=?", (op_id,))
        moves = cur.fetchall()
        restored = 0
        failed = 0
        missing = 0
        fail_details = []
        for from_path, to_path, name in reversed(moves):
            dst = Path(to_path)
            src = Path(from_path)
            if not dst.exists():
                missing += 1
                continue
            try:
                src.parent.mkdir(parents=True, exist_ok=True)
                final = get_unique_path(src)
                shutil.move(str(dst), str(final))
                restored += 1
            except Exception as e:
                failed += 1
                fail_details.append(f"{name}: {e}")
        if failed == 0:
            cur.execute("UPDATE operations SET status='undone' WHERE id=?", (op_id,))
            conn.commit()
            conn.close()
            return restored, 0, missing, len(moves), None
        else:
            conn.close()
            return restored, failed, missing, len(moves), "; ".join(fail_details[:5])
    except Exception as e:
        try:
            conn.close()
        except Exception:
            pass
        return 0, 0, 0, 0, f"Undo failed: {e}"

def organize_folder_core(source: Path, dest_root: Path | None, move_shortcuts: bool, label: str):
    if not source.exists():
        return 0, [], [{"name": str(source), "error": "Not found"}]
    reason = is_protected_path(source.resolve())
    if reason:
        return 0, [], [{"name": source.name, "error": reason}]
    is_desktop = dest_root is not None
    actual_root = dest_root if is_desktop else source
    if is_desktop:
        actual_root.mkdir(exist_ok=True)
    moved = 0
    moves = []
    errors = []
    try:
        items = list(source.iterdir())
    except Exception as e:
        return 0, [], [{"name": source.name, "error": f"Cannot list dir: {e}"}]
    for item in items:
        if should_skip(item) or item.name.startswith("00_") or item.is_dir():
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
        try:
            dest_dir.mkdir(exist_ok=True)
            orig = item.resolve()
            shutil.move(str(item), str(dest_path))
            moves.append({"from": str(orig.parent / item.name), "to": str(dest_path.resolve()), "name": item.name, "category": target})
            moved += 1
        except Exception as e:
            err_msg = f"{type(e).__name__}: {e}"
            errors.append({"name": item.name, "error": err_msg})
    if moves or errors:
        op_id, db_err = write_undo_log(source, moves, errors, label)
        if db_err:
            errors.append({"name": "DB", "error": db_err})
    return moved, moves, errors

def scan_folder_stats(folder: Path):
    counts = defaultdict(int)
    total = 0
    total_size = 0
    details = []
    try:
        for item in folder.iterdir():
            if item.is_file() and not should_skip(item) and not item.name.startswith("00_"):
                if item.suffix.lower() in TEMP_EXTS:
                    continue
                ext = item.suffix.lower()
                target = UNKNOWN_FOLDER
                for folder_name, exts in CATEGORIES.items():
                    if ext in exts:
                        target = folder_name
                        break
                counts[target] += 1
                total += 1
                try:
                    sz = item.stat().st_size
                    total_size += sz
                    if len(details) < 100:
                        details.append((item.name, target, sz))
                except Exception:
                    pass
    except Exception as e:
        print(f"[Stats Error] {e}")
    return total, dict(counts), total_size, details

# ========== Workers ==========

class OrganizeWorker(QThread):
    log_signal = Signal(str, str)
    finished_signal = Signal(int, dict, int, list)
    progress_signal = Signal(int)

    def __init__(self, folders, move_shortcuts, tag=""):
        super().__init__()
        self.folders = folders
        self.move_shortcuts = move_shortcuts
        self.tag = tag  # "Auto" for scheduled runs; shown as the Type in History

    def _label(self, base):
        return f"{self.tag} {base}".strip()

    def run(self):
        with FS_LOCK:  # if Watch is running it waits (a moment) instead of moving files at the same time
            self._run_all()

    def _run_all(self):
        total_moved = 0
        total_errors = 0
        all_counts = defaultdict(int)
        all_errors = []
        for idx, folder in enumerate(self.folders):
            self.progress_signal.emit(int((idx / len(self.folders)) * 100))
            if folder == DOWNLOADS_PATH:
                moved, moves, errors = organize_folder_core(folder, None, self.move_shortcuts, self._label("Downloads"))
            elif folder == DESKTOP_PATH:
                moved, moves, errors = organize_folder_core(folder, ORGANIZED_ROOT, self.move_shortcuts, self._label("Desktop"))
            else:
                moved, moves, errors = organize_folder_core(folder, None, self.move_shortcuts, self._label(f"Folder {folder.name}"))
            total_moved += moved
            total_errors += len(errors)
            for m in moves:
                all_counts[m.get('category', UNKNOWN_FOLDER)] += 1
                self.log_signal.emit(f"Moved: {m['name']} -> {m.get('category')}", "info")
            for e in errors:
                all_errors.append(e)
                self.log_signal.emit(f"Failed: {e['name']}: {e['error']}", "error")
        self.finished_signal.emit(total_moved, dict(all_counts), total_errors, all_errors)

class PreviewWorker(QThread):
    result_signal = Signal(int, dict, int, list)
    def __init__(self, folders):
        super().__init__()
        self.folders = folders
    def run(self):
        total = 0
        all_counts = defaultdict(int)
        total_size = 0
        all_details = []
        for folder in self.folders:
            t, counts, sz, details = scan_folder_stats(folder)
            total += t
            total_size += sz
            all_details.extend([(folder.name, n, cat) for n, cat, _ in details])
            for k,v in counts.items():
                all_counts[k] += v
        self.result_signal.emit(total, dict(all_counts), total_size, all_details)

class WatchWorker(QThread):
    log_signal = Signal(str, str)
    stopped_signal = Signal()

    def __init__(self, folder, move_shortcuts, batch_interval_sec=60):
        super().__init__()
        self.folder = folder
        self.move_shortcuts = move_shortcuts
        self._stop = False
        self.batch_interval = batch_interval_sec
        self.current_op_id = None
        self.last_flush = time.time()
        self.pending_log_times = {}

    def stop(self):
        self._stop = True

    def _ensure_session(self):
        if not self.current_op_id:
            self.current_op_id = create_watch_session(self.folder)
            if self.current_op_id:
                self.log_signal.emit(f"Watch session {self.current_op_id} started", "info")
        return self.current_op_id

    def is_file_ready(self, file_path: Path):
        try:
            if not file_path.exists() or not file_path.is_file():
                return False
            name_lower = file_path.name.lower()
            if any(name_lower.endswith(ext) for ext in TEMP_EXTS):
                return False
            if should_skip(file_path) or file_path.name.startswith("00_"):
                return False
            size1 = file_path.stat().st_size
            time.sleep(0.8)
            if not file_path.exists():
                return False
            size2 = file_path.stat().st_size
            return size1 == size2 and size1 > 0
        except Exception:
            return False

    def get_sig(self, p: Path):
        try:
            s = p.stat()
            return (p.name, s.st_size, int(s.st_mtime))
        except Exception as e:
            print(f"get_sig failed {p}: {e}")
            return (p.name, -1, -1)

    def run(self):
        # Sessions are created on the first move/error, so Watch never writes empty history rows
        self.current_op_id = None

        processed = {}
        failed_retries = {}
        try:
            for f in self.folder.iterdir():
                if f.is_file():
                    processed[f.name] = self.get_sig(f)
        except Exception as e:
            self.log_signal.emit(f"Initial scan failed: {e}", "error")
        self.log_signal.emit(f"Watching {len(processed)} existing files, immediate DB + batch close every {self.batch_interval}s", "info")

        while not self._stop:
            time.sleep(1.5)
            if not self.folder.exists() or self._stop:
                break
            # Close and create new session every interval
            if time.time() - self.last_flush >= self.batch_interval:
                if self.current_op_id:
                    close_watch_session(self.current_op_id)
                    self.log_signal.emit(f"Closed watch session {self.current_op_id}", "info")
                self.current_op_id = None  # the next session is created on the next move
                self.last_flush = time.time()

            try:
                for item in self.folder.iterdir():
                    if self._stop:
                        break
                    if not item.is_file():
                        continue
                    sig = self.get_sig(item)
                    if item.name in processed and processed[item.name] == sig:
                        continue
                    if should_skip(item) or item.name.startswith("00_"):
                        processed[item.name] = sig
                        continue
                    now = time.time()
                    last = self.pending_log_times.get(item.name, 0)
                    if now - last >= 5.0:
                        self.log_signal.emit(f"New/Changed: {item.name}", "info")
                        self.pending_log_times[item.name] = now
                    if not self.is_file_ready(item):
                        if now - self.pending_log_times.get(item.name+"_waiting", 0) >= 5.0:
                            self.log_signal.emit(f"Waiting {item.name} to finish...", "warning")
                            self.pending_log_times[item.name+"_waiting"] = now
                        continue
                    ext = item.suffix.lower()
                    target = UNKNOWN_FOLDER
                    for folder_name, exts in CATEGORIES.items():
                        if ext in exts:
                            target = folder_name
                            break
                    if not self.move_shortcuts and target == "10_Shortcuts":
                        processed[item.name] = sig
                        continue
                    dest_root = ORGANIZED_ROOT if self.folder == DESKTOP_PATH else None
                    actual_root = dest_root if dest_root else self.folder
                    if dest_root:
                        try:
                            actual_root.mkdir(exist_ok=True)
                        except Exception as e:
                            self.log_signal.emit(f"Cannot create {actual_root}: {e}", "error")
                            continue
                    dest_dir = actual_root / target
                    if not FS_LOCK.acquire(timeout=1.0):
                        continue  # Auto/Organize is moving files right now - this file is picked up again next round
                    try:
                        if not item.exists():  # Auto/Organize already moved it
                            continue
                        dest_dir.mkdir(exist_ok=True)
                        dest_path = get_unique_path(dest_dir / item.name)
                        orig = item.resolve()
                        shutil.move(str(item), str(dest_path))
                        self.log_signal.emit(f"Moved: {item.name} -> {target} (DB immediate)", "success")
                        move_dict = {"from": str(orig.parent / item.name), "to": str(dest_path.resolve()), "name": item.name, "category": target}
                        if self._ensure_session():
                            add_move_to_session(self.current_op_id, move_dict)
                        processed[item.name] = sig
                        if item.name in failed_retries:
                            del failed_retries[item.name]
                        self.pending_log_times.pop(item.name, None)
                        self.pending_log_times.pop(item.name+"_waiting", None)
                    except Exception as e:
                        err = f"{type(e).__name__}: {e}"
                        self.log_signal.emit(f"Failed {item.name}: {err}", "error")
                        if self._ensure_session():
                            add_error_to_session(self.current_op_id, {"name": item.name, "error": err})
                        retries = failed_retries.get(item.name, 0) + 1
                        failed_retries[item.name] = retries
                        if retries >= 5:
                            self.log_signal.emit(f"Giving up on {item.name} after 5 retries", "error")
                            processed[item.name] = sig
                    finally:
                        FS_LOCK.release()
            except Exception as e:
                self.log_signal.emit(f"Scan error: {e}", "error")
                time.sleep(2)

        # Final close
        if self.current_op_id:
            close_watch_session(self.current_op_id)
            self.log_signal.emit(f"Closed final session {self.current_op_id}", "info")
        self.stopped_signal.emit()

class StatsWorker(QThread):
    stats_signal = Signal(int, dict, int)
    def __init__(self, folder):
        super().__init__()
        self.folder = folder
    def run(self):
        total, counts, size, _ = scan_folder_stats(self.folder)
        self.stats_signal.emit(total, counts, size)

# ========== History Dialog ==========

class HistoryDialog(QDialog):
    def __init__(self, parent=None, lang="en"):
        super().__init__(parent)
        self.lang = lang
        self.setWindowTitle("السجل - History" if lang=="ar" else "History")
        self.resize(950, 550)
        self.setup_ui()
        self.load_history()

    def tr(self, en, ar):
        return ar if self.lang=="ar" else en

    def setup_ui(self):
        layout = QVBoxLayout(self)
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            self.tr("Date", "التاريخ"), self.tr("Type", "النوع"), self.tr("Folder", "المجلد"),
            self.tr("Files", "الملفات"), self.tr("Status", "الحالة"), self.tr("Errors", "أخطاء"), self.tr("Source", "المسار")
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)
        btn_layout = QHBoxLayout()
        self.undo_btn = QPushButton(self.tr("Undo Selected", "استرجاع المحدد"))
        self.undo_btn.setObjectName("danger")
        self.undo_btn.clicked.connect(self.undo_selected)
        self.refresh_btn = QPushButton(self.tr("Refresh", "تحديث"))
        self.refresh_btn.setObjectName("secondary")
        self.refresh_btn.clicked.connect(self.load_history)
        self.details_btn = QPushButton(self.tr("Show Details", "تفاصيل"))
        self.details_btn.setObjectName("secondary")
        self.details_btn.clicked.connect(self.show_details)
        btn_layout.addWidget(self.undo_btn)
        btn_layout.addWidget(self.details_btn)
        btn_layout.addWidget(self.refresh_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def load_history(self):
        try:
            conn = sqlite3.connect(str(DB_PATH))
            cur = conn.cursor()
            cur.execute("SELECT id, readable_date, folder_name, file_count, status, error_count, source_path, label FROM operations WHERE status!='watch_open' AND (file_count>0 OR error_count>0) ORDER BY id DESC LIMIT 100")
            rows = cur.fetchall()
            conn.close()
        except Exception as e:
            print(f"load_history failed: {e}")
            rows = []
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            label = str(r[7] or "")
            if label.startswith("Watch"):
                kind = self.tr("Watch", "مراقبة")
            elif label.startswith("Auto"):
                kind = self.tr("Auto", "تلقائي")
            else:
                kind = self.tr("Manual", "يدوي")
            shown = [r[1], kind, r[2], r[3], r[4], r[5], r[6]]  # the internal ID stays in self.rows only, it is never displayed
            for j, val in enumerate(shown):
                self.table.setItem(i, j, QTableWidgetItem(str(val)))
        self.rows = rows

    def _row_text(self, row):
        r = self.rows[row]
        return f"{r[1]} | {r[2]} | {r[3]} files"

    def undo_selected(self):
        owner = self.parent()
        if owner is not None and getattr(owner, "watch_running", False):
            QMessageBox.warning(self, self.tr("Watch running", "المراقبة شغالة"), self.tr("Stop Watch before undoing an operation", "أوقف المراقبة قبل الاسترجاع"))
            return
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.warning(self, self.tr("No selection", "لم تحدد"), self.tr("Select an operation first", "اختر عملية أولا"))
            return
        row = selected[0].row()
        op_id = self.rows[row][0]
        status = self.rows[row][4]
        if status != "done":
            QMessageBox.warning(self, self.tr("Already undone", "تم استرجاعه"), self.tr("This operation is already undone", "تم استرجاعها مسبقا"))
            return
        reply = QMessageBox.question(self, self.tr("Confirm Undo", "تأكيد"), self.tr(f"Undo this operation?\n{self._row_text(row)}", f"استرجاع هذه العملية؟\n{self._row_text(row)}"), QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        restored, failed, missing, total, err = undo_operation(op_id)
        if failed>0 or missing>0:
            QMessageBox.warning(self, self.tr("Partial", "جزئي"), self.tr(f"Restored {restored}/{total}, failed {failed}, missing {missing}: {err}", f"تم {restored}/{total}، فشل {failed}، مفقود {missing}: {err}"))
        else:
            QMessageBox.information(self, self.tr("Done", "تم"), self.tr(f"Restored {restored}/{total}", f"تم {restored}/{total}"))
        self.load_history()

    def show_details(self):
        selected = self.table.selectedItems()
        if not selected:
            return
        row = selected[0].row()
        op_id = self.rows[row][0]
        try:
            conn = sqlite3.connect(str(DB_PATH))
            cur = conn.cursor()
            cur.execute("SELECT name, category, to_path FROM moves WHERE operation_id=?", (op_id,))
            moves = cur.fetchall()
            cur.execute("SELECT file_name, error_msg FROM errors WHERE operation_id=?", (op_id,))
            errors = cur.fetchall()
            conn.close()
        except Exception as e:
            print(f"show_details db failed: {e}")
            moves, errors = [], []
        details = f"{self._row_text(row)} - {len(moves)} files, {len(errors)} errors\n\n"
        for name, cat, to_path in moves[:100]:
            details += f"{name} -> {cat}\n"
        if errors:
            details += "\nErrors:\n"
            for fname, err in errors:
                details += f"{fname}: {err}\n"
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Details - {self.rows[row][1]}")
        dlg.resize(650, 450)
        lay = QVBoxLayout(dlg)
        txt = QTextEdit()
        txt.setReadOnly(True)
        txt.setText(details)
        lay.addWidget(txt)
        btn = QDialogButtonBox(QDialogButtonBox.Close)
        btn.rejected.connect(dlg.reject)
        lay.addWidget(btn)
        dlg.exec()

# ========== Modern Card ==========

class ModernCard(QFrame):
    def __init__(self, title, value="0", color="#6366f1"):
        super().__init__()
        self.setObjectName("card")
        self.setStyleSheet(f"""
            #card {{ background-color: #1e1e1e; border-radius: 12px; border: 1px solid #2d2d2d; }}
            QLabel {{ color: #ffffff; background: transparent; border: none; }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("color: #888888; font-size: 11px; font-weight: 600;")
        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(f"color: {color}; font-size: 22px; font-weight: 700;")
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)

    def set_value(self, val):
        self.value_label.setText(str(val))

    def set_title(self, title):
        self.title_label.setText(title)

def refresh_button_style(btn):
    try:
        btn.style().unpolish(btn)
        btn.style().polish(btn)
        btn.update()
    except Exception as e:
        print(f"refresh style failed: {e}")

# ========== Main Window ==========

class MainWindow(QMainWindow):
    def __init__(self, initial_folder: Path | None = None, start_watch: bool = False, start_auto: int | None = None, start_background: bool = False):
        super().__init__()
        self.setWindowTitle("File Organizer FREE v3.2 - Free Edition")
        self.setGeometry(100, 100, 1150, 780)
        self.start_background = start_background
        # Load settings first
        self.settings = load_settings()
        self.lang = self.settings.get("lang", "en")
        self.translations = {
            "en": {
                "title": "File Organizer", "subtitle": "FREE v3.2 - Watch + Auto + History",
                "target": "Target Folder", "actions": "Actions", "system": "System",
                "total": "Total Files", "pdfs": "PDFs", "images": "Images",
                "preview": "Preview", "organize": "Organize Now", "watch": "Watch Live",
                "stop_watch": "Stop Watch", "auto": "Auto", "stop_auto": "Stop Auto",
                "install": "Install Right-Click", "uninstall": "Remove Right-Click", "undo": "Undo Latest", "history": "History",
                "browse": "Browse", "include_short": "Include shortcuts", "live_log": "Live Log",
                "clear": "Clear", "stop": "Stop", "busy": "Busy", "confirm": "Confirm",
                "done": "Done", "error": "Error", "no_folder": "Select valid folder",
                "watch_needs_one": "Watch needs one folder", "organize_confirm": "Organize {n} folder(s)? Undo available via History.",
                "organized": "Organized {n} files!", "blocked": "Blocked", "already_undone": "Already undone",
                "no_selection": "No selection", "select_op": "Select an operation first",
                "auto_running": "Auto: every {m} min - Running", "auto_stopped": "Auto: Stopped",
                "startup": "Start with Windows", "tray_hide": "Minimized to tray - Watch/Auto still running",
                "batch_running": "Organize running - cannot close now",
                "quit_confirm": "Watch/Auto running - minimize to tray instead?"
            },
            "ar": {
                "title": "منظم الملفات", "subtitle": "FREE v3.2 - مجاني - مراقبة + تنظيم تلقائي",
                "target": "المجلد الهدف", "actions": "العمليات", "system": "النظام",
                "total": "إجمالي الملفات", "pdfs": "PDF", "images": "الصور",
                "preview": "معاينة", "organize": "نظم الآن", "watch": "مراقبة مباشرة",
                "stop_watch": "إيقاف المراقبة", "auto": "تلقائي", "stop_auto": "إيقاف التلقائي",
                "install": "تثبيت كليك يمين", "uninstall": "إزالة كليك يمين", "undo": "استرجاع الأخير", "history": "السجل",
                "browse": "تصفح", "include_short": "تضمين الاختصارات", "live_log": "السجل المباشر",
                "clear": "مسح", "stop": "إيقاف", "busy": "مشغول", "confirm": "تأكيد",
                "done": "تم", "error": "خطأ", "no_folder": "اختر مجلد صحيح",
                "watch_needs_one": "المراقبة تحتاج مجلد واحد", "organize_confirm": "تنظيم {n} مجلد؟ يمكن الاسترجاع من السجل.",
                "organized": "تم تنظيم {n} ملف!", "blocked": "محمي", "already_undone": "تم استرجاعه",
                "no_selection": "لم تحدد", "select_op": "اختر عملية أولا",
                "auto_running": "تلقائي: كل {m} دقيقة - شغال", "auto_stopped": "تلقائي: متوقف",
                "startup": "ابدأ مع ويندوز", "tray_hide": "تم التصغير للـ tray - المراقبة لا تزال شغالة",
                "batch_running": "التنظيم شغال - لا يمكن الإغلاق الآن",
                "quit_confirm": "المراقبة شغالة - تصغير للـ tray بدل الإغلاق؟"
            }
        }
        self.setStyleSheet(self.get_dark_stylesheet())
        # Determine folder
        if initial_folder:
            self.current_folder = initial_folder
        else:
            last_folder_str = self.settings.get("last_folder")
            if last_folder_str and Path(last_folder_str).exists():
                self.current_folder = Path(last_folder_str)
            else:
                self.current_folder = DOWNLOADS_PATH
        self.initial_watch = start_watch or self.settings.get("watch_was_active", False)
        self.initial_auto = start_auto if start_auto is not None else (self.settings.get("auto_interval") if self.settings.get("auto_was_active") else None)
        self.watch_worker = None
        self.auto_timer = None
        self.auto_folders = []
        self.stats_worker = None
        self.preview_worker = None
        self.batch_running = False
        self.watch_running = False
        self.auto_running = False
        self.mutex = QMutex()
        self.setup_ui()
        self.setup_tray()
        self.update_stats()
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self.update_stats)
        self.stats_timer.start(10000)
        # Restore state
        if self.settings.get("auto_interval"):
            try:
                interval = int(self.settings["auto_interval"])
                # Set combo
                for i in range(self.auto_interval.count()):
                    if str(interval) in self.auto_interval.itemText(i):
                        self.auto_interval.setCurrentIndex(i)
                        break
            except Exception as e:
                print(f"restore interval failed: {e}")
        # Auto-start if needed
        if self.initial_watch and self.current_folder:
            QTimer.singleShot(700, self.toggle_watch)
        if self.initial_auto is not None and self.current_folder:
            QTimer.singleShot(1000, lambda: self.start_auto_with_interval(int(self.initial_auto) if isinstance(self.initial_auto, int) else 60))

    def tr_txt(self, key, **kwargs):
        txt = self.translations[self.lang].get(key, key)
        try:
            return txt.format(**kwargs)
        except Exception:
            return txt

    def get_dark_stylesheet(self):
        return """
            QMainWindow { background-color: #121212; }
            QWidget { background-color: #121212; color: #e0e0e0; font-family: 'Segoe UI', sans-serif; }
            QGroupBox { background-color: #1e1e1e; border: 1px solid #2d2d2d; border-radius: 12px; margin-top: 12px; padding-top: 20px; font-weight: 600; }
            QGroupBox::title { subcontrol-origin: margin; left: 16px; padding: 0 8px; color: #888888; }
            QPushButton { background-color: #6366f1; color: white; border: none; border-radius: 8px; padding: 10px 20px; font-weight: 600; font-size: 13px; }
            QPushButton:hover { background-color: #5454d4; }
            QPushButton#secondary { background-color: #2d2d2d; color: #e0e0e0; }
            QPushButton#secondary:hover { background-color: #3a3a3a; }
            QPushButton#danger { background-color: #ef4444; }
            QPushButton#danger:hover { background-color: #dc2626; }
            QPushButton#success { background-color: #10b981; }
            QPushButton#success:hover { background-color: #059669; }
            QLineEdit, QComboBox { background-color: #2d2d2d; border: 1px solid #3a3a3a; border-radius: 8px; padding: 10px 12px; color: #e0e0e0; }
            QTextEdit { background-color: #1e1e1e; border: 1px solid #2d2d2d; border-radius: 12px; padding: 12px; font-family: 'Consolas', monospace; font-size: 12px; }
            QCheckBox { spacing: 8px; }
            QCheckBox::indicator { width: 20px; height: 20px; border-radius: 4px; border: 1px solid #3a3a3a; background-color: #2d2d2d; }
            QCheckBox::indicator:checked { background-color: #6366f1; border-color: #6366f1; }
            QProgressBar { background-color: #2d2d2d; border: none; border-radius: 4px; height: 6px; }
            QProgressBar::chunk { background-color: #6366f1; border-radius: 4px; }
            QTableWidget { background-color: #1e1e1e; border: 1px solid #2d2d2d; border-radius: 8px; }
        """

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(16, 16, 16, 16)
        left_panel = QVBoxLayout()
        left_panel.setSpacing(16)

        header_layout = QHBoxLayout()
        header_text = QVBoxLayout()
        self.title_label = QLabel(self.tr_txt("title"))
        self.title_label.setStyleSheet("font-size: 24px; font-weight: 800; color: white;")
        self.subtitle_label = QLabel(self.tr_txt("subtitle"))
        self.subtitle_label.setStyleSheet("font-size: 11px; color: #6366f1; font-weight: 600;")
        header_text.addWidget(self.title_label)
        header_text.addWidget(self.subtitle_label)
        header_layout.addLayout(header_text)
        header_layout.addStretch()
        self.lang_btn = QPushButton("عربي / EN")
        self.lang_btn.setObjectName("secondary")
        self.lang_btn.clicked.connect(self.toggle_lang)
        header_layout.addWidget(self.lang_btn)
        left_panel.addLayout(header_layout)

        stats_layout = QHBoxLayout()
        self.card_total = ModernCard(self.tr_txt("total"), "0", "#6366f1")
        self.card_pdfs = ModernCard(self.tr_txt("pdfs"), "0", "#ef4444")
        self.card_images = ModernCard(self.tr_txt("images"), "0", "#10b981")
        stats_layout.addWidget(self.card_total)
        stats_layout.addWidget(self.card_pdfs)
        stats_layout.addWidget(self.card_images)
        left_panel.addLayout(stats_layout)

        # Right panel created early to avoid crash when startup_check triggers log before log_text exists
        right_panel = QVBoxLayout()
        self.log_group = QGroupBox(self.tr_txt("live_log"))
        log_layout = QVBoxLayout(self.log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.document().setMaximumBlockCount(3000)  # a long-running Watch must not grow the log forever
        self.log_text.setPlaceholderText("Logs... Drag & drop any folder!")
        log_layout.addWidget(self.log_text)
        log_btns = QHBoxLayout()
        clear_btn = QPushButton(self.tr_txt("clear"))
        clear_btn.setObjectName("secondary")
        clear_btn.clicked.connect(lambda: self.log_text.clear())
        self.stop_btn = QPushButton(self.tr_txt("stop"))
        self.stop_btn.setObjectName("danger")
        self.stop_btn.clicked.connect(self.do_stop)
        self.stop_btn.setEnabled(False)
        log_btns.addWidget(clear_btn)
        log_btns.addWidget(self.stop_btn)
        log_btns.addStretch()
        log_layout.addLayout(log_btns)
        right_panel.addWidget(self.log_group)

        self.target_group = QGroupBox(self.tr_txt("target"))
        target_layout = QVBoxLayout(self.target_group)
        combo_layout = QHBoxLayout()
        self.target_combo = QComboBox()
        self.target_combo.addItems(["Downloads", "Desktop", "Both", "Custom..."])
        self.target_combo.currentTextChanged.connect(self.on_target_changed)
        combo_layout.addWidget(self.target_combo, 1)
        self.browse_btn = QPushButton(self.tr_txt("browse"))
        self.browse_btn.setObjectName("secondary")
        self.browse_btn.clicked.connect(self.browse_folder)
        combo_layout.addWidget(self.browse_btn)
        target_layout.addLayout(combo_layout)
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Drag & drop folder here...")
        self.path_edit.setText(str(self.current_folder))
        self.sync_target_combo()
        target_layout.addWidget(self.path_edit)
        bottom_target = QHBoxLayout()
        self.shortcut_check = QCheckBox(self.tr_txt("include_short"))
        self.startup_check = QCheckBox(self.tr_txt("startup"))
        self.startup_check.stateChanged.connect(self.toggle_startup)
        # Fix #4: blockSignals to prevent crash because log_text now exists earlier but still safe
        self.startup_check.blockSignals(True)
        self.startup_check.setChecked(self.is_startup_enabled())
        self.startup_check.blockSignals(False)
        bottom_target.addWidget(self.shortcut_check)
        bottom_target.addWidget(self.startup_check)
        target_layout.addLayout(bottom_target)
        left_panel.addWidget(self.target_group)

        self.action_group = QGroupBox(self.tr_txt("actions"))
        action_layout = QVBoxLayout(self.action_group)
        row1 = QHBoxLayout()
        self.preview_btn = QPushButton(self.tr_txt("preview"))
        self.preview_btn.setObjectName("secondary")
        self.preview_btn.clicked.connect(self.do_preview)
        self.organize_btn = QPushButton(self.tr_txt("organize"))
        self.organize_btn.clicked.connect(self.do_organize)
        row1.addWidget(self.preview_btn)
        row1.addWidget(self.organize_btn)
        action_layout.addLayout(row1)

        row2 = QHBoxLayout()
        self.watch_btn = QPushButton(self.tr_txt("watch"))
        self.watch_btn.setObjectName("success")
        self.watch_btn.clicked.connect(self.toggle_watch)
        auto_layout = QHBoxLayout()
        self.auto_btn = QPushButton(self.tr_txt("auto"))
        self.auto_btn.setObjectName("secondary")
        self.auto_btn.clicked.connect(self.toggle_auto)
        self.auto_interval = QComboBox()
        self.auto_interval.addItems(["15 min", "30 min", "60 min", "120 min"])
        self.auto_interval.setCurrentText("60 min")
        auto_layout.addWidget(self.auto_btn)
        auto_layout.addWidget(self.auto_interval)
        row2.addLayout(auto_layout)
        row2.addWidget(self.watch_btn)
        action_layout.addLayout(row2)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        action_layout.addWidget(self.progress)
        self.auto_status = QLabel(self.tr_txt("auto_stopped"))
        self.auto_status.setStyleSheet("color: #888888; font-size: 11px;")
        action_layout.addWidget(self.auto_status)
        left_panel.addWidget(self.action_group)

        self.quick_group = QGroupBox(self.tr_txt("system"))
        quick_layout = QVBoxLayout(self.quick_group)
        self.install_btn = QPushButton(self.tr_txt("install"))
        self.install_btn.setObjectName("secondary")
        self.install_btn.clicked.connect(self.toggle_menu)
        self.refresh_menu_btn()
        self.undo_btn = QPushButton(self.tr_txt("undo"))
        self.undo_btn.setObjectName("secondary")
        self.undo_btn.clicked.connect(self.do_undo_quick)
        self.history_btn = QPushButton(self.tr_txt("history"))
        self.history_btn.setObjectName("secondary")
        self.history_btn.clicked.connect(self.show_history)
        quick_row = QHBoxLayout()
        quick_row.addWidget(self.install_btn)
        quick_row.addWidget(self.undo_btn)
        quick_row.addWidget(self.history_btn)
        quick_layout.addLayout(quick_row)
        left_panel.addWidget(self.quick_group)
        left_panel.addStretch()

        left_widget = QWidget()
        left_widget.setLayout(left_panel)
        left_widget.setMaximumWidth(460)
        left_widget.setMinimumWidth(380)
        right_widget = QWidget()
        right_widget.setLayout(right_panel)
        main_layout.addWidget(left_widget)
        main_layout.addWidget(right_widget, 1)
        self.setAcceptDrops(True)

        # Apply lang RTL if needed
        if self.lang == "ar":
            self.setLayoutDirection(Qt.RightToLeft)

    def setup_tray(self):
        try:
            if not QSystemTrayIcon.isSystemTrayAvailable():
                print("setup_tray: system tray not available")
                self.tray = None
                return
            self.tray = QSystemTrayIcon(self)
            icon = QIcon()
            icon_file = get_resource_path("icon.ico")
            if icon_file.exists():
                icon = QIcon(str(icon_file))
            if icon.isNull():  # no icon.ico next to the app (or it failed to load): use a built-in icon so the tray still shows
                icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
            self.tray.setIcon(icon)
            menu = QMenu()
            show_action = QAction("Show / إظهار", self)
            show_action.triggered.connect(self.show_from_tray)
            menu.addAction(show_action)
            quit_action = QAction("Quit / خروج", self)
            quit_action.triggered.connect(self.quit_app)
            menu.addAction(quit_action)
            self.tray.setContextMenu(menu)
            self.tray.activated.connect(self.on_tray_activated)
            self.tray.show()
            self.tray.setToolTip("File Organizer FREE v3.2")
        except Exception as e:
            print(f"setup_tray failed: {e}")
            self.tray = None

    def quit_app(self):
        """Fix #1: stop watcher first then quit"""
        try:
            if self.watch_running and self.watch_worker:
                self.log("Stopping watch before quit...", "warning")
                self.watch_worker.stop()
                self.watch_worker.wait(3000)
            if self.auto_running and self.auto_timer:
                self.auto_timer.stop()
        except Exception as e:
            print(f"quit_app stop failed: {e}")
        # Save settings
        try:
            save_settings({**load_settings(),
                "last_folder": str(self.current_folder),
                "auto_interval": int(self.auto_interval.currentText().split()[0]),
                "lang": self.lang,
                "watch_was_active": False,
                "auto_was_active": False,
                "last_updated": datetime.datetime.now().isoformat()
            })
        except Exception as e:
            print(f"save settings on quit failed: {e}")
        QApplication.quit()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_from_tray()

    def show_from_tray(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        # Fix #6: block if batch_running
        if self.batch_running:
            QMessageBox.warning(self, self.tr_txt("busy"), self.tr_txt("batch_running"))
            event.ignore()
            return
        # If watch or auto running, hide to tray
        if (self.watch_running or self.auto_running) and not self.tray:
            # Without a tray icon, hiding the window would leave Watch running with no way to reach it
            msg = ("لا توجد أيقونة tray - الإغلاق سيوقف المراقبة/التلقائي. إغلاق؟" if self.lang == "ar"
                   else "No tray icon is available - closing will stop Watch/Auto. Quit?")
            event.ignore()
            if QMessageBox.question(self, self.tr_txt("confirm"), msg, QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
                self.quit_app()
            return
        if self.watch_running or self.auto_running:
            reply = QMessageBox.question(self, self.tr_txt("confirm"), self.tr_txt("quit_confirm"), QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                event.ignore()
                self.hide()
                if self.tray:
                    try:
                        self.tray.showMessage("File Organizer", self.tr_txt("tray_hide"), QSystemTrayIcon.Information, 3000)
                    except Exception as e:
                        print(f"tray message failed: {e}")
                self.log("Minimized to tray - Watch/Auto still running", "warning")
                # Save settings that watch/auto was active
                update_setting("watch_was_active", self.watch_running)
                update_setting("auto_was_active", self.auto_running)
                update_setting("last_folder", str(self.current_folder))
            else:
                event.ignore()
                self.quit_app()  # "No" = really quit (stops Watch, then exits)
        else:
            # Save settings
            try:
                save_settings({**load_settings(),
                    "last_folder": str(self.current_folder),
                    "auto_interval": int(self.auto_interval.currentText().split()[0]),
                    "lang": self.lang,
                    "watch_was_active": False,
                    "auto_was_active": False
                })
            except Exception as e:
                print(f"save settings on close failed: {e}")
            if self.tray:
                try:
                    self.tray.hide()
                except Exception as e:
                    print(f"tray hide failed: {e}")
            event.accept()
            QTimer.singleShot(0, QApplication.quit)  # quit-on-last-window-closed is off (tray), so exit explicitly

    def is_startup_enabled(self) -> bool:
        if sys.platform != "win32":
            return False
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
            try:
                winreg.QueryValueEx(key, "FileOrganizerPRO")
                winreg.CloseKey(key)
                return True
            except FileNotFoundError:
                winreg.CloseKey(key)
                return False
        except Exception as e:
            print(f"is_startup check failed: {e}")
            return False

    def toggle_startup(self):
        # Fix #4: use isChecked() not state==2, and check log_text exists
        try:
            is_checked = self.startup_check.isChecked()
        except Exception as e:
            print(f"toggle_startup isChecked failed: {e}")
            return
        if sys.platform != "win32":
            QMessageBox.information(self, "Info", "Start with Windows only on Windows")
            try:
                self.startup_check.blockSignals(True)
                self.startup_check.setChecked(False)
                self.startup_check.blockSignals(False)
            except Exception as e:
                print(f"reset startup_check failed: {e}")
            return
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_WRITE)
            if is_checked:
                exe_path = Path(sys.executable).resolve() if getattr(sys, 'frozen', False) else Path(__file__).resolve()
                if getattr(sys, 'frozen', False):
                    # Fix #2: add --background flag
                    cmd = f'"{exe_path}" --background'
                else:
                    pythonw = Path(sys.executable).parent / "pythonw.exe"
                    if pythonw.exists():
                        cmd = f'"{pythonw}" "{exe_path}" --background'
                    else:
                        cmd = f'"{Path(sys.executable).resolve()}" "{exe_path}" --background'
                winreg.SetValueEx(key, "FileOrganizerPRO", 0, winreg.REG_SZ, cmd)
                if hasattr(self, 'log_text'):
                    self.log("Enabled start with Windows (--background)", "success")
                update_setting("startup_enabled", True)
            else:
                try:
                    winreg.DeleteValue(key, "FileOrganizerPRO")
                    if hasattr(self, 'log_text'):
                        self.log("Disabled start with Windows", "info")
                except FileNotFoundError:
                    pass
                update_setting("startup_enabled", False)
            winreg.CloseKey(key)
        except Exception as e:
            print(f"toggle_startup failed: {e}")
            if hasattr(self, 'log_text'):
                self.log(f"Startup toggle failed: {e}", "error")

    def toggle_lang(self):
        self.lang = "ar" if self.lang=="en" else "en"
        self.title_label.setText(self.tr_txt("title"))
        self.subtitle_label.setText(self.tr_txt("subtitle"))
        self.target_group.setTitle(self.tr_txt("target"))
        self.action_group.setTitle(self.tr_txt("actions"))
        self.quick_group.setTitle(self.tr_txt("system"))
        self.log_group.setTitle(self.tr_txt("live_log"))
        self.card_total.set_title(self.tr_txt("total"))
        self.card_pdfs.set_title(self.tr_txt("pdfs"))
        self.card_images.set_title(self.tr_txt("images"))
        self.browse_btn.setText(self.tr_txt("browse"))
        self.shortcut_check.setText(self.tr_txt("include_short"))
        self.startup_check.setText(self.tr_txt("startup"))
        self.preview_btn.setText(self.tr_txt("preview"))
        self.organize_btn.setText(self.tr_txt("organize"))
        self.watch_btn.setText(self.tr_txt("stop_watch") if self.watch_running else self.tr_txt("watch"))
        refresh_button_style(self.watch_btn)
        self.auto_btn.setText(self.tr_txt("stop_auto") if self.auto_running else self.tr_txt("auto"))
        refresh_button_style(self.auto_btn)
        self.refresh_menu_btn()
        self.undo_btn.setText(self.tr_txt("undo"))
        self.history_btn.setText(self.tr_txt("history"))
        self.auto_status.setText(self.tr_txt("auto_running", m=self.auto_interval.currentText().split()[0]) if self.auto_running else self.tr_txt("auto_stopped"))
        update_setting("lang", self.lang)
        if self.lang == "ar":
            self.setLayoutDirection(Qt.RightToLeft)
        else:
            self.setLayoutDirection(Qt.LeftToRight)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            path = Path(urls[0].toLocalFile())
            if path.is_dir():
                reason = is_protected_path(path.resolve())
                if reason:
                    QMessageBox.warning(self, self.tr_txt("blocked"), reason)
                    self.log(f"Blocked drop: {reason}", "error")
                    return
                self.set_custom_folder(path)
                self.log(f"Dropped: {path.name}", "info")

    def sync_target_combo(self):
        """Make the combo match current_folder (otherwise 'Downloads' wins over the folder the path box shows)."""
        if self.current_folder == DOWNLOADS_PATH:
            text = "Downloads"
        elif self.current_folder == DESKTOP_PATH:
            text = "Desktop"
        else:
            text = "Custom..."
        self.target_combo.blockSignals(True)
        self.target_combo.setCurrentText(text)
        self.target_combo.blockSignals(False)

    def set_custom_folder(self, path: Path):
        """Select a custom folder without re-triggering the Browse dialog via currentTextChanged."""
        if self.watch_running:
            self.log(f"Folder changed to {path.name} - stopping Watch", "warning")
            self.toggle_watch()
        self.current_folder = path
        self.path_edit.setText(str(path))
        self.target_combo.blockSignals(True)
        self.target_combo.setCurrentText("Custom...")
        self.target_combo.blockSignals(False)
        update_setting("last_folder", str(path))
        self.update_stats()

    def on_target_changed(self, text):
        if self.watch_running and text in ("Downloads", "Desktop", "Both"):
            self.log("Target changed - stopping Watch", "warning")
            self.toggle_watch()
        if text == "Downloads":
            self.current_folder = DOWNLOADS_PATH
            self.path_edit.setText(str(DOWNLOADS_PATH))
        elif text == "Desktop":
            self.current_folder = DESKTOP_PATH
            self.path_edit.setText(str(DESKTOP_PATH))
        elif text == "Custom...":
            self.browse_folder()
        update_setting("last_folder", str(self.current_folder))
        self.update_stats()

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            reason = is_protected_path(Path(folder).resolve())
            if reason:
                QMessageBox.warning(self, self.tr_txt("blocked"), reason)
                return
            self.set_custom_folder(Path(folder))

    def get_folders(self, silent=False):
        text = self.target_combo.currentText()
        folders = []
        if text == "Downloads":
            folders = [DOWNLOADS_PATH]
        elif text == "Desktop":
            folders = [DESKTOP_PATH]
        elif text == "Both":
            folders = [DOWNLOADS_PATH, DESKTOP_PATH]
        else:
            p = Path(self.path_edit.text().strip().strip('"'))
            if p.exists() and p.is_dir():
                folders = [p]
        safe_folders = []
        for f in folders:
            reason = is_protected_path(f.resolve())
            if reason:
                if not silent:  # the stats timer calls this every 10s - never pop a dialog from it
                    QMessageBox.warning(self, self.tr_txt("blocked"), reason)
                    self.log(f"Blocked: {reason}", "error")
            else:
                safe_folders.append(f)
        return safe_folders

    def log(self, msg, level="info"):
        if not hasattr(self, 'log_text'):
            print(f"[{level}] {msg}")
            return
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        color_map = {"error": "#ef4444", "warning": "#f59e0b", "success": "#10b981", "info": "#e0e0e0"}
        color = color_map.get(level, "#e0e0e0")
        self.log_text.append(f'<span style="color: #888888;">[{timestamp}]</span> <span style="color: {color};">{html.escape(str(msg))}</span>')

    def update_stats(self):
        folders = self.get_folders(silent=True)
        if not folders:
            return
        folder = folders[0]
        if self.stats_worker and self.stats_worker.isRunning():
            return
        self.stats_worker = StatsWorker(folder)
        self.stats_worker.stats_signal.connect(self.on_stats_ready)
        self.stats_worker.start()

    def on_stats_ready(self, total, counts, size):
        self.card_total.set_value(str(total))
        self.card_pdfs.set_value(str(counts.get("01_PDFs", 0)))
        self.card_images.set_value(str(counts.get("05_Images", 0)))

    def set_batch_busy(self, busy):
        self.mutex.lock()
        self.batch_running = busy
        self.mutex.unlock()
        self.organize_btn.setEnabled(not busy and not self.watch_running)
        self.preview_btn.setEnabled(not busy)
        self.stop_btn.setEnabled(busy or self.watch_running or self.auto_running)

    def do_preview(self):
        folders = self.get_folders()
        if not folders:
            QMessageBox.warning(self, self.tr_txt("error"), self.tr_txt("no_folder"))
            return
        self.log("Preview scanning...", "info")
        self.progress.setVisible(True)
        self.preview_btn.setEnabled(False)
        self.preview_worker = PreviewWorker(folders)
        self.preview_worker.result_signal.connect(self.on_preview_ready)
        self.preview_worker.start()

    def on_preview_ready(self, total, counts, total_size, details):
        self.progress.setVisible(False)
        self.preview_btn.setEnabled(True)
        self.log(f"Preview: {total} files, {total_size//1024//1024} MB", "info")
        for cat, cnt in counts.items():
            if cnt>0:
                self.log(f"  {cat}: {cnt}", "info")
        if details:
            self.log("Files:", "info")
            for folder_name, fname, cat in details[:20]:
                self.log(f"  {fname} -> {cat}", "info")
            if len(details)>20:
                self.log(f"  ... and {len(details)-20} more", "info")

    def do_organize(self):
        if self.batch_running:
            QMessageBox.warning(self, self.tr_txt("busy"), "Batch operation already running")
            return
        if self.watch_running:
            QMessageBox.warning(self, self.tr_txt("busy"), "Watch is running - stop it first")
            return
        folders = self.get_folders()
        if not folders:
            return
        reply = QMessageBox.question(self, self.tr_txt("confirm"), self.tr_txt("organize_confirm", n=len(folders)), QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        self.log(f"Organizing {len(folders)} folder(s)...", "info")
        self.progress.setVisible(True)
        self.set_batch_busy(True)
        self.worker = OrganizeWorker(folders, self.shortcut_check.isChecked())
        self.worker.log_signal.connect(self.log)
        self.worker.progress_signal.connect(self.progress.setValue)
        self.worker.finished_signal.connect(self.on_organize_finished)
        self.worker.start()

    def on_organize_finished(self, total, counts, err_count, errors):
        self.progress.setVisible(False)
        self.set_batch_busy(False)
        self.log(f"Done! Organized {total} files, {err_count} errors", "success" if err_count==0 else "warning")
        for cat, cnt in counts.items():
            self.log(f"  {cat}: {cnt}", "info")
        if errors:
            for e in errors[:10]:
                self.log(f"  Error: {e['name']}: {e['error']}", "error")
        self.update_stats()
        msg = self.tr_txt("organized", n=total)
        if err_count>0:
            msg += f"\n{err_count} errors - check log"
        QMessageBox.information(self, self.tr_txt("done"), msg)

    def toggle_watch(self):
        if self.watch_running:
            if self.watch_worker:
                self.watch_worker.stop()
                self.watch_worker.wait()
            self.watch_running = False
            self.watch_btn.setText(self.tr_txt("watch"))
            self.watch_btn.setObjectName("success")
            refresh_button_style(self.watch_btn)
            self.stop_btn.setEnabled(self.batch_running or self.auto_running)
            self.organize_btn.setEnabled(not self.batch_running)
            update_setting("watch_was_active", False)
            self.log("Watch stopped", "warning")
        else:
            if self.batch_running:
                QMessageBox.warning(self, self.tr_txt("busy"), "Organize running - stop first")
                return
            folders = self.get_folders()
            if len(folders) != 1:
                QMessageBox.warning(self, self.tr_txt("error"), self.tr_txt("watch_needs_one"))
                return
            folder = folders[0]
            self.log(f"Starting Watch: {folder.name} (immediate DB writes)", "info")
            self.watch_worker = WatchWorker(folder, self.shortcut_check.isChecked(), batch_interval_sec=60)
            self.watch_worker.log_signal.connect(self.log)
            self.watch_worker.stopped_signal.connect(self.on_watch_stopped)
            self.watch_worker.start()
            self.watch_running = True
            self.watch_btn.setText(self.tr_txt("stop_watch"))
            self.watch_btn.setObjectName("danger")
            refresh_button_style(self.watch_btn)
            self.stop_btn.setEnabled(True)
            self.organize_btn.setEnabled(False)
            update_setting("watch_was_active", True)
            update_setting("last_folder", str(folder))

    def on_watch_stopped(self):
        self.watch_running = False
        self.watch_btn.setText(self.tr_txt("watch"))
        self.watch_btn.setObjectName("success")
        refresh_button_style(self.watch_btn)
        self.stop_btn.setEnabled(self.batch_running or self.auto_running)
        self.organize_btn.setEnabled(not self.batch_running)

    def start_auto_with_interval(self, interval_min):
        interval_min = max(1, int(interval_min))  # --auto 0 would make the timer fire non-stop
        folders = self.get_folders()
        if not folders:
            return
        self.auto_folders = folders
        self.log(f"Auto started every {interval_min} min for {len(folders)} folder(s)", "info")
        self.do_auto_run()
        self.auto_timer = QTimer()
        self.auto_timer.timeout.connect(self.do_auto_run)
        self.auto_timer.start(interval_min * 60 * 1000)
        self.auto_running = True
        self.auto_btn.setText(self.tr_txt("stop_auto") + f" ({interval_min}m)")
        self.auto_btn.setObjectName("danger")
        refresh_button_style(self.auto_btn)
        self.auto_status.setText(self.tr_txt("auto_running", m=interval_min))
        self.stop_btn.setEnabled(True)
        update_setting("auto_was_active", True)
        update_setting("auto_interval", interval_min)

    def toggle_auto(self):
        if self.auto_running:
            if self.auto_timer:
                self.auto_timer.stop()
            self.auto_running = False
            self.auto_btn.setText(self.tr_txt("auto"))
            self.auto_btn.setObjectName("secondary")
            refresh_button_style(self.auto_btn)
            self.auto_status.setText(self.tr_txt("auto_stopped"))
            self.stop_btn.setEnabled(self.batch_running or self.watch_running)
            update_setting("auto_was_active", False)
            self.log("Auto stopped", "warning")
        else:
            if self.batch_running:
                QMessageBox.warning(self, self.tr_txt("busy"), "Organize running")
                return
            folders = self.get_folders()
            if not folders:
                QMessageBox.warning(self, self.tr_txt("error"), self.tr_txt("no_folder"))
                return
            interval_text = self.auto_interval.currentText()
            try:
                interval_min = int(interval_text.split()[0])
            except Exception as e:
                print(f"parse interval failed: {e}")
                interval_min = 60
            self.start_auto_with_interval(interval_min)

    def do_auto_run(self):
        if self.batch_running:  # Watch may be running: the two take turns (FS_LOCK), so Auto still runs
            self.log("Auto skipped - another organize is still running", "warning")
            return
        self.log(f"Auto run - {datetime.datetime.now().strftime('%H:%M:%S')}", "info")
        self.set_batch_busy(True)
        self.auto_worker = OrganizeWorker(self.auto_folders, self.shortcut_check.isChecked(), tag="Auto")
        self.auto_worker.log_signal.connect(self.log)
        self.auto_worker.finished_signal.connect(self.on_auto_finished)
        self.auto_worker.start()

    def on_auto_finished(self, total, counts, err_count, errors):
        self.set_batch_busy(False)
        self.log(f"Auto done: {total} files, {err_count} errors", "success" if err_count==0 else "warning")
        self.update_stats()

    def do_stop(self):
        if self.watch_running:
            self.toggle_watch()
        if self.auto_running:
            self.toggle_auto()
        if self.batch_running:
            self.log("Batch operation - wait for finish or close app", "warning")

    def get_exe_command(self, extra_args=""):
        is_frozen = getattr(sys, 'frozen', False)
        if is_frozen:
            exe_path = Path(sys.executable).resolve()
            if extra_args:
                return f'"{exe_path}" {extra_args} "%V"'
            else:
                return f'"{exe_path}" "%V"'
        else:
            python_dir = Path(sys.executable).parent
            pythonw = python_dir / "pythonw.exe"
            script_path = Path(__file__).resolve()
            if pythonw.exists():
                base = f'"{pythonw}" "{script_path}"'
            else:
                base = f'"{Path(sys.executable).resolve()}" "{script_path}"'
            if extra_args:
                return f'{base} {extra_args} "%V"'
            else:
                return f'{base} "%V"'

    def install_menu(self):
        self.log("Installing right-click menu...", "info")
        try:
            import winreg
            exe_path = Path(sys.executable).resolve() if getattr(sys, 'frozen', False) else Path(__file__).resolve()
            icon_path_obj = get_resource_path("icon.ico")
            # _MEIPASS is a temp folder that is deleted on exit, so a packaged app must point at its own exe
            icon_path = str(exe_path) if getattr(sys, "frozen", False) else (str(icon_path_obj) if icon_path_obj.exists() else str(exe_path))
            items = {
                "FileOrganizer": ("Organize with File Organizer", ""),
                "FileOrganizer.Watch": ("Watch this folder (Live)", "--watch"),
                "FileOrganizer.Auto": ("Auto-Organize every 60 min", "--auto 60"),
            }
            for key_name, (display, extra) in items.items():
                cmd = self.get_exe_command(extra)
                for base in [r"Directory\shell", r"Directory\Background\shell"]:
                    full_key = rf"{base}\{key_name}"
                    try:
                        k = winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{full_key}")
                        winreg.SetValueEx(k, "", 0, winreg.REG_SZ, display)
                        winreg.SetValueEx(k, "Icon", 0, winreg.REG_SZ, icon_path)
                        winreg.CloseKey(k)
                        cmd_key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{full_key}\command")
                        winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ, cmd)
                        winreg.CloseKey(cmd_key)
                    except Exception as e:
                        self.log(f"Failed {full_key}: {e}", "error")
            self.log("Installed! Both Directory and Background", "success")
            QMessageBox.information(self, self.tr_txt("done"), "Right-click installed!\n- Directory\n- Background\nIcon via _MEIPASS")
        except Exception as e:
            self.log(f"Failed: {e}", "error")
            QMessageBox.warning(self, self.tr_txt("error"), str(e))

    def refresh_menu_btn(self):
        self.install_btn.setText(self.tr_txt("uninstall" if is_menu_installed() else "install"))

    def toggle_menu(self):
        if is_menu_installed():
            self.uninstall_menu()
        else:
            self.install_menu()
        self.refresh_menu_btn()

    def uninstall_menu(self):
        removed, errors = uninstall_context_menu()
        for e in errors:
            self.log(f"Failed: {e}", "error")
        if errors:
            QMessageBox.warning(self, self.tr_txt("error"), "\n".join(errors))
        else:
            self.log(f"Right-click menu removed ({removed} entries)", "success")
            QMessageBox.information(self, self.tr_txt("done"), "Right-click menu removed.")

    def do_undo_quick(self):
        if self.watch_running:
            QMessageBox.warning(self, self.tr_txt("busy"), "Stop Watch before undoing an operation")
            return
        try:
            conn = sqlite3.connect(str(DB_PATH))
            cur = conn.cursor()
            cur.execute("SELECT id FROM operations WHERE status='done' ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()
            conn.close()
        except Exception as e:
            self.log(f"DB read failed: {e}", "error")
            return
        if not row:
            QMessageBox.information(self, "No history", "No operation to undo")
            return
        op_id = row[0]
        reply = QMessageBox.question(self, self.tr_txt("confirm"), f"Undo latest operation ID {op_id}?", QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        restored, failed, missing, total, err = undo_operation(op_id)
        if failed>0 or missing>0:
            self.log(f"Undo partial: restored {restored}/{total}, failed {failed}, missing {missing}: {err}", "warning")
            QMessageBox.warning(self, "Partial", f"Restored {restored}/{total}, failed {failed}, missing {missing}")
        else:
            self.log(f"Undo done: {restored}/{total}", "success")
            QMessageBox.information(self, self.tr_txt("done"), f"Restored {restored}/{total}")
        self.update_stats()

    def show_history(self):
        dlg = HistoryDialog(self, self.lang)
        dlg.exec()

def parse_args():
    import argparse
    parser = argparse.ArgumentParser(description="File Organizer FREE v3.2", add_help=False)
    parser.add_argument("folder", nargs="?", help="Folder path")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--auto", nargs="?", const="60", default=None, help="Auto interval")
    parser.add_argument("--background", action="store_true", help="Start hidden in tray")
    parser.add_argument("--minimized", action="store_true", help="Start minimized")
    parser.add_argument("--downloads", action="store_true")
    parser.add_argument("--desktop", action="store_true")
    parser.add_argument("--both", action="store_true")
    # Use parse_known_args to ignore unknown flags like --dry-run etc
    args, unknown = parser.parse_known_args()

    # Robust handling for --auto: if value looks like path not number, treat as folder
    if args.auto is not None:
        # args.auto could be string like "60" or folder path or None
        auto_val = args.auto
        folder_candidate = None
        # If auto is a path (exists as dir or contains :\ or /), treat it as folder
        if isinstance(auto_val, str):
            # Check if it's a number
            try:
                int(auto_val)
                # It's number, keep as is
                pass
            except ValueError:
                # Not number - could be folder path
                if not args.folder and Path(auto_val).exists():
                    folder_candidate = auto_val
                    args.auto = "60"  # default interval
                elif "\\" in auto_val or "/" in auto_val:
                    # Likely path passed as --auto value due to --auto without number before path
                    folder_candidate = auto_val
                    args.auto = "60"
        if folder_candidate and not args.folder:
            args.folder = folder_candidate

    return args

def main():
    if "--uninstall-context-menu" in sys.argv:
        removed, errors = uninstall_context_menu()
        print(f"Removed {removed} right-click entries" + (f" | errors: {errors}" if errors else ""))
        return
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    # Fix #3: prevent quit when window hidden
    app.setQuitOnLastWindowClosed(False)
    args = parse_args()
    initial_folder = None
    start_watch = False
    start_auto = None
    start_background = False

    if args.background or args.minimized:
        start_background = True

    if args.folder:
        p = Path(args.folder)
        if p.exists() and p.is_dir():
            reason = is_protected_path(p.resolve())
            if not reason:
                initial_folder = p
            else:
                print(f"Blocked: {reason}")

    if args.watch:
        start_watch = True
    if args.auto is not None:
        try:
            start_auto = int(args.auto) if isinstance(args.auto, str) and args.auto.isdigit() else (int(args.auto) if isinstance(args.auto, int) else 60)
        except Exception as e:
            print(f"parse auto interval failed: {e}, using 60")
            start_auto = 60

    # Handle --downloads etc (fix #5)
    if args.downloads and not initial_folder:
        initial_folder = DOWNLOADS_PATH
    if args.desktop and not initial_folder:
        initial_folder = DESKTOP_PATH

    # Load settings for background start
    if not initial_folder:
        s = load_settings()
        last = s.get("last_folder")
        if last and Path(last).exists():
            initial_folder = Path(last)

    if (start_watch or start_auto is not None) and not initial_folder:
        initial_folder = DOWNLOADS_PATH if DOWNLOADS_PATH.exists() else None

    window = MainWindow(initial_folder=initial_folder, start_watch=start_watch, start_auto=start_auto, start_background=start_background)
    if start_background and window.tray:
        # Start hidden in tray (only when there is a tray icon to bring the window back from)
        window.hide()
        try:
            window.tray.showMessage("File Organizer", "Running in background - tray", QSystemTrayIcon.Information, 3000)
        except Exception as e:
            print(f"tray message failed: {e}")
    else:
        window.show()
    if initial_folder:
        window.log(f"Opened: {initial_folder.name} | watch={start_watch} auto={start_auto} bg={start_background}", "info")
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
