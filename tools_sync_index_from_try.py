"""Make index.html the public apps marketing page (same as try.html)."""
from pathlib import Path

root = Path(__file__).resolve().parent
try_html = (root / "try.html").read_text(encoding="utf-8")

index = try_html
# Canonical / OG for site root
index = index.replace(
    "https://13ond21.github.io/portfolio-websites/try.html",
    "https://13ond21.github.io/portfolio-websites/",
)
# Nav: this page is Home; Apps jumps to #apps
old_nav = """      <nav class="nav" aria-label="Main">
        <a href="index.html">Home</a>
        <a href="try.html" aria-current="page">Apps</a>
        <a href="mailto:autoaccentsni@gmail.com" class="nav-cta">Contact</a>
      </nav>"""
new_nav = """      <nav class="nav" aria-label="Main">
        <a href="index.html" aria-current="page">Home</a>
        <a href="#apps">Apps</a>
        <a href="mailto:autoaccentsni@gmail.com" class="nav-cta">Contact</a>
      </nav>"""
if old_nav not in index:
    raise SystemExit("nav block not found — try.html structure changed")
index = index.replace(old_nav, new_nav)

# QR / share link stays on try.html forever (printed QR does not change)
index = index.replace(
    'var PAGE_URL = "https://13ond21.github.io/portfolio-websites/";',
    'var PAGE_URL = "https://13ond21.github.io/portfolio-websites/try.html";',
)
# Show both URLs in the chip area: prefer displaying permanent try.html for QR
index = index.replace(
    '<code id="fav-url">https://13ond21.github.io/portfolio-websites/</code>',
    '<code id="fav-url">https://13ond21.github.io/portfolio-websites/try.html</code>',
)

index = index.replace("styles.css?v=20260716e", "styles.css?v=20260719a")
# Title: home
index = index.replace(
    "<title>Our Android apps — Google Play</title>",
    "<title>Our Android apps — Google Play</title>",
)

(root / "index.html").write_text(index, encoding="utf-8")

# Sanity
for name in ("try.html", "index.html"):
    t = (root / name).read_text(encoding="utf-8")
    assert "fridge-share" in t, name
    assert "Fridge Share" in t, name
    assert "one QR" not in t, name
print("OK: index.html = apps marketing page; Fridge Share on try + index")
