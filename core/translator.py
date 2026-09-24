"""แกนแปล: เลือกโหมด สร้าง prompt ยิงผู้ให้บริการตามลำดับสำรอง และนับการใช้งาน"""
from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass
from datetime import date
from typing import Callable

from core.config import MODES, TONES, Config, load_config
from core.prompts import build_system_prompt, build_user_prompt
from core.providers import PROVIDERS, Provider, ProviderCancelled, ProviderError

log = logging.getLogger("translator")

OnDelta = Callable[[str], None]
OnReset = Callable[[], None]


@dataclass
class Result:
    text: str
    mode: str
    tone: str
    provider: str
    model: str
    seconds: float
    fallback_used: bool


class UsageCounter:
    """นับจำนวนครั้งต่อวันต่อผู้ให้บริการ เก็บใน data/usage.json"""

    def __init__(self, config: Config):
        self.path = config.data_dir / "usage.json"

    def _load(self) -> dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def record(self, provider: str) -> None:
        data = self._load()
        today = date.today().isoformat()
        day = data.setdefault(today, {})
        day[provider] = day.get(provider, 0) + 1
        # เก็บแค่ 30 วันล่าสุด
        for key in sorted(data)[:-30]:
            data.pop(key, None)
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def today(self) -> dict[str, int]:
        return self._load().get(date.today().isoformat(), {})


