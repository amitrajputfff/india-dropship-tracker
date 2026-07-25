"""Best-effort scraper for Meesho search results.

UNTESTED against a live connection - meesho.com was blocked by a network-level
policy (Zscaler) in the environment this was built in, which is a network
control, not Meesho's own bot defense. Verify this returns real products once
you run it on your own connection, and expect to adjust the URL/selectors.
"""

from . import common

SEARCH_URL = "https://www.meesho.com/search?q={query}"


def fetch_keyword_trending(keyword: str, limit: int = 15):
    url = SEARCH_URL.format(query=keyword.replace(" ", "%20"))
    html, error = common.fetch(url)
    if error:
        return {"keyword": keyword, "error": error, "products": []}

    titles = common.extract_titles(html)
    items = [{"rank": i + 1, "title": t, "keyword": keyword} for i, t in enumerate(titles[:limit])]

    if not items:
        return {
            "keyword": keyword,
            "error": "No products parsed - Meesho likely blocked the request or changed page layout.",
            "products": [],
        }
    return {"keyword": keyword, "error": None, "products": items}
