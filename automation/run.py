"""KhabarKaro news automation — one run.

collect trending stories -> safety check -> Gemini writes Hinglish post
-> add affiliate products + photo -> save content/posts/*.json

Run:  python -m automation.run
Settings live in config.json under "automation".
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import collect, images, products, safety, writer

ROOT = Path(__file__).resolve().parent.parent
POSTS = ROOT / "content" / "posts"
SEEN = ROOT / "automation" / "state" / "seen.json"
LOG = ROOT / "automation" / "state" / "last_run.log"
IST = timezone(timedelta(hours=5, minutes=30))

_lines = []


def log(msg):
    line = f"{datetime.now(IST):%H:%M:%S} {msg}"
    print(line, flush=True)
    _lines.append(line)


def load_seen():
    try:
        return json.loads(SEEN.read_text(encoding="utf-8"))
    except Exception:
        return []


def already_seen(cluster, seen):
    links = {i["link"] for i in cluster["items"]}
    tok = cluster["tok"]
    for s in seen:
        if links & set(s.get("links", [])):
            return True
        if collect.similar(tok, set(s.get("tok", []))) >= 0.6:
            return True
    return False


def unique_slug(base):
    slug, n = base, 2
    while any(POSTS.glob(f"*-{slug}.json")):
        slug = f"{base}-{n}"
        n += 1
    return slug


def backfill_images():
    """Give older posts a photo once a Pexels key exists (one try per post)."""
    for path in sorted(POSTS.glob("*.json")):
        try:
            p = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if p.get("image") or p.get("image_checked") or not p.get("image_query"):
            continue
        if safety.is_tragedy(p.get("title", "") + " " + " ".join(p.get("body", []))):
            continue
        photo = images.find_photo(p["image_query"], log)
        if photo is None and not images.has_provider():
            return  # no key yet; try again next run
        if photo:
            p.update(photo)
        p["image_checked"] = True
        path.write_text(json.dumps(p, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def post_is_due(auto):
    """Hourly wake-ups (GitHub may drop some): publish only inside the posting
    window and when enough time has passed since the last automated post."""
    now = datetime.now(IST)
    start, end = auto.get("posting_hours_ist", [7, 22])
    if not (start <= now.hour < end):
        print(f"not due: {now:%H:%M} IST is outside posting hours {start}:00-{end}:00")
        return False
    last = None
    for path in POSTS.glob("*.json"):
        try:
            p = json.loads(path.read_text(encoding="utf-8"))
            if p.get("generated_by"):
                d = datetime.fromisoformat(p["date"])
                last = d if last is None or d > last else last
        except Exception:
            continue
    gap = auto.get("min_hours_between_posts", 3.5)
    if last and (now - last).total_seconds() < gap * 3600:
        print(f"not due: last post {last:%d %b %H:%M}, next after {gap}h gap")
        return False
    return True


def load_secrets():
    """The workflow passes every repo secret as JSON (ALL_SECRETS), so a new
    key added in GitHub settings works without editing the workflow."""
    raw = os.environ.get("ALL_SECRETS", "")
    if not raw:
        return
    try:
        for k, v in json.loads(raw).items():
            if k.isupper() and isinstance(v, str) and not os.environ.get(k):
                os.environ[k] = v
    except Exception:
        log("could not read ALL_SECRETS")


def main():
    load_secrets()
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    auto = cfg.get("automation", {})
    if auto.get("amazon_selftest"):
        log("AMAZON SELF-TEST (no news run)")
        for p in products.amazon_products(["chess board set", "cricket bat"], auto.get("amazon_tag", ""), log):
            log(f"  result: {p}")
        LOG.write_text("\n".join(_lines) + "\n", encoding="utf-8")
        return 0
    if auto.get("paused"):
        log("automation is PAUSED in config.json — nothing to do")
        return 0
    if os.environ.get("GITHUB_EVENT_NAME") == "schedule" and not post_is_due(auto):
        return 0  # hourly wake-up, nothing due: exit without touching any files

    categories = {c["slug"] for c in cfg["categories"]}
    feeds = json.loads((ROOT / "automation" / "feeds.json").read_text(encoding="utf-8"))["feeds"]
    seen = load_seen()

    clusters = collect.collect(feeds, auto.get("max_age_hours", 12), log)
    min_sources = auto.get("min_sources", 2)
    want = auto.get("posts_per_run", 1)
    max_tries = auto.get("max_candidates_per_run", 6)
    models = auto.get("gemini_models", ["gemini-3.8-flash", "gemini-flash-latest"])

    backfill_images()

    published, tried = 0, 0
    new_slugs = []
    for c in clusters:
        if published >= want or tried >= max_tries:
            break
        if len(c["sources"]) < min_sources:
            continue
        head = c["items"][0]["title"]
        if already_seen(c, seen):
            continue
        all_text = " ".join(i["title"] + " " + i["summary"] for i in c["items"])
        verdict = safety.classify(all_text)
        if verdict == "skip":
            log(f"SAFETY SKIP: {head}")
            seen.append({"tok": sorted(c["tok"]), "links": [i["link"] for i in c["items"]], "status": "safety-skip"})
            continue

        tried += 1
        log(f"candidate ({len(c['sources'])} sources: {', '.join(c['sources'])}): {head}")
        articles = {}
        for it in c["items"][:3]:
            text = collect.fetch_article_text(it["link"], log)
            if len(text) > 500:
                articles[it["link"]] = text
        material = sum(len(i["summary"]) for i in c["items"]) + sum(len(t) for t in articles.values())
        if material < auto.get("min_source_chars", 700):
            log(f"  skip: not enough source material ({material} chars)")
            continue

        try:
            post, model = writer.call_gemini(writer.build_prompt(c, articles), models, log)
        except Exception as e:
            log(f"  writer error: {e}")
            log("  Gemini unavailable — stopping this run; the story will be retried next run")
            break
        err = writer.validate(post, categories)
        record = {"tok": sorted(c["tok"]), "links": [i["link"] for i in c["items"]]}
        if err:
            log(f"  rejected: {err}")
            seen.append({**record, "status": "rejected"})
            continue

        sensitive = verdict == "sensitive" or bool(post.get("sensitive")) \
            or safety.classify(post["title"] + " " + " ".join(post["body"])) != "ok"
        prods = [] if sensitive else products.amazon_products(
            post.get("product_keywords", []), auto.get("amazon_tag", ""), log)

        now = datetime.now(IST)
        slug = unique_slug(writer.slugify(post.get("slug_en") or post["title"]))
        primary = c["items"][0]
        out = {
            "slug": slug,
            "title": post["title"].strip(),
            "summary": post["summary"].strip(),
            "category": post["category"],
            "date": now.isoformat(timespec="seconds"),
            "key_points": post["key_points"][:5],
            "body": post["body"][:6],
            "why_it_matters": post["why_it_matters"].strip(),
            "source": {"name": primary["source"], "url": primary["link"]},
            "also_reported_by": [s for s in c["sources"] if s != primary["source"]],
            "products": prods,
            "sensitive": sensitive,
            "generated_by": model,
            "image_query": (post.get("image_query") or "").strip()[:60],
        }
        text_all = out["title"] + " " + " ".join(out["body"])
        if not safety.is_tragedy(text_all):
            photo = images.find_photo(out["image_query"], log)
            if photo:
                out.update(photo)
        else:
            log("  image: tragedy-related story — headline card only")
        path = POSTS / f"{now:%Y-%m-%d-%H%M}-{slug}.json"
        path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        seen.append({**record, "status": "published", "slug": slug})
        published += 1
        new_slugs.append(slug)
        log(f"  PUBLISHED: {out['title']}  -> {path.name} (products: {len(prods)}, sensitive: {sensitive})")

    SEEN.write_text(json.dumps(seen[-1500:], ensure_ascii=False) + "\n", encoding="utf-8")
    log(f"done: {published} published, {tried} tried")
    out_file = os.environ.get("GITHUB_OUTPUT")
    if out_file:
        with open(out_file, "a", encoding="utf-8") as f:
            f.write(f"new_posts={' '.join(new_slugs)}\n")
    LOG.write_text("\n".join(_lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
