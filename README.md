# Portfolio app websites (premium)

Public GitHub Pages sites for every portfolio Android app — quality bar matched to
**Kitchen Buddy** and **Daily Affirmation**.

Each app folder includes:

- `index.html` — premium marketing + legal entry
- `privacy.html` — full privacy policy (TOC, Play-ready)
- `terms.html` — terms of use
- `delete-data.html` — **data deletion request** URL for Play Console
- `styles.css` — Fraunces + DM Sans, ambient background, phone mockup, Free vs Premium

**Live hub:** https://13ond21.github.io/portfolio-websites/  
**★ Bookmark all home pages:** https://13ond21.github.io/portfolio-websites/apps.html  
**Repo:** https://github.com/13ond21/portfolio-websites  

## Regenerate

```powershell
python "C:\Users\corey\Desktop\App Builds\portfolio-24\factory\publish_legal_sites.py"
cd "C:\Users\corey\Desktop\App Builds\portfolio-24\github-pages-publish"
git add -A
git commit -m "Upgrade legal sites to premium quality"
git push
```
