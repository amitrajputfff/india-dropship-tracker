"""Shared helpers for the JS-heavy storefronts (Meesho, Myntra, Snapdeal, Alibaba, AliExpress).

These render primarily client-side and fight scraping harder than Amazon does,
so every function here is best-effort: try a couple of extraction strategies,
return whatever is found, never raise.
"""

import json
import re
import time

import requests
from bs4 import BeautifulSoup

from config import REQUEST_DELAY_SECONDS, REQUEST_HEADERS, REQUEST_TIMEOUT_SECONDS
from product_titles import looks_like_product_title

_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


def fetch(url):
    """GET a URL with the shared headers/timeout/delay. Returns (html, error_str)."""
    try:
        resp = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT_SECONDS)
        resp.raise_for_status()
        return resp.text, None
    except requests.RequestException as exc:
        return None, str(exc)
    finally:
        time.sleep(REQUEST_DELAY_SECONDS)


def extract_next_data(html):
    """Pull the __NEXT_DATA__ JSON blob many React/Next.js storefronts embed for SSR/SEO.

    Returns the parsed dict, or None if the site doesn't use this pattern
    (fully client-rendered with no SSR payload) or the shape doesn't match.
    """
    match = _NEXT_DATA_RE.search(html)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def find_product_like_strings(node, name_keys=("name", "title", "productName", "displayName"), max_results=40, _out=None):
    """Walk an arbitrary JSON structure and collect strings that look like product titles.

    Deliberately pattern-based (a dict with a name/title-ish key) rather than a
    fixed path, since every site's data shape differs and reshapes itself over
    time without notice.
    """
    if _out is None:
        _out = []
    if len(_out) >= max_results:
        return _out
    if isinstance(node, dict):
        for key in name_keys:
            value = node.get(key)
            if isinstance(value, str) and 8 <= len(value) <= 150:
                _out.append(value)
                break
        for value in node.values():
            find_product_like_strings(value, name_keys, max_results, _out)
    elif isinstance(node, list):
        for item in node:
            find_product_like_strings(item, name_keys, max_results, _out)
    return _out


def extract_title_like_text(html, min_len=15, max_len=120):
    """Fallback for sites with no __NEXT_DATA__: a generic 'looks like a title' text scan."""
    soup = BeautifulSoup(html, "lxml")
    seen = []
    for tag in soup.find_all(["div", "a", "span", "h2", "h3", "h4"]):
        text = tag.get_text(strip=True)
        if min_len <= len(text) <= max_len:
            stripped = text.replace(",", "").replace("₹", "").replace("%", "").strip()
            if not stripped.isdigit() and text not in seen:
                seen.append(text)
    return seen


_TOKEN_RE = re.compile(r"[a-zA-Z]+")


def shares_content_tokens(query: str, title: str, min_shared: int = 2) -> bool:
    """True if `title` shares at least `min_shared` words (len > 2) with `query`.

    Used to gate the Alibaba/AliExpress "supplier found" claim - without this,
    check_sourcing() reported `available: True` for whatever extract_titles()
    returned, even when it was irrelevant filler text ("FREE with any
    purchase | Upgraded Pet Hair Cleaning Gloves...") that happened to survive
    the junk filter but has nothing to do with the product being checked.
    """
    query_tokens = {w.lower() for w in _TOKEN_RE.findall(query) if len(w) > 2}
    title_tokens = {w.lower() for w in _TOKEN_RE.findall(title) if len(w) > 2}
    return len(query_tokens & title_tokens) >= min_shared


def extract_titles(html):
    """Try __NEXT_DATA__ first, fall back to the generic text scan.

    Filtered through looks_like_product_title() - this is the one path that
    feeds the Alibaba/AliExpress sourcing checks, which never go through
    aggregator.filter_dropshippable, so junk (nav menus, filters, breadcrumbs)
    needs to be rejected here or it sails straight into a sourcing "found"
    claim.
    """
    data = extract_next_data(html)
    titles = find_product_like_strings(data) if data else []
    if not titles:
        titles = extract_title_like_text(html)
    return [t for t in titles if looks_like_product_title(t)]
