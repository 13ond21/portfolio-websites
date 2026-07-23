"""Prepare hub images + QR for tester directory."""
from __future__ import annotations

import io
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

HUB = Path(r"C:\Users\corey\portfolio-websites\assets\hub")
URL = "https://13ond21.github.io/portfolio-websites/apps.html"
QR_PATH = HUB / "qr-apps-hub.png"


def make_qr() -> None:
    api = (
        "https://api.qrserver.com/v1/create-qr-code/"
        f"?size=600x600&ecc=M&margin=16&format=png&data={urllib.parse.quote(URL, safe='')}"
    )
    try:
        data = urllib.request.urlopen(api, timeout=30).read()
        QR_PATH.write_bytes(data)
        im = Image.open(io.BytesIO(data))
        print("qr api", im.size, len(data))
        if len(data) < 2000:
            raise RuntimeError("QR too small, likely bad")
        return
    except Exception as e:
        print("api fail", e)

    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "qrcode[pil]", "-q"]
    )
    import qrcode

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=12,
        border=3,
    )
    qr.add_data(URL)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(QR_PATH)
    print("qrcode lib", QR_PATH.stat().st_size)


def to_webp(src: Path, max_w: int = 900, quality: int = 80) -> None:
    if not src.exists():
        return
    im = Image.open(src).convert("RGB")
    if im.width > max_w:
        h = int(im.height * max_w / im.width)
        im = im.resize((max_w, h), Image.Resampling.LANCZOS)
    out = HUB / f"{src.stem}.webp"
    im.save(out, "WEBP", quality=quality, method=4)
    print("webp", out.name, out.stat().st_size)


def main() -> None:
    HUB.mkdir(parents=True, exist_ok=True)
    make_qr()

    # Compress daily affirmation screenshot for card use
    daily = HUB / "daily-affirmation.png"
    if daily.exists():
        im = Image.open(daily).convert("RGB")
        if im.width > 720:
            h = int(im.height * 720 / im.width)
            im = im.resize((720, h), Image.Resampling.LANCZOS)
        im.save(HUB / "daily-affirmation.jpg", "JPEG", quality=82, optimize=True)
        im.save(HUB / "daily-affirmation.webp", "WEBP", quality=80, method=4)
        print("daily jpg/webp done")

    for name in [
        "decibel-meter.png",
        "bt-mic.png",
        "uk-pay-calc.png",
        "morse-beacon.png",
        "facts-kids.png",
        "kitchen-buddy.png",
    ]:
        to_webp(HUB / name)

    print("assets ready")
    for p in sorted(HUB.iterdir()):
        print(f"  {p.name:30} {p.stat().st_size:>10}")


if __name__ == "__main__":
    main()
