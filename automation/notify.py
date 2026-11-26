"""Share newly published posts to the KhabarKaro Telegram channel.

Runs after the site is deployed (so links and share images work).
NEW_POSTS = space-separated post slugs from this run.
Needs secret TELEGRAM_BOT_TOKEN and config.json "telegram_channel".
"""
import html
import json
import os
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
API = "https://api.telegram.org/bot{token}/{method}"


def find_post(slug):
    for path in (ROOT / "content" / "posts").glob(f"*-{slug}.json"):
        p = json.loads(path.read_text(encoding="utf-8"))
        if p.get("slug") == slug:
            return p
    return None


def caption_for(p, cfg, url):
    cat = next((c["name"] for c in cfg["categories"] if c["slug"] == p["category"]), "")
    tag = "#" + "".join(ch for ch in cat if ch.isalnum()) if cat else ""
    points = "\n".join(f"• {html.escape(k)}" for k in p.get("key_points", [])[:3])
    text = f"<b>{html.escape(p['title'])}</b>\n\n{points}\n\n👉 <a href=\"{url}\">Poori khabar padho</a>\n\n{tag} #KhabarKaro"
    if len(text) > 1000:  # Telegram caption limit is 1024
        text = f"<b>{html.escape(p['title'])}</b>\n\n{html.escape(p.get('summary', ''))[:500]}\n\n👉 <a href=\"{url}\">Poori khabar padho</a>\n\n{tag} #KhabarKaro"
    return text


def send(token, method, payload):
    r = requests.post(API.format(token=token, method=method), json=payload, timeout=30)
    data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    return r.status_code == 200 and data.get("ok"), data.get("description", r.text[:200])


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    slugs = os.environ.get("NEW_POSTS", "").split()
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    channel = cfg.get("telegram_channel", "").strip()
    if not slugs:
        print("no new posts to share")
        return 0
    if not token or not channel:
        print("Telegram not configured (TELEGRAM_BOT_TOKEN secret / telegram_channel in config.json) — skipping")
        return 0
    for slug in slugs:
        p = find_post(slug)
        if not p:
            print(f"post {slug} not found")
            continue
        url = f"{cfg['base_url']}/post/{slug}/"
        photo = p.get("image") or f"{cfg['base_url']}/cards/{slug}.png"
        caption = caption_for(p, cfg, url)
        buttons = {"inline_keyboard": [[{"text": "📰 Poori khabar padho", "url": url}],
                                       [{"text": "🛍️ Aaj ki Deals", "url": cfg["super_deals_india"]["telegram"]}]]}
        ok, err = send(token, "sendPhoto", {"chat_id": channel, "photo": photo, "caption": caption,
                                            "parse_mode": "HTML", "reply_markup": buttons})
        if not ok:
            print(f"sendPhoto failed for {slug} ({err}); sending text instead")
            ok, err = send(token, "sendMessage", {"chat_id": channel, "text": caption, "parse_mode": "HTML",
                                                  "reply_markup": buttons})
        print(("shared " if ok else f"FAILED ({err}) ") + slug)
        time.sleep(2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
