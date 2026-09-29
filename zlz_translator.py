"""จุดเข้าโปรแกรมเดียวสำหรับตัว .exe (PyInstaller) และรันจากซอร์ส

    python zlz_translator.py                เปิดโปรแกรม hotkey (ไป system tray) ถ้ายังไม่เคยตั้งค่าจะเปิดตัวช่วยก่อน
    python zlz_translator.py --setup        เปิดตัวช่วยตั้งค่าอย่างเดียว
    python zlz_translator.py --discord-bot  รัน Discord user app (ตัว hotkey เรียกเองเป็นโปรเซสลูก)
"""
from __future__ import annotations

import os
import sys

# ให้ import core/hotkey ได้ทั้งตอนรันจากซอร์สและตอนถูก PyInstaller อบเป็น .exe
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--discord-bot" in args:
        from discord_app.bot import main as bot_main

        return bot_main()
    if "--setup" in args:
        from hotkey.setup_wizard import run_wizard

        return 0 if run_wizard() else 1
    from hotkey.app import main as app_main

    app_main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
