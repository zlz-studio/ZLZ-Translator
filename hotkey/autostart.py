"""เปิดโปรแกรมอัตโนมัติเมื่อเข้า Windows ด้วย shortcut ในโฟลเดอร์ Startup ของผู้ใช้

ไม่ต้องใช้สิทธิ์ admin และตรวจสอบแล้วว่าไม่โดน redirect แม้ถูกเรียกจากโปรแกรมที่ติดตั้งแบบ Store package
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from core.config import APP_NAME, is_frozen

SHORTCUT_NAME = f"{APP_NAME}.lnk"
_OLD_SHORTCUT_NAMES = ("Discord Translator.lnk",)  # ชื่อเก่า ยังลบ/ตรวจให้ได้
_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def startup_dir() -> Path:
    return Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def shortcut_path() -> Path:
    return startup_dir() / SHORTCUT_NAME


def _all_shortcut_paths() -> list[Path]:
    return [shortcut_path(), *(startup_dir() / n for n in _OLD_SHORTCUT_NAMES)]


def is_enabled() -> bool:
    return any(p.exists() for p in _all_shortcut_paths())


def _pythonw(root: Path) -> Path:
    p = root / ".venv" / "Scripts" / "pythonw.exe"
    return p if p.exists() else Path(sys.executable)


def enable(root: Path) -> tuple[bool, str]:
    if is_frozen():
        # ติดตั้งเป็น .exe แล้ว: ชี้ไปที่ตัวโปรแกรมตรง ๆ
        target = Path(sys.executable)
        arguments = ""
        workdir = target.parent
    else:
        target = _pythonw(root)
        arguments = f'"{root / "hotkey" / "app.py"}"'
        workdir = root
    lnk = shortcut_path()
    script = (
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}'); "
        "$s.TargetPath = '{target}'; "
        "$s.Arguments = '{arguments}'; "
        "$s.WorkingDirectory = '{workdir}'; "
        "$s.Description = '{name}'; "
        "$s.Save()"
    ).format(lnk=str(lnk).replace("'", "''"), target=str(target).replace("'", "''"),
             arguments=arguments.replace("'", "''"), workdir=str(workdir).replace("'", "''"),
             name=APP_NAME.replace("'", "''"))
    try:
        proc = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                              capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=30, creationflags=_NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, str(e)
    if proc.returncode != 0 or not lnk.exists():
        return False, (proc.stderr or proc.stdout).strip()[:300] or "สร้าง shortcut ไม่สำเร็จ"
    return True, "จะเปิดเองทุกครั้งที่เข้า Windows"


def disable() -> tuple[bool, str]:
    try:
        for lnk in _all_shortcut_paths():
            if lnk.exists():
                lnk.unlink()
    except OSError as e:
        return False, str(e)
    return True, "ยกเลิกเปิดอัตโนมัติแล้ว"
