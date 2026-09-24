"""ตัวเชื่อม Google Gemini API (มีโควต้าฟรี) ผ่าน REST ไม่ต้องติดตั้งไลบรารีเพิ่ม"""
from __future__ import annotations

import json
import logging
import threading
import time
import urllib.error
import urllib.request
from typing import Callable

from core.providers.base import Provider, ProviderCancelled, ProviderError

# ใช้ endpoint แบบ stream (SSE) เสมอ จะได้ทยอยส่งข้อความให้ป๊อปอัปตั้งแต่คำแรก
_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse"

log = logging.getLogger("gemini")

# Gemini มักตอบ 503 (คนใช้เยอะ) เป็นช่วง ๆ ลองใหม่สักครั้งสองครั้งมักผ่าน
_RETRY_CODES = {429, 500, 502, 503, 504}

# ถ้าเซิร์ฟเวอร์บอกให้รอนานกว่านี้ (เช่น โควต้ารายวันหมด) รอไปก็ไม่หาย
# ไปใช้ตัวสำรองเลยดีกว่า จะได้ไม่ถ่วงทุกการแปล
_MAX_RETRY_WAIT = 5.0


def _server_retry_delay(detail: str) -> float | None:
    """อ่าน retryDelay ที่ Gemini แนบมา (เช่น "54s") คืน None ถ้าไม่มี"""
    try:
        for d in json.loads(detail).get("error", {}).get("details", []):
            delay = d.get("retryDelay")
            if delay:
                return float(str(delay).rstrip("s"))
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return None


class GeminiProvider(Provider):
    name = "gemini"

    def __init__(self, config):
        super().__init__(config)
        self.model = str(self.cfg.get("model", "gemini-2.5-flash"))
        self.api_key = config.secret("GEMINI_API_KEY")
        # รุ่น 3.x เปิดโหมดคิดก่อนตอบมาให้เอง ทำให้ช้า 3-6 เท่าโดยไม่ได้ช่วยงานแปล
        # "low" = แทบไม่คิด (เร็วสุด) ตั้งเป็น "" ถ้าอยากใช้ค่าเริ่มต้นของโมเดล
        self.thinking_level = str(self.cfg.get("thinking_level", "low") or "")
        self.retries = int(self.cfg.get("retries", 2))

    def available(self) -> bool:
        return bool(self.api_key)

    def _open(self, system: str, user: str, thinking: bool):
        generation_config: dict = {"temperature": 0.3}
        if thinking and self.thinking_level:
            generation_config["thinkingConfig"] = {"thinkingLevel": self.thinking_level}
        body = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": generation_config,
        }
        req = urllib.request.Request(
            _ENDPOINT.format(model=self.model),
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key},
            method="POST",
        )
        return urllib.request.urlopen(req, timeout=self.config.timeout)

    def _connect(self, system: str, user: str):
        """เปิดการเชื่อมต่อ (ลองใหม่เมื่อเจอ 503/429 สั้น ๆ) คืน response ที่พร้อมอ่านทีละบรรทัด"""
        thinking = True
        last: ProviderError | None = None
        for attempt in range(self.retries + 1):
            try:
                return self._open(system, user, thinking)
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", "replace")[:300]
                # โมเดลรุ่นเก่าไม่รู้จัก thinkingConfig ลองใหม่แบบไม่ส่งฟิลด์นี้
                if e.code == 400 and thinking and "think" in detail.lower():
                    log.info("โมเดล %s ไม่รับ thinkingConfig ลองใหม่โดยไม่ส่ง", self.model)
                    thinking = False
                    continue
                last = ProviderError(f"Gemini ตอบ HTTP {e.code}: {detail}")
                if e.code not in _RETRY_CODES:
                    raise last from e
                # โควต้ารายวันหมด (retryDelay ยาว) ไม่ต้องรอ ไปตัวสำรองทันที
                delay = _server_retry_delay(detail)
                if delay is not None and delay > _MAX_RETRY_WAIT:
                    log.info("Gemini บอกให้รอ %.0f วินาที ยาวเกิน ข้ามไปใช้ตัวสำรอง", delay)
                    raise last from e
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last = ProviderError(f"ติดต่อ Gemini ไม่ได้: {e}")
            if attempt < self.retries:
                wait = 1.5 * (attempt + 1)
                log.info("Gemini ล้มเหลว (%s) ลองใหม่ใน %.1f วินาที", last, wait)
                time.sleep(wait)
        raise last or ProviderError("Gemini ล้มเหลวโดยไม่ทราบสาเหตุ")

    def complete(self, system: str, user: str, model_alias: str) -> str:
        return self.stream(system, user, model_alias)

    def stream(
        self,
        system: str,
        user: str,
        model_alias: str,
        on_delta: Callable[[str], None] | None = None,
        cancel: threading.Event | None = None,
    ) -> str:
        if not self.api_key:
            raise ProviderError("ยังไม่ได้ใส่ GEMINI_API_KEY ในไฟล์ .env")

        resp = self._connect(system, user)
        parts: list[str] = []
        reason = None
        try:
            with resp:
                for raw in resp:  # SSE: บรรทัด "data: {...}" ทีละก้อน
                    if cancel is not None and cancel.is_set():
                        raise ProviderCancelled("ยกเลิก")
                    line = raw.decode("utf-8", "replace").strip()
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if not payload:
                        continue
                    try:
                        chunk = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(chunk, dict):
                        continue
                    reason = chunk.get("promptFeedback", {}).get("blockReason") or reason
                    for cand in chunk.get("candidates", [])[:1]:
                        for part in cand.get("content", {}).get("parts", []):
                            text = part.get("text", "")
                            if text:
                                parts.append(text)
                                if on_delta is not None:
                                    on_delta(text)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise ProviderError(f"ติดต่อ Gemini ไม่ได้: {e}") from e

        text = "".join(parts).strip()
        if not text:
            raise ProviderError(f"Gemini ไม่ส่งข้อความกลับมา ({reason or 'unknown'})")
        return text
