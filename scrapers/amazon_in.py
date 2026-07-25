"""Best-effort scraper for Amazon.in bestseller category pages.

Amazon has no free "trending products" API (the Product Advertising API requires
an active Associates account with qualifying sales, and it's for catalog lookups,
not trend discovery) - so this scrapes the public bestseller pages instead.

Amazon renames its CSS classes constantly, which breaks class-based scrapers
every few months. What's stayed stable is that every product slot in the
ranked grid carries id="p13n-asin-index-N" (N = 0, 1, 2, ...) - so we anchor
on that id pattern rather than any class name, then pull the `alt` text off
the first image inside each slot (Amazon sets alt="<product title>" there).

Keep this to one run/day and don't parallelize requests: scraping product
listing pages sits in a ToS gray area for most e-commerce sites, and hammering
it is what gets an IP blocked.
"""

import re
import time

import requests
from bs4 import BeautifulSoup

from config import REQUEST_DELAY_SECONDS, REQUEST_HEADERS, REQUEST_TIMEOUT_SECONDS

_SLOT_ID_RE = re.compile(r"^p13n-asin-index-(\d+)$")


def fetch_category_bestsellers(category_name: str, url: str, limit: int = 20):
    """Scrape one bestseller category page.

    Returns {"category", "error", "products": [{"rank","title","category"}]}.
    Never raises - a blocked/changed page just yields an empty item list plus
    an error string, so one bad category doesn't kill the whole report.
    """
    try:
        resp = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT_SECONDS)
        resp.raise_for_status()
    except requests.RequestException as exc:
        return {"category": category_name, "error": str(exc), "products": []}
    finally:
        time.sleep(REQUEST_DELAY_SECONDS)

    soup = BeautifulSoup(resp.text, "lxml")

    slots = []
    for tag in soup.find_all(id=_SLOT_ID_RE):
        match = _SLOT_ID_RE.match(tag["id"])
        slots.append((int(match.group(1)), tag))
    slots.sort(key=lambda pair: pair[0])

    items = []
    seen_titles = set()
    for _, slot in slots:
        img = slot.find("img", alt=True)
        if img is None:
            continue
        alt = img["alt"].strip()
        if not alt or alt in seen_titles:
            continue
        seen_titles.add(alt)
        items.append({"rank": len(items) + 1, "title": alt, "category": category_name})
        if len(items) >= limit:
            break

    if not items:
        return {
            "category": category_name,
            "error": "No products parsed - Amazon likely blocked the request or changed page layout. "
            "Open the URL in a browser, view source, and check whether product slots still use "
            "id=\"p13n-asin-index-N\".",
            "products": [],
        }

    return {"category": category_name, "error": None, "products": items}
