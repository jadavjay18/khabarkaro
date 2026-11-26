"""Affiliate product box for a post.

With Amazon Creators API credentials (secrets AMAZON_CLIENT_ID and
AMAZON_CLIENT_SECRET) each product keyword becomes a real product card:
title, image, price, discount, tagged link. Without them (or if the API
fails) it falls back to a tagged Amazon search link.
"""
import os
import re
import time
from urllib.parse import quote_plus

import requests

SEARCH_URL = "https://creatorsapi.amazon/catalog/v1/searchItems"
MARKETPLACE = "www.amazon.in"
# India sits in the EU region (credential version 3.2); NA endpoint kept as a fallback.
TOKEN_URLS = ["https://api.amazon.co.uk/auth/o2/token", "https://api.amazon.com/auth/o2/token"]
RESOURCES = ["images.primary.large", "itemInfo.title", "offersV2.listings.price"]

_token = {"value": None, "exp": 0}


def _get_token(log):
    if _token["value"] and time.time() < _token["exp"] - 60:
        return _token["value"]
    cid = os.environ.get("AMAZON_CLIENT_ID", "").strip()
    secret = os.environ.get("AMAZON_CLIENT_SECRET", "").strip()
    if not cid or not secret:
        return None
    for url in TOKEN_URLS:
        try:
            r = requests.post(url, json={"grant_type": "client_credentials", "client_id": cid,
                                         "client_secret": secret, "scope": "creatorsapi::default"}, timeout=20)
            if r.status_code == 200 and r.json().get("access_token"):
                d = r.json()
                _token.update(value=d["access_token"], exp=time.time() + int(d.get("expires_in", 3600)))
                return _token["value"]
            log(f"  amazon: token {url} -> HTTP {r.status_code} {r.text[:150]}")
        except Exception as e:
            log(f"  amazon: token {url} error {e}")
    return None


def _num(display):
    """'₹1,499.00' -> '1,499'"""
    m = re.search(r"[\d,]+(?:\.\d+)?", display or "")
    if not m:
        return None
    s = m.group(0)
    return s[:-3] if s.endswith(".00") else s


def _search(keyword, tag, token, log):
    body = {"keywords": keyword, "searchIndex": "All", "itemCount": 3, "marketplace": MARKETPLACE,
            "partnerTag": tag, "resources": RESOURCES}
    try:
        r = requests.post(SEARCH_URL, json=body, timeout=20, headers={
            "Authorization": f"Bearer {token}", "Content-Type": "application/json", "x-marketplace": MARKETPLACE})
    except Exception as e:
        log(f"  amazon: search error {e}")
        return None
    if r.status_code != 200:
        log(f"  amazon: search '{keyword}' -> HTTP {r.status_code} {r.text[:200]}")
        return None
    items = (r.json().get("searchResult") or {}).get("items") or []
    for it in items:
        title = (((it.get("itemInfo") or {}).get("title") or {}).get("displayValue") or "").strip()
        url = it.get("detailPageURL")
        if not title or not url:
            continue
        img = (((it.get("images") or {}).get("primary") or {}).get("large") or {}).get("url")
        listing = ((it.get("offersV2") or {}).get("listings") or [{}])[0] or {}
        price = listing.get("price") or {}
        money = price.get("money") or {}
        basis = ((price.get("savingBasis") or {}).get("money") or {})
        pct = (price.get("savings") or {}).get("percentage")
        return {
            "name": title[:120],
            "store": "Amazon",
            "url": url,
            "image": img,
            "price": _num(money.get("displayAmount")),
            "mrp": _num(basis.get("displayAmount")),
            "off": int(pct) if pct else None,
            "asin": it.get("asin"),
        }
    log(f"  amazon: no items for '{keyword}'")
    return None


def search_link(kw, tag):
    return {"name": kw.title(), "store": "Amazon",
            "url": f"https://www.amazon.in/s?k={quote_plus(kw)}&tag={quote_plus(tag)}"}


def amazon_products(keywords, tag, log, limit=3):
    keywords = [k.strip() for k in (keywords or []) if k and k.strip() and len(k.strip()) <= 80][:limit]
    if not keywords:
        return []
    token = _get_token(log)
    out = []
    for kw in keywords:
        card = _search(kw, tag, token, log) if token else None
        if card:
            log(f"  amazon: card for '{kw}': {card['name'][:50]} ({card.get('price')})")
        out.append(card or search_link(kw, tag))
    return out


# backward-compatible name
def amazon_search_products(keywords, tag, limit=3):
    return [search_link(k.strip(), tag) for k in (keywords or [])[:limit] if k and k.strip()]
