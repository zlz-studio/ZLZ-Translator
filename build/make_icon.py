"""สร้าง assets/icon.ico (ไอคอนโปรแกรม/ตัวติดตั้ง) จากรูปเดียวกับไอคอนใน tray

    .venv\\Scripts\\python.exe build\\make_icon.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

BLUE = (88, 101, 242, 255)


def draw(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = max(1, size // 32)
    d.rounded_rectangle((pad, pad, size - pad, size - pad), radius=size // 5, fill=BLUE)
    try:
        font = ImageFont.truetype("segoeuib.ttf", int(size * 0.52))
        d.text((size / 2, size / 2), "แปล", fill="white", font=font, anchor="mm")
    except OSError:
        font = ImageFont.load_default()
        d.text((size / 2, size / 2), "T", fill="white", font=font, anchor="mm")
    return img


def main() -> int:
    out = ROOT / "assets" / "icon.ico"
    out.parent.mkdir(exist_ok=True)
    sizes = [16, 24, 32, 48, 64, 128, 256]
    base = draw(256)
    base.save(out, format="ICO", sizes=[(s, s) for s in sizes])
    (ROOT / "assets" / "icon.png").write_bytes(b"")  # ให้มีไฟล์ไว้ก่อน แล้วเขียนทับด้วย png จริง
    base.save(ROOT / "assets" / "icon.png", format="PNG")
    print(f"สร้าง {out} ({', '.join(str(s) for s in sizes)} px)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
