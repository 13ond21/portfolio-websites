#!/usr/bin/env python3
"""Fail if a tile on try.html disagrees with itself.

WHAT THIS GUARDS
  Each tile on the hub carries `data-live`, and the page's own script reads it to set the status
  pill, the Google Play button's href and disabled state, and the "not public yet" note - and to
  sort live apps first. The static markup therefore has to agree with the attribute, because a
  reader with JavaScript off (and every crawler) sees only the markup.

  The defect this exists for: four tiles carried `data-live="true"` while their markup said
  "Coming soon" with a greyed, `href="#"` button, so with JavaScript on the hub advertised a
  Google Play listing the page could not honour, and without it the attribute and the badge
  contradicted each other. See PLAY_CONSOLE_URLS.md: every app here is "closed testing unless
  marked live", so `true` is a claim that has to be earned.

USAGE
    python tools_check_hub_tiles.py          # report every tile, exit 1 if any disagrees
    python tools_check_hub_tiles.py --quiet  # only the verdict
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
PAGE = ROOT / "try.html"


def tiles(text):
    for block in re.findall(r'(?s)<article class="app-tile"(.*?)</article>', text):
        yield (
            re.search(r'data-id="([^"]+)"', block).group(1),
            re.search(r'data-live="([^"]+)"', block).group(1),
            re.search(r'class="pill ([a-z]+)[^"]*"[^>]*>([^<]+)<', block),
            re.search(r'<a class="btn-play[^"]*" href="([^"]+)"([^>]*)>', block),
        )


def main(argv=None):
    parser = argparse.ArgumentParser(prog="tools_check_hub_tiles.py")
    parser.add_argument("--quiet", action="store_true", help="print only the verdict")
    args = parser.parse_args(argv)

    text = PAGE.read_text(encoding="utf-8")
    problems = []
    count = 0
    for tile_id, live, pill, cta in tiles(text):
        count += 1
        if pill is None or cta is None:
            problems.append("%s: tile has no status pill or Play button" % tile_id)
            continue
        pill_class, pill_text = pill.group(1), pill.group(2).strip()
        href, attrs = cta.group(1), cta.group(2)
        links_to_play = href.startswith("https://play.google.com/store/apps/details")
        if live == "true":
            if pill_class != "live" or pill_text != "On Google Play" or not links_to_play \
                    or "aria-disabled" in attrs:
                problems.append("%s: data-live=true but pill=%r/%r href=%r%s"
                                % (tile_id, pill_class, pill_text, href[:46],
                                   " (aria-disabled)" if "aria-disabled" in attrs else ""))
        else:
            if pill_class != "soon" or pill_text != "Coming soon" or href != "#" \
                    or "aria-disabled" not in attrs:
                problems.append("%s: data-live=false but pill=%r/%r href=%r"
                                % (tile_id, pill_class, pill_text, href[:46]))
        if not args.quiet:
            print("  %-24s live=%-5s pill=%-5s %-16s %s"
                  % (tile_id, live, pill_class, pill_text,
                     "links to Play" if links_to_play else href))

    if not count:
        print("no app tiles found in %s" % PAGE.name, file=sys.stderr)
        return 2
    for problem in problems:
        print("MISMATCH  %s" % problem)
    print("\n%d tile(s), %d mismatch(es)" % (count, len(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
