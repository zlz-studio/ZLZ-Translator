"""โปรแกรม Hotkey บน Windows: รันใน system tray, กดปุ่มลัดเพื่อแปลได้ทุกแอป

    python -m hotkey.app

โหมด (ค่าเริ่มต้นใน config.toml [hotkeys]):
  read    ลากคลุมอังกฤษ -> ป๊อปอัปไทย
  reply   พิมพ์ไทยในช่องแชท -> แทนที่ด้วยอังกฤษ (ยังไม่ส่ง)
  explain ลากคลุมอังกฤษ -> อธิบายว่าลูกค้าหมายถึงอะไร
  polish  อังกฤษที่พิมพ์เอง -> แก้ให้ถูกและเป็นธรรมชาติ
"""
from __future__ import annotations

import logging
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from logging.handlers import RotatingFileHandler
from typing import Callable

# ให้รันได้ทั้ง `python -m hotkey.app` และ `pythonw hotkey\app.py` (จาก Task Scheduler)
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import keyboard  # noqa: E402

from core.config import MODEL_PRESETS, MODES, apply_preset, current_preset, load_config  # noqa: E402
from core.providers import ProviderError  # noqa: E402
from core.translator import Result, Translator  # noqa: E402
from hotkey import autostart  # noqa: E402
from hotkey import clipboard as clip  # noqa: E402
from hotkey.popup import ResultPopup, Toast  # noqa: E402
from hotkey.settings_dialog import SettingsDialog  # noqa: E402
from hotkey.tray import Tray  # noqa: E402

log = logging.getLogger("hotkey")

# ช่องพิมพ์ Discord รับได้สูงสุด 4000 ตัวอักษร (Nitro) ถ้าก๊อปมาได้ยาวกว่านี้
# แปลว่าไม่ได้ก๊อปจากช่องพิมพ์ แต่ไปโดนข้อความทั้งหน้าจอ ห้ามเอาไปแปลแล้ววางทับ
MAX_DRAFT_CHARS = 4000


