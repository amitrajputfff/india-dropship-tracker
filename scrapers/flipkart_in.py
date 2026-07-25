"""Best-effort scraper for Flipkart's "popularity"-sorted search results.

Flipkart has no equivalent of Amazon's bestseller page, so this is the closest
free proxy: search results for a keyword, sorted by popularity. Treat this as
the weakest/noisiest source in the report - Flipkart's markup gives no stable
"this is a product title" marker, so we fall back to a generic heuristic
(text length + not-a-price) which will occasionally pick up menu/filter text.
If this source looks consistently noisy, it's the first one to manually
re-inspect and tighten.
"""

import time

import requests
from bs4 import BeautifulSoup

from config import REQUEST_DELAY_SECONDS, REQUEST_HEADERS, REQUEST_TIMEOUT_SECONDS

SEARCH_URL = "https://www.flipkart.com/search?q={query}&sort=popularity"


def _looks_like_title(text: str) -> bool:
    if not (15 <= len(text) <= 120):
        return False
    stripped = text.replace(",", "").replace("₹", "").replace("%", "").strip()
    if stripped.isdigit():
        return False
    if text.lower() in {"login", "sign up", "become a seller", "explore plus"}:
        return False
    return True


def fetch_keyword_trending(keyword: str, limit: int = 15):
    """Scrape one keyword's popularity-sorted search page.

    Returns {"keyword", "error", "products": [{"rank","title","keyword"}]}.
    """
    url = SEARCH_URL.format(query=keyword.replace(" ", "+"))
    try:
        resp = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT_SECONDS)
        resp.raise_for_status()
    except requests.RequestException as exc:
        return {"keyword": keyword, "error": str(exc), "products": []}
    finally:
        time.sleep(REQUEST_DELAY_SECONDS)

    soup = BeautifulSoup(resp.text, "lxml")

    titles = []
    for tag in soup.find_all(["div", "a"]):
        text = tag.get_text(strip=True)
        if _looks_like_title(text) and text not in titles:
            titles.append(text)
        if len(titles) >= limit * 3:
            break

    items = [
        {"rank": i + 1, "title": t, "keyword": keyword} for i, t in enumerate(titles[:limit])
    ]

    if not items:
        return {
            "keyword": keyword,
            "error": "No products parsed - Flipkart likely blocked the request or changed page layout.",
            "products": [],
        }

    return {"keyword": keyword, "error": None, "products": items}
