"""Scraper for Amazon.in's regular keyword SEARCH (not bestseller lists).

The 9 bestseller categories in scrapers/amazon_in.py only cover the "utility,
solves one annoyance" dropship archetype (sink guards, cable organizers).
There's an equally classic archetype it structurally can't reach:
novelty/gift/room-decor items people buy on impulse because they're fun, not
because they solve a problem - a galaxy/star projector is the canonical
example. Amazon.in has no bestseller page for decor/lighting/gift
subcategories (confirmed live: "home-decor", "lighting", "night-lights",
"gifts" all 200 with zero product slots), so this scrapes Amazon's normal
product search instead, targeting specific known-viral search terms
(config.FUN_PRODUCT_KEYWORDS).

Confirmed live: `amazon.in/s?k=galaxy+projector` returns real results (60
products) from small/generic seller-brand labels (Desidiya, Jamboree!!!,
Gesto) - exactly the dropshippable pattern. Extraction anchors on the stable
`data-component-type="s-search-result"` marker on each result block, with the
title in a nested <h2> - not the generic text-scan in scrapers/common.py
(a known bug source elsewhere in this project).

Unlike the bestseller pages (zero anti-bot friction across 15+ live test
requests in this project), Amazon's search endpoint has REAL Akamai Bot
Manager protection - and it's sensitive to request *pattern*, not just luck:
standalone test calls (spaced out by minutes, mixed with other work)
succeeded consistently, but running 8 keyword searches back-to-back in the
real pipeline (only config.REQUEST_DELAY_SECONDS=3s apart, the same pacing
that's fine for bestseller pages) got only the first one through - every
subsequent request in that burst hit the challenge. So this uses its own,
much longer delay between requests than the rest of the project, plus a
longer backoff before retrying a challenged request (a fresh attempt only
sometimes clears it - this can't solve the actual JS challenge, it's a
plain `requests` call).
"""

import time

import requests
from bs4 import BeautifulSoup

from config import REQUEST_HEADERS, REQUEST_TIMEOUT_SECONDS

SEARCH_URL = "https://www.amazon.in/s?k={query}"
MAX_ATTEMPTS = 2
BETWEEN_REQUEST_DELAY_SECONDS = 12  # longer than config.REQUEST_DELAY_SECONDS - this endpoint is more bot-sensitive
RETRY_BACKOFF_SECONDS = 20


def _looks_like_akamai_interstitial(html: str) -> bool:
    return len(html) < 10_000 and "bm-verify" in html


def _fetch_search_page(url: str):
    """GET with a generous delay, retrying once (after a longer backoff) on an Akamai interstitial.

    Returns (html, error_str).
    """
    last_html = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            resp = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT_SECONDS)
            resp.raise_for_status()
        except requests.RequestException as exc:
            return None, str(exc)

        if not _looks_like_akamai_interstitial(resp.text):
            time.sleep(BETWEEN_REQUEST_DELAY_SECONDS)
            return resp.text, None
        last_html = resp.text
        if attempt < MAX_ATTEMPTS:
            time.sleep(RETRY_BACKOFF_SECONDS)

    time.sleep(BETWEEN_REQUEST_DELAY_SECONDS)  # still pace out before the next keyword, even on failure
    return last_html, "Amazon served an anti-bot (Akamai) interstitial challenge on every attempt"


def fetch_keyword_search(keyword: str, limit: int = 20):
    """Scrape one search results page.

    Returns {"keyword", "error", "products": [{"rank","title"}]}. Never raises.
    """
    url = SEARCH_URL.format(query=keyword.replace(" ", "+"))
    html, error = _fetch_search_page(url)
    if html is None:
        return {"keyword": keyword, "error": error, "products": []}

    soup = BeautifulSoup(html, "lxml")
    blocks = soup.find_all(attrs={"data-component-type": "s-search-result"})

    items = []
    seen_titles = set()
    for block in blocks:
        h2 = block.find("h2")
        if h2 is None:
            continue
        title = h2.get_text(strip=True)
        if not title or title in seen_titles:
            continue
        seen_titles.add(title)
        items.append({"rank": len(items) + 1, "title": title, "keyword": keyword})
        if len(items) >= limit:
            break

    if not items:
        return {
            "keyword": keyword,
            "error": error or "No products parsed - Amazon likely changed its search page layout. "
            "Open the URL in a browser and check whether result blocks still carry "
            'data-component-type="s-search-result".',
            "products": [],
        }

    return {"keyword": keyword, "error": None, "products": items}
