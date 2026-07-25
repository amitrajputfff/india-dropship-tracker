"""Scores scraped products and cross-references them against Google Trends.

Products from different sources never match by exact string (a bestseller
title like "boAt Airdopes 141 Bluetooth Earbuds" vs a trend term like
"wireless earbuds" share no exact substring), so matching is done by token
overlap instead of exact/fuzzy string comparison.
"""

import re

from config import BRAND_BLOCKLIST, NOISE_PHRASES
from product_titles import looks_like_product_title

_STOPWORDS = {"the", "a", "an", "for", "with", "and", "of", "in", "on", "to", "pack", "set"}


def _tokenize(title: str):
    words = re.findall(r"[a-zA-Z]+", title.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 2}


def is_dropshippable(title: str) -> bool:
    """False for junk (nav/filter text), recognizable brands, or noise entries."""
    if not looks_like_product_title(title):
        return False
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
    """Min-denominator overlap, used only for trend-term matching.

    Guarded against <2-token sides - without this, a title tokenizing to a
    single word (or a junk fragment) can read as a "perfect" 1.0 match
    against anything, which is exactly how junk once collected a full trend
    bonus it had no business getting.
    """
    if len(tokens_a) < 2 or len(tokens_b) < 2:
        return 0.0
    return len(tokens_a & tokens_b) / min(len(tokens_a), len(tokens_b))


def _jaccard_ratio(tokens_a, tokens_b) -> float:
    """Union-denominator overlap, used for the cross-source merge/dedupe step.

    Min-denominator overlap lets any short token subset (junk, or a shorter
    product title that happens to share words with a longer, unrelated one)
    read as a perfect match. Jaccard requires the two titles to actually be
    *mostly the same set of words*, not just one being a subset of the other -
    this is what stopped three different Purepet flavour variants from
    merging into a single inflated "cross-platform" entry.
    """
    if not tokens_a or not tokens_b:
        return 0.0
    union = tokens_a | tokens_b
    return len(tokens_a & tokens_b) / len(union)


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
    # not two separate weak ones. Jaccard (not min-denominator) so a shorter
    # title can't falsely "contain" an unrelated longer one, and same-source
    # duplicates don't stack score or repeat in the sources badge list.
    merged = []
    for entry in sorted(scored, key=lambda e: -e["score"]):
        tokens = _tokenize(entry["title"])
        match = next((m for m in merged if _jaccard_ratio(tokens, _tokenize(m["title"])) > 0.55), None)
        if match:
            if entry["source"] not in match["sources"]:
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


def _round_robin_select(candidates, pool_size):
    """Pick candidates round-robin across distinct source labels, not a flat top-N slice.

    With 1/rank scoring, a flat top-N-by-score slice is dominated by every
    source's own rank-1/2/3 items (they all score close to 1.0), so ranks 4+
    - where a lot of the actual dropship-shaped products sit - never reach
    the KPI judge at all. Round-robin guarantees every source gets a fair
    share of the pool instead of the highest-momentum few sources eating it.
    """
    buckets, order = {}, []
    for c in candidates:
        key = c["sources"][0]
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(c)

    selected = []
    depth = 0
    while len(selected) < pool_size and any(depth < len(buckets[k]) for k in order):
        for key in order:
            if len(selected) >= pool_size:
                break
            if depth < len(buckets[key]):
                selected.append(buckets[key][depth])
        depth += 1
    return selected


def build_top_picks(sources, trending_terms, kpi_judger, top_n=15, candidate_pool_size=25):
    """Rank by momentum, round-robin a shortlist, then gate on the 13-KPI rubric.

    KPI judging (an LLM call per candidate) only runs on the `candidate_pool_size`
    shortlist, not every scraped product, to keep the number of judge calls
    bounded and predictable regardless of how many sources/categories are
    configured. `kpi_judger(title, category_hint)` must return
    {"matched", "count", "passes", "is_recognizable_brand", "source"} on
    success, or None if the candidate couldn't be judged (e.g. API quota
    exhausted, invalid key) - see llm_kpi_judge.judge. There is no
    keyword-based fallback: an unjudgeable candidate is excluded entirely
    rather than given an approximate score.

    Returns {"passed": [...], "near_misses": [...]} - near_misses is only
    populated to backfill up to `top_n` when fewer than `top_n` candidates
    genuinely pass, so the report can show a full list while staying honest
    about which rows actually cleared the bar.
    """
    merged = rank_candidates(sources, trending_terms)
    candidates = _round_robin_select(merged, candidate_pool_size)

    for e in candidates:
        e["kpi"] = kpi_judger(e["title"], " ".join(e["sources"]))

    judge_failures = sum(1 for e in candidates if e["kpi"] is None)
    judged_candidates = [e for e in candidates if e["kpi"] is not None]

    # The keyword BRAND_BLOCKLIST is a free pre-filter but structurally can't
    # catch every brand (a small D2C brand and a national one often share no
    # distinguishing words) - the judge's own brand call is the backstop.
    judged = [e for e in judged_candidates if not e["kpi"]["is_recognizable_brand"]]

    passed = [e for e in judged if e["kpi"]["passes"]]
    passed.sort(key=lambda e: (-e["kpi"]["count"], -e["score"]))

    near_misses = [e for e in judged if not e["kpi"]["passes"]]
    near_misses.sort(key=lambda e: (-e["kpi"]["count"], -e["score"]))

    remaining = max(0, top_n - len(passed))
    return {
        "passed": passed[:top_n],
        "near_misses": near_misses[:remaining],
        "candidates_judged": len(judged_candidates),
        "excluded_as_brand": len(judged_candidates) - len(judged),
        "judge_failures": judge_failures,
    }


def attach_sourcing_checks(picks, alibaba_checker, aliexpress_checker, top_n):
    """Run the Alibaba/AliExpress supplier-availability check against the top N picks.

    Mutates and returns `picks` with an added "sourcing" dict per checked pick:
    {"alibaba": {...}, "aliexpress": {...}}. Picks beyond top_n are left as-is
    (sourcing = None) to bound the number of extra HTTP requests per run.
    """
    for pick in picks[:top_n]:
        pick["sourcing"] = {
            "alibaba": alibaba_checker(pick["title"]),
            "aliexpress": aliexpress_checker(pick["title"]),
        }
    for pick in picks[top_n:]:
        pick["sourcing"] = None
    return picks
