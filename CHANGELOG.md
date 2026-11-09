# Changelog - File Organizer

All versions are preserved as a journey. The current stable version is **v3.2**.

---

## v3.2 - Current (PySide6 GUI)
**File:** `Organize-PySide6.py`

- PySide6 Dark Theme GUI + Drag & Drop
- Live Watch - Organizes new files automatically
- Auto Organize every X minutes - Watch + Auto run together
- History with SQLite + Undo last operation
- Dry-run Preview
- System Tray + Start with Windows + Run in background
- Right-Click Integration: Organize any folder from Explorer
- Safe: No overwrite, skips protected paths, hidden / system files, `desktop.ini`, `Thumbs.db`
- Downloads / Desktop resolved from Windows Shell (works with OneDrive)
- English / Arabic

**v3.2.4 details:**
- History has a Type column instead of internal ID: Watch / Auto / Manual
- Closing the app really exits (no zombie process)
- Watch does not create an empty history row every minute
- Undo is blocked while Watch is running
- Right-Click button is a toggle

---

## v2 - Organize-All (CLI - Evolution Stage)
**Old file:** `Organize-All.py` -> Now in `legacy/v2-all/`

- Interactive menu: Choose Downloads / Desktop / Both / Custom Folder
- Preview with `--dry-run` before moving anything
- Right-Click Integration for the first time
- Protection: Blocks `C:\`, Home, Windows, Program Files
- 11 categories - 60+ extensions
- No overwrite: `file.txt` -> `file (1).txt`

---

## v1 - The Beginning (CLI - Separate Files)
**Old files:**
- `Organize-Downloads.py` -> Now in `legacy/v1-downloads/`
- `Organize-Desktop.py` -> Now in `legacy/v1-desktop/`

- Each file organizes one folder only
- First version built to clean Downloads and Desktop
- The 11-category idea started here

---

## Note about v3.3
A Release was created by mistake with the name v3.3 and was removed.
The stable version is **v3.2**. There is no v3.3.
