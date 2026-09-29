"""ตัวเชื่อม Claude Code CLI แบบไม่โต้ตอบ (ใช้โควต้าสมาชิก ไม่ใช้เครดิต API)

เรียก:  claude -p --tools "" --no-session-persistence --output-format json
               --model <m> --effort <e> --system-prompt <s>  <prompt>
ผลลัพธ์เป็น JSON หนึ่งก้อน มีฟิลด์ result / is_error
"""
from __future__ import annotations

import glob
import json
import logging
import os
import shlex
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable

from core.providers.base import Provider, ProviderCancelled, ProviderError

log = logging.getLogger("claude_code")

# ไบนารีที่ติดมากับแอป Claude Desktop บน Windows
# แอปเวอร์ชัน Store/MSIX เก็บไว้ใต้ AppData\Local\Packages\Claude_*\LocalCache\Roaming แทน AppData\Roaming
_DESKTOP_GLOBS = [
    os.path.join(os.environ.get("APPDATA", ""), "Claude", "claude-code", "*", "claude.exe"),
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Packages", "Claude_*", "LocalCache", "Roaming",
                 "Claude", "claude-code", "*", "claude.exe"),
    os.path.join(os.environ.get("USERPROFILE", ""), ".local", "bin", "claude.exe"),
]


# แฟล็กที่ทำให้ Claude Code เริ่มเร็วขึ้น: ไม่โหลด MCP server, ปลั๊กอิน/skill และส่วนเสริม Chrome
# (--mcp-config รับได้หลายค่า จึงต้องมีแฟล็กอื่นตามหลังเสมอ ห้ามวาง prompt ต่อท้ายทันที)
FAST_START_ARGS = [
    "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
    "--disable-slash-commands",
    "--no-chrome",
]


# สคริปต์ครอบของ npm (claude.cmd / claude.ps1) ต้องรันผ่าน cmd.exe หรือ powershell
# ซึ่ง "ตัดบรรทัดคำสั่งทิ้งตรงตัวขึ้นบรรทัดใหม่" ทำให้ --system-prompt และ prompt ที่มีหลายบรรทัด
# หายไปกลางทาง (claude แจ้งว่า "Input must be provided...") จึงต้องเรียก claude.exe ตรง ๆ เสมอ
_SHIM_SUFFIXES = {".cmd", ".bat", ".ps1"}


