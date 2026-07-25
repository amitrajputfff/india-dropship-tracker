"""Scores scraped products and cross-references them against Google Trends.

Products from different sources never match by exact string (a bestseller
title like "boAt Airdopes 141 Bluetooth Earbuds" vs a trend term like
"wireless earbuds" share no exact substring), so matching is done by token
overlap instead of exact/fuzzy string comparison.
"""

import re

from config import BRAND_BLOCKLIST, NOISE_PHRASES

_STOPWORDS = {"the", "a", "an", "for", "with", "and", "of", "in", "on", "to", "pack", "set"}


def _tokenize(title: str):
    words = re.findall(r"[a-zA-Z]+", title.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 2}


def is_dropshippable(title: str) -> bool:
    """False for recognizable brands (can't source them wholesale) or noise entries."""
    lower = f" {title.lower()} "
    if any(brand in lower for brand in BRAND_BLOCKLIST):
        return False
    if any(phrase in lower for phrase in NOISE_PHRASES):
        return False
    return True


def filter_dropshippable(results):
    """Drop non-dropshippable products from each result's "products" list in place."""
    for result in results:
        result["products"] = [p for p in result["products"] if is_dropshippable(p["title"])]
    return results


def _overlap_ratio(tokens_a, tokens_b) -> float:
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / min(len(tokens_a), len(tokens_b))


def _entry_source_label(source_name, result):
    if "category" in result:
        return f"{source_name} - {result['category']}"
    return f'{source_name} - "{result["keyword"]}"'


def rank_candidates(sources, trending_terms):
    """Merge and rank products across all retail sources by momentum (no KPI gate).

    `sources` is a list of (source_name, results) pairs, e.g.
    [("Amazon.in", amazon_results), ("Flipkart", flipkart_results), ...].
    Each result dict has "error", "products" (list of {"rank","title"}), and
    either a "category" or "keyword" field for display.

    Score = 1/rank (higher for better-ranked items) + a bonus for matching a
    live Google Trends term + a bonus for showing up under more than one
    source/category (i.e. cross-platform confirmation).
    """
    trend_tokens = [(_tokenize(term), term) for term in trending_terms]

    entries = []
    for source_name, results in sources:
        for result in results:
            label = _entry_source_label(source_name, result)
            for item in result["products"]:
                entries.append({"title": item["title"], "source": label, "rank": item["rank"]})

    scored = []
    for entry in entries:
        tokens = _tokenize(entry["title"])
        rank_score = 1.0 / entry["rank"]

        best_overlap, trend_match = 0.0, None
        for trend_tok, trend_term in trend_tokens:
            overlap = _overlap_ratio(tokens, trend_tok)
            if overlap > best_overlap:
                best_overlap, trend_match = overlap, trend_term

        trend_bonus = best_overlap * 2.0 if best_overlap >= 0.5 else 0.0

        scored.append(
            {
                **entry,
                "score": rank_score + trend_bonus,
                "trend_match": trend_match if trend_bonus > 0 else None,
            }
        )

    # Merge near-duplicate titles across sources so the same product
    # appearing on Amazon *and* Flipkart counts as one stronger signal,
    # not two separate weak ones.
    merged = []
    for entry in sorted(scored, key=lambda e: -e["score"]):
        tokens = _tokenize(entry["title"])
        match = next((m for m in merged if _overlap_ratio(tokens, _tokenize(m["title"])) > 0.6), None)
        if match:
            match["sources"].append(entry["source"])
            match["score"] += entry["score"] * 0.5
            if entry["trend_match"] and not match["trend_match"]:
                match["trend_match"] = entry["trend_match"]
        else:
            merged.append({**entry, "sources": [entry["source"]]})

    merged.sort(key=lambda e: -e["score"])
    for e in merged:
        e["score"] = round(e["score"], 2)
    return merged


def build_top_picks(sources, trending_terms, kpi_judger, top_n=15, candidate_pool_size=25):
    """Rank by momentum, then gate the top `candidate_pool_size` on the 13-KPI rubric.

    KPI judging (an LLM call per candidate) only runs on the momentum-ranked
    shortlist, not every scraped product, to keep the number of judge calls
    bounded and predictable regardless of how many sources/categories are
    configured. `kpi_judger(title, category_hint)` must return
    {"matched", "count", "passes", "source"} - see kpi_scoring.score_kpis /
    llm_kpi_judge.judge.
    """
    candidates = rank_candidates(sources, trending_terms)[:candidate_pool_size]

    for e in candidates:
        e["kpi"] = kpi_judger(e["title"], " ".join(e["sources"]))

    qualified = [e for e in candidates if e["kpi"]["passes"]]
    qualified.sort(key=lambda e: (-e["kpi"]["count"], -e["score"]))
    return qualified[:top_n]


def attach_sourcing_checks(top_picks, alibaba_checker, aliexpress_checker, top_n):
    """Run the Alibaba/AliExpress supplier-availability check against the top N picks.

    Mutates and returns top_picks with an added "sourcing" dict per checked pick:
    {"alibaba": {...}, "aliexpress": {...}}. Picks beyond top_n are left as-is
    (sourcing = None) to bound the number of extra HTTP requests per run.
    """
    for pick in top_picks[:top_n]:
        pick["sourcing"] = {
            "alibaba": alibaba_checker(pick["title"]),
            "aliexpress": aliexpress_checker(pick["title"]),
        }
    for pick in top_picks[top_n:]:
        pick["sourcing"] = None
    return top_picks
