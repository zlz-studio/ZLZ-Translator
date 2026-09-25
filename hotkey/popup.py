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
CHECK_FG = "#c7d2fe"

TONE_LABELS = {"formal": "ทางการ", "friendly": "เป็นกันเอง", "brief": "สั้น"}
MODE_LABELS = {"read": "แปลเป็นไทย", "reply": "ตอบเป็นอังกฤษ", "explain": "อธิบาย", "polish": "ขัดเกลา"}
SECTION_LABELS = {"orig": "ต้นฉบับ", "out": "ผลลัพธ์", "check": "ลูกค้าจะอ่านว่า (แปลกลับเพื่อเช็ก)"}

NORMAL_WIDTH = 560
# พื้นที่ที่ป๊อปอัปขนาดปกติใช้ได้สูงสุด (สัดส่วนของความสูงจอ) เกินนี้ค่อยมี scrollbar
NORMAL_SCREEN_SHARE = 0.85
# ความสูงส่วนที่ไม่ใช่ข้อความ (หัวป๊อปอัป, หัวข้อ 3 อัน, เส้นคั่น, ปุ่ม, ระยะขอบ) ใช้หักออกจากพื้นที่จอ
CHROME_PX = 230


def _needed_lines(text: str, chars_per_line: int) -> int:
    """จำนวนบรรทัดที่ต้องใช้แสดงข้อความทั้งหมด (นับการตัดคำโดยประมาณ)"""
    return sum(1 + len(line) // chars_per_line for line in text.rstrip("\n").split("\n")) or 1


def _allocate_lines(need: dict[str, int], line_px: dict[str, int], budget_px: int) -> dict[str, int]:
    """แบ่งบรรทัดให้แต่ละส่วน: ถ้าพอใส่ได้ทั้งหมดก็ให้เต็ม ถ้าไม่พอลดตามสัดส่วน (ขั้นต่ำ 3 บรรทัด)"""
    total = sum(need[k] * line_px[k] for k in need)
    if total <= budget_px:
        return dict(need)
    scale = budget_px / total
    return {k: max(3, int(need[k] * scale)) for k in need}


def _place_near_mouse(win: tk.Toplevel, width: int, height: int) -> None:
    win.update_idletasks()
    x, y = win.winfo_pointerxy()
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    x = max(8, min(x + 16, sw - width - 8))
    y = max(8, min(y + 16, sh - height - 48))
    win.geometry(f"{width}x{height}+{x}+{y}")


def _height_for(text: str, cap: int, chars_per_line: int = 70) -> int:
    lines = sum(1 + len(line) // chars_per_line for line in text.rstrip("\n").split("\n"))
    return min(cap, max(2, lines))


def _title_for(result: Result, pending: bool) -> str:
    if pending:
        return f"{MODE_LABELS.get(result.mode, result.mode)}  ·  กำลังแปล..."
    title = f"{MODE_LABELS.get(result.mode, result.mode)}  ·  {result.provider} / {result.model}  ·  {result.seconds:.1f}s"
    if result.fallback_used:
        title += "  (ตัวสำรอง)"
    return title


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
    """หน้าต่างผลแปล: ต้นฉบับ (เทา) + ผลลัพธ์ (ขาว) + แปลกลับ (ฟ้า) + ปุ่มก๊อป / น้ำเสียง / แปลกลับ / ปิด

    - ทุกส่วนมี scrollbar เมื่อยาวเกิน และคลิกหัวข้อเพื่อพับเก็บ/ขยาย
    - ปุ่ม ⛶ (หรือ F11) สลับเต็มจอ ให้ทุกส่วนมีที่พอแสดงข้อความยาว ๆ
    - ความสูงแต่ละส่วนคิดจากพื้นที่จอจริง: ถ้าข้อความยาวแต่ยังพอใส่ในจอได้ จะโชว์ครบไม่ต้องเลื่อน
    - สถานะเต็มจอถูกจำไว้ตลอดที่โปรแกรมเปิดอยู่ ส่วนการพับเป็นของป๊อปอัปนั้น ๆ (ป๊อปอัปใหม่เปิดครบทุกส่วนเสมอ)
    - เปิดแบบ pending=True ได้ตั้งแต่ยังไม่มีผล แล้ว append_text() ทีละส่วน จบด้วย finish(result)
    """

    _current: "ResultPopup | None" = None
    _maximized: bool = False

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
        pending: bool = False,
        stream_id: object | None = None,
    ):
        if ResultPopup._current is not None:
            ResultPopup._current.close()
        ResultPopup._current = self

        self.result = result
        self.pending = pending
        self.stream_id = stream_id
        self.on_copy = on_copy
        self.auto_close = auto_close
        self.font_size = font_size
        self._collapsed: dict[str, bool] = {"orig": False, "out": False, "check": False}
        win = self.win = tk.Toplevel(root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=BG, highlightthickness=1, highlightbackground=ACCENT)
        self.font = ("Segoe UI", font_size)
        self.small = ("Segoe UI", max(font_size - 2, 8))

        # ---- แถบหัว (ลากย้ายได้) ----
        header = tk.Frame(win, bg=PANEL)
        header.pack(fill="x")
        self._title = tk.Label(header, text=_title_for(result, pending), bg=PANEL, fg=MUTED, font=self.small,
                               anchor="w", padx=10, pady=4)
        self._title.pack(side="left", fill="x", expand=True)
        tk.Button(header, text="✕", bg=PANEL, fg=FG, bd=0, font=self.small, padx=8, activebackground="#c0392b",
                  command=self.close).pack(side="right")
        self._btn_max = tk.Button(header, text="⛶", bg=PANEL, fg=FG, bd=0, font=self.small, padx=8,
                                  activebackground=ACCENT, command=self._toggle_max)
        self._btn_max.pack(side="right")
        for widget in (header, self._title):
            widget.bind("<ButtonPress-1>", self._drag_start)
            widget.bind("<B1-Motion>", self._drag_move)

        self.body = tk.Frame(win, bg=BG, padx=10, pady=8)
        self.body.pack(fill="both", expand=True)

        # ---- สามส่วน (สร้างครั้งเดียว จัดวางใหม่ได้ใน _apply_layout) ----
        self._sections: dict[str, dict] = {}
        self._add_section("orig", original, fg=MUTED, font=self.small, editable=False)
        self._add_section("out", result.text, fg=FG, font=self.font, editable=True)
        self.check: tk.Text | None = None
        if result.mode in ("reply", "polish"):
            self._add_section("check", "กำลังแปลกลับ..." if show_check_placeholder else "",
                              fg=CHECK_FG, font=self.small, editable=False)
            self.check = self._sections["check"]["text"]
        self.out: tk.Text = self._sections["out"]["text"]
        self._seps = [ttk.Separator(self.body) for _ in range(len(self._sections) - 1)]

        # ---- ปุ่ม ----
        self.bar = tk.Frame(self.body, bg=BG)
        self._button(self.bar, "ก๊อป", self._copy).pack(side="left")
        if result.mode in ("reply", "polish") and on_retone:
            for tone, label in TONE_LABELS.items():
                state = "disabled" if tone == result.tone else "normal"
                self._button(self.bar, label, lambda t=tone: on_retone(t), state=state).pack(side="left", padx=(6, 0))
        if result.mode in ("reply", "polish") and on_back_translate:
            self._button(self.bar, "แปลกลับเช็ก", lambda: on_back_translate(self.result.text)).pack(side="left", padx=(6, 0))
        self._button(self.bar, "ปิด", self.close).pack(side="right")

        win.bind("<Escape>", lambda _e: self.close())
        win.bind("<F11>", lambda _e: self._toggle_max())

        self._placed = False
        self._apply_layout()
        if take_focus:
            win.focus_force()
            self.out.focus_set()
        if auto_close > 0 and not pending:
            win.after(int(auto_close * 1000), self.close)

    # ---------------------------------------------------------------- สร้างส่วน
    def _add_section(self, key: str, text: str, *, fg: str, font, editable: bool) -> None:
        holder = tk.Frame(self.body, bg=BG)
        title = tk.Label(holder, bg=BG, fg=MUTED, font=self.small, anchor="w", cursor="hand2")
        title.pack(fill="x")
        title.bind("<Button-1>", lambda _e, k=key: self._toggle(k))
        area = tk.Frame(holder, bg=BG)
        txt = tk.Text(area, wrap="word", bg=BG, fg=fg, font=font, bd=0, padx=4, pady=2, insertbackground=FG, height=2)
        sb = ttk.Scrollbar(area, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=lambda first, last, s=sb: self._scrollbar_auto(s, first, last))
        txt.insert("1.0", text)
        if not editable:
            txt.configure(state="disabled")
        txt.pack(side="left", fill="both", expand=True)
        self._sections[key] = {"holder": holder, "area": area, "text": txt, "title": title, "scrollbar": sb}

    @staticmethod
    def _scrollbar_auto(sb: ttk.Scrollbar, first: str, last: str) -> None:
        """โชว์ scrollbar เฉพาะตอนข้อความยาวเกินช่อง"""
        sb.set(first, last)
        try:
            if float(first) <= 0.0 and float(last) >= 1.0:
                sb.pack_forget()
            elif not sb.winfo_ismapped():
                sb.pack(side="right", fill="y")
        except tk.TclError:
            pass

    def _set_text(self, key: str, text: str) -> None:
        txt = self._sections[key]["text"]
        editable = str(txt.cget("state")) == "normal"
        txt.configure(state="normal")
        txt.delete("1.0", "end")
        txt.insert("1.0", text)
        if not editable:
            txt.configure(state="disabled")

    # ---------------------------------------------------------------- จัดวาง
    def _section_heights(self, keys: list[str]) -> dict[str, int]:
        """ความสูง (บรรทัด) ของแต่ละส่วนที่เปิดอยู่ ให้ทุกส่วนโชว์ครบถ้าจอพอ ไม่งั้นลดตามสัดส่วน"""
        maximized = ResultPopup._maximized
        sh = self.win.winfo_screenheight()
        budget_px = (sh - 80 if maximized else int(sh * NORMAL_SCREEN_SHARE)) - CHROME_PX
        width_px = (self.win.winfo_screenwidth() - 40) if maximized else NORMAL_WIDTH
        need: dict[str, int] = {}
        line_px: dict[str, int] = {}
        for key in keys:
            size = self.font_size if key == "out" else max(self.font_size - 2, 8)
            chars_per_line = max(20, int(width_px / (size * 0.75)))  # ความกว้างตัวอักษรโดยประมาณ
            need[key] = _needed_lines(self._sections[key]["text"].get("1.0", "end"), chars_per_line)
            line_px[key] = int(size * 2.0)
        return _allocate_lines(need, line_px, budget_px)

    def _apply_layout(self) -> None:
        """จัดวางทุกส่วนใหม่ตามสถานะพับ/เต็มจอ แล้วปรับขนาดหน้าต่าง"""
        for child in self.body.winfo_children():
            child.pack_forget()
        keys = [k for k in ("orig", "out", "check") if k in self._sections]
        open_keys = [k for k in keys if not self._collapsed.get(k, False)]
        heights = self._section_heights(open_keys)
        for i, key in enumerate(keys):
            s = self._sections[key]
            collapsed = key not in open_keys
            s["title"].configure(
                text=("▸  " if collapsed else "▾  ") + SECTION_LABELS[key] + ("   (คลิกเพื่อขยาย)" if collapsed else ""),
                fg=ACCENT if collapsed else MUTED,
            )
            # ปกติให้ผลลัพธ์รับพื้นที่ที่เหลือ ส่วนเต็มจอแบ่งพื้นที่ให้ทุกส่วนที่เปิดอยู่
            expand = not collapsed and (key == "out" or ResultPopup._maximized)
            s["holder"].pack(fill="both", expand=expand)
            if collapsed:
                s["area"].pack_forget()
            else:
                s["text"].configure(height=max(2, heights[key]))
                s["area"].pack(fill="both", expand=True)
            if i < len(self._seps):
                self._seps[i].pack(fill="x", pady=6)
        self.bar.pack(fill="x", pady=(8, 0))
        self._btn_max.configure(text="🗗" if ResultPopup._maximized else "⛶")
        self._fit()

    def _fit(self) -> None:
        """ปรับขนาด/ตำแหน่งหน้าต่าง: เต็มจอ หรือกว้างคงที่สูงตามเนื้อหา (ไม่ให้ล้นขอบล่างจอ)"""
        win = self.win
        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        if ResultPopup._maximized:
            win.geometry(f"{sw - 16}x{sh - 80}+8+8")
            self._placed = True
            return
        height = win.winfo_reqheight()
        if not self._placed:
            _place_near_mouse(win, NORMAL_WIDTH, height)
            self._placed = True
            return
        x, y = win.winfo_x(), win.winfo_y()
        limit = sh - 48
        if y + height > limit:
            y = max(8, limit - height)
        if x + NORMAL_WIDTH > sw - 8:
            x = max(8, sw - 8 - NORMAL_WIDTH)
        win.geometry(f"{NORMAL_WIDTH}x{height}+{x}+{y}")

    def _toggle(self, key: str) -> None:
        self._collapsed[key] = not self._collapsed.get(key, False)
        self._apply_layout()

    def _toggle_max(self) -> None:
        ResultPopup._maximized = not ResultPopup._maximized
        if not ResultPopup._maximized:
            self._placed = False  # กลับมาขนาดปกติ วางใกล้เมาส์ใหม่
        self._apply_layout()

    def _button(self, parent, text, command, state="normal"):
        return tk.Button(parent, text=text, command=command, state=state, bg=PANEL, fg=FG, bd=0,
                         padx=10, pady=3, font=("Segoe UI", 9), activebackground=ACCENT, activeforeground="white",
                         disabledforeground="#6a6c72", cursor="hand2")

    def _copy(self) -> None:
        text = self.out.get("1.0", "end").strip()
        if self.on_copy:
            self.on_copy(text)

    # ---------------------------------------------------------------- streaming
    def append_text(self, delta: str) -> None:
        """เติมข้อความต่อท้าย (เรียกจากเธรด tkinter) ขยายช่องตามเมื่อยาวขึ้น"""
        try:
            self.out.insert("end", delta)
            self.out.see("end")
            # จัดวางใหม่เฉพาะตอนจำนวนบรรทัดเปลี่ยน (ไม่ทำทุก delta จะได้ไม่กระตุก)
            lines = int(self.out.index("end-1c").split(".")[0])
            if lines != getattr(self, "_last_lines", None):
                self._last_lines = lines
                self._apply_layout()
        except tk.TclError:
            pass

    def reset_text(self) -> None:
        """ล้างข้อความที่ทยอยมา (ตัวแปลแรกล้มกลางทาง กำลังเปลี่ยนตัว)"""
        try:
            self._set_text("out", "")
            self._apply_layout()
        except tk.TclError:
            pass

    def finish(self, result: Result) -> None:
        """ใส่ผลสุดท้าย: ข้อความเต็ม + หัวข้อ (ตัวแปล/รุ่น/เวลา)"""
        self.result = result
        self.pending = False
        try:
            self._title.configure(text=_title_for(result, False))
            self._set_text("out", result.text)
            self._apply_layout()
            if self.auto_close > 0:
                self.win.after(int(self.auto_close * 1000), self.close)
        except tk.TclError:
            pass

    def set_check(self, text: str) -> None:
        """ใส่ผลแปลกลับ (เรียกจากเธรด tkinter)"""
        if self.check is None:
            return
        try:
            self._set_text("check", text)
            self._apply_layout()
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
