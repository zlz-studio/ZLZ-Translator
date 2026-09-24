"""จัดการ clipboard และการจำลองปุ่มกด (Windows)

ส่งปุ่มด้วย virtual-key code ผ่าน Win32 โดยตรง จึงไม่ขึ้นกับภาษาแป้นพิมพ์ที่เปิดอยู่
(ไลบรารี keyboard จะหาปุ่มตามชื่อ ซึ่งพลาดได้เมื่อสลับเป็นแป้นไทย)

หลักการก๊อป: สำรอง clipboard เดิม -> ใส่ค่าสัญลักษณ์ -> สั่ง Ctrl+C -> รอจนค่าเปลี่ยน -> คืน clipboard เดิม
"""
from __future__ import annotations

import ctypes
import time
from typing import Callable

import pyperclip

user32 = ctypes.windll.user32

VK_SHIFT, VK_CONTROL, VK_MENU, VK_LWIN, VK_RWIN = 0x10, 0x11, 0x12, 0x5B, 0x5C
VK_LSHIFT, VK_RSHIFT, VK_LCONTROL, VK_RCONTROL, VK_LMENU, VK_RMENU = 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5
VK_A, VK_C, VK_V = 0x41, 0x43, 0x56
VK_HOME, VK_END = 0x24, 0x23
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
MAPVK_VK_TO_VSC = 0

# ปุ่มนำทาง (Home/End) บนคีย์บอร์ดจริงเป็น extended key ต้องส่งแฟล็กและ scan code ให้ครบ
# ไม่งั้นบางแอป (โดยเฉพาะ Chromium/Electron อย่าง Discord) อาจไม่รู้จักปุ่ม
_EXTENDED_KEYS = {VK_HOME, VK_END}

_SENTINEL = "​<<translator-sentinel>>​"
_MODIFIERS = (VK_SHIFT, VK_CONTROL, VK_MENU, VK_LWIN, VK_RWIN)
_ALL_MODIFIER_KEYS = (VK_LSHIFT, VK_RSHIFT, VK_LCONTROL, VK_RCONTROL, VK_LMENU, VK_RMENU, VK_LWIN, VK_RWIN)


def _is_down(vk: int) -> bool:
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def _key(vk: int, up: bool = False) -> None:
    flags = KEYEVENTF_KEYUP if up else 0
    scan = 0
    if vk in _EXTENDED_KEYS:
        flags |= KEYEVENTF_EXTENDEDKEY
        scan = user32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC)
    user32.keybd_event(vk, scan, flags, 0)


