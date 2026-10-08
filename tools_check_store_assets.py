#!/usr/bin/env python3
"""Fail if a store listing ships an asset Play will reject, or ships one screenshot twice.

WHAT THIS GUARDS
  Every app folder here carries the images the listing uploads: assets/feature_graphic.png
  (1024x500), assets/icon_512.png (512x512) and screenshots/*.png. Play validates those on
  upload, but nothing validated them on commit, and the two defects this exists for both
  reached a release:

    * factswipe/screenshots/04-challenge.png was a second capture of the home screen while
      01-home.png already showed it - a duplicate that says nothing about the app. Play
      allows it, but the listing loses a screenshot slot and the gallery repeats itself.
    * factswipe/assets/feature_graphic.png still carried the app's pre-rename name, so the
      one image every glance lands on advertised a name the app no longer has. Text is not
      machine-readable here, so the tool cannot catch that one - it catches the duplicates
      and the sizes, which are the failures that happen silently.

  Screenshots are compared perceptually (64x64 greyscale, mean absolute error), because a
  re-encoded or re-cropped copy of the same screen is the realistic duplicate, not an
  identical file.

  It also warns - never fails - on a feature graphic carrying transparent pixels, and on a
  screenshot whose proportions are past 2:1. Both are things a person should look at: an
  opaque alpha channel is what most files here carry and is fine, and 20:9 captures are
  accepted in practice.

USAGE
    python tools_check_store_assets.py                 # every app folder in this repo
    python tools_check_store_assets.py <dir> [<dir>]   # extra roots, e.g. an app checkout
    python tools_check_store_assets.py --quiet
"""

from __future__ import annotations

import argparse
import hashlib
import pathlib
import sys

from PIL import Image, ImageChops

ROOT = pathlib.Path(__file__).resolve().parent
FEATURE_GRAPHIC = (1024, 500)
ICON = (512, 512)
MIN_SIDE, MAX_SIDE = 320, 3840
# Play's help states a screenshot's longest side "can't be more than twice the minimum dimension".
# Reported as a warning, not a failure: modern 20:9 captures (1440x3120 = 2.17:1) exceed 2:1 and
# are accepted in practice, so this is a prompt to look, never a verdict.
ASPECT_LIMIT = 2.0
THUMB = 64
# Two captures of the same screen land near 0-2 even when the clock in the status bar moved; two
# genuinely different screens land well past 10. The line sits in that gap with margin on both sides.
DUP_MAE = 3.0


def thumb(path):
    return Image.open(path).convert("L").resize((THUMB, THUMB), Image.Resampling.LANCZOS)


def mae(a, b):
    hist = ImageChops.difference(a, b).histogram()
    total = sum(i * n for i, n in enumerate(hist))
    return total / sum(hist)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def app_dirs(root):
    return sorted(p for p in root.iterdir()
                  if p.is_dir() and ((p / "assets").is_dir() or (p / "screenshots").is_dir()))


def check_asset(app, path, expected, kind, problems, warnings, args):
    im = Image.open(path)
    size = im.size
    if expected is not None:
        if size != expected:
            problems.append("%s: %s is %dx%d, Play wants %dx%d"
                            % (app.name, path.name, size[0], size[1], expected[0], expected[1]))
    else:
        long_side, short_side = max(size), min(size)
        if short_side < MIN_SIDE or long_side > MAX_SIDE:
            problems.append("%s: %s is %dx%d, outside Play's %d..%d px"
                            % (app.name, path.name, size[0], size[1], MIN_SIDE, MAX_SIDE))
        elif long_side / short_side > ASPECT_LIMIT:
            warnings.append("%s: %s is %dx%d, aspect %.2f:1 is over Play's %.1f:1"
                            % (app.name, path.name, size[0], size[1],
                               long_side / short_side, ASPECT_LIMIT))
    # The icon may keep its alpha; the feature graphic may not - Play asks for "JPEG or 24-bit PNG
    # (no alpha)" there. An opaque alpha channel is what most of these files carry and is fine.
    if kind == "graphic" and im.mode.endswith("A") and im.getchannel("A").getextrema()[0] < 255:
        warnings.append("%s: %s has transparent pixels; Play wants no alpha on the feature graphic"
                        % (app.name, path.name))
    if not args.quiet:
        print("  %-16s %-10s %-28s %dx%d" % (app.name, kind, path.name, size[0], size[1]))
    return size


def check_screenshots(app, shots, problems, warnings, args):
    """Size-check every screenshot, then flag two that show the same screen."""
    marks = []
    for path in shots:
        check_asset(app, path, None, "screenshot", problems, warnings, args)
        marks.append((path, thumb(path), sha(path)))
    for i in range(len(marks)):
        for j in range(i + 1, len(marks)):
            (pa, ta, ha), (pb, tb, hb) = marks[i], marks[j]
            if ha == hb:
                problems.append("%s: %s and %s are the same file" % (app.name, pa.name, pb.name))
                continue
            diff = mae(ta, tb)
            if diff <= DUP_MAE:
                problems.append("%s: %s and %s show the same screen (MAE %.2f)"
                                % (app.name, pa.name, pb.name, diff))


def main(argv=None):
    parser = argparse.ArgumentParser(prog="tools_check_store_assets.py")
    parser.add_argument("roots", nargs="*", type=pathlib.Path,
                        help="extra roots to scan (default: this repo)")
    parser.add_argument("--quiet", action="store_true", help="print only the verdict")
    args = parser.parse_args(argv)
    roots = args.roots or [ROOT]

    problems, warnings, shots = [], [], 0
    for root in roots:
        if not root.is_dir():
            print("not a directory: %s" % root, file=sys.stderr)
            return 2
        for app in app_dirs(root):
            assets = app / "assets"
            if assets.is_dir():
                for pattern, expected, kind in (
                    ("*feature*graphic*.png", FEATURE_GRAPHIC, "graphic"),
                    ("*icon*.png", ICON, "icon"),
                ):
                    for path in sorted(assets.glob(pattern)):
                        check_asset(app, path, expected, kind, problems, warnings, args)
            if (app / "screenshots").is_dir():
                found = sorted((app / "screenshots").glob("**/*.png"))
                shots += len(found)
                check_screenshots(app, found, problems, warnings, args)

    for warning in warnings:
        print("WARN      %s" % warning)
    for problem in problems:
        print("PROBLEM   %s" % problem)
    print("\n%d screenshot(s), %d problem(s), %d warning(s)"
          % (shots, len(problems), len(warnings)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
