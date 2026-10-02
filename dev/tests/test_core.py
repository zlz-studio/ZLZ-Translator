"""ทดสอบแกนแปลโดยไม่ต้องล็อกอินหรือมีคีย์จริง (ใช้ตัวปลอมของ claude)

    .venv\\Scripts\\python.exe dev\\tests\\test_core.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # dev/tests/ -> โปรเจกต์
sys.path.insert(0, str(ROOT))
os.environ["CLAUDE_CODE_COMMAND"] = f"{sys.executable} {Path(__file__).resolve().parent / 'fake_claude.py'}"

from core.config import load_config  # noqa: E402
from core.prompts import build_system_prompt, build_user_prompt  # noqa: E402
from core.providers import ProviderError  # noqa: E402
from core.providers.claude_code import _parse_output  # noqa: E402
from core.translator import Translator  # noqa: E402


def check(name: str, condition: bool, detail: str = "") -> None:
    print(("PASS " if condition else "FAIL ") + name + (f"  ({detail})" if detail and not condition else ""))
    if not condition:
        sys.exit(1)


cfg = load_config(ROOT)
t = Translator(cfg)

# prompt ครบส่วนสำคัญ
sp = build_system_prompt("reply", cfg.glossary, "formal")
check("system prompt มี glossary", "ZLZ Anime Shader" in sp)
check("system prompt มีน้ำเสียง formal", "formal" in sp.lower())
check("user prompt ห่อข้อความ", "<<<" in build_user_prompt("read", "hi"))

# แปลผ่านตัวปลอม
r = t.run("read", "Could you send the files?", provider="claude_code")
check("read ใช้รุ่นตาม config", r.model == cfg.model_for("read"), r.model)
check("read คืนข้อความ", r.text.startswith("[ไทย/"), r.text)
r = t.run("reply", "เดี๋ยวส่งให้ครับ", tone="brief", provider="claude_code")
check("reply ใช้รุ่นตาม config", r.model == cfg.model_for("reply"), r.model)
check("reply จำน้ำเสียง", r.tone == "brief")

# กรณีไม่ได้ล็อกอิน -> ProviderError ข้อความไทยบอกวิธีแก้
os.environ["FAKE_CLAUDE_MODE"] = "error"
t._providers.clear()
try:
    t.run("read", "x", provider="claude_code")
    check("error -> ProviderError", False)
except ProviderError as e:
    check("error -> ProviderError บอกให้ /login", "/login" in str(e), str(e))
os.environ.pop("FAKE_CLAUDE_MODE")

# parser ทนต่อบรรทัดขยะนำหน้า JSON
out, _ = _parse_output('some log line\n{"is_error": false, "result": "OK"}', "", 0)
check("parser ข้ามบรรทัดที่ไม่ใช่ JSON", out == "OK")

print("\nทุกอย่างผ่าน")
