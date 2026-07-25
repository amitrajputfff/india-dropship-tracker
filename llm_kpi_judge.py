"""LLM-based judging against the 13-KPI dropship rubric (see kpi_scoring.py).

A title alone can't reveal "feels premium" or "builds confidence" - keyword
matching maxed out at 5/13 on a known-good reference product (a silicone sink
guard), well under the 7/13 bar. Gemini judging the same product hit 9/13, so
every candidate is judged by the model instead of pattern-matched.

Also asks the model to flag recognizable brands directly. config.BRAND_BLOCKLIST
is a free substring pre-filter, but it structurally can't separate a small
D2C brand ("Zulaxy", "JIALTO") from a national one ("Boldfit", "Cetaphil") -
they don't share distinguishing words. A live run caught 0/121 real brand
leaks with the blocklist alone; this is the backstop.

Requires GEMINI_API_KEY (loaded from a local .env file via python-dotenv,
never hardcoded). If it's missing, or every retry fails, callers fall back to
the keyword heuristic in kpi_scoring.py with a "source" field flagging the
fallback - the report will show which picks got a real judgment vs. a
best-effort guess.
"""

import json
import os
import time

from dotenv import load_dotenv

from kpi_scoring import KPI_KEYWORDS, MIN_KPIS_TO_PASS, score_kpis as _keyword_score_kpis

load_dotenv()

KPI_NAMES = list(KPI_KEYWORDS.keys())
MODEL = "gemini-2.5-flash"
MAX_ATTEMPTS = 2  # one retry on a transient error before falling back to keyword scoring

_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "matched_kpis": {"type": "ARRAY", "items": {"type": "STRING", "enum": KPI_NAMES}},
        "is_recognizable_brand": {
            "type": "BOOLEAN",
            "description": "True if this is a nationally/internationally recognized brand with its "
            "own supply chain (e.g. Nike, Cetaphil, Boldfit) - False for a no-name marketplace "
            "seller label (e.g. Zulaxy, JIALTO) that could plausibly be a dropshipper's own listing.",
        },
    },
    "required": ["matched_kpis", "is_recognizable_brand"],
}

_RUBRIC_TEXT = "\n".join(f"- {name}" for name in KPI_NAMES)

_client = None
_client_load_attempted = False


def _get_client():
    global _client, _client_load_attempted
    if _client_load_attempted:
        return _client
    _client_load_attempted = True
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    from google import genai

    _client = genai.Client(api_key=api_key)
    return _client


def judge(title: str, category_hint: str = ""):
    """Return {"matched", "count", "passes", "is_recognizable_brand", "source"}.

    "source" is "llm" on success, or "keyword-fallback (<reason>)" if no API
    key is set or every attempt failed.
    """
    client = _get_client()
    if client is None:
        fallback = _keyword_score_kpis(title, category_hint)
        return {**fallback, "source": "keyword-fallback (no GEMINI_API_KEY set)"}

    prompt = (
        "You are screening a candidate dropshipping product against a standard 13-point rubric. "
        "A product is worth testing only if it genuinely matches at least 7 of these 13 KPIs:\n"
        f"{_RUBRIC_TEXT}\n\n"
        f"Product title: {title}\n"
        f"Category: {category_hint or 'unknown'}\n\n"
        "Judge honestly based on what a real online shopper would perceive - do not assume a KPI "
        "is met just because a related word appears in the title. Also flag whether this is a "
        "recognizable brand with its own supply chain, as opposed to a generic marketplace seller "
        "label - a dropshipper can't source someone else's established brand."
    )

    last_exc = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            resp = client.models.generate_content(
                model=MODEL,
                contents=prompt,
                config={"response_mime_type": "application/json", "response_schema": _SCHEMA},
            )
            data = json.loads(resp.text)
            matched = data.get("matched_kpis", [])
            return {
                "matched": matched,
                "count": len(matched),
                "passes": len(matched) >= MIN_KPIS_TO_PASS,
                "is_recognizable_brand": bool(data.get("is_recognizable_brand", False)),
                "source": "llm",
            }
        except Exception as exc:
            last_exc = exc
            if attempt < MAX_ATTEMPTS:
                time.sleep(1.5 * attempt)

    fallback = _keyword_score_kpis(title, category_hint)
    return {**fallback, "source": f"keyword-fallback (Gemini call failed after {MAX_ATTEMPTS} attempts: {last_exc})"}
