"""Best-effort scraper for Myntra search results (fashion-focused keywords).

UNTESTED against a live connection - myntra.com was blocked by a network-level
policy (Zscaler) in the environment this was built in, which is a network
control, not Myntra's own bot defense. Myntra's real search URL pattern is
also the least certain of everything in this project (it sometimes routes
searches to slug-style category pages instead of a query param) - if this
comes back empty, open myntra.com in a browser, search a keyword, and copy
the resulting URL pattern here.
"""

from . import common

SEARCH_URL = "https://www.myntra.com/search?q={query}"


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
            "error": "No products parsed - Myntra likely blocked the request, or its search URL pattern has changed.",
            "products": [],
        }
    return {"keyword": keyword, "error": None, "products": items}
