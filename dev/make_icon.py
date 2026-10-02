"""สร้าง assets/icon.ico + assets/icon.png (ไอคอนโปรแกรม / ตัวติดตั้ง / shortcut บน Desktop)

    .venv\\Scripts\\python.exe dev\\make_icon.py

ดีไซน์: สี่เหลี่ยมมุมมนแบ่งทแยง  ซ้ายบนน้ำเงิน "ก"  ขวาล่างน้ำเงินเข้ม "A"  = แปลไทย <-> อังกฤษ
วาดแยกทีละขนาด (ขนาดเล็กลดรายละเอียด) เพื่อให้คมทั้งใน tray, Explorer และ Start Menu
"""
from __future__ import annotations

import sys
from pathlib import Path

# console บน Windows มักเป็น cp1252/cp850 พิมพ์ไทยแล้วพัง (ทั้งในเครื่องและบน GitHub Actions)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from PIL import Image, ImageChops, ImageDraw, ImageFont  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BLUE = (88, 101, 242, 255)
NAVY = (28, 31, 66, 255)
WHITE = (255, 255, 255, 255)
# ฟอนต์ที่มีตัวไทย (Windows 10/11 และเครื่อง GitHub Actions มีทั้งคู่)  segoeuib ไม่มีตัวไทย ห้ามใช้วาด "ก"
THAI_FONTS = ["LeelaUIb.ttf", "leelawdb.ttf", "tahomabd.ttf"]
LATIN_FONTS = ["segoeuib.ttf", "arialbd.ttf", "tahomabd.ttf"]
SIZES = [16, 20, 24, 32, 40, 48, 64, 128, 256]


def _font(names: list[str], size: int) -> ImageFont.FreeTypeFont | None:
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return None


def draw(size: int) -> Image.Image:
    ss = 4  # วาดใหญ่กว่า 4 เท่าแล้วย่อ ให้ขอบเรียบ
    s = size * ss
    pad = max(ss, s // 32)
    radius = s // 5
    box = (pad, pad, s - pad, s - pad)

    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(box, radius=radius, fill=BLUE)

    # ครึ่งขวาล่างสีเข้ม (ตัดตามมุมมน)
    shape = Image.new("L", (s, s), 0)
    ImageDraw.Draw(shape).rounded_rectangle(box, radius=radius, fill=255)
    tri = Image.new("L", (s, s), 0)
    ImageDraw.Draw(tri).polygon([(s, 0), (s, s), (0, s)], fill=255)
    img.paste(Image.new("RGBA", (s, s), NAVY), (0, 0), ImageChops.multiply(shape, tri))

    small = size <= 24
    thai = _font(THAI_FONTS, int(s * (0.62 if small else 0.50)))
    latin = _font(LATIN_FONTS, int(s * (0.56 if small else 0.46)))
    if thai is None or latin is None:
        # ไม่มีฟอนต์ (ไม่น่าเกิดบน Windows): วาดลูกศรสองทางแทนตัวอักษร
        w = s // 10
        d.line([(s * 0.25, s * 0.40), (s * 0.75, s * 0.40)], fill=WHITE, width=w)
        d.line([(s * 0.25, s * 0.60), (s * 0.75, s * 0.60)], fill=WHITE, width=w)
        return img.resize((size, size), Image.LANCZOS)

    if small:
        # เล็กมาก: ตัวเดียวพออ่านออก
        d.text((s * 0.50, s * 0.52), "ก", fill=WHITE, font=thai, anchor="mm")
    else:
        d.text((s * 0.34, s * 0.37), "ก", fill=WHITE, font=thai, anchor="mm")
        d.text((s * 0.67, s * 0.66), "A", fill=WHITE, font=latin, anchor="mm")
    return img.resize((size, size), Image.LANCZOS)


def main() -> int:
    out_dir = ROOT / "assets"
    out_dir.mkdir(exist_ok=True)
    images = [draw(s) for s in SIZES]
    ico = out_dir / "icon.ico"
    images[-1].save(ico, format="ICO", append_images=images[:-1], sizes=[(s, s) for s in SIZES])
    images[-1].save(out_dir / "icon.png", format="PNG")
    print(f"สร้าง {ico} ({', '.join(str(s) for s in SIZES)} px)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
