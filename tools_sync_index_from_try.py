"""Keep index.html a permanent redirect to try.html (the live apps hub)."""
from pathlib import Path

root = Path(__file__).resolve().parent
target = "https://13ond21.github.io/portfolio-websites/try.html"

redirect = f"""<!DOCTYPE html>
<html lang="en-GB">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Our apps &mdash; redirecting&hellip;</title>
  <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate" />
  <meta http-equiv="refresh" content="0; url=try.html" />
  <link rel="canonical" href="{target}" />
  <meta property="og:title" content="Our Android apps &mdash; Google Play" />
  <meta property="og:url" content="{target}" />
  <script>location.replace("try.html");</script>
</head>
<body style="font-family:system-ui,sans-serif;padding:2rem;max-width:36rem;margin:auto;line-height:1.5">
  <h1>Moved</h1>
  <p>Our apps hub is now here:</p>
  <p><a href="try.html"><strong>{target}</strong></a></p>
  <p>If you still see an old page, you are on a cached version &mdash; open the link above.</p>
</body>
</html>
"""

(root / "index.html").write_text(redirect, encoding="utf-8")

# Sanity
t = (root / "try.html").read_text(encoding="utf-8")
assert "fridge-share" in t, "try.html missing Fridge Share"
assert "daily-affirmation" in t, "try.html missing Daily Affirmation"
print("OK: index.html is a permanent redirect to try.html")