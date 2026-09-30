"""ปุ่มลัดทั่วระบบด้วย Win32 RegisterHotKey (ไม่ใช้ keyboard hook)

ทำไมไม่ใช้ไลบรารี keyboard: มันดักปุ่มด้วย low-level hook ซึ่ง Windows จะถอดทิ้งเงียบๆ
ถ้าโปรแกรมตอบ hook ช้าเกิน ~300ms ติดกันไม่กี่ครั้ง (เกิดได้ตอนกำลังแปล/เปิดป๊อปอัป)
ผลคือโปรแกรมยังเปิดอยู่ ไอคอนปกติ แต่กด F8/F9 แล้วเงียบ

RegisterHotKey ให้ Windows ส่งข้อความ WM_HOTKEY มาให้เธรดที่ลงทะเบียนโดยตรง ไม่มีหมดอายุ
ข้อแตกต่างคือปุ่มจะถูก "กิน" ไม่ส่งต่อให้โปรแกรมอื่น จึงมีกลไกส่งปุ่มต่อให้เอง (pass-through)
ตอนที่ผู้ใช้หยุดโปรแกรมชั่วคราว หรืออยู่ในโปรแกรมที่ไม่ได้เปิดใช้ปุ่มลัด
"""
from __future__ import annotations

import ctypes
import logging
import threading
import time
from ctypes import wintypes
from typing import Callable

