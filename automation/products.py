"""Affiliate product box for a post.

Today: Amazon India search links tagged with your Associates tag (earns
commission on qualifying purchases). Next step: real product cards with
price + image from the Amazon Creators API.
"""
from urllib.parse import quote_plus


def amazon_search_products(keywords, tag, limit=3):
    products = []
    for kw in keywords[:limit]:
        kw = (kw or "").strip()
        if not kw or len(kw) > 80:
            continue
        products.append({
            "name": kw.title(),
            "store": "Amazon",
            "url": f"https://www.amazon.in/s?k={quote_plus(kw)}&tag={quote_plus(tag)}",
        })
    return products
