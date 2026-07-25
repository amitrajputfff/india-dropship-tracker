"""Config for the daily India trend tracker.

This is tuned for DROPSHIPPING specifically: generic/novelty/gadget items you
could actually source from a wholesale supplier, not mainstream branded
products (OnePlus, Jockey, Nike, Amazon Brand, ...) that you can't dropship.
See BRAND_BLOCKLIST below and aggregator.is_dropshippable().

Edit AMAZON_CATEGORIES / *_KEYWORDS to change what gets tracked.
"""

# Categories picked to skew toward generic/novelty/gadget bestsellers rather
# than brand-dominated ones - "Electronics"/"Computers"/"Clothing" bestseller
# lists are almost entirely OnePlus/Samsung/Jockey/Nike-type products, which
# get filtered out anyway, so scraping them mostly wastes requests.
AMAZON_CATEGORIES = {
    "Kitchen & Home": "https://www.amazon.in/gp/bestsellers/kitchen/",
    "Home Improvement": "https://www.amazon.in/gp/bestsellers/home-improvement/",
    "Beauty": "https://www.amazon.in/gp/bestsellers/beauty/",
    "Toys & Games": "https://www.amazon.in/gp/bestsellers/toys/",
    "Sports & Fitness": "https://www.amazon.in/gp/bestsellers/sports/",
    "Pet Supplies": "https://www.amazon.in/gp/bestsellers/pet-supplies/",
    "Car & Motorbike": "https://www.amazon.in/gp/bestsellers/car-motorbike/",
    "Garden & Outdoors": "https://www.amazon.in/gp/bestsellers/garden/",
}

# Products containing any of these (case-insensitive substring match) are
# dropped before scoring - they're real brands with their own supply chain,
# not something a dropshipper can source. This list is a heuristic, not
# exhaustive - if a recognizable brand keeps leaking into your top picks,
# add it here.
BRAND_BLOCKLIST = {
    # electronics / mobile
    "oneplus", "samsung", "xiaomi", "redmi", "realme", "vivo", "oppo", "apple",
    "iphone", "nokia", "motorola", "asus", "acer", " hp ", "dell", "lenovo", "sony",
    " lg ", "boat", "noise", "jbl", "bose", "sennheiser", "philips", "panasonic",
    "ambrane", "portronics",
    # home appliances
    "whirlpool", "bosch", "prestige", "bajaj", "havells", "usha", "orient",
    # fashion
    "nike", "adidas", "puma", "reebok", "levis", "jockey", "van heusen",
    "allen solly", "peter england", "titan", "fastrack", "fossil", "woodland", "bata",
    # marketplace house brands - still "branded" in that you can't source them
    "amazon brand", "presto!", "solimo", "amazonbasics", "flipkart smartbuy",
    # toys
    "lego", "hot wheels", "barbie", "fisher-price", "fisher price", "hasbro",
    "mattel", "funskool", "nerf", "disney", "marvel", "beyblade",
}

# Generic noise that occasionally shows up in bestseller widgets but isn't a
# physical product at all (gift cards, bill-payment shortcuts, etc.).
NOISE_PHRASES = {"booking", "recharge", "gift card", "bill payment", "subscription"}

# None of Flipkart/Meesho/Snapdeal have a public "bestsellers" page like
# Amazon, so we approximate it by scraping search results sorted by
# popularity/relevance for a fixed keyword watchlist.
#
# Keywords are aimed at the classic "viral Shopify dropship" archetype - cheap,
# generic, single-problem silicone/plastic gadgets (e.g. a silicone sink-edge
# splash guard: solves one annoyance, easy to source wholesale, no brand
# equity) - rather than branded consumer electronics, which get filtered out
# by BRAND_BLOCKLIST anyway.
GENERAL_PRODUCT_KEYWORDS = [
    "silicone kitchen gadget",
    "sink splash guard",
    "gap cover strip",
    "reusable stretch lids",
    "cable organizer clip",
    "posture corrector",
    "car seat organizer",
    "silicone ice tray",
    "multipurpose storage rack",
    "led lights",
    "dancing cactus toy",
    "interactive plush toy",
    "musical baby toy",
]
FLIPKART_KEYWORDS = GENERAL_PRODUCT_KEYWORDS
MEESHO_KEYWORDS = GENERAL_PRODUCT_KEYWORDS
SNAPDEAL_KEYWORDS = GENERAL_PRODUCT_KEYWORDS

# Myntra is fashion-only, so the general keyword list above doesn't fit its catalog.
MYNTRA_KEYWORDS = [
    "oversized t-shirt",
    "sneakers men",
    "ethnic kurta",
    "saree",
    "formal shirt",
]

# How many top cross-platform picks to show in the report, how many
# momentum-ranked candidates to run the (LLM) 13-KPI judge against, and how
# many of the final picks to run the Alibaba/AliExpress supplier check against.
TOP_PICKS_COUNT = 10
CANDIDATE_POOL_SIZE = 25  # bounds LLM judge calls per run regardless of source count
SOURCING_CHECK_TOP_N = 10

REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.google.com/",
    "Upgrade-Insecure-Requests": "1",
}

REQUEST_DELAY_SECONDS = 3  # be polite - space out requests to avoid getting blocked
REQUEST_TIMEOUT_SECONDS = 15

OUTPUT_DIR = "output"
