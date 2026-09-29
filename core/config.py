"""โหลด config.toml, glossary.md และ .env จากโฟลเดอร์โปรเจกต์"""
from __future__ import annotations

import os
import shutil
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

APP_NAME = "ZLZ Translator"
APP_VERSION = "1.0.0"  # build.bat และตัวติดตั้งอ่านค่านี้

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ไฟล์ค่าเริ่มต้นที่ต้องมีในโฟลเดอร์ข้อมูลผู้ใช้ (ชื่อในโฟลเดอร์ผู้ใช้ -> ชื่อต้นฉบับใน bundle)
_DEFAULT_FILES = {"config.toml": "config.toml", "glossary.md": "glossary.md", ".env": ".env.example"}


def is_frozen() -> bool:
    """รันจาก .exe ที่ PyInstaller สร้าง (ไม่ใช่จากซอร์ส)"""
    return bool(getattr(sys, "frozen", False))


def bundle_dir() -> Path:
    """โฟลเดอร์ที่มีไฟล์ค่าเริ่มต้น: ใน .exe คือโฟลเดอร์ชั่วคราวของ PyInstaller, รันจากซอร์สคือโปรเจกต์"""
    return Path(getattr(sys, "_MEIPASS", PROJECT_ROOT))


def user_data_dir() -> Path:
    """ที่เก็บ config.toml / glossary.md / .env / data ของผู้ใช้

    รันจากซอร์ส = โฟลเดอร์โปรเจกต์ (เหมือนเดิม)  รันจาก .exe = %APPDATA%/ZLZ Translator
    เพราะโฟลเดอร์ที่ติดตั้งโปรแกรมอาจเขียนไม่ได้ และผู้ใช้ไม่ควรต้องรู้ว่าโปรแกรมติดตั้งอยู่ที่ไหน
    """
    override = os.environ.get("TRANSLATOR_ROOT")
    if override:
        return Path(override)
    if is_frozen():
        base = os.environ.get("APPDATA") or str(Path.home())
        return Path(base) / APP_NAME
    return PROJECT_ROOT


def ensure_user_files(root: Path) -> None:
    """สร้างโฟลเดอร์ผู้ใช้และก๊อปไฟล์ค่าเริ่มต้นที่ยังไม่มี (ไม่ทับของเดิม)"""
    src_dir = bundle_dir()
    if root.resolve() == src_dir.resolve():
        return
    root.mkdir(parents=True, exist_ok=True)
    for name, source in _DEFAULT_FILES.items():
        target = root / name
        src = src_dir / source
        if not target.exists() and src.exists():
            shutil.copyfile(src, target)

MODEL_ALIASES = {
    "haiku": "claude-haiku-4-5",
    "sonnet": "claude-sonnet-5",
    "opus": "claude-opus-5",
}

TONES = ("formal", "friendly", "brief")
MODES = ("read", "reply", "explain", "polish")

# ชุดโมเดลให้เลือกจากเมนู tray: key -> (ชื่อในเมนู, provider_order, ชื่อย่อรุ่น Claude ที่จะตั้งให้ทุกโหมด หรือ None = ไม่แตะ)
# ตัวเลข ~วินาที มาจากการวัดจริงกับอีเมล 600 ตัวอักษร (โหมดแปลเป็นไทย)
MODEL_PRESETS: dict[str, tuple[str, list[str], str | None]] = {
    "auto": ("อัตโนมัติ: Gemini ก่อน, Claude Sonnet สำรอง (แนะนำ)", ["gemini", "claude_code"], None),
    "gemini": ("Gemini flash-lite อย่างเดียว (เร็วสุด ~4 วิ)", ["gemini"], None),
    "sonnet": ("Claude Sonnet อย่างเดียว (แม่นกว่า ~9 วิ)", ["claude_code"], "sonnet"),
    "opus": ("Claude Opus อย่างเดียว (ดีสุด ~9 วิ กินโควต้ามาก)", ["claude_code"], "opus"),
}