class App:
    def __init__(self) -> None:
        self.translator = Translator(load_config())
        self.cfg = self.translator.config
        self.tone = self.cfg.default_tone
        self.paused = False
        self.busy = threading.Lock()
        self.ui_queue: "queue.Queue[tuple[Callable, tuple]]" = queue.Queue()

        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("Discord Translator")

        self.tray = Tray(
            get_status=self._status_text,
            get_tone=lambda: self.tone,
            set_tone=self._set_tone,
            get_usage=self._usage_text,
            reload=lambda: self.ui(self._reload),
            quit_app=lambda: self.ui(self.quit),
            root_dir=str(self.cfg.root),
            get_enabled=lambda: not self.paused,
            toggle_enabled=self._toggle_paused,
            get_discord_running=self._discord_running,
            toggle_discord=self._toggle_discord,
            has_discord_token=lambda: bool(self.cfg.secret("DISCORD_TOKEN")),
            open_settings=lambda: self.ui(self._open_settings),
            get_autostart=lambda: self._autostart_state,
            toggle_autostart=lambda: self.ui(self._toggle_autostart),
            get_hotkeys=self._hotkeys_text,
            get_preset=self._get_preset,
            set_preset=lambda key: self.ui(self._set_preset, key),
        )
        self._autostart_state = autostart.is_enabled()
        self.discord_proc: subprocess.Popen | None = None
        self._register_hotkeys()

    # ---------------------------------------------------------------- Discord app (โปรเซสลูก)
    def _discord_running(self) -> bool:
        return self.discord_proc is not None and self.discord_proc.poll() is None

    def _start_discord(self) -> None:
        if self._discord_running():
            return
        if not self.cfg.secret("DISCORD_TOKEN"):
            self.toast("ยังไม่ได้ใส่ DISCORD_TOKEN ในไฟล์ .env")
            return
        exe = sys.executable
        creationflags = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
        self.discord_proc = subprocess.Popen([exe, "-m", "discord_app.bot"], cwd=str(self.cfg.root),
                                             creationflags=creationflags)
        log.info("discord app started pid=%s", self.discord_proc.pid)
        self.toast("เปิด Discord app แล้ว (พร้อมใช้ใน 10 วินาที)")
        self.tray.refresh()

    def _stop_discord(self) -> None:
        if self._discord_running():
            self.discord_proc.terminate()
            try:
                self.discord_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.discord_proc.kill()
            log.info("discord app stopped")
        self.discord_proc = None
        self.tray.refresh()

    def _toggle_discord(self) -> None:
        if self._discord_running():
            self._stop_discord()
            self.toast("ปิด Discord app แล้ว")
        else:
            self._start_discord()
        self.tray.refresh()

    # ---------------------------------------------------------------- UI thread helpers
    def ui(self, fn: Callable, *args) -> None:
        """ส่งงานไปทำบนเธรด tkinter (เรียกจากเธรดไหนก็ได้)"""
        self.ui_queue.put((fn, args))

    def _poll(self) -> None:
        try:
            while True:
                fn, args = self.ui_queue.get_nowait()
                try:
                    fn(*args)
                except Exception:  # noqa: BLE001
                    log.exception("UI task failed")
        except queue.Empty:
            pass
        self.root.after(40, self._poll)

    def toast(self, text: str, seconds: float = 2.5) -> None:
        self.ui(Toast, self.root, text, seconds, int(self.cfg.ui("font_size", 11)) - 1)

    # ---------------------------------------------------------------- hotkeys
    def _register_hotkeys(self) -> None:
        for handle in getattr(self, "_hotkey_handles", []):
            try:
                keyboard.remove_hotkey(handle)
            except (KeyError, ValueError):
                pass
        self._hotkey_handles = []
        bound = []
        for mode in MODES:
            combo = self.cfg.hotkey(mode)
            if not combo:
                continue
            try:
                self._hotkey_handles.append(
                    keyboard.add_hotkey(combo, self._on_hotkey, args=(mode,), suppress=False)
                )
                bound.append(f"{combo} = {mode}")
            except (ValueError, KeyError) as e:
                log.error("ผูกปุ่ม %s ให้โหมด %s ไม่ได้: %s", combo, mode, e)
        log.info("hotkeys: %s", ", ".join(bound))

    def _on_hotkey(self, mode: str) -> None:
        if self.paused:
            return
        apps = self.cfg.only_in_apps
        if apps:
            title = clip.foreground_window_title()
            if not any(a.lower() in title.lower() for a in apps):
                return  # อยู่ในโปรแกรมอื่น ปล่อยให้ปุ่มทำงานตามปกติของโปรแกรมนั้น
        if not self.busy.acquire(blocking=False):
            self.toast("กำลังแปลอันก่อนหน้าอยู่ รอสักครู่...")
            return
        threading.Thread(target=self._work, args=(mode,), daemon=True, name=f"translate-{mode}").start()

    def _toggle_paused(self) -> None:
        self.paused = not self.paused
        self.toast("ปิดการทำงานชั่วคราว (ไอคอนสีเทา) คลิกไอคอนอีกครั้งเพื่อเปิด" if self.paused else "เปิดใช้งานแล้ว")
        self.tray.refresh()

    # ---------------------------------------------------------------- ตั้งค่า / เปิดอัตโนมัติ
    def _open_settings(self) -> None:
        SettingsDialog(self.root, self, on_saved=self._on_settings_saved)

    def _on_settings_saved(self) -> None:
        self._reload(quiet=True)
        if self.cfg.secret("DISCORD_TOKEN") and not self._discord_running() and self.cfg.discord_autostart:
            self._start_discord()
        elif not self.cfg.secret("DISCORD_TOKEN") and self._discord_running():
            self._stop_discord()
        self.tray.refresh()

    def _toggle_autostart(self) -> None:
        if self._autostart_state:
            ok, msg = autostart.disable()
        else:
            ok, msg = autostart.enable(self.cfg.root)
        if ok:
            self._autostart_state = autostart.is_enabled()
            self.toast(msg)
        else:
            self._show_error(f"ตั้งค่าเปิดอัตโนมัติไม่สำเร็จ: {msg}")
        self.tray.refresh()

    # ---------------------------------------------------------------- worker thread
    def _work(self, mode: str) -> None:
        previous_clip: str | None = None
        try:
            self.ui(self.tray.set_busy, True)
            clip.wait_modifiers_released()
            if mode in ("read", "explain"):
                text = clip.copy_selection()
                if not text:
                    self.toast("ไม่พบข้อความที่ลากคลุมไว้ (ลากคลุมข้อความก่อนแล้วกดปุ่มลัด)")
                    return
            else:
                text, previous_clip = clip.select_all_and_copy()
                if not text:
                    clip.restore_clipboard(previous_clip)
                    previous_clip = None
                    self.toast("ช่องพิมพ์ว่าง (คลิกในช่องพิมพ์แล้วพิมพ์ข้อความก่อน)")
                    return
                if len(text) > MAX_DRAFT_CHARS:
                    clip.restore_clipboard(previous_clip)
                    previous_clip = None
                    self.toast(f"ได้ข้อความมา {len(text):,} ตัวอักษร ยาวเกินช่องพิมพ์ "
                               "น่าจะโฟกัสไม่ได้อยู่ในช่องพิมพ์ (คลิกในช่องพิมพ์ก่อนแล้วกดใหม่)", seconds=5)
                    return

            if mode in ("reply", "polish"):
                self.toast("กำลังแปล...", seconds=0)
                result = self.translator.run(mode, text, tone=self.tone)
                log.info("%s via %s/%s in %.1fs", mode, result.provider, result.model, result.seconds)
                clip.paste_replace(result.text, previous_clip or "")
                previous_clip = None
                self.ui(self._show_popup, result, text, False)
                self._auto_check(result)
            else:
                # เปิดป๊อปอัปทันที แล้วทยอยเติมคำแปลระหว่างที่โมเดลกำลังพิมพ์ ไม่ต้องรอจนจบ
                stream_id = object()
                pending = Result("", mode, self.tone, "", "", 0.0, False)
                self.ui(self._show_popup, pending, text, True, stream_id, True)
                try:
                    result = self.translator.run(
                        mode, text, tone=self.tone,
                        on_delta=lambda chunk: self.ui(self._append_popup, stream_id, chunk),
                        on_reset=lambda: self.ui(self._reset_popup, stream_id),
                    )
                except Exception:
                    self.ui(self._close_popup, stream_id)
                    raise
                log.info("%s via %s/%s in %.1fs", mode, result.provider, result.model, result.seconds)
                self.ui(self._finish_popup, stream_id, result)
        except ProviderError as e:
            log.warning("translate failed: %s", e)
            self.ui(self._show_error, str(e))
        except Exception as e:  # noqa: BLE001
            log.exception("unexpected error")
            self.ui(self._show_error, f"ข้อผิดพลาดไม่คาดคิด: {e}")
        finally:
            if previous_clip is not None:
                clip.restore_clipboard(previous_clip)
            self.ui(self.tray.set_busy, False)
            self.ui(self.tray.refresh)
            self.busy.release()

    def _retone(self, original: str, tone: str, mode: str) -> None:
        """กดปุ่มน้ำเสียงในป๊อปอัป -> แปลใหม่ด้วยน้ำเสียงนั้น (ไม่ paste ทับ แค่โชว์)"""
        if not self.busy.acquire(blocking=False):
            self.toast("กำลังแปลอยู่ รอสักครู่...")
            return

        def run():
            try:
                self.ui(self.tray.set_busy, True)
                self.toast("กำลังแปลใหม่...", seconds=0)
                result = self.translator.run(mode, original, tone=tone)
                self.ui(self._show_popup, result, original, True)
                self._auto_check(result)
            except ProviderError as e:
                self.ui(self._show_error, str(e))
            finally:
                self.ui(self.tray.set_busy, False)
                self.busy.release()

        threading.Thread(target=run, daemon=True).start()

    def _auto_check(self, result: Result) -> None:
        """แปลอังกฤษที่ได้กลับเป็นไทยอัตโนมัติ แล้วเติมลงป๊อปอัป (ไม่ล็อก busy เพื่อไม่ขวางปุ่มลัดถัดไป)"""
        if not self.cfg.auto_back_translate or result.mode not in ("reply", "polish"):
            return

        def run():
            try:
                back = self.translator.run("read", result.text)
                text = back.text
            except ProviderError as e:
                text = f"(แปลกลับไม่สำเร็จ: {e})"

            def apply():
                popup = ResultPopup._current
                if popup is not None and popup.result is result:
                    popup.set_check(text)

            self.ui(apply)

        threading.Thread(target=run, daemon=True, name="auto-check").start()

    def _back_translate(self, english: str) -> None:
        if not self.busy.acquire(blocking=False):
            self.toast("กำลังแปลอยู่ รอสักครู่...")
            return

        def run():
            try:
                self.ui(self.tray.set_busy, True)
                self.toast("กำลังแปลกลับ...", seconds=0)
                result = self.translator.run("read", english)
                self.ui(self._show_popup, result, english, True)
            except ProviderError as e:
                self.ui(self._show_error, str(e))
            finally:
                self.ui(self.tray.set_busy, False)
                self.busy.release()

        threading.Thread(target=run, daemon=True).start()

    # ---------------------------------------------------------------- UI callbacks (tk thread)
    def _show_popup(self, result: Result, original: str, take_focus: bool,
                    stream_id: object | None = None, pending: bool = False) -> None:
        if Toast._current:
            Toast._current.close()
        ResultPopup(
            self.root,
            result,
            original,
            font_size=int(self.cfg.ui("font_size", 11)),
            take_focus=take_focus,
            auto_close=float(self.cfg.ui("auto_close_seconds", 0)),
            on_retone=lambda tone, o=original, m=result.mode: self._retone(o, tone, m),
            on_back_translate=self._back_translate,
            on_copy=self._copy_to_clipboard,
            show_check_placeholder=self.cfg.auto_back_translate,
            pending=pending,
            stream_id=stream_id,
        )

    # ป๊อปอัปแบบทยอยเติม: ทุกตัวเช็ค stream_id กันเติมผิดหน้าต่าง (ผู้ใช้อาจกดแปลอันใหม่ไปแล้ว)
    def _popup_for(self, stream_id: object) -> ResultPopup | None:
        popup = ResultPopup._current
        return popup if popup is not None and popup.stream_id is stream_id else None

    def _append_popup(self, stream_id: object, chunk: str) -> None:
        popup = self._popup_for(stream_id)
        if popup is not None:
            popup.append_text(chunk)

    def _reset_popup(self, stream_id: object) -> None:
        popup = self._popup_for(stream_id)
        if popup is not None:
            popup.reset_text()

    def _finish_popup(self, stream_id: object, result: Result) -> None:
        popup = self._popup_for(stream_id)
        if popup is not None:  # ถ้าผู้ใช้ปิดไปแล้วระหว่างรอ ก็ไม่ต้องเด้งขึ้นมาใหม่
            popup.finish(result)

    def _close_popup(self, stream_id: object) -> None:
        popup = self._popup_for(stream_id)
        if popup is not None:
            popup.close()

    def _show_error(self, message: str) -> None:
        if Toast._current:
            Toast._current.close()
        Toast(self.root, "❌ " + message, seconds=8, font_size=int(self.cfg.ui("font_size", 11)) - 1)

    def _copy_to_clipboard(self, text: str) -> None:
        clip.restore_clipboard(text)
        Toast(self.root, "ก๊อปแล้ว", seconds=1.2)

    def _set_tone(self, tone: str) -> None:
        self.tone = tone
        self.toast(f"น้ำเสียงตอนตอบ: {tone}")
        self.tray.refresh()

    def _reload(self, quiet: bool = False) -> None:
        try:
            self.translator.reload()
            self.cfg = self.translator.config
            self._register_hotkeys()
            if not quiet:
                self.toast("โหลดการตั้งค่าใหม่แล้ว")
        except Exception as e:  # noqa: BLE001
            self._show_error(f"โหลดการตั้งค่าไม่ได้: {e}")
        self.tray.refresh()

    def _hotkeys_text(self) -> str:
        labels = {"read": "แปล", "reply": "ตอบ", "explain": "อธิบาย", "polish": "แก้"}
        parts = [f"{(self.cfg.hotkey(m) or '-').upper()}={labels[m]}" for m in MODES if self.cfg.hotkey(m)]
        return "ปุ่มลัด: " + "  ".join(parts) if parts else "ปุ่มลัด: ยังไม่ได้ตั้ง"

    # ---------------------------------------------------------------- เลือกโมเดลจากเมนู tray
    def _get_preset(self) -> str:
        return current_preset(self.cfg)

    def _set_preset(self, key: str) -> None:
        try:
            apply_preset(self.cfg.root, key)
        except (OSError, KeyError) as e:
            self._show_error(f"บันทึกโมเดลไม่ได้: {e}")
            return
        self._reload(quiet=True)
        self.toast(f"โมเดลแปล: {MODEL_PRESETS[key][0]}")

    def _status_text(self) -> str:
        key = current_preset(self.cfg)
        if key in MODEL_PRESETS:
            return f"โมเดลแปล: {MODEL_PRESETS[key][0]}"
        return f"โมเดลแปล: กำหนดเอง ({' → '.join(self.cfg.provider_order)})"

    def _usage_text(self) -> str:
        used = self.translator.usage.today()
        if not used:
            return "วันนี้ยังไม่ได้ใช้"
        return "วันนี้: " + ", ".join(f"{k} {v} ครั้ง" for k, v in used.items())

    # ---------------------------------------------------------------- lifecycle
    def run(self) -> None:
        self.tray.start()
        self.root.after(40, self._poll)
        if self.cfg.discord_autostart and self.cfg.secret("DISCORD_TOKEN"):
            self.root.after(500, self._start_discord)
        hint = "  ".join(f"{self.cfg.hotkey(m)}={m}" for m in MODES if self.cfg.hotkey(m))
        self.root.after(300, lambda: Toast(self.root, f"Discord Translator พร้อมใช้\n{hint}", seconds=4))
        log.info("app started")
        try:
            self.root.mainloop()
        finally:
            keyboard.unhook_all()
            self.tray.stop()

    def quit(self) -> None:
        log.info("quit")
        self._stop_discord()
        self.root.quit()


def _setup_logging(cfg) -> None:
    handler = RotatingFileHandler(cfg.data_dir / "hotkey.log", maxBytes=512_000, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler, logging.StreamHandler()])


def main() -> None:
    app = App()
    _setup_logging(app.cfg)
    app.run()


if __name__ == "__main__":
    main()