def resolve_shim(path: str) -> str:
    """ถ้า path เป็นสคริปต์ครอบของ npm ให้คืน claude.exe ตัวจริงที่มันเรียกอยู่ข้างใน"""
    p = Path(path)
    if p.suffix.lower() not in _SHIM_SUFFIXES:
        return path
    for real in (p.with_suffix(".exe"),
                 p.parent / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"):
        if real.exists():
            return str(real)
    return path


def find_claude_command(configured: str = "") -> list[str]:
    """คืนคำสั่งเป็น list (รองรับ 'python fake.py' สำหรับทดสอบ)"""
    env_cmd = os.environ.get("CLAUDE_CODE_COMMAND")  # สำหรับทดสอบ มาก่อน config
    if env_cmd:
        return shlex.split(env_cmd, posix=False)
    if configured:
        parts = shlex.split(configured, posix=False)
        parts[0] = parts[0].strip('"')
        # พาธที่ระบุไว้อาจเป็นของเครื่องอื่น (เช่น ส่งโปรเจกต์ให้เพื่อน) ถ้าไม่มีไฟล์ให้หาอัตโนมัติแทน
        found = parts[0] if os.path.exists(parts[0]) else shutil.which(parts[0])
        if found:
            parts[0] = resolve_shim(found)
            return parts

    on_path = shutil.which("claude")
    resolved = resolve_shim(on_path) if on_path else ""
    # ได้ .exe ตัวจริงจาก PATH แล้ว ใช้ได้เลย
    if resolved and Path(resolved).suffix.lower() == ".exe":
        return [resolved]

    # ไม่งั้นลองหาไบนารีที่ติดมากับแอป Claude Desktop
    candidates: list[str] = []
    for pattern in _DESKTOP_GLOBS:
        candidates.extend(glob.glob(pattern))
    candidates = sorted(set(candidates), key=_version_key)
    if candidates:
        return [candidates[-1]]

    # เหลือแค่สคริปต์ครอบ ก็ยังดีกว่าไม่มีอะไรเลย (prompt หลายบรรทัดจะใช้ไม่ได้)
    if on_path:
        log.warning("ใช้ %s ได้อย่างเดียว prompt หลายบรรทัดอาจส่งไม่ถึง", on_path)
        return [on_path]
    return []


def _version_key(path: str) -> tuple[int, ...]:
    ver = Path(path).parent.name
    try:
        return tuple(int(x) for x in ver.split("."))
    except ValueError:
        return (0,)


class ClaudeCodeProvider(Provider):
    name = "claude_code"

    def __init__(self, config):
        super().__init__(config)
        self.command = find_claude_command(str(self.cfg.get("command", "")))
        self.effort = str(self.cfg.get("effort", "low") or "")
        self.extra_args = [str(a) for a in self.cfg.get("extra_args", [])]
        self.fast_start = bool(self.cfg.get("fast_start", True))

    def available(self) -> bool:
        return bool(self.command)

    def complete(self, system: str, user: str, model_alias: str) -> str:
        if not self.command:
            raise ProviderError("ไม่พบ Claude Code CLI (ตั้งค่า providers.claude_code.command หรือติดตั้ง claude)")

        args = self._args(system, user, model_alias, streaming=False)

        creationflags = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        started = time.perf_counter()
        try:
            proc = subprocess.run(
                args,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.config.timeout,
                creationflags=creationflags,
                env=env,
                # ไม่ปิด stdin claude จะรอข้อมูลจาก stdin 3 วินาทีก่อนทุกครั้ง
                stdin=subprocess.DEVNULL,
            )
        except subprocess.TimeoutExpired as e:
            raise ProviderError(f"Claude Code ไม่ตอบภายใน {self.config.timeout:.0f} วินาที") from e
        except OSError as e:
            raise ProviderError(f"รัน Claude Code ไม่ได้: {e}") from e

        result, data = _parse_output(proc.stdout, proc.stderr, proc.returncode)
        wall = time.perf_counter() - started
        api = float(data.get("duration_api_ms") or 0) / 1000
        log.info("model=%s wall=%.1fs api=%.1fs startup=%.1fs", model_alias, wall, api, wall - api)
        return result

    def _args(self, system: str, user: str, model_alias: str, streaming: bool) -> list[str]:
        args = [*self.command, "-p", *(FAST_START_ARGS if self.fast_start else []),
                "--tools", "", "--no-session-persistence"]
        if streaming:
            # stream-json ต้องคู่กับ --verbose ส่วน --include-partial-messages = ส่งข้อความทีละชิ้นระหว่างพิมพ์
            args += ["--output-format", "stream-json", "--verbose", "--include-partial-messages"]
        else:
            args += ["--output-format", "json"]
        args += ["--model", model_alias, "--system-prompt", system]
        if self.effort:
            args += ["--effort", self.effort]
        args += self.extra_args
        args.append(user)
        return args

    def stream(
        self,
        system: str,
        user: str,
        model_alias: str,
        on_delta: Callable[[str], None] | None = None,
        cancel: threading.Event | None = None,
    ) -> str:
        """เหมือน complete() แต่ทยอยส่งข้อความผ่าน on_delta ตั้งแต่คำแรก (ก่อนบูตเสร็จ ~1.5 วิ)"""
        if not self.command:
            raise ProviderError("ไม่พบ Claude Code CLI (ตั้งค่า providers.claude_code.command หรือติดตั้ง claude)")

        creationflags = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        started = time.perf_counter()
        try:
            proc = subprocess.Popen(
                self._args(system, user, model_alias, streaming=True),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # รวมกับ stdout กัน pipe ตัน (บรรทัดที่ไม่ใช่ JSON ถูกกรองทิ้ง)
                stdin=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=creationflags,
                env=env,
            )
        except OSError as e:
            raise ProviderError(f"รัน Claude Code ไม่ได้: {e}") from e

        timed_out = threading.Event()

        def on_timeout() -> None:
            timed_out.set()
            proc.kill()

        timer = threading.Timer(self.config.timeout, on_timeout)
        timer.daemon = True
        timer.start()
        if cancel is not None:
            def watch_cancel() -> None:  # ถูกยกเลิก (อีกเจ้าตอบก่อน) -> ฆ่า process ทันที
                while proc.poll() is None:
                    if cancel.wait(0.1):
                        proc.kill()
                        return

            threading.Thread(target=watch_cancel, daemon=True).start()

        parts: list[str] = []
        data: dict = {}
        noise: list[str] = []  # บรรทัดที่ไม่ใช่ JSON เก็บไว้โชว์ตอน error
        try:
            for line in proc.stdout:
                line = line.strip()
                if not line.startswith("{"):
                    if line:
                        noise = (noise + [line])[-5:]
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                kind = event.get("type")
                if kind == "stream_event":
                    inner = event.get("event", {})
                    if inner.get("type") == "content_block_delta":
                        delta = inner.get("delta", {})
                        chunk = delta.get("text", "") if delta.get("type") == "text_delta" else ""
                        if chunk:
                            parts.append(chunk)
                            if on_delta is not None:
                                on_delta(chunk)
                elif kind == "result":
                    data = event
            proc.wait()
        finally:
            timer.cancel()

        if cancel is not None and cancel.is_set():
            raise ProviderCancelled("ยกเลิก")
        if timed_out.is_set():
            raise ProviderError(f"Claude Code ไม่ตอบภายใน {self.config.timeout:.0f} วินาที")
        stderr = "\n".join(noise)
        if not data:
            raise ProviderError(f"Claude Code ตอบไม่เป็น JSON (exit {proc.returncode}): {(stderr or 'ไม่มีผลลัพธ์')[:300]}")
        result = _result_from_data(data, stderr, "".join(parts).strip())
        wall = time.perf_counter() - started
        api = float(data.get("duration_api_ms") or 0) / 1000
        log.info("model=%s wall=%.1fs api=%.1fs startup=%.1fs", model_alias, wall, api, wall - api)
        return result


def _parse_output(stdout: str, stderr: str, returncode: int) -> tuple[str, dict]:
    text = (stdout or "").strip()
    data = None
    if text:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # บางเวอร์ชันพิมพ์บรรทัดอื่นนำหน้า ลองหาบรรทัดสุดท้ายที่เป็น JSON
            for line in reversed(text.splitlines()):
                line = line.strip()
                if line.startswith("{"):
                    try:
                        data = json.loads(line)
                        break
                    except json.JSONDecodeError:
                        continue
    if data is None:
        msg = (stderr or text or "ไม่มีผลลัพธ์").strip()
        raise ProviderError(f"Claude Code ตอบไม่เป็น JSON (exit {returncode}): {msg[:300]}")
    return _result_from_data(data, stderr), data


def _result_from_data(data: dict, stderr: str, streamed: str = "") -> str:
    """ดึงข้อความจากก้อน result ของ claude (ถ้าว่างใช้ที่ stream มา) แปลง error เป็น ProviderError ภาษาไทย"""
    result = str(data.get("result", "")).strip()
    if data.get("is_error"):
        if "login" in result.lower():
            raise ProviderError(
                "Claude Code ยังไม่ได้ล็อกอิน: เปิด PowerShell แล้วรันคำสั่ง claude จากนั้นพิมพ์ /login หนึ่งครั้ง"
            )
        raise ProviderError(f"Claude Code แจ้งข้อผิดพลาด: {result or stderr.strip()[:300]}")
    result = result or streamed
    if not result:
        raise ProviderError(f"Claude Code แจ้งข้อผิดพลาด: {stderr.strip()[:300] or 'ไม่มีผลลัพธ์'}")
    return result
