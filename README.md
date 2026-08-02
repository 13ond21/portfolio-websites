# App websites (premium)

Public GitHub Pages sites for portfolio Android apps — quality bar matched to
**Kitchen Buddy** and **Daily Affirmation**.

**★ Live apps hub:** https://13ond21.github.io/portfolio-websites/try.html  
(The root https://13ond21.github.io/portfolio-websites/ redirects here.)

Each portfolio app folder includes:

- `index.html` — premium marketing + legal entry
- `privacy.html` — full privacy policy
- `terms.html` — terms of use
- `delete-data.html` — data deletion request URL for Play Console
- `styles.css` — premium theme

**Repo:** https://github.com/13ond21/portfolio-websites  

## Regenerate

```powershell
python "C:\Users\corey\Desktop\App Builds\portfolio-24\factory\publish_legal_sites.py"
cd "C:\Users\corey\Desktop\App Builds\portfolio-24\github-pages-publish"
git add -A
git commit -m "Update app websites"
git push
```
