# KhabarKaro

Trending news in Hinglish — automatically collected, written, and published.

Live site: https://jadavjay18.github.io/khabarkaro

A [Super Deals India](https://t.me/FlipkartMeeshoMyntraAjio) network site.

## How it works

- `config.json` — site name, categories, Super Deals India links, disclosure text
- `content/posts/*.json` — one file per news post (the automation writes these)
- `content/pages/*.json` — About, Contact, Privacy Policy, Disclaimer
- `assets/style.css` — the theme (mobile-first)
- `site_builder/` — Python builder that turns everything into the website
- `.github/workflows/deploy.yml` — builds and publishes the site on every push

## Post format

```json
{
  "slug": "short-url-name",
  "title": "Headline in Hinglish",
  "summary": "One-line summary",
  "category": "tech",
  "date": "2026-11-26T10:30:00+05:30",
  "image": "https://... (optional)",
  "key_points": ["...", "..."],
  "body": ["paragraph 1", "paragraph 2"],
  "why_it_matters": "...",
  "source": {"name": "Source name", "url": "https://..."},
  "products": [{"name": "...", "price": "1,499", "mrp": "2,999", "off": 50, "store": "Amazon", "url": "https://...", "image": "https://..."}],
  "sensitive": false
}
```

`sensitive: true` hides affiliate products (for news on deaths, disasters, violence).

## Build locally

```
pip install -r requirements.txt
python -m site_builder.build
```
