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
    """Return {"available", "error", "sample_titles"} for a product title."""
    query = "+".join(product_title.split()[:6])
    url = SEARCH_URL.format(query=query)
    html, error = common.fetch(url)
    if error:
        return {"available": None, "error": error, "sample_titles": []}

    titles = common.extract_titles(html)
    if not titles:
        return {
            "available": None,
            "error": "No listings parsed - AliExpress likely blocked the request or changed page layout.",
            "sample_titles": [],
        }
    return {"available": True, "error": None, "sample_titles": titles[:sample_size]}
