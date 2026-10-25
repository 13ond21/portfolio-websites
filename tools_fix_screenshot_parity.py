#!/usr/bin/env python3
"""Align the app sites' screenshot presentation with the real 2:1 store captures.

WHAT THIS FIXES (measured 2026-10-08, decibel-meter-pro and pa-mic)

  * `width="720" height="1400"` on the hero carousel images. The captures are 1440x2880,
    i.e. exactly 1:2.00, and 720x1400 is 1:1.944 - a 2.8% wrong aspect ratio handed to the
    browser as its layout hint, which is the one thing an intrinsic-size hint must not be.
    Corrected to 720x1440: half the real capture, ratio-true.
  * The gallery's `.shot-frame` images carried no `width`/`height` at all while the hero
    next to them did, so the one column the page reserves space for was the one column the
    browser could not reserve space for. They now carry the same 720x1440.

A CLAIM THAT WAS CHECKED AND DROPPED

  This tool was written expecting to add `width`/`height` to pa-mic's brand icon as well,
  because the landing page looked like it was missing what the legal pages had. It was not:
  all four pa-mic pages and all four decibel-meter-pro pages give the brand icon 38x38, and
  the pattern below matched zero times - which is what the exact-match guard is for. The
  suspected defect was not there, so there is no edit for it.

WHAT IT DOES NOT DO
  It does not touch the copy, the colours or the `aspect-ratio` declarations - those live in
  each app's `styles.css`, and the notes on them are there. It refuses to write anything if a
  pattern does not match the expected number of times, so a page that has been edited by hand
  since this was written stops the run instead of being silently rewritten.

USAGE
    python tools_fix_screenshot_parity.py            # dry run: report what would change
    python tools_fix_screenshot_parity.py --write    # apply
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent

# (file, pattern, replacement, expected matches)
EDITS = [
    # ---- decibel-meter-pro ------------------------------------------------------------------
    (
        "decibel-meter-pro/index.html",
        r'width="720" height="1400"',
        'width="720" height="1440"',
        3,
    ),
    (
        "decibel-meter-pro/index.html",
        r'<div class="shot-frame"><img src="(screenshots/[^"]+)" alt="',
        r'<div class="shot-frame"><img src="\1" width="720" height="1440" alt="',
        3,
    ),
    # ---- pa-mic -----------------------------------------------------------------------------
    (
        "pa-mic/index.html",
        r'width="720" height="1400"',
        'width="720" height="1440"',
        3,
    ),
    (
        "pa-mic/index.html",
        r'<div class="shot-frame"><img src="(screenshots/[^"]+)" alt="',
        r'<div class="shot-frame"><img src="\1" width="720" height="1440" alt="',
        5,
    ),
]

# (file, regex that must hold afterwards, expected count). The invariant, not the edit.
CHECKS = [
    # No half-of-the-wrong-ratio hint may survive anywhere in either landing page.
    ("decibel-meter-pro/index.html", r'height="1400"', 0),
    ("pa-mic/index.html", r'height="1400"', 0),
    # Every hero and gallery image now carries the 1:2.00 reservation: 3 + 3 and 3 + 5.
    ("decibel-meter-pro/index.html", r'<img[^>]* width="720" height="1440"', 6),
    ("pa-mic/index.html", r'<img[^>]* width="720" height="1440"', 8),
    # And the brand icon still carries the 38x38 every page gives it (checked, not assumed).
    ("decibel-meter-pro/index.html", r'class="brand"[^>]*><img[^>]* width="38" height="38"', 1),
    ("pa-mic/index.html", r'class="brand"[^>]*><img[^>]* width="38" height="38"', 1),
]


def main(argv=None):
    parser = argparse.ArgumentParser(prog="tools_fix_screenshot_parity.py")
    parser.add_argument("--write", action="store_true", help="apply the edits (default: dry run)")
    args = parser.parse_args(argv)

    problems = 0
    changed = 0

    # What must be true once the edits have been applied. Checked separately from the edits
    # themselves, because the *replacement* of the gallery rule is a regex template and a
    # template cannot be counted as if it were a pattern - the first draft of this tool tried
    # that and raised "invalid group reference 1" on the re-run.
    for name, expectation, expected in CHECKS:
        path = ROOT / name
        if not path.is_file():
            print("MISSING   %s" % name)
            problems += 1
            continue

        found = len(re.findall(expectation, path.read_text(encoding="utf-8")))
        if found == expected:
            print("OK        %s: %d of %r" % (name, found, expectation[:58]))
        else:
            print("PROBLEM   %s: %d of %r, expected %d" % (name, found, expectation[:58], expected))
            problems += 1

    for name, pattern, replacement, expected in EDITS:
        path = ROOT / name
        if not path.is_file():
            print("MISSING   %s" % name)
            problems += 1
            continue

        text = path.read_text(encoding="utf-8")
        found = len(re.findall(pattern, text))

        if found == 0:
            print("OK        %s: nothing left to rewrite for %r" % (name, pattern[:58]))
            continue

        if found != expected:
            print("PROBLEM   %s: %d match(es) for %r, expected %d - refusing to touch it"
                  % (name, found, pattern[:58], expected))
            problems += 1
            continue

        changed += 1
        if args.write:
            path.write_text(re.sub(pattern, replacement, text), encoding="utf-8")

        print("%-9s %s: %d occurrence(s) of %r"
              % ("REWROTE" if args.write else "WOULD", name, found, pattern[:58]))

    print("\n%d file edit(s) %s, %d problem(s)"
          % (changed, "applied" if args.write else "pending (dry run)", problems))

    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
