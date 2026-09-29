"""หน้าต่างตั้งค่าคีย์และบัญชี (เปิดจากเมนู tray) ไม่ต้องแก้ไฟล์เอง"""
from __future__ import annotations

import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from tkinter import ttk
from typing import Callable

import keyboard

from core.config import APP_NAME, MODES, set_config_value, set_env_value
from core.providers import ProviderError
from hotkey.popup import ACCENT, BG, FG, MUTED, PANEL

HOTKEY_LABELS = {
    "read": "แปลที่ลากคลุม -> ไทย",
    "reply": "ไทยในช่องพิมพ์ -> อังกฤษ",
    "explain": "อธิบายที่ลากคลุม",
    "polish": "แก้อังกฤษที่พิมพ์เอง",
}

GEMINI_URL = "https://aistudio.google.com/apikey"
DISCORD_URL = "https://discord.com/developers/applications"


class SettingsDialog:
    _current: "SettingsDialog | None" = None

    def __init__(self, root: tk.Tk, app, on_saved: Callable[[], None]):
        if SettingsDialog._current is not None:
            SettingsDialog._current.win.lift()
            return
        SettingsDialog._current = self
        self.app = app
        self.on_saved = on_saved
        cfg = app.cfg
        font = ("Segoe UI", 10)
        small = ("Segoe UI", 9)

        win = self.win = tk.Toplevel(root)
        win.title(f"{APP_NAME}: ตั้งค่าคีย์และบัญชี")
        win.configure(bg=BG)
        win.attributes("-topmost", True)
        win.resizable(False, False)
        win.protocol("WM_DELETE_WINDOW", self.close)
        body = tk.Frame(win, bg=BG, padx=16, pady=14)
        body.pack(fill="both", expand=True)

        # ---------- Gemini ----------
        self._section(body, "1. Gemini (ฟรี, เร็ว, แนะนำ)", font)
        tk.Label(body, text="ขอคีย์ด้วยบัญชี Google ของคุณ กดปุ่มด้านล่าง กด Create API key แล้วก๊อปคีย์มาวางในช่อง",
                 bg=BG, fg=MUTED, font=small, justify="left", wraplength=520).pack(anchor="w")
        self._link_button(body, "เปิดหน้าขอคีย์ Gemini (aistudio.google.com)", GEMINI_URL).pack(anchor="w", pady=(4, 6))
        self.gemini_var = tk.StringVar(value=cfg.env.get("GEMINI_API_KEY", ""))
        self._entry(body, "GEMINI_API_KEY", self.gemini_var)

        # ---------- Discord ----------
        self._section(body, "2. Discord app (ทางเลือก: คลิกขวาแปลในตัว Discord และใช้บนมือถือ)", font, top=14)
        tk.Label(body, text="สร้างแอปที่ Developer Portal > Installation ติ๊ก User Install > Bot กด Reset Token แล้วก๊อปมาวาง (ดู SETUP_GUIDE.md ขั้นที่ 4)",
                 bg=BG, fg=MUTED, font=small, justify="left", wraplength=520).pack(anchor="w")
        self._link_button(body, "เปิด Discord Developer Portal", DISCORD_URL).pack(anchor="w", pady=(4, 6))
        self.discord_var = tk.StringVar(value=cfg.env.get("DISCORD_TOKEN", ""))
        self._entry(body, "DISCORD_TOKEN", self.discord_var)

        # ---------- Claude ----------
        self._section(body, "3. Claude Code (ทางเลือก: ใช้แพ็กเกจ Claude Pro/Max ที่มีอยู่ เป็นตัวสำรอง)", font, top=14)
        row = tk.Frame(body, bg=BG)
        row.pack(anchor="w", fill="x")
        self.claude_status = tk.Label(row, text="กำลังตรวจสถานะ...", bg=BG, fg=MUTED, font=small)
        self.claude_status.pack(side="left")
        self._button(row, "ล็อกอิน Claude Code", self._claude_login).pack(side="right")

        # ---------- ปุ่มลัด ----------
        self._section(body, "4. ปุ่มลัด (ใช้ได้ทุกโปรแกรม ไม่ใช่แค่ Discord)", font, top=14)
        tk.Label(body, text='กด "กดปุ่ม" แล้วกดปุ่มที่ต้องการบนคีย์บอร์ด เช่น F7 หรือ Ctrl+Shift+T  (พิมพ์เองก็ได้ เช่น ctrl+shift+t)',
                 bg=BG, fg=MUTED, font=small, justify="left", wraplength=520).pack(anchor="w")
        self.hotkey_vars: dict[str, tk.StringVar] = {}
        for mode in MODES:
            row = tk.Frame(body, bg=BG)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=HOTKEY_LABELS[mode], bg=BG, fg=MUTED, font=small, width=24, anchor="w").pack(side="left")
            var = tk.StringVar(value=cfg.hotkey(mode) or "")
            self.hotkey_vars[mode] = var
            tk.Entry(row, textvariable=var, bg=PANEL, fg=FG, insertbackground=FG, relief="flat",
                     font=("Consolas", 10), width=18).pack(side="left", ipady=3)
            self._button(row, "กดปุ่ม", lambda m=mode: self._capture_hotkey(m)).pack(side="left", padx=(6, 0))
        self.only_discord_var = tk.BooleanVar(value=any("discord" in a.lower() for a in cfg.only_in_apps))
        tk.Checkbutton(body, text="ให้ปุ่มลัดทำงานเฉพาะตอนหน้าต่าง Discord เปิดอยู่ (กันชนกับ Unity / Visual Studio)",
                       variable=self.only_discord_var, bg=BG, fg=FG, selectcolor=PANEL, activebackground=BG,
                       activeforeground=FG, font=small, anchor="w").pack(anchor="w", pady=(4, 0))

        # ---------- ปุ่มล่าง ----------
        ttk.Separator(body).pack(fill="x", pady=12)
        bar = tk.Frame(body, bg=BG)
        bar.pack(fill="x")
        self._button(bar, "บันทึก", self._save, primary=True).pack(side="left")
        self._button(bar, "บันทึกแล้วทดสอบแปล", self._save_and_test).pack(side="left", padx=(8, 0))
        self._button(bar, "ปิด", self.close).pack(side="right")
        self.status = tk.Label(body, text="", bg=BG, fg="#c7d2fe", font=small, justify="left", wraplength=540)
        self.status.pack(anchor="w", pady=(8, 0))

        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        w, h = win.winfo_reqwidth(), win.winfo_reqheight()
        win.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")
        win.focus_force()
        threading.Thread(target=self._check_claude, daemon=True).start()

    # ---------------------------------------------------------------- widgets
    def _section(self, parent, text, font, top=0):
        tk.Label(parent, text=text, bg=BG, fg=FG, font=(font[0], font[1], "bold"), anchor="w").pack(fill="x", pady=(top, 2))

    def _entry(self, parent, label, var):
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x")
        tk.Label(row, text=label, bg=BG, fg=MUTED, font=("Consolas", 9), width=16, anchor="w").pack(side="left")
        show = tk.StringVar(value="•")
        entry = tk.Entry(row, textvariable=var, show="•", bg=PANEL, fg=FG, insertbackground=FG, relief="flat",
                         font=("Consolas", 10), width=46)
        entry.pack(side="left", fill="x", expand=True, ipady=4)
        tk.Button(row, text="แสดง", bg=PANEL, fg=MUTED, bd=0, font=("Segoe UI", 8), padx=6,
                  command=lambda e=entry: e.configure(show="" if e.cget("show") else "•")).pack(side="left", padx=(4, 0))

    def _button(self, parent, text, command, primary=False):
        return tk.Button(parent, text=text, command=command, bg=ACCENT if primary else PANEL, fg="white" if primary else FG,
                         bd=0, padx=12, pady=5, font=("Segoe UI", 9), cursor="hand2",
                         activebackground=ACCENT, activeforeground="white")

    def _link_button(self, parent, text, url):
        return self._button(parent, "🌐 " + text, lambda: webbrowser.open(url))

    # ---------------------------------------------------------------- actions
    def _save(self, quiet: bool = False) -> bool:
        # ตรวจปุ่มลัดก่อน: ต้องเป็นชื่อปุ่มที่รู้จัก และห้ามซ้ำกัน
        hotkeys: dict[str, str] = {}
        for mode, var in self.hotkey_vars.items():
            combo = var.get().strip().lower().replace(" ", "")
            if not combo:
                continue
            try:
                keyboard.parse_hotkey(combo)
            except (ValueError, KeyError):
                self.status.configure(text=f"ปุ่มลัด '{combo}' ({HOTKEY_LABELS[mode]}) ไม่ถูกต้อง ลองกดปุ่ม \"กดปุ่ม\" แล้วกดคีย์ที่ต้องการ", fg="#f87171")
                return False
            if combo in hotkeys.values():
                self.status.configure(text=f"ปุ่มลัด '{combo}' ถูกใช้ซ้ำ 2 โหมด", fg="#f87171")
                return False
            hotkeys[mode] = combo
        try:
            set_env_value(self.app.cfg.root, "GEMINI_API_KEY", self.gemini_var.get())
            set_env_value(self.app.cfg.root, "DISCORD_TOKEN", self.discord_var.get())
            for mode in MODES:
                set_config_value(self.app.cfg.root, "hotkeys", mode, hotkeys.get(mode, ""))
            set_config_value(self.app.cfg.root, "hotkeys", "only_in_apps", ["Discord"] if self.only_discord_var.get() else [])
        except OSError as e:
            self.status.configure(text=f"บันทึกไม่สำเร็จ: {e}", fg="#f87171")
            return False
        self.on_saved()
        if not quiet:
            self.status.configure(text="บันทึกแล้ว โปรแกรมโหลดค่าใหม่ให้เรียบร้อย", fg="#86efac")
        return True

    def _save_and_test(self) -> None:
        if not self._save(quiet=True):
            return
        self.status.configure(text="กำลังทดสอบแปล...", fg="#c7d2fe")

        def run():
            try:
                r = self.app.translator.run("read", "Hello! Could you send me the files by Friday?")
                text = f"ใช้ได้: แปลผ่าน {r.provider} ({r.model}) ใน {r.seconds:.1f} วินาที\n{r.text}"
                color = "#86efac"
            except (ProviderError, ValueError) as e:
                text, color = f"ยังใช้ไม่ได้:\n{e}", "#f87171"
            self._ui(lambda: self.status.configure(text=text, fg=color))

        threading.Thread(target=run, daemon=True).start()

    def _capture_hotkey(self, mode: str) -> None:
        """รอให้ผู้ใช้กดปุ่มบนคีย์บอร์ด แล้วใส่ชื่อปุ่มลงช่อง (หยุดปุ่มลัดเดิมชั่วคราวระหว่างรอ)"""
        self.status.configure(text=f"กดปุ่มที่ต้องการสำหรับ \"{HOTKEY_LABELS[mode]}\" ได้เลย (รอ 10 วินาที)", fg="#c7d2fe")
        was_paused = getattr(self.app, "paused", False)
        if hasattr(self.app, "paused"):
            self.app.paused = True

        def run():
            combo = ""
            try:
                combo = keyboard.read_hotkey(suppress=False)
            except Exception as e:  # noqa: BLE001
                self._ui(lambda: self.status.configure(text=f"อ่านปุ่มไม่ได้: {e}", fg="#f87171"))
            finally:
                if hasattr(self.app, "paused"):
                    self.app.paused = was_paused
            if combo:
                def apply():
                    self.hotkey_vars[mode].set(combo)
                    self.status.configure(text=f"ตั้งเป็น {combo} แล้ว กด \"บันทึก\" เพื่อใช้งาน", fg="#86efac")
                self._ui(apply)

        threading.Thread(target=run, daemon=True).start()

    def _check_claude(self) -> None:
        from core.providers.claude_code import find_claude_command
        cmd = find_claude_command(str(self.app.cfg.provider_cfg("claude_code").get("command", "")))
        if not cmd:
            text = "ยังไม่ได้ติดตั้ง Claude Code (ไม่จำเป็นถ้าใช้ Gemini)"
        else:
            try:
                proc = subprocess.run([*cmd, "auth", "status"], capture_output=True, text=True, encoding="utf-8",
                                      errors="replace", timeout=30, creationflags=0x08000000 if sys.platform == "win32" else 0)
                text = "ล็อกอินแล้ว" if '"loggedIn": true' in proc.stdout else "ยังไม่ได้ล็อกอิน"
            except (OSError, subprocess.TimeoutExpired):
                text = "ตรวจสถานะไม่ได้"
        self._ui(lambda: self.claude_status.configure(text="สถานะ: " + text))

    def _ui(self, fn) -> None:
        """เรียก fn บนเธรด tkinter (ผ่านคิวของแอปถ้ามี)"""
        def safe():
            try:
                fn()
            except tk.TclError:
                pass  # หน้าต่างถูกปิดไปแล้ว
        if hasattr(self.app, "ui"):
            self.app.ui(safe)
        else:
            try:
                self.win.after(0, safe)
            except RuntimeError:
                pass

    def _claude_login(self) -> None:
        from core.providers.claude_code import find_claude_command
        cmd = find_claude_command(str(self.app.cfg.provider_cfg("claude_code").get("command", "")))
        if not cmd:
            webbrowser.open("https://claude.com/claude-code")
            self.status.configure(text="ยังไม่มี Claude Code ในเครื่อง เปิดหน้าดาวน์โหลดให้แล้ว ติดตั้งเสร็จค่อยกดปุ่มนี้อีกครั้ง", fg="#c7d2fe")
            return
        subprocess.Popen([*cmd, "auth", "login", "--claudeai"], creationflags=0x08000000 if sys.platform == "win32" else 0)
        self.status.configure(text="เปิดเบราว์เซอร์ให้ล็อกอินแล้ว กด Authorize ในเบราว์เซอร์ แล้วปิด-เปิดหน้าต่างนี้ใหม่เพื่อดูสถานะ", fg="#c7d2fe")

    def close(self) -> None:
        SettingsDialog._current = None
        try:
            self.win.destroy()
        except tk.TclError:
            pass
