#!/usr/bin/env python3
"""Make every feature graphic a 24-bit opaque PNG, the way Play's spec asks for it.

Play's help for the feature graphic says "JPEG or 24-bit PNG (no alpha)". Every file this
touches is an RGBA PNG whose alpha channel is *fully opaque* - min alpha 255, so nothing is
transparent and dropping the channel changes no pixel. `tools_check_store_assets.py` warns
only when a graphic has genuinely transparent pixels, which is why these files have always
passed it while still not being what the spec describes.

REFUSES TO CONVERT ANYTHING THAT IS ACTUALLY TRANSPARENT
  If min(alpha) < 255 the file is reported and left alone: flattening it would visibly change
  the image, and that is a decision for a person, not for a batch job.

USAGE
    python tools_flatten_feature_graphics.py            # dry run
    python tools_flatten_feature_graphics.py --write    # apply
"""

from __future__ import annotations

import argparse
import pathlib
import sys

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent


def graphics(root):
    for app in sorted(p for p in root.iterdir() if p.is_dir()):
        assets = app / "assets"
        if not assets.is_dir():
            continue
        for path in sorted(assets.glob("*feature*graphic*.png")):
            yield app.name, path


def main(argv=None):
    parser = argparse.ArgumentParser(prog="tools_flatten_feature_graphics.py")
    parser.add_argument("--write", action="store_true", help="apply (default: dry run)")
    args = parser.parse_args(argv)

    transparent = 0
    converted = 0
    already = 0

    for app, path in graphics(ROOT):
        image = Image.open(path)
        size = image.size

        if not image.mode.endswith("A"):
            print("OK        %-18s %-26s %-5s %dx%d - already has no alpha channel"
                  % (app, path.name, image.mode, size[0], size[1]))
            already += 1
            continue

        low = image.getchannel("A").getextrema()[0]
        if low < 255:
            print("REFUSED   %-18s %-26s has real transparency (min alpha %d) - a person decides"
                  % (app, path.name, low))
            transparent += 1
            continue

        if args.write:
            image.convert("RGB").save(path, "PNG", optimize=True)

        print("%-9s %-18s %-26s RGBA(fully opaque) -> RGB  %dx%d  %d bytes"
              % ("CONVERTED" if args.write else "WOULD", app, path.name, size[0], size[1],
                 path.stat().st_size))
        converted += 1

    print("\n%d converted, %d already alpha-free, %d refused, %d total"
          % (converted, already, transparent, converted + already + transparent))

    return 0 if transparent == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