def wait_modifiers_released(timeout: float = 2.0) -> None:
    """รอให้ผู้ใช้ปล่อยปุ่ม Ctrl/Alt/Shift ที่กดเรียก hotkey ก่อน"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not any(_is_down(vk) for vk in _MODIFIERS):
            break
        time.sleep(0.02)
    # เผื่อระบบยังคิดว่ามีปุ่มค้าง ส่ง key-up ให้ทุก modifier
    for vk in _ALL_MODIFIER_KEYS:
        _key(vk, up=True)
    time.sleep(0.05)


def send_combo(*vks: int) -> None:
    """กดปุ่มชุดพร้อมกัน เช่น send_combo(VK_CONTROL, VK_SHIFT, VK_HOME) กดตามลำดับ ปล่อยย้อนลำดับ"""
    for vk in vks:
        _key(vk)
        time.sleep(0.01)
    time.sleep(0.02)
    for vk in reversed(vks):
        _key(vk, up=True)
        time.sleep(0.01)


def send_ctrl(vk: int) -> None:
    """กด Ctrl+<ปุ่ม> โดยใช้ virtual-key code"""
    send_combo(VK_CONTROL, vk)


def _read_clipboard() -> str:
    try:
        return pyperclip.paste() or ""
    except pyperclip.PyperclipException:
        return ""


def _write_clipboard(text: str) -> None:
    for _ in range(5):
        try:
            pyperclip.copy(text)
            return
        except pyperclip.PyperclipException:
            time.sleep(0.05)


def _capture(select: Callable[[], None] | None = None) -> tuple[str, str]:
    """(เลือกข้อความด้วย select ถ้ามี) แล้ว Ctrl+C อ่านสิ่งที่ถูกก๊อป คืน (ข้อความที่ได้, clipboard เดิม)"""
    previous = _read_clipboard()
    _write_clipboard(_SENTINEL)
    captured = ""
    for attempt in range(3):  # ถ้าครั้งแรกยังว่าง (แอปยังอัปเดตการเลือกไม่ทัน) ลองซ้ำเฉพาะ Ctrl+C
        if attempt == 0 and select is not None:
            select()
            time.sleep(0.25)  # ให้แอป (โดยเฉพาะ Discord) อัปเดตการเลือกก่อนก๊อป
        send_ctrl(VK_C)
        time.sleep(0.25)
        for _ in range(25):  # รอผลก๊อปสูงสุด ~0.75 วินาที
            time.sleep(0.03)
            current = _read_clipboard()
            if current and current != _SENTINEL:
                captured = current
                break
        if captured:
            break
    return captured, previous


def select_field() -> None:
    """เลือกข้อความทั้งหมด "เฉพาะในช่องพิมพ์ที่โฟกัสอยู่": Ctrl+End ไปท้ายสุด แล้ว Ctrl+Shift+Home ลากถึงต้น

    ไม่ใช้ Ctrl+A เพราะถ้าโฟกัสไม่ได้อยู่ในช่องพิมพ์ (เช่น อยู่ที่หน้าแชท Discord)
    Ctrl+A จะไปเลือกข้อความทั้งหน้าจอค้างไว้ ส่วนปุ่มชุดนี้นอกช่องพิมพ์จะไม่เลือกอะไรเลย
    """
    send_combo(VK_CONTROL, VK_END)
    time.sleep(0.03)
    send_combo(VK_CONTROL, VK_SHIFT, VK_HOME)


def deselect() -> None:
    """ยกเลิกการเลือกโดยไม่แตะข้อความ (Ctrl+End = ย้ายเคอร์เซอร์ไปท้ายสุด การเลือกหลุดเอง)

    สำคัญกับโหมด reply/polish: เดิมข้อความถูกเลือกค้างไว้ตลอดช่วงรอแปล 5-10 วินาที
    ถ้าผู้ใช้เผลอพิมพ์อะไรระหว่างนั้น ดราฟต์ทั้งหมดจะถูกแทนที่ทันที
    """
    send_combo(VK_CONTROL, VK_END)


def copy_selection() -> str:
    """ก๊อปข้อความที่ผู้ใช้ลากคลุมไว้ แล้วคืน clipboard เดิม"""
    text, previous = _capture()
    _write_clipboard(previous)
    return text.strip()


def select_all_and_copy() -> tuple[str, str]:
    """เลือกทั้งช่องพิมพ์แล้วก๊อป จากนั้นยกเลิกการเลือกทันที

    ไม่ปล่อยให้เลือกค้างระหว่างรอแปล เพราะถ้าแปลล้มเหลวหรือผู้ใช้เผลอพิมพ์
    ข้อความจะหายทั้งก้อน ตอนจะวางทับค่อยเลือกใหม่ใน paste_replace()
    """
    text, previous = _capture(select_field)
    deselect()
    return text.strip(), previous


def paste_replace(text: str, previous_clipboard: str) -> None:
    """เลือกทั้งช่องพิมพ์ใหม่แล้ววางทับ จากนั้นคืน clipboard เดิม"""
    _write_clipboard(text)
    time.sleep(0.08)
    select_field()  # เลือกใหม่ตรงนี้ เพราะ select_all_and_copy() ยกเลิกการเลือกไปแล้ว
    time.sleep(0.08)
    send_ctrl(VK_V)
    time.sleep(0.4)
    _write_clipboard(previous_clipboard)


def restore_clipboard(previous_clipboard: str) -> None:
    _write_clipboard(previous_clipboard)


def foreground_window_title() -> str:
    hwnd = user32.GetForegroundWindow()
    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value
