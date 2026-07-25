"""Heuristic scoring against the standard 13-KPI "good dropship product" rubric:

  1. Small in size            8. Solves a real problem / fills a gap
  2. Easy to ship              9. Saves people money
  3. High margin              10. Extremely unique
  4. Proof of concept from    11. Improves quality of life
     past winners             12. High perceived value
  5. Improves confidence      13. Woman-dominated audience
  6. Improves convenience
  7. Saves people time

Rule of thumb: a product needs >= MIN_KPIS_TO_PASS (7) matched to be worth
testing. We only have a product title (and category) to go on - no real
cost, weight, or margin data - so every KPI here is a keyword-based proxy,
not a certainty. Treat the count as "worth a closer look," not proof.

If a KPI keeps mis-firing (or missing) on products you manually check,
tune its keyword set below rather than adding a new scraper - the rubric
should stay stable, the keyword tuning is what improves over time.
"""

import re

MIN_KPIS_TO_PASS = 7

KPI_KEYWORDS = {
    "Small in size": {
        "mini", "compact", "small", "clip", "strip", "cover", "guard", "holder",
        "organizer", "tray", "band", "mat", "cable", "pouch",
    },
    "Easy to ship": {
        "silicone", "plastic", "foldable", "portable", "mini", "compact",
        "lightweight", "stackable", "collapsible",
    },
    "High margin": {
        "silicone", "plastic", "gadget", "mini", "compact", "accessory", "reusable",
    },
    "Proof of concept from past winners": {
        "organizer", "corrector", "holder", "stretch", "reusable", "foldable",
        "portable", "slip", "magnetic", "multipurpose", "purpose", "adjustable",
        "splash", "gap", "silicone",
    },
    "Improves confidence": {
        "whitening", "glow", "skin", "confidence", "beauty", "facial", "hair",
    },
    "Improves convenience": {
        "easy", "quick", "instant", "portable", "foldable", "automatic", "touch",
        "mess", "effortless", "hands", "free", "adjustable", "auto",
    },
    "Saves people time": {
        "instant", "quick", "fast", "auto", "automatic", "rapid",
    },
    "Solves a real problem / fills a gap": {
        "splash", "slip", "guard", "protect", "protection", "prevents", "stops",
        "proof", "leakproof", "waterproof", "fix", "solution", "net", "stain", "cover",
    },
    "Saves people money": {
        "reusable", "refillable", "multiuse", "replaces", "multipurpose", "purpose", "pack",
    },
    "Extremely unique": {
        "magic", "genius", "clever", "smart", "innovative", "unique",
    },
    "Improves quality of life": {
        "comfort", "ergonomic", "relax", "wellness", "health", "posture", "massage",
    },
    "High perceived value": {
        "premium", "professional", "heavy", "duty", "upgraded", "pro", "deluxe",
    },
    "Woman-dominated audience": {
        "beauty", "skin", "hair", "kitchen", "decor", "organizer", "cleaning",
        "facial", "soap", "bath", "cosmetic",
    },
}

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def score_kpis(title: str, category: str = None):
    """Return {"matched": [kpi names], "count": int, "passes": bool}."""
    text = title.lower()
    if category:
        text += " " + category.lower()
    tokens = set(_TOKEN_RE.findall(text))

    matched = [name for name, keywords in KPI_KEYWORDS.items() if tokens & keywords]
    return {"matched": matched, "count": len(matched), "passes": len(matched) >= MIN_KPIS_TO_PASS}
