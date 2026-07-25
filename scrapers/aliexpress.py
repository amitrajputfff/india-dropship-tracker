"""Supplier-availability check against AliExpress - not a trend source.

Same role as scrapers/alibaba.py: given a trending product's title, check
whether matching retail-dropship listings exist on AliExpress.

UNTESTED against a live connection - aliexpress.com was blocked by a
network-level policy (Zscaler) in the environment this was built in, which is
a network control, not AliExpress's own bot defense. AliExpress has rebuilt
its search UI multiple times and is one of the harder sites to scrape with
plain requests (heavy client-side rendering + anti-bot) - if this comes back
empty even outside a blocked network, a headless browser (Playwright) is the
realistic next step rather than tweaking this further.
"""

from . import common

SEARCH_URL = "https://www.aliexpress.com/wholesale?SearchText={query}"


def check_sourcing(product_title: str, sample_size: int = 5):
    """Return {"available", "error", "sample_titles"} for a product title.

    "available" is only True if at least one returned listing actually shares
    words with the query - see scrapers/alibaba.py for the false-positive
    this fixes (a live run once reported "found" off unrelated filler text).
    """
    query = "+".join(product_title.split()[:6])
    url = SEARCH_URL.format(query=query)
    html, error = common.fetch(url)
    if error:
        return {"available": None, "error": error, "sample_titles": []}

    titles = common.extract_titles(html)
    relevant = [t for t in titles if common.shares_content_tokens(product_title, t)]
    if not relevant:
        return {
            "available": None,
            "error": "No relevant listings found - AliExpress may have blocked the request, changed page "
            "layout, or genuinely has nothing matching.",
            "sample_titles": [],
        }
    return {"available": True, "error": None, "sample_titles": relevant[:sample_size]}
