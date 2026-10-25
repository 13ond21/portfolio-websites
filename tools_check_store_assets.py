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

  Two spellings, one deliverable. The glob used to be "*feature*graphic*.png" alone, which is
  how fifteen of this repo's sixteen feature graphics are named; the sixteenth,
  perimenopause-tracker/assets/feature.png, went unmeasured. It is one of three byte-identical
  copies of the PeriLog feature graphic (this app folder, assets/hub/, and the app repo's own
  website dir), so the file whose look is the brand's was the one file nothing looked at.

BRAND MARKS ARE PINNED, NOT CROPPED
  assets/icon.png is the PeriLog mark, and it is the busiest asset here: the favicon of four
  pages, the 34-38 px brand chip in their headers, and the app's Play icon. It is a rounded
  tile drawn across a 512x512 canvas with an eight-to-nine pixel transparent margin - that
  margin is the safe zone the launcher mask and the pages' own border-radius rely on - and its
  outermost ring of opaque pixels is the mark's own peach bevel rather than a background
  fringe. Measured, it therefore has no padding to crop, and cropping it would cut the bevel
  and its anti-aliasing while breaking the square those four placements assume. So the mark is
  asserted here instead of cropped: the size the placements were laid out around, the alpha
  channel they need, four transparent corners, and a margin small enough to prove nobody has
  letterboxed it.

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
# The second spelling of the feature graphic. It is checked for its size - a landing-page hero
# that is not 1024x500 is what breaks silently - but not for alpha: this spelling is the *web*
# copy, and the upload Play validates is the app repo's own source/play-store-assets/
# feature-graphic.png, which has carried no alpha channel since the flatten pass.
FEATURE_PLAIN = "feature.png"
# Brand marks, by app folder: (size, widest transparent margin in px, least opaque coverage).
# The margin ceiling is a letterboxing alarm, not a target: the shipped tile sits at 8-9 px of
# 512 (1.6%), so 12 catches a re-export that has been scaled down inside its canvas without
# failing a file that is merely anti-aliased. Coverage floors the same way: 12.5% of this tile
# is transparent by design, so 60% leaves room for the rounding while catching a shrink.
BRAND_MARKS = {
    "perimenopause-tracker": (ICON, 12, 0.60),
}
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


def check_asset(app, path, expected, kind, problems, warnings, args, alpha_matters=True):
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
    if alpha_matters and kind == "graphic" and im.mode.endswith("A") and im.getchannel("A").getextrema()[0] < 255:
        warnings.append("%s: %s has transparent pixels; Play wants no alpha on the feature graphic"
                        % (app.name, path.name))
    if not args.quiet:
        print("  %-16s %-10s %-28s %dx%d" % (app.name, kind, path.name, size[0], size[1]))
    return size


def check_brand_mark(app, path, spec, problems, args):
    """Assert the brand mark is still the tile the page layouts were designed around.

    The four placements (the four pages' favicons, the two header chips that scale it to 34 and
    38 px, the Play icon) all assume the same thing: a square canvas with the rounded tile drawn
    across it and transparent corners. The realistic way that breaks is a well-meant "remove the
    padding" crop, which is why the padding is pinned here rather than removed.
    """
    size, max_margin, min_coverage = spec
    im = Image.open(path).convert("RGBA")

    if im.size != size:
        problems.append("%s: %s is %dx%d, but the brand chip and the four favicons assume %dx%d"
                        % (app.name, path.name, im.size[0], im.size[1], size[0], size[1]))
        return im.size

    alpha = im.getchannel("A")
    box = alpha.getbbox()   # the tile's own edges: everything the canvas actually draws
    if box is None:
        problems.append("%s: %s is entirely transparent" % (app.name, path.name))
        return im.size

    left, top, right, bottom = box
    margin = max(left, top, size[0] - right, size[1] - bottom)
    if margin > max_margin:
        problems.append("%s: %s clears %d px of transparent margin, past the %d px the placements allow"
                        % (app.name, path.name, margin, max_margin))

    corners = [alpha.getpixel(p) for p in ((0, 0), (size[0] - 1, 0), (0, size[1] - 1), (size[0] - 1, size[1] - 1))]
    if any(c > 0 for c in corners):
        problems.append("%s: %s has an opaque corner (%s), so the tile's rounded corners are gone"
                        % (app.name, path.name, corners))

    opaque = sum(i * n for i, n in enumerate(alpha.histogram())) / (255.0 * size[0] * size[1])
    if opaque < min_coverage:
        problems.append("%s: %s is only %.1f%% opaque: the mark has been shrunk inside its canvas"
                        % (app.name, path.name, opaque * 100))

    if not args.quiet:
        print("  %-16s %-10s %-28s %dx%d  margin %d px, %.1f%% opaque"
              % (app.name, "brand", path.name, size[0], size[1], margin, opaque * 100))
    return im.size


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
                for pattern, expected, kind, alpha_matters in (
                    ("*feature*graphic*.png", FEATURE_GRAPHIC, "graphic", True),
                    (FEATURE_PLAIN, FEATURE_GRAPHIC, "graphic", False),
                    ("*icon*.png", ICON, "icon", True),
                ):
                    for path in sorted(assets.glob(pattern)):
                        check_asset(app, path, expected, kind, problems, warnings, args, alpha_matters)

                spec = BRAND_MARKS.get(app.name)
                if spec is not None:
                    mark = assets / "icon.png"
                    if mark.is_file():
                        check_brand_mark(app, mark, spec, problems, args)
                    else:
                        problems.append("%s: assets/icon.png is missing - it is the four favicons and "
                                        "the header chips" % app.name)
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
