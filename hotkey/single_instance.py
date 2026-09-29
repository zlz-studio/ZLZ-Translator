"""ให้โปรแกรม hotkey เปิดได้ทีละตัว (Windows)

ถ้าเปิดตัวใหม่ตอนที่ตัวเก่ายังอยู่ ตัวใหม่จะสั่งตัวเก่าให้ปิดตัวเองแล้วทำงานแทน
จึงได้โค้ด/การตั้งค่าล่าสุดเสมอ และไม่มีสองตัวแย่งกันรับปุ่มลัด (กด F9 ครั้งเดียวแต่ทำงานสองรอบ)

ใช้ named mutex บอกว่า "มีตัวที่ทำงานอยู่" และ named event เป็นสัญญาณ "ตัวเก่าปิดได้แล้ว"
ชื่ออยู่ใน namespace Local\\ จึงแยกตามผู้ใช้ที่ล็อกอิน และใช้ร่วมกันทั้งตัว .exe และรันจากซอร์ส
"""
from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes
from typing import Callable

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
kernel32.CreateMutexW.restype = wintypes.HANDLE
kernel32.CreateEventW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR)
kernel32.CreateEventW.restype = wintypes.HANDLE
kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
kernel32.WaitForSingleObject.restype = wintypes.DWORD
for _fn in ("SetEvent", "ResetEvent", "ReleaseMutex", "CloseHandle"):
    getattr(kernel32, _fn).argtypes = (wintypes.HANDLE,)
    getattr(kernel32, _fn).restype = wintypes.BOOL

_MUTEX_NAME = "Local\\ZLZTranslator.Hotkey.Instance"
_QUIT_EVENT_NAME = "Local\\ZLZTranslator.Hotkey.Quit"
WAIT_OBJECT_0, WAIT_ABANDONED = 0x0, 0x80
INFINITE = 0xFFFFFFFF


class SingleInstance:
    def __init__(self) -> None:
        self._mutex = None
        self._event = None
        self._owned = False
        self.replaced_previous = False

    def acquire(self, timeout: float = 15.0) -> bool:
        """เป็นตัวที่ทำงานอยู่ตัวเดียว ถ้ามีตัวเก่า สั่งให้ปิดแล้วรอ
        คืน False ถ้าตัวเก่าไม่ยอมปิดภายในเวลาที่กำหนด (ต้องเรียกบนเธรดหลัก เพราะ mutex ผูกกับเธรดที่ถือ)"""
        self._event = kernel32.CreateEventW(None, True, False, _QUIT_EVENT_NAME)  # manual-reset
        self._mutex = kernel32.CreateMutexW(None, False, _MUTEX_NAME)
        if not self._event or not self._mutex:
            return True  # สร้างไม่ได้ (ไม่น่าเกิด) อย่าขวางการเปิดโปรแกรม

        if kernel32.WaitForSingleObject(self._mutex, 0) not in (WAIT_OBJECT_0, WAIT_ABANDONED):
            # มีตัวเก่าถืออยู่: ส่งสัญญาณให้ปิด แล้วรอจนตัวเก่าปล่อย (ตัวเก่าต้องปิด Discord app ลูกก่อน อาจใช้หลายวินาที)
            kernel32.SetEvent(self._event)
            result = kernel32.WaitForSingleObject(self._mutex, int(timeout * 1000))
            if result not in (WAIT_OBJECT_0, WAIT_ABANDONED):
                kernel32.ResetEvent(self._event)
                return False
            self.replaced_previous = True
        kernel32.ResetEvent(self._event)  # ล้างสัญญาณ ไม่งั้นตัวเราเองจะเห็นแล้วปิดตาม
        self._owned = True
        return True

    def watch(self, on_quit_requested: Callable[[], None]) -> None:
        """เรียก on_quit_requested (จากเธรดเบื้องหลัง) เมื่อมีตัวใหม่เปิดขึ้นมาและขอให้เราปิด"""
        if not self._event:
            return

        def run() -> None:
            if kernel32.WaitForSingleObject(self._event, INFINITE) == WAIT_OBJECT_0:
                on_quit_requested()

        threading.Thread(target=run, daemon=True, name="single-instance").start()

    def release(self) -> None:
        """ปล่อย mutex ให้ตัวใหม่ทำงานต่อ (เรียกหลังเลิกดักปุ่มลัดและปิด tray แล้ว)"""
        if self._owned and self._mutex:
            kernel32.ReleaseMutex(self._mutex)
            self._owned = False
