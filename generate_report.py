#!/usr/bin/env python3
"""Daily entry point: scrape all sources, score, render the HTML report.

Usage:
    python generate_report.py [--open]

Writes output/report-<YYYY-MM-DD>.html and output/latest.html (same content,
stable filename so you can bookmark/open it without checking the date).
"""

import argparse
import os
import webbrowser
from collections import Counter
from datetime import date

from jinja2 import Template

import llm_kpi_judge
from aggregator import attach_sourcing_checks, build_top_picks, filter_dropshippable
from config import (
    AMAZON_CATEGORIES,
    CANDIDATE_POOL_SIZE,
    ENABLED_SOURCES,
    FLIPKART_KEYWORDS,
    FUN_PRODUCT_KEYWORDS,
    MEESHO_KEYWORDS,
    MYNTRA_KEYWORDS,
    OUTPUT_DIR,
    SNAPDEAL_KEYWORDS,
    SOURCING_CHECK_TOP_N,
    TOP_PICKS_COUNT,
)
from kpi_scoring import MIN_KPIS_TO_PASS
from scrapers import alibaba, aliexpress, amazon_in, amazon_search, flipkart_in, google_trends, meesho, myntra, snapdeal

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def _fetch_keyword_source(label, keywords, fetch_fn, enabled):
    if not enabled:
        print(f"Skipping {label} (disabled in config.ENABLED_SOURCES)")
        return []
    print(f"Fetching {label}...")
    results = []
    for kw in keywords:
        result = fetch_fn(kw)
        print(f"  {kw}: {'ok' if not result['error'] else 'FAILED - ' + result['error']}")
        results.append(result)
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--open", action="store_true", help="open the report in your browser when done")
    args = parser.parse_args()

    print("Fetching Google Trends (India)...")
    try:
        trending_terms = google_trends.fetch_trending_searches()
        print(f"  ok - {len(trending_terms)} terms")
    except Exception as exc:  # upstream endpoint can change without notice
        print(f"  FAILED - {exc}")
        trending_terms = []

    print("Fetching Amazon.in bestsellers...")
    amazon_results = []
    for name, url in AMAZON_CATEGORIES.items():
        result = amazon_in.fetch_category_bestsellers(name, url)
        print(f"  {name}: {'ok' if not result['error'] else 'FAILED - ' + result['error']}")
        amazon_results.append(result)

    print("Fetching Amazon.in search results (novelty/gift/decor archetype)...")
    amazon_search_results = []
    for kw in FUN_PRODUCT_KEYWORDS:
        result = amazon_search.fetch_keyword_search(kw)
        print(f"  {kw}: {'ok' if not result['error'] else 'FAILED - ' + result['error']}")
        amazon_search_results.append(result)

    flipkart_results = _fetch_keyword_source(
        "Flipkart trending listings", FLIPKART_KEYWORDS, flipkart_in.fetch_keyword_trending, ENABLED_SOURCES["flipkart"]
    )
    meesho_results = _fetch_keyword_source(
        "Meesho trending listings", MEESHO_KEYWORDS, meesho.fetch_keyword_trending, ENABLED_SOURCES["meesho"]
    )
    myntra_results = _fetch_keyword_source(
        "Myntra trending listings", MYNTRA_KEYWORDS, myntra.fetch_keyword_trending, ENABLED_SOURCES["myntra"]
    )
    snapdeal_results = _fetch_keyword_source(
        "Snapdeal trending listings", SNAPDEAL_KEYWORDS, snapdeal.fetch_keyword_trending, ENABLED_SOURCES["snapdeal"]
    )

    print("Filtering out junk/branded/non-dropshippable products...")
    for results in (amazon_results, amazon_search_results, flipkart_results, meesho_results, myntra_results, snapdeal_results):
        filter_dropshippable(results)

    print(f"Ranking candidates, round-robin selecting {CANDIDATE_POOL_SIZE}, judging against the {MIN_KPIS_TO_PASS}/13 KPI rubric...")
    top_picks = build_top_picks(
        [
            ("Amazon.in", amazon_results),
            ("Amazon Search", amazon_search_results),
            ("Flipkart", flipkart_results),
            ("Meesho", meesho_results),
            ("Myntra", myntra_results),
            ("Snapdeal", snapdeal_results),
        ],
        trending_terms,
        kpi_judger=llm_kpi_judge.judge,
        top_n=TOP_PICKS_COUNT,
        candidate_pool_size=CANDIDATE_POOL_SIZE,
    )

    all_judged = top_picks["passed"] + top_picks["near_misses"]
    histogram = Counter(e["kpi"]["count"] for e in all_judged)
    histogram_str = ", ".join(f"{n}/13:{histogram[n]}" for n in sorted(histogram, reverse=True))
    print(
        f"  judged {top_picks['candidates_judged']} candidates "
        f"({top_picks['excluded_as_brand']} excluded as recognizable brands) - counts: {histogram_str}"
    )
    print(f"  {len(top_picks['passed'])} passed, {len(top_picks['near_misses'])} near-miss backfill")
    for tag, tier in (("PASS", top_picks["passed"]), ("near-miss", top_picks["near_misses"])):
        for pick in tier:
            print(f"    [{tag}] {pick['kpi']['count']}/13 ({pick['kpi']['source']}): {pick['title'][:60]!r}")

    print(f"Checking supplier availability (Alibaba/AliExpress) for top {SOURCING_CHECK_TOP_N} passed picks...")
    top_picks["passed"] = attach_sourcing_checks(
        top_picks["passed"], alibaba.check_sourcing, aliexpress.check_sourcing, SOURCING_CHECK_TOP_N
    )
    for pick in top_picks["passed"][:SOURCING_CHECK_TOP_N]:
        ali_ok = pick["sourcing"]["alibaba"]["available"]
        aliexp_ok = pick["sourcing"]["aliexpress"]["available"]
        print(f"  {pick['title'][:50]!r}: Alibaba={ali_ok} AliExpress={aliexp_ok}")

    output_dir = os.path.join(SCRIPT_DIR, OUTPUT_DIR)
    os.makedirs(output_dir, exist_ok=True)
    today = date.today().isoformat()
    out_path = os.path.join(output_dir, f"report-{today}.html")
    latest_path = os.path.join(output_dir, "latest.html")

    template_path = os.path.join(SCRIPT_DIR, "report_template.html")
    with open(template_path, encoding="utf-8") as f:
        template = Template(f.read())

    html = template.render(
        report_date=today,
        top_picks=top_picks,
        trending_terms=trending_terms,
        amazon_results=amazon_results,
        amazon_search_results=amazon_search_results,
        flipkart_results=flipkart_results,
        meesho_results=meesho_results,
        myntra_results=myntra_results,
        snapdeal_results=snapdeal_results,
        min_kpis=MIN_KPIS_TO_PASS,
    )

    for path in (out_path, latest_path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)

    print(f"\nReport written to {out_path}")
    print(f"(also updated {latest_path})")

    if args.open:
        webbrowser.open(f"file://{out_path}")


if __name__ == "__main__":
    main()
