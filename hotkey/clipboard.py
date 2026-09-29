"""จัดการ clipboard และการจำลองปุ่มกด (Windows)

ส่งปุ่มด้วย virtual-key code ผ่าน Win32 โดยตรง จึงไม่ขึ้นกับภาษาแป้นพิมพ์ที่เปิดอยู่
(ไลบรารี keyboard จะหาปุ่มตามชื่อ ซึ่งพลาดได้เมื่อสลับเป็นแป้นไทย)

หลักการก๊อป: สำรอง clipboard เดิม -> ใส่ค่าสัญลักษณ์ -> สั่ง Ctrl+C -> รอจนค่าเปลี่ยน -> คืน clipboard เดิม
"""
from __future__ import annotations

import ctypes
import time

import pyperclip

user32 = ctypes.windll.user32

VK_SHIFT, VK_CONTROL, VK_MENU, VK_LWIN, VK_RWIN = 0x10, 0x11, 0x12, 0x5B, 0x5C
VK_LSHIFT, VK_RSHIFT, VK_LCONTROL, VK_RCONTROL, VK_LMENU, VK_RMENU = 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5
VK_A, VK_C, VK_V = 0x41, 0x43, 0x56
KEYEVENTF_KEYUP = 0x0002

_SENTINEL = "​<<translator-sentinel>>​"
_MODIFIERS = (VK_SHIFT, VK_CONTROL, VK_MENU, VK_LWIN, VK_RWIN)
_ALL_MODIFIER_KEYS = (VK_LSHIFT, VK_RSHIFT, VK_LCONTROL, VK_RCONTROL, VK_LMENU, VK_RMENU, VK_LWIN, VK_RWIN)


def _is_down(vk: int) -> bool:
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def _key(vk: int, up: bool = False) -> None:
    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP if up else 0, 0)


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


def send_ctrl(vk: int) -> None:
    """กด Ctrl+<ปุ่ม> โดยใช้ virtual-key code"""
    _key(VK_CONTROL)
    time.sleep(0.01)
    _key(vk)
    time.sleep(0.02)
    _key(vk, up=True)
    time.sleep(0.01)
    _key(VK_CONTROL, up=True)


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


def _begin_capture() -> str:
    """สำรอง clipboard เดิมแล้วใส่ค่าสัญลักษณ์ไว้ตรวจว่าก๊อปสำเร็จไหม"""
    previous = _read_clipboard()
    _write_clipboard(_SENTINEL)
    return previous


def _capture(keys: list[int], attempts: int = 3, polls: int = 25) -> str:
    """ส่งชุด Ctrl+ปุ่ม แล้วอ่านสิ่งที่ถูกก๊อป (ต้องเรียก _begin_capture ก่อน)"""
    for attempt in range(attempts):  # ถ้าครั้งแรกยังว่าง (แอปยังอัปเดตการเลือกไม่ทัน) ลองซ้ำ
        for vk in keys if attempt == 0 else keys[-1:]:
            send_ctrl(vk)
            time.sleep(0.25)  # ให้แอป (โดยเฉพาะ Discord) อัปเดตการเลือกก่อนก๊อป
        for _ in range(polls):  # รอผลก๊อปสูงสุด polls x 0.03 วินาที
            time.sleep(0.03)
            current = _read_clipboard()
            if current and current != _SENTINEL:
                return current
    return ""


def copy_selection() -> str:
    """ก๊อปข้อความที่ผู้ใช้ลากคลุมไว้ แล้วคืน clipboard เดิม"""
    previous = _begin_capture()
    text = _capture([VK_C])
    _write_clipboard(previous)
    return text.strip()


def copy_selection_or_all() -> tuple[str, str, bool]:
    """ถ้ามีข้อความที่ลากคลุมอยู่ ใช้แค่ส่วนนั้น (ส่วนอื่นในช่องพิมพ์ เช่นรูป/อีโมจิ ไม่ถูกแตะ)
    ถ้าไม่ได้ลากคลุม เลือกทั้งช่องพิมพ์แทน
    คืน (ข้อความดิบ, clipboard เดิม, เป็นแค่ส่วนที่ลากคลุมไหม)
    ยังไม่คืน clipboard เพราะจะ paste ทับส่วนที่เลือกต่อ"""
    previous = _begin_capture()
    text = _capture([VK_C], attempts=1, polls=20)
    if text:
        return text, previous, True
    return _capture([VK_A, VK_C]), previous, False


def paste_replace(text: str, previous_clipboard: str) -> None:
    """วางข้อความทับสิ่งที่เลือกอยู่ แล้วคืน clipboard เดิม"""
    _write_clipboard(text)
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
