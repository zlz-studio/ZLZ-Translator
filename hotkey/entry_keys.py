"""ให้ช่องกรอกของ tkinter รับ Ctrl+V / Ctrl+C / Ctrl+X / Ctrl+A ได้แม้แป้นพิมพ์กำลังเป็นภาษาไทย

tkinter ผูก <<Paste>> ไว้กับ keysym "v" ซึ่งตอนแป้นไทยกด Ctrl+V จะได้ตัว "อ" ไม่ใช่ "v" จึงไม่วาง
ที่นี่เทียบด้วย keycode (virtual-key ของ Windows) ที่ไม่ขึ้นกับภาษา และเพิ่มเมนูคลิกขวา
วาง / ก๊อป / เลือกทั้งหมด กับฟังก์ชัน paste() ไว้ผูกกับปุ่ม "วาง" สำหรับคนที่ไม่ถนัดคีย์ลัด
"""
from __future__ import annotations

import tkinter as tk

_VK_V, _VK_C, _VK_X, _VK_A = 0x56, 0x43, 0x58, 0x41


def _enabled(entry: tk.Entry) -> bool:
    return str(entry.cget("state")) != "disabled"


def _selected_range(entry: tk.Entry) -> tuple[int, int] | None:
    try:
        if entry.selection_present():
            return entry.index("sel.first"), entry.index("sel.last")
    except tk.TclError:
        pass
    return None


def paste(entry: tk.Entry) -> None:
    """วางข้อความจากคลิปบอร์ดแทนที่ส่วนที่เลือก (ตัดขึ้นบรรทัดใหม่/ช่องว่างหัวท้ายออก เพราะเป็นคีย์หรือโค้ด)"""
    if not _enabled(entry):
        return
    try:
        text = entry.clipboard_get()
    except tk.TclError:
        return
    text = text.replace("\r", "").replace("\n", "").strip()
    if not text:
        return
    rng = _selected_range(entry)
    if rng:
        entry.delete(*rng)
    entry.insert("insert", text)
    entry.focus_set()


def copy(entry: tk.Entry, cut: bool = False) -> None:
    """ก๊อปข้อความจริง (ไม่ใช่จุด • ที่แสดง) ของส่วนที่เลือก หรือทั้งช่องถ้าไม่ได้เลือก"""
    rng = _selected_range(entry)
    text = entry.get()[rng[0]:rng[1]] if rng else entry.get()
    if not text:
        return
    entry.clipboard_clear()
    entry.clipboard_append(text)
    if cut and rng and _enabled(entry):
        entry.delete(*rng)


def select_all(entry: tk.Entry) -> None:
    entry.selection_range(0, "end")
    entry.icursor("end")


def install(entry: tk.Entry) -> None:
    """ผูกคีย์ลัดแบบไม่ขึ้นกับภาษาแป้นพิมพ์ และเมนูคลิกขวาให้ช่องกรอกนี้"""

    def on_ctrl(e: tk.Event) -> str | None:
        if e.keycode == _VK_V:
            paste(entry)
        elif e.keycode == _VK_C:
            copy(entry)
        elif e.keycode == _VK_X:
            copy(entry, cut=True)
        elif e.keycode == _VK_A:
            select_all(entry)
        else:
            return None
        return "break"  # กันไม่ให้ tkinter วางซ้ำอีกรอบตอนแป้นเป็นอังกฤษ

    entry.bind("<Control-KeyPress>", on_ctrl)

    menu = tk.Menu(entry, tearoff=0)
    menu.add_command(label="วาง", command=lambda: paste(entry))
    menu.add_command(label="ก๊อป", command=lambda: copy(entry))
    menu.add_command(label="เลือกทั้งหมด", command=lambda: select_all(entry))

    def on_right_click(e: tk.Event) -> str:
        entry.focus_set()
        menu.tk_popup(e.x_root, e.y_root)
        return "break"

    entry.bind("<Button-3>", on_right_click)
