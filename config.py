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
#
# Exactly 9 categories, deliberately: with CANDIDATE_POOL_SIZE=18 and
# round-robin selection (aggregator._round_robin_select), that's exactly
# depth-2 coverage per category (ranks 1 AND 2 from every category judged,
# not just whichever categories have the highest-momentum rank-1 item). Add
# categories in matching multiples of the pool size if you raise it, or the
# round-robin depth gets uneven. "car-motorbike" 404s its bestseller grid -
# the real Amazon.in slug is "automotive" - and "office-products"/
# "baby-products"/"health-personal-care" return 200 with zero product slots
# (no bestseller grid at that URL), so they're left out rather than wasting
# a request every run.
AMAZON_CATEGORIES = {
    "Kitchen & Home": "https://www.amazon.in/gp/bestsellers/kitchen/",
    "Home Improvement": "https://www.amazon.in/gp/bestsellers/home-improvement/",
    "Beauty": "https://www.amazon.in/gp/bestsellers/beauty/",
    "Toys & Games": "https://www.amazon.in/gp/bestsellers/toys/",
    "Sports & Fitness": "https://www.amazon.in/gp/bestsellers/sports/",
    "Pet Supplies": "https://www.amazon.in/gp/bestsellers/pet-supplies/",
    "Car & Motorbike": "https://www.amazon.in/gp/bestsellers/automotive/",
    "Garden & Outdoors": "https://www.amazon.in/gp/bestsellers/garden/",
    "Luggage & Bags": "https://www.amazon.in/gp/bestsellers/luggage/",
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
    # observed leaks from a live run - unambiguous national/international CPG
    # brands only. Deliberately NOT including "boldfit"/"lifelong": both had
    # products (a pull-up bar, a foldable scooter) genuinely pass the KPI
    # judge in an earlier run, so a hard block would re-exclude legitimate
    # picks. Their brand-locked items (if any) are left to
    # llm_kpi_judge.judge()'s is_recognizable_brand field, which can judge
    # case-by-case rather than blocking the whole brand name outright.
    "amazon basics", "pedigree", "whiskas", "drools", "purepet", "meat up",
    "cetaphil", "mortein", "milton", "nivia", "gala",
    "the derma co", "bare anatomy", "be bodywise",
}

# Generic noise that occasionally shows up in bestseller widgets but isn't a
# physical product at all (gift cards, bill-payment shortcuts, etc.).
NOISE_PHRASES = {"booking", "recharge", "gift card", "bill payment", "subscription"}

# Flipkart/Meesho/Snapdeal/Myntra are DISABLED (see ENABLED_SOURCES below) -
# confirmed live that Meesho/Snapdeal 403 and Myntra times out even from
# GitHub Actions' cloud IPs (an IP/ASN-level anti-bot block, not something
# header tuning or better parsing fixes), and Flipkart's Actions response
# contains zero real product strings at all - just nav/filter chrome. Keeping
# the keyword lists and scraper code in place so re-enabling any of them
# later, if a source ever starts working, is one line in ENABLED_SOURCES.
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

# scrapers/amazon_search.py - Amazon.in's regular keyword SEARCH (not
# bestseller lists), for the "novelty/gift/room-decor" dropship archetype
# AMAZON_CATEGORIES structurally can't reach (Amazon.in has no bestseller
# page for decor/lighting/gift subcategories). Spans four India-relevant
# sub-archetypes, live-validated (real results, small-seller brands, not
# big names) - see scrapers/amazon_search.py's docstring for the research.
FUN_PRODUCT_KEYWORDS = [
    # room-decor / novelty (validated: Desidiya, Jamboree!!!, Gesto, One94Store)
    "galaxy projector",
    "sunset lamp",
    "led fairy lights",
    # India-festive gifting
    "designer diya lights",
    "oxidised jewellery earrings",
    # India-seasonal (extreme summer heat)
    "portable misting fan",
    # distinct-niche gadgets not covered by the existing bestseller categories
    "mini handheld projector",
    "pet camera treat dispenser",
]

# Which non-Amazon sources generate_report.py actually fetches. Flip any of
# these back to True to re-enable - no other code changes needed.
ENABLED_SOURCES = {
    "flipkart": False,
    "meesho": False,
    "myntra": False,
    "snapdeal": False,
}

# How many top cross-platform picks to show in the report, how many
# momentum-ranked candidates to run the (LLM) 13-KPI judge against, and how
# many of the final picks to run the Alibaba/AliExpress supplier check against.
#
# CANDIDATE_POOL_SIZE is capped by the Gemini free-tier quota: 20 requests/day
# for gemini-2.5-flash, hard - not a soft cost concern, a real wall hit twice
# in one day of testing. 20 uses the full quota with no buffer - the existing
# llm_kpi_judge.judge() retry+fallback and the near-miss backfill already
# absorb a stray degraded judgment gracefully, so there's no reliability
# cliff from dropping the buffer that was here when there were only 9
# sources (AMAZON_CATEGORIES). Now there are 9 + len(FUN_PRODUCT_KEYWORDS) =
# 17 distinct source labels feeding aggregator._round_robin_select, which
# gives every source at least depth-1 coverage and depth-2 for whichever
# ~3 sources rank highest that day - uneven, but the round-robin logic
# already handles that automatically, no code change needed there.
TOP_PICKS_COUNT = 10
CANDIDATE_POOL_SIZE = 20
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
