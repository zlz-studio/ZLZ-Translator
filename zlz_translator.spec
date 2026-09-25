# -*- mode: python ; coding: utf-8 -*-
"""สเปก PyInstaller: อบโปรแกรม + Python + ไลบรารีเป็นโฟลเดอร์ dist/ZLZ Translator/ (ผู้ใช้ไม่ต้องลง Python)

    .venv\\Scripts\\python.exe -m PyInstaller --noconfirm --clean --workpath build\\pyi --distpath dist zlz_translator.spec

ไฟล์ค่าเริ่มต้น (config.toml, glossary.md, .env.example) ถูกฝังไปด้วย ตอนเปิดครั้งแรกโปรแกรมจะก๊อปไป
%APPDATA%\\ZLZ Translator ให้ (ดู core/config.py: ensure_user_files)
"""
import os

from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(".")

datas = [
    ("config.toml", "."),
    ("glossary.md", "."),
    (".env.example", "."),
]

hiddenimports = (
    collect_submodules("pystray")  # เลือก backend ตามระบบตอนรัน (pystray._win32) PyInstaller มองไม่เห็นเอง
    + ["PIL.ImageFont", "PIL.ImageDraw", "keyboard", "pyperclip"]
)

a = Analysis(
    ["zlz_translator.py"],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tests", "pytest", "unittest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ZLZ Translator",
    icon="assets/icon.ico",
    console=False,  # ไม่มีหน้าต่างดำ ไปอยู่ system tray
    disable_windowed_traceback=False,
    uac_admin=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="ZLZ Translator",
)
