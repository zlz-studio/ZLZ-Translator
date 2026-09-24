"""ตัวเชื่อม Google Gemini API (มีโควต้าฟรี) ผ่าน REST ไม่ต้องติดตั้งไลบรารีเพิ่ม"""
from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request

from core.providers.base import Provider, ProviderError

_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

log = logging.getLogger("gemini")

# Gemini มักตอบ 503 (คนใช้เยอะ) เป็นช่วง ๆ ลองใหม่สักครั้งสองครั้งมักผ่าน
_RETRY_CODES = {429, 500, 502, 503, 504}


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

    def _post(self, system: str, user: str, thinking: bool) -> dict:
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
        with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def complete(self, system: str, user: str, model_alias: str) -> str:
        if not self.api_key:
            raise ProviderError("ยังไม่ได้ใส่ GEMINI_API_KEY ในไฟล์ .env")

        thinking = True
        last: ProviderError | None = None
        for attempt in range(self.retries + 1):
            try:
                data = self._post(system, user, thinking)
                break
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
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last = ProviderError(f"ติดต่อ Gemini ไม่ได้: {e}")
            if attempt < self.retries:
                wait = 1.5 * (attempt + 1)
                log.info("Gemini ล้มเหลว (%s) ลองใหม่ใน %.1f วินาที", last, wait)
                time.sleep(wait)
        else:
            raise last or ProviderError("Gemini ล้มเหลวโดยไม่ทราบสาเหตุ")

        try:
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts).strip()
        except (KeyError, IndexError, TypeError) as e:
            reason = data.get("promptFeedback", {}).get("blockReason") if isinstance(data, dict) else None
            raise ProviderError(f"Gemini ไม่ส่งข้อความกลับมา ({reason or 'unknown'})") from e
        if not text:
            raise ProviderError("Gemini ส่งข้อความว่างกลับมา")
        return text
