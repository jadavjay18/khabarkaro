"""Free stock photos for posts from the Pexels API.

Pexels photos are free for commercial use; we still show a credit
("Photo: <name> / Pexels") as Pexels asks API users to do.
"""
import os

import requests

API = "https://api.pexels.com/v1/search"


def find_photo(query, log):
    key = os.environ.get("PEXELS_API_KEY", "").strip()
    query = (query or "").strip()
    if not key or not query:
        if not key:
            log("  image: PEXELS_API_KEY not set — headline card will be used")
        return None
    try:
        r = requests.get(API, headers={"Authorization": key},
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
                },
            }
    log(f"  image: no Pexels result for '{query}'")
    return None
