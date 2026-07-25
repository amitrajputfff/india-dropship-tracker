"""Supplier-availability check against Alibaba.com - not a trend source.

Alibaba is B2B (suppliers, not retail shoppers), so it's used differently
from the other scrapers: given a trending product's title, check whether
wholesale listings for something similar actually exist. That's the "can I
even source this" check that should happen before auto-publishing a
"trending" pick to a storefront.

UNTESTED against a live connection - alibaba.com was blocked by a
network-level policy (Zscaler) in the environment this was built in, which is
a network control, not Alibaba's own bot defense. Verify on your own network.
"""

from . import common

SEARCH_URL = "https://www.alibaba.com/trade/search?SearchText={query}"


def check_sourcing(product_title: str, sample_size: int = 5):
    """Return {"available", "error", "sample_titles"} for a product title.

    "available" is only True if at least one returned listing actually shares
    words with the query - a live run once reported "found" for a cat-food
    query on the strength of an unrelated "FREE with any purchase" filler
    string, since the old code treated ANY parsed text as a hit.
    """
    query = "+".join(product_title.split()[:6])  # keep the query short and relevant
    url = SEARCH_URL.format(query=query)
    html, error = common.fetch(url)
    if error:
        return {"available": None, "error": error, "sample_titles": []}

    titles = common.extract_titles(html)
    relevant = [t for t in titles if common.shares_content_tokens(product_title, t)]
    if not relevant:
        return {
            "available": None,
            "error": "No relevant listings found - Alibaba may have blocked the request, changed page "
            "layout, or genuinely has nothing matching.",
            "sample_titles": [],
        }
    return {"available": True, "error": None, "sample_titles": relevant[:sample_size]}
