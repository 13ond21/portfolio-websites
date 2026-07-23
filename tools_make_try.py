from pathlib import Path
import urllib.parse
import urllib.request

root = Path(__file__).resolve().parent
src = (root / "apps.html").read_text(encoding="utf-8")

# New public URL
old_url = "https://13ond21.github.io/portfolio-websites/apps.html"
new_url = "https://13ond21.github.io/portfolio-websites/try.html"

t = src
t = t.replace(old_url, new_url)
t = t.replace('href="apps.html"', 'href="try.html"')
t = t.replace("assets/hub/qr-apps-hub.png", "assets/hub/qr-try-hub.png")
t = t.replace("<h1>Try our Android apps</h1>", "<h1>Closed testing apps</h1>")
t = t.replace(
    "<title>Try our Android apps — closed testing</title>",
    "<title>Closed testing apps — join &amp; install</title>",
)
t = t.replace(
    'content="Try our Android apps — closed testing"',
    'content="Closed testing apps — join &amp; install"',
)

# Unmissable banner under hero eyebrow
banner = """
        <p class="hero-eyebrow">Hand this page to testers · scan · install</p>
        <div class="note" style="margin:0 0 1rem;font-weight:700">
          Updated hub · closed testing only · 6 apps · UK Pay Calc not listed
        </div>
        <h1>Closed testing apps</h1>
"""
# if we already replaced h1, fix structure carefully
old_block = """        <p class="hero-eyebrow">Hand this page to testers · scan · install</p>
        <h1>Closed testing apps</h1>"""
if old_block in t:
    t = t.replace(old_block, banner.strip() + "\n", 1)

(root / "try.html").write_text(t, encoding="utf-8")
print("wrote try.html", (root / "try.html").stat().st_size)
print("Join closed:", "Join closed testing" in t)
print("old All app home:", "All app home pages" in t)
print("UK Pay in cards:", "UK Pay Calc" in t)

# QR
api = (
    "https://api.qrserver.com/v1/create-qr-code/"
    f"?size=600x600&ecc=M&margin=16&format=png&data={urllib.parse.quote(new_url, safe='')}"
)
data = urllib.request.urlopen(api, timeout=30).read()
qr_path = root / "assets" / "hub" / "qr-try-hub.png"
qr_path.write_bytes(data)
print("qr", qr_path, len(data))

# Replace apps.html with a hard redirect so even partial caches get nudged
# when the CDN refreshes
redirect = f"""<!DOCTYPE html>
<html lang="en-GB">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Redirecting to closed testing…</title>
  <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate" />
  <meta http-equiv="refresh" content="0; url=try.html" />
  <link rel="canonical" href="{new_url}" />
  <script>location.replace("try.html");</script>
</head>
<body style="font-family:system-ui,sans-serif;padding:2rem;max-width:36rem;margin:auto;line-height:1.5">
  <h1>Moved</h1>
  <p>The tester hub is now here (closed testing only, no UK Pay Calc):</p>
  <p><a href="try.html"><strong>{new_url}</strong></a></p>
  <p>If you still see an old “All app home pages” list, you are on a cached page — open the link above.</p>
</body>
</html>
"""
(root / "apps.html").write_text(redirect, encoding="utf-8")
print("apps.html is now redirect")
