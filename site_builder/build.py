"""KhabarKaro static site builder.

Reads config.json + content/posts/*.json + content/pages/*.json
and writes the full website into _site/.

Run:  python -m site_builder.build
"""
import json
import math
import re
import shutil
import time
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .cards import make_card

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "_site"
TEMPLATES = Path(__file__).resolve().parent / "templates"
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,120}$")


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def parse_date(s):
    # Accepts "2026-11-26" or full ISO "2026-11-26T10:30:00+05:30"
    if len(s) == 10:
        return datetime.fromisoformat(s + "T00:00:00+05:30")
    d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def load_posts(cfg):
    cats = {c["slug"]: c for c in cfg["categories"]}
    posts = []
    for path in sorted((ROOT / "content" / "posts").glob("*.json")):
        try:
            p = load_json(path)
        except Exception as e:  # never let one bad file break the site
            print(f"SKIP {path.name}: invalid JSON ({e})")
            continue
        if p.get("draft"):
            continue
        slug = p.get("slug", "")
        if not SLUG_RE.match(slug) or p.get("category") not in cats or not p.get("title"):
            print(f"SKIP {path.name}: missing/invalid slug, title or category")
            continue
        d = parse_date(p["date"])
        body = p.get("body", [])
        words = sum(len(x.split()) for x in body) + len(" ".join(p.get("key_points", [])).split())
        p.update(
            cat=cats[p["category"]],
            dt=d,
            date_label=f"{d.day} {MONTHS[d.month - 1]} {d.year}",
            read_min=p.get("read_min") or max(1, math.ceil(words / 200)),
            url=f"/post/{slug}/",
            author=p.get("author", "KhabarKaro Desk"),
            products=p.get("products", []),
            sensitive=bool(p.get("sensitive")),
        )
        posts.append(p)
    posts.sort(key=lambda x: x["dt"], reverse=True)
    return posts


def jsonld(p, cfg):
    data = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": p["title"][:110],
        "description": p.get("summary", ""),
        "datePublished": p["dt"].isoformat(),
        "dateModified": p["dt"].isoformat(),
        "inLanguage": cfg["language"],
        "mainEntityOfPage": cfg["base_url"] + p["url"],
        "author": {"@type": "Organization", "name": p["author"]},
        "publisher": {"@type": "Organization", "name": cfg["site_name"]},
    }
    if p.get("share_image"):
        data["image"] = [p["share_image"]]
    # escape "</" so the JSON can't close the <script> tag
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def write(rel, html):
    path = OUT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


def build():
    cfg = load_json(ROOT / "config.json")
    base = cfg["base_path"].rstrip("/")
    posts = load_posts(cfg)

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    shutil.copytree(ROOT / "assets", OUT / "assets")
    (OUT / ".nojekyll").write_text("")

    # Headline cards: share image for every post, picture when no photo
    for p in posts:
        try:
            make_card(p["title"], p["cat"]["name"], p["cat"]["color"], cfg["name_first"], cfg["name_second"],
                      ROOT / ".card-cache" / f"{p['slug']}.png")
            (OUT / "cards").mkdir(exist_ok=True)
            shutil.copy(ROOT / ".card-cache" / f"{p['slug']}.png", OUT / "cards" / f"{p['slug']}.png")
            card = f"{base}/cards/{p['slug']}.png"
        except Exception as e:
            print(f"card failed for {p['slug']}: {e}")
            card = None
        p["card"] = card
        p["thumb"] = p.get("image") or card
        p["share_image"] = p.get("image") or (cfg["base_url"] + f"/cards/{p['slug']}.png" if card else None)

    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html"]))
    common = dict(cfg=cfg, base=base, year=datetime.now().year, build_id=int(time.time()))

    # Homepage
    featured = posts[0] if posts else None
    trending = posts[1:5]
    latest = posts[5:17] if len(posts) > 5 else []
    cat_sections = []
    for c in cfg["categories"]:
        cp = [p for p in posts if p["category"] == c["slug"]][: cfg.get("posts_per_category_section", 3)]
        if cp:
            cat_sections.append({"cat": c, "posts": cp})
    write("index.html", env.get_template("index.html").render(
        **common, active="home", featured=featured, trending=trending, latest=latest, cat_sections=cat_sections[:6]))

    # Posts
    tpl = env.get_template("post.html")
    for p in posts:
        same = [r for r in posts if r is not p and r["category"] == p["category"]]
        other = [r for r in posts if r is not p and r["category"] != p["category"]]
        related = (same + other)[:4]
        p["jsonld"] = jsonld(p, cfg)
        write(f"post/{p['slug']}/index.html", tpl.render(**common, active=p["category"], p=p, related=related))

    # Categories
    tpl = env.get_template("category.html")
    for c in cfg["categories"]:
        cp = [p for p in posts if p["category"] == c["slug"]]
        write(f"category/{c['slug']}/index.html", tpl.render(**common, active=c["slug"], cat=c, posts=cp))

    # Static pages
    tpl = env.get_template("page.html")
    pages = []
    for path in sorted((ROOT / "content" / "pages").glob("*.json")):
        pg = load_json(path)
        pg["html"] = pg["html"].replace("{{contact_email}}", cfg.get("contact_email", ""))
        pages.append(pg)
        write(f"{pg['slug']}/index.html", tpl.render(**common, active=None, page=pg))

    # Search page + index
    write("search/index.html", env.get_template("search.html").render(**common, active=None))
    search_items = [
        {"title": p["title"], "summary": p.get("summary", ""), "cat": p["cat"]["name"],
         "color": p["cat"]["color"], "url": p["url"], "date": p["date_label"]}
        for p in posts
    ]
    write("search.json", json.dumps(search_items, ensure_ascii=False))

    # 404
    write("404.html", env.get_template("page.html").render(
        **common, active=None,
        page={"title": "Page nahi mila", "slug": "404",
              "html": f'<p>Yeh page exist nahi karta. <a href="{base}/" style="color:var(--accent)">Homepage par jao →</a></p>'}))

    # RSS feed (latest 30)
    items = []
    for p in posts[:30]:
        link = cfg["base_url"] + p["url"]
        items.append(
            "<item>"
            f"<title>{escape(p['title'])}</title><link>{link}</link><guid>{link}</guid>"
            f"<pubDate>{format_datetime(p['dt'])}</pubDate>"
            f"<category>{escape(p['cat']['name'])}</category>"
            f"<description>{escape(p.get('summary', ''))}</description>"
            "</item>")
    write("feed.xml",
          '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
          f"<title>{escape(cfg['site_name'])}</title><link>{cfg['base_url']}/</link>"
          f"<description>{escape(cfg['description'])}</description><language>hi</language>"
          + "".join(items) + "</channel></rss>")

    # Sitemap + robots
    urls = ["/"] + [f"/category/{c['slug']}/" for c in cfg["categories"]] \
        + [f"/{pg['slug']}/" for pg in pages] + [p["url"] for p in posts]
    write("sitemap.xml",
          '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
          + "".join(f"<url><loc>{cfg['base_url']}{u}</loc></url>" for u in urls) + "</urlset>")
    write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {cfg['base_url']}/sitemap.xml\n")

    print(f"Built {len(posts)} posts, {len(cfg['categories'])} categories, {len(pages)} pages -> {OUT}")


if __name__ == "__main__":
    build()
