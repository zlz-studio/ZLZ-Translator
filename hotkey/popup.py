"""หน้าต่างป๊อปอัปแสดงผลแปล และ toast แจ้งสถานะสั้นๆ (tkinter)"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from core.translator import Result

BG = "#1e1f22"
FG = "#f2f3f5"
MUTED = "#9a9ca3"
ACCENT = "#5865f2"
PANEL = "#2b2d31"

TONE_LABELS = {"formal": "ทางการ", "friendly": "เป็นกันเอง", "brief": "สั้น"}
MODE_LABELS = {"read": "แปลเป็นไทย", "reply": "ตอบเป็นอังกฤษ", "explain": "อธิบาย", "polish": "ขัดเกลา"}


def _place_near_mouse(win: tk.Toplevel, width: int, height: int) -> None:
    win.update_idletasks()
    x, y = win.winfo_pointerxy()
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    x = max(8, min(x + 16, sw - width - 8))
    y = max(8, min(y + 16, sh - height - 48))
    win.geometry(f"{width}x{height}+{x}+{y}")


class Toast:
    """ข้อความเล็กๆ ใกล้เมาส์ หายเองใน N วินาที ไม่แย่งโฟกัส"""

    _current: "Toast | None" = None

    def __init__(self, root: tk.Tk, text: str, seconds: float = 2.5, font_size: int = 10):
        if Toast._current is not None:
            Toast._current.close()
        Toast._current = self
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg=ACCENT)
        label = tk.Label(self.win, text=text, bg=ACCENT, fg="white", font=("Segoe UI", font_size),
                         padx=12, pady=6, justify="left", wraplength=420)
        label.pack()
        self.win.update_idletasks()
        _place_near_mouse(self.win, self.win.winfo_reqwidth(), self.win.winfo_reqheight())
        if seconds > 0:
            self.win.after(int(seconds * 1000), self.close)

    def close(self) -> None:
        if Toast._current is self:
            Toast._current = None
        try:
            self.win.destroy()
        except tk.TclError:
            pass


class ResultPopup:
    """หน้าต่างผลแปล: ต้นฉบับ (เทา) + ผลลัพธ์ (ขาว) + ปุ่มก๊อป / เปลี่ยนน้ำเสียง / แปลกลับ / ปิด"""

    _current: "ResultPopup | None" = None

    def __init__(
        self,
        root: tk.Tk,
        result: Result,
        original: str,
        *,
        font_size: int = 11,
        take_focus: bool = True,
        auto_close: float = 0,
        on_retone: Callable[[str], None] | None = None,
        on_back_translate: Callable[[str], None] | None = None,
        on_copy: Callable[[str], None] | None = None,
        show_check_placeholder: bool = False,
    ):
        if ResultPopup._current is not None:
            ResultPopup._current.close()
        ResultPopup._current = self

        self.result = result
        self.on_copy = on_copy
        win = self.win = tk.Toplevel(root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=BG, highlightthickness=1, highlightbackground=ACCENT)
        font = ("Segoe UI", font_size)
        small = ("Segoe UI", max(font_size - 2, 8))

        # ---- แถบหัว (ลากย้ายได้) ----
        header = tk.Frame(win, bg=PANEL)
        header.pack(fill="x")
        title = f"{MODE_LABELS.get(result.mode, result.mode)}  ·  {result.provider} / {result.model}  ·  {result.seconds:.1f}s"
        if result.fallback_used:
            title += "  (ตัวสำรอง)"
        tk.Label(header, text=title, bg=PANEL, fg=MUTED, font=small, anchor="w", padx=10, pady=4).pack(side="left", fill="x", expand=True)
        tk.Button(header, text="✕", bg=PANEL, fg=FG, bd=0, font=small, padx=8, activebackground="#c0392b",
                  command=self.close).pack(side="right")
        for widget in (header, header.winfo_children()[0]):
            widget.bind("<ButtonPress-1>", self._drag_start)
            widget.bind("<B1-Motion>", self._drag_move)

        body = tk.Frame(win, bg=BG, padx=10, pady=8)
        body.pack(fill="both", expand=True)

        # ---- ต้นฉบับ ----
        orig = tk.Text(body, height=min(4, max(2, original.count("\n") + 1 + len(original) // 90)), wrap="word", bg=BG, fg=MUTED,
                       font=small, bd=0, padx=4, pady=2)
        orig.insert("1.0", original)
        orig.configure(state="disabled")
        orig.pack(fill="x")
        ttk.Separator(body).pack(fill="x", pady=6)

        # ---- ผลลัพธ์ ----
        lines = result.text.count("\n") + 1 + len(result.text) // 70
        self.out = tk.Text(body, height=min(14, max(2, lines)), wrap="word", bg=BG, fg=FG, font=font,
                           bd=0, padx=4, pady=2, insertbackground=FG)
        self.out.insert("1.0", result.text)
        self.out.pack(fill="both", expand=True)

        # ---- แปลกลับเพื่อเช็ก (โหมดตอบ/ขัดเกลา) ----
        self.check: tk.Text | None = None
        if result.mode in ("reply", "polish"):
            ttk.Separator(body).pack(fill="x", pady=6)
            tk.Label(body, text="ลูกค้าจะอ่านว่า (แปลกลับเพื่อเช็ก):", bg=BG, fg=MUTED, font=small, anchor="w").pack(fill="x")
            self.check = tk.Text(body, height=2, wrap="word", bg=BG, fg="#c7d2fe", font=small, bd=0, padx=4, pady=2)
            self.check.insert("1.0", "กำลังแปลกลับ..." if show_check_placeholder else "")
            self.check.configure(state="disabled")
            self.check.pack(fill="x")

        # ---- ปุ่ม ----
        bar = tk.Frame(body, bg=BG)
        bar.pack(fill="x", pady=(8, 0))
        self._button(bar, "ก๊อป", self._copy).pack(side="left")
        if result.mode in ("reply", "polish") and on_retone:
            for tone, label in TONE_LABELS.items():
                state = "disabled" if tone == result.tone else "normal"
                self._button(bar, label, lambda t=tone: on_retone(t), state=state).pack(side="left", padx=(6, 0))
        if result.mode in ("reply", "polish") and on_back_translate:
            self._button(bar, "แปลกลับเช็ก", lambda: on_back_translate(result.text)).pack(side="left", padx=(6, 0))
        self._button(bar, "ปิด", self.close).pack(side="right")

        for widget in (orig, self.out, self.check):
            if widget is not None:
                self._make_copyable(widget)

        win.bind("<Escape>", lambda _e: self.close())
        width = 520
        win.update_idletasks()
        _place_near_mouse(win, width, win.winfo_reqheight())
        if take_focus:
            win.focus_force()
            self.out.focus_set()
        if auto_close > 0:
            win.after(int(auto_close * 1000), self.close)

    def _button(self, parent, text, command, state="normal"):
        return tk.Button(parent, text=text, command=command, state=state, bg=PANEL, fg=FG, bd=0,
                         padx=10, pady=3, font=("Segoe UI", 9), activebackground=ACCENT, activeforeground="white",
                         disabledforeground="#6a6c72", cursor="hand2")

    def _copy(self) -> None:
        self._copy_text(self.out.get("1.0", "end").strip())

    def _copy_text(self, text: str) -> None:
        if not text:
            return
        if self.on_copy:
            self.on_copy(text)
        else:
            self.win.clipboard_clear()
            self.win.clipboard_append(text)

    # ---- ลากคลุม/ก๊อปข้อความในป๊อปอัปได้ทุกช่อง (ต้นฉบับ, ผลแปล, แปลกลับ) ----
    def _make_copyable(self, widget: tk.Text) -> None:
        widget.configure(cursor="xterm", selectbackground=ACCENT, selectforeground="white",
                         inactiveselectbackground=ACCENT)

        def focus(_e):
            # ช่องที่ disabled ไม่รับโฟกัสเองตอนคลิก และป๊อปอัปอาจเปิดแบบไม่แย่งโฟกัส ต้องดึงเอง
            self.win.focus_force()
            widget.focus_set()

        def on_ctrl_key(e):
            # เทียบด้วย keycode (virtual-key) เพราะตอนเปิดแป้นไทย Ctrl+C ไม่ได้ส่งตัว "c"
            if e.keycode == 0x43:  # C
                self._copy_widget(widget)
                return "break"
            if e.keycode == 0x41:  # A
                widget.tag_add("sel", "1.0", "end-1c")
                return "break"
            return None

        menu = tk.Menu(widget, tearoff=0)
        menu.add_command(label="ก๊อปส่วนที่เลือก", command=lambda: self._copy_widget(widget))
        menu.add_command(label="ก๊อปทั้งหมดในช่องนี้",
                         command=lambda: self._copy_text(widget.get("1.0", "end").strip()))
        menu.add_command(label="เลือกทั้งหมด", command=lambda: widget.tag_add("sel", "1.0", "end-1c"))

        widget.bind("<Button-1>", focus, add="+")
        widget.bind("<Control-KeyPress>", on_ctrl_key)
        widget.bind("<Button-3>", lambda e: menu.tk_popup(e.x_root, e.y_root))

    def _copy_widget(self, widget: tk.Text) -> None:
        """ก๊อปส่วนที่ลากคลุมไว้ ถ้าไม่ได้ลากคลุมก๊อปทั้งช่อง"""
        try:
            text = widget.get("sel.first", "sel.last")
        except tk.TclError:
            text = widget.get("1.0", "end")
        self._copy_text(text.strip())

    def set_check(self, text: str) -> None:
        """ใส่ผลแปลกลับ (เรียกจากเธรด tkinter)"""
        if self.check is None:
            return
        try:
            self.check.configure(state="normal")
            self.check.delete("1.0", "end")
            self.check.insert("1.0", text)
            lines = text.count("\n") + 1 + len(text) // 80
            self.check.configure(height=min(6, max(2, lines)), state="disabled")
            self.win.update_idletasks()
            self.win.geometry(f"{self.win.winfo_width()}x{self.win.winfo_reqheight()}")
        except tk.TclError:
            pass

    def _drag_start(self, event):
        self._dx, self._dy = event.x_root - self.win.winfo_x(), event.y_root - self.win.winfo_y()

    def _drag_move(self, event):
        self.win.geometry(f"+{event.x_root - self._dx}+{event.y_root - self._dy}")

    def close(self) -> None:
        if ResultPopup._current is self:
            ResultPopup._current = None
        try:
            self.win.destroy()
        except tk.TclError:
            pass
