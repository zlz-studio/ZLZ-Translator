"""ไอคอนใน system tray (pystray) พร้อมเมนูตั้งค่าเร็ว

คลิกซ้ายที่ไอคอน = เปิด/ปิดการทำงาน (ไอคอนสีเทาเมื่อปิด)
คลิกขวา = เมนู
"""
from __future__ import annotations

import os
from typing import Callable

import pystray
from PIL import Image, ImageDraw, ImageFont

from core.config import MODEL_PRESETS, TONES

TONE_LABELS = {"formal": "ทางการ", "friendly": "เป็นกันเอง", "brief": "สั้น"}

_BLUE = (88, 101, 242, 255)
_ORANGE = (255, 170, 0, 255)
_GRAY = (120, 120, 128, 255)


def _make_icon_image(color: tuple) -> Image.Image:
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((2, 2, size - 2, size - 2), radius=14, fill=color)
    try:
        font = ImageFont.truetype("segoeuib.ttf", 34)
    except OSError:
        font = ImageFont.load_default()
    draw.text((size / 2, size / 2), "แปล" if font.size > 20 else "T", fill="white", font=font, anchor="mm")
    return img


class Tray:
    def __init__(
        self,
        *,
        get_status: Callable[[], str],
        get_tone: Callable[[], str],
        set_tone: Callable[[str], None],
        get_usage: Callable[[], str],
        reload: Callable[[], None],
        quit_app: Callable[[], None],
        root_dir: str,
        get_enabled: Callable[[], bool] = lambda: True,
        toggle_enabled: Callable[[], None] = lambda: None,
        get_discord_running: Callable[[], bool] = lambda: False,
        toggle_discord: Callable[[], None] = lambda: None,
        has_discord_token: Callable[[], bool] = lambda: False,
        open_settings: Callable[[], None] = lambda: None,
        get_autostart: Callable[[], bool] = lambda: False,
        toggle_autostart: Callable[[], None] = lambda: None,
        get_hotkeys: Callable[[], str] = lambda: "",
        get_preset: Callable[[], str] = lambda: "auto",
        set_preset: Callable[[str], None] = lambda _key: None,
    ):
        self._get_hotkeys = get_hotkeys
        self._get_preset = get_preset
        self._set_preset = set_preset
        self._get_status = get_status
        self._get_tone = get_tone
        self._set_tone = set_tone
        self._get_usage = get_usage
        self._reload = reload
        self._quit = quit_app
        self._root_dir = root_dir
        self._get_enabled = get_enabled
        self._toggle_enabled = toggle_enabled
        self._get_discord_running = get_discord_running
        self._toggle_discord = toggle_discord
        self._has_discord_token = has_discord_token
        self._open_settings = open_settings
        self._get_autostart = get_autostart
        self._toggle_autostart = toggle_autostart
        self._icons = {"normal": _make_icon_image(_BLUE), "busy": _make_icon_image(_ORANGE), "off": _make_icon_image(_GRAY)}
        self._busy = False
        self.icon = pystray.Icon("discord-translator", self._icons["normal"], "Discord Translator", menu=self._menu())

    def _menu(self) -> pystray.Menu:
        def tone_item(tone: str):
            return pystray.MenuItem(
                TONE_LABELS[tone],
                lambda: self._set_tone(tone),
                checked=lambda _item, t=tone: self._get_tone() == t,
                radio=True,
            )

        def preset_item(key: str):
            return pystray.MenuItem(
                MODEL_PRESETS[key][0],
                lambda: self._set_preset(key),
                checked=lambda _item, k=key: self._get_preset() == k,
                radio=True,
            )

        return pystray.Menu(
            # default=True -> คลิกซ้ายที่ไอคอนจะเรียกรายการนี้
            pystray.MenuItem(
                lambda _i: "เปิดใช้งานอยู่ (คลิกเพื่อปิด)" if self._get_enabled() else "ปิดอยู่ (คลิกเพื่อเปิด)",
                lambda: self._toggle_enabled(),
                checked=lambda _item: self._get_enabled(),
                default=True,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(lambda _i: self._get_hotkeys(), None, enabled=False),
            pystray.MenuItem(lambda _i: self._get_status(), None, enabled=False),
            pystray.MenuItem(lambda _i: self._get_usage(), None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("ตั้งค่า: คีย์ / ปุ่มลัด / บัญชี...", lambda: self._open_settings()),
            pystray.MenuItem("น้ำเสียงตอนตอบ", pystray.Menu(*[tone_item(t) for t in TONES])),
            pystray.MenuItem("โมเดลแปล", pystray.Menu(*[preset_item(k) for k in MODEL_PRESETS])),
            pystray.MenuItem(
                lambda _i: "Discord app: กำลังทำงาน (คลิกเพื่อปิด)" if self._get_discord_running()
                else "Discord app: ปิดอยู่ (คลิกเพื่อเปิด)",
                lambda: self._toggle_discord(),
                enabled=lambda _item: self._has_discord_token(),
            ),
            pystray.MenuItem("เปิดอัตโนมัติเมื่อเข้า Windows", lambda: self._toggle_autostart(),
                             checked=lambda _item: self._get_autostart()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("เปิดไฟล์ตั้งค่า (config.toml)", lambda: self._open("config.toml")),
            pystray.MenuItem("เปิดคลังศัพท์ (glossary.md)", lambda: self._open("glossary.md")),
            pystray.MenuItem("โหลดการตั้งค่าใหม่", lambda: self._reload()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("ออกจากโปรแกรม", lambda: self._quit()),
        )

    def _open(self, name: str) -> None:
        os.startfile(os.path.join(self._root_dir, name))

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.refresh_icon()

    def refresh_icon(self) -> None:
        if not self._get_enabled():
            self.icon.icon = self._icons["off"]
            self.icon.title = "Discord Translator (ปิดอยู่)"
        elif self._busy:
            self.icon.icon = self._icons["busy"]
            self.icon.title = "Discord Translator (กำลังแปล...)"
        else:
            self.icon.icon = self._icons["normal"]
            self.icon.title = "Discord Translator"

    def refresh(self) -> None:
        self.refresh_icon()
        self.icon.update_menu()

    def start(self) -> None:
        self.icon.run_detached()

    def stop(self) -> None:
        try:
            self.icon.stop()
        except Exception:
            pass
