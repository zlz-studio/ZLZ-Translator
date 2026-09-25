"""ตัวช่วยตั้งค่าครั้งแรกแบบทีละขั้น (tkinter) — กด "ถัดไป" ไม่ได้จนกว่าขั้นนั้นจะผ่านจริง

    1 ยินดีต้อนรับ
    2 Claude Code CLI   ตรวจ/ติดตั้งให้ (หรือเลือกใช้ Gemini อย่างเดียว)
    3 Gemini API key    ปุ่มพาไปขอคีย์ -> วาง -> ตรวจกับ Google จริง
    4 Login Claude      ปุ่ม login -> ตรวจด้วยการแปลทดสอบจริง (ไม่เชื่อ `claude auth status`)
    5 เสร็จ             เปิดอัตโนมัติเมื่อเข้า Windows -> เริ่มใช้งาน

เรียกได้ทั้งตอนเปิดโปรแกรมครั้งแรก (run_wizard()) และจากเมนู tray (run_wizard(parent=root))
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import tkinter as tk
import urllib.error
import urllib.request
import webbrowser
from typing import Callable

from core.config import APP_NAME, MODES, load_config, set_config_value, set_env_value
from core.providers import ProviderError
from core.providers.claude_code import ClaudeCodeProvider, find_claude_command
from hotkey import autostart

BG = "#1e1f22"
FG = "#f2f3f5"
MUTED = "#9a9ca3"
ACCENT = "#5865f2"
PANEL = "#2b2d31"
OK = "#57f287"
ERR = "#ed4245"

GEMINI_KEY_URL = "https://aistudio.google.com/apikey"
CLAUDE_INSTALL_COMMAND = "irm https://claude.ai/install.ps1 | iex"  # ตัวติดตั้งทางการ ไม่ต้อง admin
_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
HOTKEY_LABELS = {"read": "แปลข้อความที่ลากคลุม", "reply": "แปลที่พิมพ์ไทยเป็นอังกฤษ",
                 "explain": "อธิบายข้อความที่ลากคลุม", "polish": "ขัดเกลาอังกฤษที่พิมพ์เอง"}


# ---------------------------------------------------------------- งานตรวจสอบ (รันในเธรดแยก)
def check_gemini_key(key: str) -> tuple[bool, str]:
    """ยิง API จริงด้วยคีย์นี้ (list models) เพื่อพิสูจน์ว่าใช้ได้"""
    key = key.strip()
    if not key:
        return False, "ยังไม่ได้วางคีย์"
    req = urllib.request.Request(
        "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1",
        headers={"x-goog-api-key": key},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            json.load(resp)
    except urllib.error.HTTPError as e:
        if e.code in (400, 401, 403):
            return False, f"Google ปฏิเสธคีย์นี้ (HTTP {e.code}) ตรวจว่าก๊อปมาครบทุกตัวอักษร"
        return False, f"Google ตอบ HTTP {e.code} ลองใหม่อีกครั้ง"
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return False, f"ติดต่อ Google ไม่ได้: {e}"
    return True, "คีย์ใช้งานได้"


def detect_claude() -> tuple[list[str], str]:
    """หา claude CLI แล้วถามเวอร์ชัน คืน (คำสั่ง, เวอร์ชัน) ถ้าไม่พบคืน ([], "")"""
    cmd = find_claude_command()
    if not cmd:
        return [], ""
    try:
        proc = subprocess.run([*cmd, "--version"], capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=30, stdin=subprocess.DEVNULL, creationflags=_NO_WINDOW)
        first = (proc.stdout or "").strip().splitlines()
        return cmd, first[0] if first else ""
    except (OSError, subprocess.TimeoutExpired):
        return cmd, ""


def check_claude_login(cfg) -> tuple[bool, str]:
    """ทดสอบด้วยการเรียกโมเดลจริง (claude auth status บอกว่า login แล้วทั้งที่ token หมดอายุ เชื่อไม่ได้)"""
    prov = ClaudeCodeProvider(cfg)
    if not prov.available():
        return False, "ไม่พบ Claude Code CLI"
    try:
        prov.complete("Reply with exactly the word OK and nothing else.", "OK?", "sonnet")
    except ProviderError as e:
        return False, str(e)
    return True, "ล็อกอินแล้ว ใช้งานได้"


def claude_account_email() -> str:
    """อีเมลบัญชีจาก claude auth status (ใช้แสดงผลเท่านั้น)"""
    cmd = find_claude_command()
    if not cmd:
        return ""
    try:
        proc = subprocess.run([*cmd, "auth", "status"], capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=30, stdin=subprocess.DEVNULL, creationflags=_NO_WINDOW)
        return str(json.loads(proc.stdout).get("email", ""))
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, ValueError):
        return ""


# ---------------------------------------------------------------- หน้าต่าง
class SetupWizard:
    def __init__(self, parent: tk.Tk | None = None):
        self.cfg = load_config()
        self.root_dir = self.cfg.root
        self.completed = False
        self._closed = False
        self.owns_root = parent is None
        self.win: tk.Misc = tk.Tk() if parent is None else tk.Toplevel(parent)
        win = self.win
        win.title(f"{APP_NAME} — ตั้งค่าครั้งแรก")
        win.configure(bg=BG)
        win.geometry("760x540")
        win.minsize(700, 500)
        win.protocol("WM_DELETE_WINDOW", self._cancel)
        self._center()

        self.font = ("Segoe UI", 11)
        self.small = ("Segoe UI", 9)
        self.bold = ("Segoe UI", 12, "bold")

        # สถานะที่ใช้ตัดสินว่า "ถัดไป" ได้ไหม
        self.skip_claude = tk.BooleanVar(value=False)
        self.autostart_var = tk.BooleanVar(value=True)
        self.claude_cmd: list[str] = []
        self.claude_version = ""
        self.gemini_ok = False
        self.claude_ok = False
        self._login_proc: subprocess.Popen | None = None

        self.steps: list[dict] = [
            {"title": "ยินดีต้อนรับ", "build": self._build_welcome, "can_next": lambda: True},
            {"title": "Claude Code CLI", "build": self._build_claude_cli, "enter": self._enter_claude_cli,
             "can_next": lambda: bool(self.claude_cmd) or self.skip_claude.get()},
            {"title": "Gemini API key", "build": self._build_gemini, "enter": self._enter_gemini,
             "can_next": lambda: self.gemini_ok},
            {"title": "Login Claude", "build": self._build_claude_login, "enter": self._enter_claude_login,
             "can_next": lambda: self.claude_ok, "skip": lambda: self.skip_claude.get()},
            {"title": "เสร็จแล้ว", "build": self._build_finish, "enter": self._enter_finish, "can_next": lambda: True},
        ]
        self.index = 0
        self._frames: dict[int, tk.Frame] = {}

        # ---- โครง: ซ้าย = รายการขั้น / ขวา = เนื้อหา / ล่าง = ปุ่ม ----
        side = tk.Frame(win, bg=PANEL, width=190)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        tk.Label(side, text=APP_NAME, bg=PANEL, fg=FG, font=self.bold, anchor="w", padx=16, pady=16).pack(fill="x")
        self._step_labels: list[tk.Label] = []
        for i, step in enumerate(self.steps):
            lbl = tk.Label(side, text=f"{i + 1}   {step['title']}", bg=PANEL, fg=MUTED, font=self.font,
                           anchor="w", padx=16, pady=6)
            lbl.pack(fill="x")
            self._step_labels.append(lbl)

        right = tk.Frame(win, bg=BG)
        right.pack(side="left", fill="both", expand=True)
        self.content = tk.Frame(right, bg=BG, padx=24, pady=20)
        self.content.pack(fill="both", expand=True)
        bar = tk.Frame(right, bg=BG, padx=24, pady=14)
        bar.pack(fill="x", side="bottom")
        self.status = tk.Label(bar, text="", bg=BG, fg=MUTED, font=self.small, anchor="w")
        self.status.pack(side="left", fill="x", expand=True)
        self.btn_next = self._button(bar, "ถัดไป  ▸", lambda: self._go(+1), primary=True)
        self.btn_next.pack(side="right")
        self.btn_back = self._button(bar, "◂  ย้อนกลับ", lambda: self._go(-1))
        self.btn_back.pack(side="right", padx=(0, 8))

        self._show(0)

    # ---------------------------------------------------------------- helpers
    def _center(self) -> None:
        self.win.update_idletasks()
        w, h = 760, 540
        x = (self.win.winfo_screenwidth() - w) // 2
        y = (self.win.winfo_screenheight() - h) // 2 - 30
        self.win.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")

    def _button(self, parent, text, command, primary=False, state="normal"):
        return tk.Button(parent, text=text, command=command, state=state, bd=0, padx=14, pady=6,
                         font=("Segoe UI", 10, "bold" if primary else "normal"),
                         bg=ACCENT if primary else PANEL, fg="white" if primary else FG,
                         activebackground="#4752c4" if primary else "#3a3c42", activeforeground="white",
                         disabledforeground="#6a6c72", cursor="hand2")

    def _heading(self, parent, text) -> None:
        tk.Label(parent, text=text, bg=BG, fg=FG, font=("Segoe UI", 16, "bold"), anchor="w").pack(fill="x", pady=(0, 6))

    def _para(self, parent, text, fg=MUTED) -> tk.Label:
        lbl = tk.Label(parent, text=text, bg=BG, fg=fg, font=self.font, anchor="w", justify="left", wraplength=500)
        lbl.pack(fill="x", pady=(0, 10))
        return lbl

    def _log_box(self, parent, height=7) -> tk.Text:
        box = tk.Text(parent, height=height, bg=PANEL, fg=MUTED, font=("Consolas", 9), bd=0, padx=8, pady=6,
                      wrap="word", state="disabled")
        box.pack(fill="both", expand=True, pady=(6, 0))
        return box

    def _log(self, box: tk.Text, line: str) -> None:
        def apply():
            try:
                box.configure(state="normal")
                box.insert("end", line.rstrip() + "\n")
                box.see("end")
                box.configure(state="disabled")
            except tk.TclError:
                pass
        self._ui(apply)

    def _ui(self, fn: Callable[[], None]) -> None:
        """เรียก fn บนเธรด tkinter (ปลอดภัยจากเธรดอื่น) เงียบถ้าหน้าต่างปิดไปแล้ว"""
        if self._closed:
            return
        try:
            self.win.after(0, fn)
        except tk.TclError:
            pass

    def _set_status(self, text: str, fg=MUTED) -> None:
        self._ui(lambda: self.status.configure(text=text, fg=fg))

    def _refresh_nav(self) -> None:
        step = self.steps[self.index]
        last = self.index == len(self.steps) - 1
        self.btn_next.configure(text="เริ่มใช้งาน  ✓" if last else "ถัดไป  ▸",
                                state="normal" if step["can_next"]() else "disabled")
        self.btn_back.configure(state="normal" if self.index > 0 else "disabled")
        for i, lbl in enumerate(self._step_labels):
            skipped = self.steps[i].get("skip", lambda: False)()
            lbl.configure(fg=ACCENT if i == self.index else ("#5a5c62" if skipped else MUTED),
                          font=("Segoe UI", 11, "bold") if i == self.index else self.font)

    def _show(self, index: int) -> None:
        for frame in self._frames.values():
            frame.pack_forget()
        self.index = index
        if index not in self._frames:
            frame = tk.Frame(self.content, bg=BG)
            self.steps[index]["build"](frame)
            self._frames[index] = frame
        self._frames[index].pack(fill="both", expand=True)
        self.status.configure(text="")
        enter = self.steps[index].get("enter")
        if enter:
            enter()
        self._refresh_nav()

    def _go(self, delta: int) -> None:
        if delta > 0 and not self.steps[self.index]["can_next"]():
            return
        if delta > 0 and self.index == len(self.steps) - 1:
            self._finish()
            return
        target = self.index + delta
        while 0 <= target < len(self.steps) and self.steps[target].get("skip", lambda: False)():
            target += delta
        if 0 <= target < len(self.steps):
            self._show(target)

    # ---------------------------------------------------------------- 1 ยินดีต้อนรับ
    def _build_welcome(self, f: tk.Frame) -> None:
        self._heading(f, f"ยินดีต้อนรับสู่ {APP_NAME}")
        self._para(f, "โปรแกรมช่วยแปลตอนคุยกับลูกค้าต่างชาติ กดปุ่มลัดได้จากทุกโปรแกรม (Discord, เว็บ, อีเมล)\n"
                      "ลากคลุมอังกฤษกด F8 = แปลไทย   พิมพ์ไทยกด F9 = เป็นอังกฤษพร้อมส่ง", fg=FG)
        self._para(f, "ตัวช่วยนี้จะพาตั้งค่าทีละขั้น ใช้เวลาประมาณ 5 นาที สิ่งที่ต้องใช้:")
        for line in ("•  บัญชี Google สำหรับขอคีย์ Gemini (ฟรี)",
                     "•  บัญชี Claude Pro ขึ้นไป (ถ้ามี — ใช้เป็นตัวแปลสำรองที่แม่นกว่า ไม่มีก็ข้ามได้)"):
            self._para(f, line, fg=FG)
        self._para(f, "กด \"ถัดไป\" เพื่อเริ่ม  ทุกขั้นเปลี่ยนทีหลังได้จากเมนูไอคอนโปรแกรมที่มุมขวาล่างจอ")

    # ---------------------------------------------------------------- 2 Claude Code CLI
    def _build_claude_cli(self, f: tk.Frame) -> None:
        self._heading(f, "Claude Code CLI")
        self._para(f, "โปรแกรมเล็ก ๆ ของ Anthropic ที่ให้เราใช้โควต้าสมาชิก Claude Pro แปลได้โดยไม่ต้องจ่ายค่า API แยก")
        row = tk.Frame(f, bg=BG)
        row.pack(fill="x", pady=(0, 8))
        self.claude_status = tk.Label(row, text="กำลังตรวจ...", bg=BG, fg=MUTED, font=self.font, anchor="w")
        self.claude_status.pack(side="left", fill="x", expand=True)
        self._button(row, "ตรวจอีกครั้ง", self._enter_claude_cli).pack(side="right")
        self.btn_install = self._button(f, "ติดตั้ง Claude Code ให้เลย", self._install_claude, primary=True)
        self.btn_install.pack(anchor="w", pady=(0, 4))
        self._para(f, "การติดตั้งใช้ตัวติดตั้งทางการของ Anthropic ไม่ต้องสิทธิ์ Admin และจะอัปเดตตัวเองในอนาคต")
        tk.Checkbutton(f, text="ไม่มีบัญชี Claude Pro  →  ข้ามขั้นนี้ ใช้ Gemini อย่างเดียว", variable=self.skip_claude,
                       command=self._refresh_nav, bg=BG, fg=FG, selectcolor=PANEL, activebackground=BG,
                       activeforeground=FG, font=self.font, anchor="w").pack(fill="x", pady=(6, 0))
        self.claude_log = self._log_box(f, height=6)

    def _enter_claude_cli(self) -> None:
        self.claude_status.configure(text="กำลังตรวจ...", fg=MUTED)

        def run():
            cmd, version = detect_claude()
            self.claude_cmd, self.claude_version = cmd, version

            def apply():
                if cmd:
                    self.claude_status.configure(text=f"✓ พบแล้ว  {version or ''}  ({cmd[0]})", fg=OK)
                    self.btn_install.configure(state="disabled")
                else:
                    self.claude_status.configure(text="✗ ยังไม่มี Claude Code ในเครื่องนี้", fg=ERR)
                    self.btn_install.configure(state="normal")
                self._refresh_nav()
            self._ui(apply)
        threading.Thread(target=run, daemon=True).start()

    def _install_claude(self) -> None:
        self.btn_install.configure(state="disabled")
        self._log(self.claude_log, f"> {CLAUDE_INSTALL_COMMAND}")
        self._set_status("กำลังติดตั้ง Claude Code... (ประมาณ 1 นาที)")

        def run():
            try:
                proc = subprocess.Popen(
                    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", CLAUDE_INSTALL_COMMAND],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                    text=True, encoding="utf-8", errors="replace", creationflags=_NO_WINDOW,
                )
                for line in proc.stdout:
                    if line.strip():
                        self._log(self.claude_log, line)
                proc.wait()
                self._log(self.claude_log, f"(จบ exit code {proc.returncode})")
            except OSError as e:
                self._log(self.claude_log, f"รันตัวติดตั้งไม่ได้: {e}")
            self._set_status("")
            self._ui(self._enter_claude_cli)
        threading.Thread(target=run, daemon=True).start()

    # ---------------------------------------------------------------- 3 Gemini
    def _build_gemini(self, f: tk.Frame) -> None:
        self._heading(f, "Gemini API key (ฟรี)")
        self._para(f, "1. กดปุ่มด้านล่าง เว็บของ Google จะเปิด  ล็อกอินบัญชี Google แล้วกด \"Create API key\"\n"
                      "2. ก๊อปคีย์ที่ได้ (ขึ้นต้นด้วย AIza... หรือ AQ...) กลับมาวางในช่องนี้ แล้วกด \"ตรวจสอบ\"")
        self._button(f, "เปิดหน้าขอคีย์ Gemini  ↗", lambda: webbrowser.open(GEMINI_KEY_URL), primary=True).pack(anchor="w", pady=(0, 12))
        row = tk.Frame(f, bg=BG)
        row.pack(fill="x")
        self.gemini_var = tk.StringVar(value=self.cfg.secret("GEMINI_API_KEY") or "")
        self.gemini_entry = tk.Entry(row, textvariable=self.gemini_var, bg=PANEL, fg=FG, insertbackground=FG,
                                     font=("Consolas", 11), bd=0, show="•")
        self.gemini_entry.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 8))
        self._button(row, "ตรวจสอบ", self._verify_gemini).pack(side="left")
        self.gemini_var.trace_add("write", lambda *_: self._invalidate_gemini())
        self.show_key = tk.BooleanVar(value=False)
        tk.Checkbutton(f, text="แสดงคีย์", variable=self.show_key, bg=BG, fg=MUTED, selectcolor=PANEL,
                       activebackground=BG, activeforeground=FG, font=self.small,
                       command=lambda: self.gemini_entry.configure(show="" if self.show_key.get() else "•")).pack(anchor="w")
        self.gemini_status = tk.Label(f, text="", bg=BG, fg=MUTED, font=self.font, anchor="w", wraplength=500, justify="left")
        self.gemini_status.pack(fill="x", pady=(10, 0))
        self._para(f, "คีย์ถูกเก็บในเครื่องคุณเท่านั้น (ไฟล์ .env ในโฟลเดอร์ข้อมูลของโปรแกรม)")

    def _enter_gemini(self) -> None:
        if self.gemini_var.get().strip() and not self.gemini_ok:
            self._verify_gemini()

    def _invalidate_gemini(self) -> None:
        self.gemini_ok = False
        self.gemini_status.configure(text="", fg=MUTED)
        self._refresh_nav()

    def _verify_gemini(self) -> None:
        key = self.gemini_var.get().strip()
        self.gemini_status.configure(text="กำลังตรวจกับ Google...", fg=MUTED)

        def run():
            ok, msg = check_gemini_key(key)

            def apply():
                self.gemini_ok = ok
                self.gemini_status.configure(text=("✓ " if ok else "✗ ") + msg, fg=OK if ok else ERR)
                if ok:
                    try:
                        set_env_value(self.root_dir, "GEMINI_API_KEY", key)
                    except OSError as e:
                        self.gemini_ok = False
                        self.gemini_status.configure(text=f"✗ บันทึกคีย์ไม่ได้: {e}", fg=ERR)
                self._refresh_nav()
            self._ui(apply)
        threading.Thread(target=run, daemon=True).start()

    # ---------------------------------------------------------------- 4 Login Claude
    def _build_claude_login(self, f: tk.Frame) -> None:
        self._heading(f, "ล็อกอิน Claude")
        self._para(f, "กดปุ่ม Login เบราว์เซอร์จะเปิดให้ยืนยันบัญชี Claude ของคุณ เสร็จแล้วกลับมาหน้านี้ โปรแกรมจะตรวจให้เอง\n"
                      "ถ้าเบราว์เซอร์ไม่เปิด ใช้ปุ่ม \"เปิดลิงก์เอง\" แล้วถ้าเว็บให้โค้ดมา ให้วางในช่องด้านล่าง")
        row = tk.Frame(f, bg=BG)
        row.pack(fill="x", pady=(0, 8))
        self.login_status = tk.Label(row, text="", bg=BG, fg=MUTED, font=self.font, anchor="w", wraplength=380, justify="left")
        self.login_status.pack(side="left", fill="x", expand=True)
        self._button(row, "ตรวจอีกครั้ง", self._enter_claude_login).pack(side="right")
        btns = tk.Frame(f, bg=BG)
        btns.pack(fill="x", pady=(0, 6))
        self.btn_login = self._button(btns, "Login Claude  ↗", self._start_login, primary=True)
        self.btn_login.pack(side="left")
        self.btn_open_url = self._button(btns, "เปิดลิงก์เอง", self._open_login_url, state="disabled")
        self.btn_open_url.pack(side="left", padx=(8, 0))
        self._login_url = ""
        code_row = tk.Frame(f, bg=BG)
        code_row.pack(fill="x")
        self.code_var = tk.StringVar()
        self.code_entry = tk.Entry(code_row, textvariable=self.code_var, bg=PANEL, fg=FG, insertbackground=FG,
                                   font=("Consolas", 10), bd=0, state="disabled")
        self.code_entry.pack(side="left", fill="x", expand=True, ipady=5, padx=(0, 8))
        self.btn_code = self._button(code_row, "ส่งโค้ด", self._send_code, state="disabled")
        self.btn_code.pack(side="left")
        self.login_log = self._log_box(f, height=6)

    def _enter_claude_login(self) -> None:
        self.login_status.configure(text="กำลังตรวจสถานะล็อกอิน (แปลทดสอบ 1 ครั้ง ~5 วินาที)...", fg=MUTED)
        self.claude_ok = False
        self._refresh_nav()

        def run():
            ok, msg = check_claude_login(load_config(self.root_dir))
            email = claude_account_email() if ok else ""

            def apply():
                self.claude_ok = ok
                text = f"✓ {msg}" + (f"  ({email})" if email else "") if ok else f"✗ ยังใช้ไม่ได้: {msg[:160]}"
                self.login_status.configure(text=text, fg=OK if ok else ERR)
                self.btn_login.configure(state="disabled" if ok else "normal")
                self._refresh_nav()
            self._ui(apply)
        threading.Thread(target=run, daemon=True).start()

    def _start_login(self) -> None:
        cmd = self.claude_cmd or find_claude_command()
        if not cmd:
            self.login_status.configure(text="✗ ไม่พบ Claude Code CLI (ย้อนกลับไปขั้นที่ 2)", fg=ERR)
            return
        self.btn_login.configure(state="disabled")
        self._log(self.login_log, "> claude auth login")

        def run():
            try:
                proc = subprocess.Popen([*cmd, "auth", "login"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        stdin=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
                                        bufsize=1, creationflags=_NO_WINDOW)
            except OSError as e:
                self._log(self.login_log, f"รันไม่ได้: {e}")
                self._ui(lambda: self.btn_login.configure(state="normal"))
                return
            self._login_proc = proc
            buffer = ""
            while True:
                ch = proc.stdout.read(1)  # อ่านทีละตัวอักษร เพราะบรรทัด "Paste code here >" ไม่มีขึ้นบรรทัดใหม่
                if not ch:
                    break
                buffer += ch
                if ch == "\n" or buffer.endswith("> "):
                    line, buffer = buffer.strip(), ""
                    if line:
                        self._handle_login_line(line)
            if buffer.strip():
                self._handle_login_line(buffer.strip())
            proc.wait()
            self._login_proc = None
            self._log(self.login_log, f"(จบ exit code {proc.returncode})")
            self._ui(lambda: (self.btn_login.configure(state="normal"), self._disable_code_entry()))
            self._ui(self._enter_claude_login)
        threading.Thread(target=run, daemon=True).start()

    def _handle_login_line(self, line: str) -> None:
        self._log(self.login_log, line)
        m = re.search(r"https://\S+", line)
        if m and "oauth" in m.group(0):
            self._login_url = m.group(0).rstrip(".,)")
            self._ui(lambda: self.btn_open_url.configure(state="normal"))
        if "paste code" in line.lower():
            self._ui(lambda: (self.code_entry.configure(state="normal"), self.btn_code.configure(state="normal"),
                              self.code_entry.focus_set()))

    def _open_login_url(self) -> None:
        if self._login_url:
            webbrowser.open(self._login_url)

    def _send_code(self) -> None:
        proc = self._login_proc
        code = self.code_var.get().strip()
        if proc is None or proc.poll() is not None or not code:
            return
        try:
            proc.stdin.write(code + "\n")
            proc.stdin.flush()
            self._log(self.login_log, "(ส่งโค้ดแล้ว รอผล...)")
        except OSError as e:
            self._log(self.login_log, f"ส่งโค้ดไม่ได้: {e}")

    def _disable_code_entry(self) -> None:
        self.code_entry.configure(state="disabled")
        self.btn_code.configure(state="disabled")

    # ---------------------------------------------------------------- 5 เสร็จ
    def _build_finish(self, f: tk.Frame) -> None:
        self._heading(f, "พร้อมใช้งานแล้ว")
        self.finish_summary = tk.Label(f, text="", bg=BG, fg=FG, font=self.font, anchor="w", justify="left")
        self.finish_summary.pack(fill="x", pady=(0, 12))
        self._para(f, "ปุ่มลัด (เปลี่ยนได้ทีหลังที่เมนูไอคอนโปรแกรม > ตั้งค่า):")
        for mode in MODES:
            combo = self.cfg.hotkey(mode)
            if combo:
                self._para(f, f"    {combo.upper():14s} {HOTKEY_LABELS[mode]}", fg=FG)
        tk.Checkbutton(f, text="เปิดโปรแกรมอัตโนมัติเมื่อเข้า Windows (แนะนำ)", variable=self.autostart_var,
                       bg=BG, fg=FG, selectcolor=PANEL, activebackground=BG, activeforeground=FG,
                       font=self.font, anchor="w").pack(fill="x", pady=(8, 0))
        self._para(f, "โปรแกรมจะไปอยู่ที่ไอคอนมุมขวาล่างจอ (ข้างนาฬิกา) คลิกขวาที่ไอคอนเพื่อเปลี่ยนโมเดล น้ำเสียง หรือปิดโปรแกรม")

    def _enter_finish(self) -> None:
        parts = ["✓ Gemini API key: ใช้งานได้"]
        if self.skip_claude.get():
            parts.append("–  Claude: ข้าม (ใช้ Gemini อย่างเดียว)")
        else:
            parts.append("✓ Claude: ล็อกอินแล้ว (ตัวสำรองเมื่อ Gemini ช้าหรือล่ม)")
        self.finish_summary.configure(text="\n".join(parts))

    def _finish(self) -> None:
        try:
            if self.skip_claude.get():
                set_config_value(self.root_dir, "general", "provider_order", ["gemini"])
            set_config_value(self.root_dir, "setup", "completed", "true")
            if self.autostart_var.get():
                autostart.enable(self.root_dir)
            else:
                autostart.disable()
        except OSError as e:
            self.status.configure(text=f"บันทึกไม่ได้: {e}", fg=ERR)
            return
        self.completed = True
        self._close()

    # ---------------------------------------------------------------- ปิด
    def _cancel(self) -> None:
        self._close()

    def _close(self) -> None:
        self._closed = True
        proc = self._login_proc
        if proc is not None and proc.poll() is None:
            proc.kill()
        try:
            if self.owns_root:
                self.win.quit()
            self.win.destroy()
        except tk.TclError:
            pass


def run_wizard(parent: tk.Tk | None = None) -> bool:
    """เปิดตัวช่วย รอจนปิด คืน True ถ้าตั้งค่าครบ (กด "เริ่มใช้งาน")"""
    wizard = SetupWizard(parent)
    if parent is None:
        wizard.win.mainloop()
    else:
        parent.wait_window(wizard.win)
    return wizard.completed


if __name__ == "__main__":
    sys.exit(0 if run_wizard() else 1)