class Translator:
    def __init__(self, config: Config | None = None):
        self.config = config or load_config()
        self.usage = UsageCounter(self.config)
        self._providers: dict[str, Provider] = {}

    def reload(self) -> None:
        self.config = load_config(self.config.root)
        self._providers.clear()

    def _provider(self, name: str) -> Provider:
        if name not in self._providers:
            cls = PROVIDERS.get(name)
            if cls is None:
                raise ProviderError(f"ไม่รู้จักผู้ให้บริการ '{name}' (มี: {', '.join(PROVIDERS)})")
            self._providers[name] = cls(self.config)
        return self._providers[name]

    def run(
        self,
        mode: str,
        text: str,
        tone: str | None = None,
        provider: str | None = None,
        on_delta: OnDelta | None = None,
        on_reset: OnReset | None = None,
    ) -> Result:
        """แปลข้อความ ถ้าให้ on_delta มาจะทยอยส่งข้อความระหว่างที่โมเดลกำลังพิมพ์

        on_reset ถูกเรียกเมื่อตัวที่ส่งข้อความไปแล้วล้มเหลวกลางทางและกำลังเปลี่ยนไปใช้ตัวอื่น
        (ฝั่ง UI ควรล้างข้อความที่แสดงไว้)
        """
        if mode not in MODES:
            raise ValueError(f"โหมดต้องเป็นหนึ่งใน {MODES}")
        text = (text or "").strip()
        if not text:
            raise ValueError("ไม่มีข้อความให้แปล")
        tone = tone if tone in TONES else self.config.default_tone

        system = build_system_prompt(mode, self.config.glossary, tone)
        user = build_user_prompt(mode, text)
        model_alias = self.config.model_for(mode)
        order = [provider] if provider else self.config.provider_order

        errors: list[str] = []
        ready: list[tuple[str, Provider]] = []
        for name in order:
            try:
                prov = self._provider(name)
            except ProviderError as e:
                errors.append(str(e))
                continue
            if not prov.available():
                errors.append(f"{name}: ยังไม่พร้อมใช้ (ขาดคีย์หรือไบนารี)")
                continue
            ready.append((name, prov))

        hedge = self.config.hedge_after_seconds
        if len(ready) >= 2 and hedge >= 0:
            result = self._hedged(ready, system, user, model_alias, mode, tone, on_delta, on_reset, hedge, errors)
        else:
            result = self._sequential(ready, system, user, model_alias, mode, tone, on_delta, on_reset, errors)
        if result is None:
            raise ProviderError("แปลไม่สำเร็จ ทุกผู้ให้บริการล้มเหลว:\n- " + "\n- ".join(errors))
        return result

    def _result(self, name: str, prov: Provider, out: str, elapsed: float, mode: str, tone: str,
                model_alias: str, fallback_used: bool) -> Result:
        self.usage.record(name)
        model = getattr(prov, "model", None) or model_alias
        return Result(out, mode, tone, name, str(model), elapsed, fallback_used)

    # ------------------------------------------------------------------ เรียงลำดับ
    def _sequential(self, ready, system, user, model_alias, mode, tone, on_delta, on_reset, errors) -> Result | None:
        """ลองทีละเจ้าตามลำดับ เจ้าไหนล้มเหลวค่อยไปเจ้าถัดไป"""
        for index, (name, prov) in enumerate(ready):
            emitted = False

            def delta(chunk: str) -> None:
                nonlocal emitted
                emitted = True
                on_delta(chunk)

            started = time.perf_counter()
            try:
                out = prov.stream(system, user, model_alias, on_delta=delta if on_delta else None)
            except ProviderError as e:
                log.warning("%s ล้มเหลว: %s", name, e)
                errors.append(f"{name}: {e}")
                if emitted and on_reset:
                    on_reset()
                continue
            return self._result(name, prov, out, time.perf_counter() - started, mode, tone, model_alias, index > 0)
        return None

    # ------------------------------------------------------------------ hedge
    def _hedged(self, ready, system, user, model_alias, mode, tone, on_delta, on_reset, delay, errors) -> Result | None:
        """ปล่อยตัวหลักก่อน ถ้ายังไม่ส่งคำแรกภายใน delay วินาที (หรือล้มเหลวไปเลย) ค่อยปล่อยตัวถัดไปวิ่งคู่

        เจ้าไหนส่งคำแรกมาก่อนชนะ เจ้าอื่นถูกยกเลิกทันที (claude ที่ยังบูตอยู่จะโดนฆ่าก่อนยิง API = ไม่เสียโควต้า)
        กรณีปกติตัวหลักตอบทัน ตัวสำรองจึงไม่ถูกเรียกเลย
        """
        lock = threading.Lock()
        winner: list[str | None] = [None]
        cancels = {name: threading.Event() for name, _ in ready}
        results: dict[str, tuple[str, float]] = {}
        threads: list[threading.Thread] = []

        def work(name: str, prov: Provider) -> None:
            started = time.perf_counter()
            emitted = False

            def delta(chunk: str) -> None:
                nonlocal emitted
                with lock:
                    if winner[0] is None:
                        winner[0] = name
                        for other, ev in cancels.items():
                            if other != name:
                                ev.set()
                    if winner[0] != name:
                        return  # แพ้ไปแล้ว ทิ้งข้อความที่ค้างมา
                    emitted = True
                    if on_delta:
                        on_delta(chunk)

            try:
                out = prov.stream(system, user, model_alias, on_delta=delta, cancel=cancels[name])
            except ProviderCancelled:
                return
            except ProviderError as e:
                log.warning("%s ล้มเหลว: %s", name, e)
                errors.append(f"{name}: {e}")
                with lock:
                    if winner[0] == name:  # ชนะแล้วแต่ล้มกลางทาง เปิดทางให้ตัวถัดไป
                        winner[0] = None
                        if emitted and on_reset:
                            on_reset()
                return
            results[name] = (out, time.perf_counter() - started)

        def launch(index: int) -> None:
            t = threading.Thread(target=work, args=ready[index], daemon=True, name=f"translate-{ready[index][0]}")
            threads.append(t)
            t.start()

        launch(0)
        next_index = 1
        deadline = time.perf_counter() + delay
        while True:
            with lock:
                current = winner[0]
            if current is not None and current in results:
                break
            alive = any(t.is_alive() for t in threads)
            if current is None:
                if not alive or time.perf_counter() >= deadline:
                    if next_index < len(ready):
                        if alive:
                            log.info("%s ยังไม่ตอบใน %.1f วินาที ปล่อย %s วิ่งคู่", ready[0][0], delay, ready[next_index][0])
                        launch(next_index)
                        next_index += 1
                        deadline = time.perf_counter() + delay
                    elif not alive:
                        return None
            time.sleep(0.03)

        name = winner[0]
        out, elapsed = results[name]
        prov = dict(ready)[name]
        return self._result(name, prov, out, elapsed, mode, tone, model_alias, name != ready[0][0])
