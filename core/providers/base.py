"""อินเทอร์เฟซกลางของผู้ให้บริการแปล"""
from __future__ import annotations

import threading
from typing import Callable

from core.config import Config


class ProviderError(Exception):
    """ผู้ให้บริการตอบไม่ได้ (ไม่ได้ล็อกอิน, โควต้าหมด, เน็ตล่ม ฯลฯ) -> ให้ลองตัวถัดไป"""


class ProviderCancelled(ProviderError):
    """ถูกสั่งยกเลิกกลางทาง (อีกเจ้าตอบก่อนแล้ว) ไม่ใช่ความผิดพลาด"""


class Provider:
    name = "base"

    def __init__(self, config: Config):
        self.config = config
        self.cfg = config.provider_cfg(self.name)

    def available(self) -> bool:
        """เช็กเบื้องต้นว่ามีสิ่งที่ต้องใช้ครบไหม (คีย์, ไบนารี) ยังไม่ยิงจริง"""
        return True

    def complete(self, system: str, user: str, model_alias: str) -> str:
        raise NotImplementedError

    def stream(
        self,
        system: str,
        user: str,
        model_alias: str,
        on_delta: Callable[[str], None] | None = None,
        cancel: threading.Event | None = None,
    ) -> str:
        """แปลแบบทยอยส่งข้อความผ่าน on_delta ระหว่างทาง แล้วคืนข้อความเต็มตอนจบ

        ค่าเริ่มต้นสำหรับผู้ให้บริการที่ยังไม่รองรับ stream: รอ complete() จบแล้วส่งทั้งก้อนทีเดียว
        cancel = Event ที่ถ้าถูก set ให้หยุดทำงานแล้วโยน ProviderCancelled
        """
        text = self.complete(system, user, model_alias)
        if cancel is not None and cancel.is_set():
            raise ProviderCancelled("ยกเลิก")
        if on_delta is not None:
            on_delta(text)
        return text
