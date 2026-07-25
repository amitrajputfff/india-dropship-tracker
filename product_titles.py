"""Filter out non-product junk (nav menus, filters, breadcrumbs) that a generic
"looks like a title" text scan picks up from real e-commerce pages.

Found live: scrapers/flipkart_in.py's old heuristic returned strings like
"ExplorePlusLoginBecome a SellerMoreCart" and "Min5001000150020004000to..." as
"products" - those then out-scored real bestsellers in momentum ranking. This
module is the shared, stricter check both aggregator.py (the single choke
point all scraped results pass through) and scrapers/common.py (used by the
sourcing-check scrapers, which bypass the aggregator) call before anything
downstream treats a string as a real product title.

Rules below were tuned against a real batch: 121 genuine Amazon bestseller
titles and 60 junk strings scraped from Flipkart's search page on the same
run. Result: 121/121 real titles kept, 59/60 junk strings dropped.
"""

import re

UI_NOISE_PHRASES = {
    "login", "cart", "explore", "become a seller", "sort by", "customer ratings",
    "gst invoice", "no cost emi", "special price", "buy more", "show more",
    "categories", "filters",
}

_WORD_RE = re.compile(r"[a-zA-Z]+")
_CASE_TRANSITION_RE = re.compile(r"[a-z][A-Z]")
_UNIT_QTY_RE = re.compile(r"\d+\s?(ml|kg|g|cm|pcs|pack|watt|inch)", re.IGNORECASE)
_DIGIT_RE = re.compile(r"\d")
_ALNUM_RE = re.compile(r"[a-zA-Z0-9]")


def _has_ui_phrase(lower_text: str) -> bool:
    for phrase in UI_NOISE_PHRASES:
        if re.search(rf"\b{re.escape(phrase)}\b", lower_text):
            return True
    return False


def looks_like_product_title(text: str) -> bool:
    """False for nav/filter/breadcrumb/price-slider junk; True for real titles."""
    if not text:
        return False
    stripped = text.strip()
    lower = stripped.lower()
    words = stripped.split()

    if len(stripped) < 20 or len(words) < 3:
        return False
    if _has_ui_phrase(lower):
        return False
    if "--" in stripped or "low to high" in lower:
        return False
    if "★" in stripped or "₹" in stripped:  # star rating glyph, rupee sign
        return False
    if len(_CASE_TRANSITION_RE.findall(stripped)) >= 2:  # "HomeToys and GamesSoft Toys"
        return False

    alnum_chars = _ALNUM_RE.findall(stripped)
    has_digits = bool(_DIGIT_RE.search(stripped))
    if alnum_chars:
        digit_share = len(_DIGIT_RE.findall(stripped)) / len(alnum_chars)
        if digit_share > 0.4:  # price sliders like "Min5001000150020004000"
            return False

    if "&" in stripped and not has_digits and len(words) < 6:  # bare breadcrumb, e.g. "Decor lighting & Accessories"
        return False

    has_descriptive_word = any(w.islower() or (w[:1].isupper() and w[1:].islower()) for w in words if w.isalpha())
    has_unit_qty = bool(_UNIT_QTY_RE.search(stripped))
    if not (has_descriptive_word or len(words) >= 7 or has_unit_qty):
        return False

    return True