log = logging.getLogger("hotkey.keys")

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32.RegisterHotKey.argtypes = (wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT)
user32.RegisterHotKey.restype = wintypes.BOOL
user32.UnregisterHotKey.argtypes = (wintypes.HWND, ctypes.c_int)
user32.UnregisterHotKey.restype = wintypes.BOOL
user32.GetMessageW.argtypes = (ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT)
user32.GetMessageW.restype = ctypes.c_int
user32.PostThreadMessageW.argtypes = (wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
user32.PostThreadMessageW.restype = wintypes.BOOL
kernel32.GetCurrentThreadId.restype = wintypes.DWORD

WM_QUIT, WM_HOTKEY = 0x0012, 0x0312
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000
ERROR_HOTKEY_ALREADY_REGISTERED = 1409
KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP = 0x1, 0x2

_MODIFIERS = {
    "ctrl": MOD_CONTROL, "control": MOD_CONTROL, "left ctrl": MOD_CONTROL, "right ctrl": MOD_CONTROL,
    "alt": MOD_ALT, "left alt": MOD_ALT, "right alt": MOD_ALT, "alt gr": MOD_ALT,
    "shift": MOD_SHIFT, "left shift": MOD_SHIFT, "right shift": MOD_SHIFT,
    "windows": MOD_WIN, "win": MOD_WIN, "left windows": MOD_WIN, "right windows": MOD_WIN,
}
# ชื่อปุ่มตามที่ไลบรารี keyboard ใช้ (settings_dialog อ่านชื่อจาก keyboard.read_hotkey) -> virtual-key code
_NAMED_KEYS = {
    "space": 0x20, "tab": 0x09, "enter": 0x0D, "return": 0x0D, "esc": 0x1B, "escape": 0x1B,
    "backspace": 0x08, "insert": 0x2D, "delete": 0x2E, "home": 0x24, "end": 0x23,
    "page up": 0x21, "page down": 0x22, "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
    "pause": 0x13, "caps lock": 0x14, "num lock": 0x90, "scroll lock": 0x91, "print screen": 0x2C,
    "`": 0xC0, "-": 0xBD, "=": 0xBB, "[": 0xDB, "]": 0xDD, "\\": 0xDC, ";": 0xBA, "'": 0xDE,
    ",": 0xBC, ".": 0xBE, "/": 0xBF,
}
_EXTENDED_KEYS = {0x2D, 0x2E, 0x24, 0x23, 0x21, 0x22, 0x25, 0x26, 0x27, 0x28, 0x2C}
for _n in range(1, 25):
    _NAMED_KEYS[f"f{_n}"] = 0x6F + _n


def parse_combo(combo: str) -> tuple[int, int]:
    """'shift+f8' -> (MOD_SHIFT, VK_F8)  โยน ValueError ถ้าไม่รู้จักชื่อปุ่ม"""
    parts = [p.strip().lower() for p in combo.split("+") if p.strip()]
    if not parts:
        raise ValueError("ว่าง")
    mods, key = 0, parts[-1]
    for part in parts[:-1]:
        if part not in _MODIFIERS:
            raise ValueError(f"ไม่รู้จักปุ่ม modifier '{part}'")
        mods |= _MODIFIERS[part]
    if key in _NAMED_KEYS:
        vk = _NAMED_KEYS[key]
    elif len(key) == 1 and (key.isascii() and key.isalnum()):
        vk = ord(key.upper())
    else:
        raise ValueError(f"ไม่รู้จักปุ่ม '{key}'")
    return mods, vk


def _tap_key(vk: int) -> None:
    flags = KEYEVENTF_EXTENDEDKEY if vk in _EXTENDED_KEYS else 0
    scan = user32.MapVirtualKeyW(vk, 0) if flags else 0
    user32.keybd_event(vk, scan, flags, 0)
    user32.keybd_event(vk, scan, flags | KEYEVENTF_KEYUP, 0)


class HotkeyManager:
    """ลงทะเบียนปุ่มลัดบนเธรดของตัวเอง (RegisterHotKey ผูกกับเธรด ต้องมี message loop)

    on_hotkey(mode) ถูกเรียกบนเธรดนี้ ต้องคืนเร็ว: คืน True = ใช้ปุ่มแล้ว,
    False = ไม่ใช้ (หยุดชั่วคราว/อยู่ผิดโปรแกรม) จะส่งปุ่มต่อให้โปรแกรมที่โฟกัสอยู่แทน
    """

    def __init__(self, on_hotkey: Callable[[str], bool]) -> None:
        self._on_hotkey = on_hotkey
        self._thread: threading.Thread | None = None
        self._thread_id = 0
        self.bound: list[str] = []
        self.errors: list[str] = []

    def set(self, bindings: dict[str, str]) -> None:
        """แทนที่ปุ่มลัดทั้งชุด (mode -> combo) ผลอยู่ใน .bound / .errors"""
        self.stop()
        ready = threading.Event()
        self._thread = threading.Thread(target=self._run, args=(dict(bindings), ready), daemon=True, name="hotkeys")
        self._thread.start()
        ready.wait(5)

    def stop(self) -> None:
        if self._thread is not None and self._thread.is_alive() and self._thread_id:
            user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
            self._thread.join(3)
        self._thread = None
        self._thread_id = 0

    # ---------------------------------------------------------------- เธรดปุ่มลัด
    def _run(self, bindings: dict[str, str], ready: threading.Event) -> None:
        registered: dict[int, tuple[str, int, int]] = {}
        last_pass_through: dict[int, float] = {}
        bound, errors = [], []
        try:
            for hk_id, (mode, combo) in enumerate(bindings.items(), start=1):
                try:
                    mods, vk = parse_combo(combo)
                except ValueError as e:
                    errors.append(f"{combo} ({mode}): {e}")
                    continue
                if user32.RegisterHotKey(None, hk_id, mods | MOD_NOREPEAT, vk):
                    registered[hk_id] = (mode, mods, vk)
                    bound.append(f"{combo} = {mode}")
                else:
                    err = ctypes.get_last_error()
                    reason = "โปรแกรมอื่นจองปุ่มนี้ไว้แล้ว" if err == ERROR_HOTKEY_ALREADY_REGISTERED else f"error {err}"
                    errors.append(f"{combo} ({mode}): {reason}")
            self.bound, self.errors = bound, errors
            self._thread_id = kernel32.GetCurrentThreadId()
            ready.set()

            msg = wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message != WM_HOTKEY or msg.wParam not in registered:
                    continue
                mode, mods, vk = registered[msg.wParam]
                if time.monotonic() - last_pass_through.get(msg.wParam, 0) < 0.3:
                    continue  # ปุ่มที่เราเพิ่งส่งต่อเองย้อนกลับมา ไม่งั้นจะวนไม่รู้จบ
                try:
                    consumed = self._on_hotkey(mode)
                except Exception:  # noqa: BLE001
                    log.exception("hotkey handler failed")
                    consumed = True
                if not consumed:
                    self._pass_through(msg.wParam, mods, vk)
                    last_pass_through[msg.wParam] = time.monotonic()
        finally:
            for hk_id in registered:
                user32.UnregisterHotKey(None, hk_id)
            ready.set()

    def _pass_through(self, hk_id: int, mods: int, vk: int) -> None:
        """ส่งปุ่มต่อให้โปรแกรมที่โฟกัสอยู่: ถอนการจองชั่วคราว กดปุ่มซ้ำ แล้วจองใหม่
        (modifier เช่น Shift ผู้ใช้ยังกดค้างอยู่จริง จึงส่งแค่ตัวปุ่มหลัก)"""
        user32.UnregisterHotKey(None, hk_id)
        _tap_key(vk)
        time.sleep(0.05)  # ให้ Windows ส่งปุ่มที่จำลองไปถึงโปรแกรมปลายทางก่อนค่อยจองใหม่
        if not user32.RegisterHotKey(None, hk_id, mods | MOD_NOREPEAT, vk):
            log.error("จองปุ่มลัดกลับไม่ได้หลังส่งต่อ (id=%s vk=%#x) error=%s", hk_id, vk, ctypes.get_last_error())