@dataclass
class Config:
    raw: dict[str, Any]
    root: Path
    glossary: str = ""
    env: dict[str, str] = field(default_factory=dict)

    # ---- general -------------------------------------------------------
    @property
    def default_tone(self) -> str:
        tone = self.raw.get("general", {}).get("default_tone", "friendly")
        return tone if tone in TONES else "friendly"

    @property
    def provider_order(self) -> list[str]:
        order = self.raw.get("general", {}).get("provider_order") or ["claude_code"]
        return [str(p) for p in order]

    @property
    def timeout(self) -> float:
        return float(self.raw.get("general", {}).get("timeout_seconds", 60))

    @property
    def auto_back_translate(self) -> bool:
        return bool(self.raw.get("general", {}).get("auto_back_translate", True))

    @property
    def hedge_after_seconds(self) -> float:
        """ตัวหลักยังไม่ส่งคำแรกภายในกี่วินาที ให้ปล่อยตัวสำรองวิ่งคู่ (0 = ยิงพร้อมกันเลย, ติดลบ = ไม่ต้อง)"""
        return float(self.raw.get("general", {}).get("hedge_after_seconds", 3.0))

    def model_for(self, mode: str) -> str:
        """ชื่อรุ่นโมเดล (ชื่อย่อ) สำหรับโหมดนั้น"""
        return str(self.raw.get("modes", {}).get(mode, "sonnet"))

    def provider_cfg(self, name: str) -> dict[str, Any]:
        return dict(self.raw.get("providers", {}).get(name, {}))

    def hotkey(self, mode: str) -> str | None:
        value = self.raw.get("hotkeys", {}).get(mode)
        return str(value) if value else None

    @property
    def discord_autostart(self) -> bool:
        return bool(self.raw.get("discord", {}).get("autostart", True))

    @property
    def only_in_apps(self) -> list[str]:
        return [str(a) for a in self.raw.get("hotkeys", {}).get("only_in_apps", []) if a]

    def ui(self, key: str, default: Any) -> Any:
        return self.raw.get("ui", {}).get(key, default)

    def secret(self, key: str) -> str | None:
        """ค่าจาก .env ก่อน ถ้าไม่มีค่อยดูตัวแปรสภาพแวดล้อมของระบบ"""
        return self.env.get(key) or os.environ.get(key)

    @property
    def data_dir(self) -> Path:
        d = self.root / "data"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def setup_completed(self) -> bool:
        """ผ่านตัวช่วยตั้งค่าครั้งแรกแล้วหรือยัง (เขียนโดย hotkey/setup_wizard.py เป็น "true"/"false")"""
        value = self.raw.get("setup", {}).get("completed", False)
        return str(value).strip().lower() in ("1", "true", "yes")


def _load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def set_env_value(root: Path, key: str, value: str) -> None:
    """เขียนค่าลง .env: แทนที่บรรทัดเดิม (รวมที่ถูก comment ไว้) หรือเพิ่มท้ายไฟล์ ค่าว่าง = ปิดบรรทัดนั้น"""
    path = root / ".env"
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    new_line = f"{key}={value.strip()}" if value.strip() else f"# {key}="
    replaced = False
    for i, line in enumerate(lines):
        stripped = line.strip().lstrip("#").strip()
        if stripped.startswith(f"{key}="):
            lines[i] = new_line
            replaced = True
            break
    if not replaced:
        lines.append(new_line)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def set_config_value(root: Path, section: str, key: str, value: str | list[str]) -> None:
    """แก้ค่าหนึ่งบรรทัดใน config.toml โดยคง comment และลำดับเดิมไว้ (ค่าเป็น string หรือ list ของ string)"""
    import re

    path = root / "config.toml"
    text = path.read_text(encoding="utf-8")
    if isinstance(value, list):
        rendered = "[" + ", ".join('"' + v.replace('"', '\\"') + '"' for v in value) + "]"
    else:
        rendered = '"' + value.replace('"', '\\"') + '"'
    lines = text.splitlines()
    in_section = False
    done = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_section = stripped == f"[{section}]"
            continue
        if in_section and re.match(rf"^\s*{re.escape(key)}\s*=", line):
            m = re.search(r"\s+#.*$", line)  # เก็บ comment ท้ายบรรทัดไว้
            comment = m.group(0) if m else ""
            lines[i] = f"{key} = {rendered}{comment}"
            done = True
            break
    if not done:
        # ไม่มีบรรทัดนี้: เพิ่มท้าย section (หรือสร้าง section ใหม่ท้ายไฟล์)
        for i, line in enumerate(lines):
            if line.strip() == f"[{section}]":
                lines.insert(i + 1, f"{key} = {rendered}")
                done = True
                break
        if not done:
            lines += ["", f"[{section}]", f"{key} = {rendered}"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_config(root: Path | None = None) -> Config:
    root = Path(root) if root else user_data_dir()
    ensure_user_files(root)
    cfg_path = root / "config.toml"
    if not cfg_path.exists():
        raise FileNotFoundError(f"ไม่พบไฟล์ตั้งค่า: {cfg_path}")
    with cfg_path.open("rb") as f:
        raw = tomllib.load(f)
    glossary_path = root / "glossary.md"
    glossary = glossary_path.read_text(encoding="utf-8") if glossary_path.exists() else ""
    return Config(raw=raw, root=root, glossary=glossary, env=_load_env(root / ".env"))


def current_preset(cfg: Config) -> str:
    """key ของ MODEL_PRESETS ที่ตรงกับ config ตอนนี้ หรือ "custom" ถ้าผู้ใช้ตั้งเองใน config.toml"""
    order = cfg.provider_order
    aliases = {cfg.model_for(m) for m in MODES}
    for key, (_label, preset_order, alias) in MODEL_PRESETS.items():
        if order == preset_order and (alias is None or aliases == {alias}):
            return key
    return "custom"


def apply_preset(root: Path, key: str) -> None:
    """บันทึกชุดโมเดลที่เลือกลง config.toml (provider_order และรุ่น Claude ของทุกโหมด)"""
    _label, order, alias = MODEL_PRESETS[key]
    set_config_value(root, "general", "provider_order", order)
    if alias:
        for mode in MODES:
            set_config_value(root, "modes", mode, alias)
