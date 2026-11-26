"""Free stock photos for posts.

Provider order: Unsplash (UNSPLASH_ACCESS_KEY), then Pexels (PEXELS_API_KEY).
Both are free for commercial use. We show a credit on every photo, and for
Unsplash we follow their API guidelines: hotlink the image URL they return,
credit the photographer + Unsplash with UTM links, and ping the download
endpoint when a photo is used.
"""
import os

import requests

UTM = "utm_source=khabarkaro&utm_medium=referral"


def _unsplash(query, key, log):
    try:
        r = requests.get("https://api.unsplash.com/search/photos",
                         headers={"Authorization": f"Client-ID {key}", "Accept-Version": "v1"},
                         params={"query": query, "orientation": "landscape", "per_page": 5,
                                 "content_filter": "high"},
                         timeout=20)
        if r.status_code != 200:
            log(f"  image: Unsplash HTTP {r.status_code} {r.text[:200]}")
            return None
        results = r.json().get("results", [])
    except Exception as e:
        log(f"  image: Unsplash error {e}")
        return None
    for p in results:
        url = (p.get("urls") or {}).get("regular")
        if not url:
            continue
        user = p.get("user") or {}
        try:  # required by Unsplash guidelines when a photo is used
            dl = (p.get("links") or {}).get("download_location")
            if dl:
                requests.get(dl, headers={"Authorization": f"Client-ID {key}"}, timeout=10)
        except Exception:
            pass
        profile = (user.get("links") or {}).get("html", "https://unsplash.com")
        log(f"  image: Unsplash photo for '{query}' by {user.get('name')}")
        return {
            "image": url,
            "image_alt": (p.get("alt_description") or query)[:150],
            "image_credit": {
                "name": user.get("name", "Unsplash"),
                "url": f"{profile}?{UTM}",
                "site": "Unsplash",
                "site_url": f"https://unsplash.com/?{UTM}",
            },
        }
    log(f"  image: no Unsplash result for '{query}'")
    return None


def _pexels(query, key, log):
    try:
        r = requests.get("https://api.pexels.com/v1/search", headers={"Authorization": key},
                         params={"query": query, "orientation": "landscape", "per_page": 5, "size": "medium"},
                         timeout=20)
        if r.status_code != 200:
            log(f"  image: Pexels HTTP {r.status_code} {r.text[:200]}")
            return None
        photos = r.json().get("photos", [])
    except Exception as e:
        log(f"  image: Pexels error {e}")
        return None
    for p in photos:
        src = p.get("src", {})
        url = src.get("landscape") or src.get("large")
        if url:
            log(f"  image: Pexels photo for '{query}' by {p.get('photographer')}")
            return {
                "image": url,
                "image_alt": (p.get("alt") or query)[:150],
                "image_credit": {
                    "name": p.get("photographer", "Pexels"),
                    "url": p.get("url") or "https://www.pexels.com",
                    "site": "Pexels",
                    "site_url": "https://www.pexels.com",
                },
            }
    log(f"  image: no Pexels result for '{query}'")
    return None


def has_provider():
    return bool(os.environ.get("UNSPLASH_ACCESS_KEY", "").strip() or os.environ.get("PEXELS_API_KEY", "").strip())


def find_photo(query, log):
    query = (query or "").strip()
    if not query:
        return None
    unsplash = os.environ.get("UNSPLASH_ACCESS_KEY", "").strip()
    pexels = os.environ.get("PEXELS_API_KEY", "").strip()
    if not unsplash and not pexels:
        log("  image: no photo API key set — headline card will be used")
        return None
    if unsplash:
        photo = _unsplash(query, unsplash, log)
        if photo:
            return photo
    if pexels:
        return _pexels(query, pexels, log)
    return None
