from pathlib import Path
import re

p = Path(__file__).resolve().parent / "try.html"
t = p.read_text(encoding="utf-8")

t2 = re.sub(
    r'\s*<a class="btn-test"[^>]*>\s*Join closed testing\s*</a>\s*',
    "\n              ",
    t,
    flags=re.I,
)

t2 = t2.replace(
    "Tap <strong>Join closed testing</strong>, accept, then install from Play.",
    "Tap <strong>Open on Play Store</strong> to install (you must be on the tester list).",
)
t2 = t2.replace(
    """        <ol>
          <li>We add your Google Play email as a tester.</li>
          <li>Tap <strong>Join closed testing</strong> and accept.</li>
          <li>Install from the Play Store.</li>
        </ol>""",
    """        <ol>
          <li>We add your Google Play email as a tester.</li>
          <li>Tap <strong>Open on Play Store</strong> and install.</li>
        </ol>""",
)

# Drop unused btn-test styles to keep clean
t2 = re.sub(
    r"\s*\.btn-test \{[^}]+\}\s*\.btn-test:hover \{[^}]+\}",
    "\n",
    t2,
)

p.write_text(t2, encoding="utf-8")
print("Join closed left:", t2.count("Join closed testing"))
print("Open on Play:", t2.count("Open on Play Store"))
print("btn-test left:", t2.count("btn-test"))
