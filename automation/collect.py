"""Collect news from RSS feeds and group the same story across sources.

A story covered by more sources is treated as more "trending" — and having
several sources also lets the writer cross-check facts.
"""
import calendar
import html
import re
import time
from datetime import datetime, timezone

import feedparser
import requests

UA = "Mozilla/5.0 (compatible; KhabarKaroBot/1.0; +https://jadavjay18.github.io/khabarkaro/about/)"
STOP = set("""a an the and or of to in on for at by with from as is are was were be been it its this that
these those after before over under into about amid new says said will can may could would should has have had
not no vs v up out more most than india indian""".split())


def clean(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def tokens(title):
    words = re.findall(r"[a-z0-9]+", title.lower())
    return {w for w in words if w not in STOP and len(w) > 2}


def fetch_feed(feed, max_age_hours, log):
    try:
        r = requests.get(feed["url"], headers={"User-Agent": UA}, timeout=20)
        r.raise_for_status()
    except Exception as e:
        log(f"feed FAIL {feed['source']} ({feed['category']}): {e}")
        return []
    parsed = feedparser.parse(r.content)
    now = time.time()
    items = []
    for e in parsed.entries[:40]:
        t = e.get("published_parsed") or e.get("updated_parsed")
        ts = calendar.timegm(t) if t else now  # feedparser gives UTC struct_time
        if now - ts > max_age_hours * 3600:
            continue
        title = clean(e.get("title"))
        link = e.get("link", "")
        if not title or not link.startswith("http"):
            continue
        items.append({
            "source": feed["source"],
            "cat_hint": feed["category"],
            "title": title,
            "link": link,
            "summary": clean(e.get("summary") or e.get("description"))[:1200],
            "ts": ts,
            "tok": tokens(title),
        })
    log(f"feed ok   {feed['source']} ({feed['category']}): {len(items)} recent items")
    return items


def similar(a, b):
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return inter / min(len(a), len(b)) if min(len(a), len(b)) >= 3 else 0.0


def cluster(items, threshold=0.5):
    clusters = []
    for it in sorted(items, key=lambda x: -x["ts"]):
        best, best_score = None, 0.0
        for c in clusters:
            s = similar(it["tok"], c["tok"])
            if s > best_score:
                best, best_score = c, s
        if best and best_score >= threshold:
            best["items"].append(it)
            best["tok"] |= it["tok"]
        else:
            clusters.append({"items": [it], "tok": set(it["tok"])})
    for c in clusters:
        c["sources"] = sorted({i["source"] for i in c["items"]})
        c["newest"] = max(i["ts"] for i in c["items"])
        hints = [i["cat_hint"] for i in c["items"]]
        c["cat_hint"] = max(set(hints), key=hints.count)
        c["key"] = " ".join(sorted(c["items"][0]["tok"]))
    # more sources first, then newest
    clusters.sort(key=lambda c: (len(c["sources"]), c["newest"]), reverse=True)
    return clusters


def collect(feeds, max_age_hours, log):
    items = []
    for f in feeds:
        items += fetch_feed(f, max_age_hours, log)
    log(f"collected {len(items)} items from {len(feeds)} feeds")
    return cluster(items)


def fetch_article_text(url, log, max_chars=6000):
    """Best-effort full-text fetch. Returns '' when blocked or unreadable."""
    try:
        import trafilatura
        r = requests.get(url, headers={"User-Agent": UA}, timeout=20)
        if r.status_code != 200:
            return ""
        text = trafilatura.extract(r.text, include_comments=False, include_tables=False) or ""
        return text[:max_chars]
    except Exception as e:
        log(f"article fetch failed {url}: {e}")
        return ""


def now_iso():
    return datetime.now(timezone.utc).isoformat()
