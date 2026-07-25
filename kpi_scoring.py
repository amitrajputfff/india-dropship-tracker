"""Defines the 13-KPI dropship rubric:

  1. Small in size            8. Solves a real problem / fills a gap
  2. Easy to ship              9. Saves people money
  3. High margin              10. Extremely unique
  4. Proof of concept from    11. Improves quality of life
     past winners             12. High perceived value
  5. Improves confidence      13. Woman-dominated audience
  6. Improves convenience
  7. Saves people time

A product needs >= MIN_KPIS_TO_PASS (7) matched to be worth testing.

Scoring itself is done entirely by llm_kpi_judge.judge() (Gemini) - things
like "feels premium" or "builds confidence" aren't judgable from a title by
keyword matching, and a prior keyword-based scorer capped out at 5/13 on a
known-good reference product (a silicone sink guard), well under the 7/13
bar, while Gemini judging the same product hit 9/13. There is deliberately
no keyword-based fallback: a candidate Gemini can't judge is excluded rather
than given an approximate score.
"""

KPI_NAMES = [
    "Small in size",
    "Easy to ship",
    "High margin",
    "Proof of concept from past winners",
    "Improves confidence",
    "Improves convenience",
    "Saves people time",
    "Solves a real problem / fills a gap",
    "Saves people money",
    "Extremely unique",
    "Improves quality of life",
    "High perceived value",
    "Woman-dominated audience",
]

MIN_KPIS_TO_PASS = 7
