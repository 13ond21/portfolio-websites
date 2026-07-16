# Portfolio app legal websites

Public GitHub Pages site for Android Play Console:

- Privacy policy
- Terms of use
- **Data deletion request** (required URL)

**Live:** https://13ond21.github.io/portfolio-websites/

**Developer:** Lucky Tools (Northern Ireland)  
**Contact:** autoaccentsni@gmail.com

## Deploy

Pages: **Settings → Pages → Deploy from branch → `main` / root**

## Regenerate locally

```powershell
python "C:\Users\corey\Desktop\App Builds\portfolio-24\factory\publish_legal_sites.py"
cd "C:\Users\corey\Desktop\App Builds\portfolio-24\github-pages-publish"
git add -A
git commit -m "Update legal sites"
git push
```
