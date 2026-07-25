"""LLM-based judging against the 13-KPI dropship rubric (see kpi_scoring.py).

A title alone can't reveal "feels premium" or "builds confidence" - a prior
keyword-based scorer maxed out at 5/13 on a known-good reference product (a
silicone sink guard), well under the 7/13 bar. A real LLM judging the same
product hit 7-9/13, so every candidate is judged by a model - there is no
keyword-based fallback. If a candidate can't be judged by any provider,
judge() returns None and the caller excludes that candidate entirely rather
than giving it an approximate score.

Cerebras (gpt-oss-120b) is the primary judge: its free-tier daily quota is
effectively unlimited (1.44M requests/day, confirmed live via response
headers), unlike Gemini's hard 20 requests/day cap, which this project
originally had to calibrate its whole candidate pool size around. Gemini is
kept as a secondary real-LLM check - only used if Cerebras is unavailable or
every attempt against it fails - so a single provider outage doesn't stop
picks from being judged; it never falls back to keyword scoring.

Also asks the model to flag recognizable brands directly. config.BRAND_BLOCKLIST
is a free substring pre-filter, but it structurally can't separate a small
D2C brand ("Zulaxy", "JIALTO") from a national one ("Boldfit", "Cetaphil") -
they don't share distinguishing words. A live run caught 0/121 real brand
leaks with the blocklist alone; this is the backstop.

Requires CEREBRAS_API_KEY and/or GEMINI_API_KEY (loaded from a local .env
file via python-dotenv, never hardcoded) - at least one, ideally both.
"""

import json
import os
import time

import requests
from dotenv import load_dotenv

from kpi_scoring import KPI_NAMES, MIN_KPIS_TO_PASS

load_dotenv()

CEREBRAS_URL = "https://api.cerebras.ai/v1/chat/completions"
CEREBRAS_MODEL = "gpt-oss-120b"
GEMINI_MODEL = "gemini-2.5-flash"
MAX_ATTEMPTS_PER_PROVIDER = 2  # one retry on a transient error before trying the next provider

_VALID_KPI_NAMES = set(KPI_NAMES)
_RUBRIC_TEXT = "\n".join(f"- {name}" for name in KPI_NAMES)

_GEMINI_SCHEMA = {
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

_gemini_client = None
_gemini_client_load_attempted = False


def _build_prompt(title: str, category_hint: str) -> str:
    return (
        "You are screening a candidate dropshipping product against a standard 13-point rubric. "
        "A product is worth testing only if it genuinely matches at least 7 of these 13 KPIs:\n"
        f"{_RUBRIC_TEXT}\n\n"
        f"Product title: {title}\n"
        f"Category: {category_hint or 'unknown'}\n\n"
        "Judge honestly based on what a real online shopper would perceive - do not assume a KPI "
        "is met just because a related word appears in the title. Also flag whether this is a "
        "recognizable brand with its own supply chain, as opposed to a generic marketplace seller "
        "label - a dropshipper can't source someone else's established brand.\n\n"
        "Respond with ONLY a JSON object of exactly this shape, no other text: "
        '{"matched_kpis": [list of matching KPI name strings, copied verbatim from the list above], '
        '"is_recognizable_brand": true or false}'
    )


def _normalize(data: dict, source: str):
    """Validate/clean a provider's parsed JSON into the standard result shape.

    Cerebras has no schema enforcement (just "respond with JSON" in the
    prompt), so matched_kpis could contain a slightly reworded or invalid
    name - silently drop anything that isn't an exact match rather than
    letting it inflate the count.
    """
    matched = [m for m in data.get("matched_kpis", []) if m in _VALID_KPI_NAMES]
    return {
        "matched": matched,
        "count": len(matched),
        "passes": len(matched) >= MIN_KPIS_TO_PASS,
        "is_recognizable_brand": bool(data.get("is_recognizable_brand", False)),
        "source": source,
    }


def _call_cerebras(prompt: str) -> dict:
    api_key = os.environ.get("CEREBRAS_API_KEY")
    if not api_key:
        raise RuntimeError("no CEREBRAS_API_KEY set")
    resp = requests.post(
        CEREBRAS_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": CEREBRAS_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
        },
        timeout=30,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    return json.loads(content)


def _get_gemini_client():
    global _gemini_client, _gemini_client_load_attempted
    if _gemini_client_load_attempted:
        return _gemini_client
    _gemini_client_load_attempted = True
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    from google import genai

    _gemini_client = genai.Client(api_key=api_key)
    return _gemini_client


def _call_gemini(prompt: str) -> dict:
    client = _get_gemini_client()
    if client is None:
        raise RuntimeError("no GEMINI_API_KEY set")
    resp = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config={"response_mime_type": "application/json", "response_schema": _GEMINI_SCHEMA},
    )
    return json.loads(resp.text)


def _try_provider(provider_name: str, call_fn, prompt: str, title: str):
    """Attempt one provider up to MAX_ATTEMPTS_PER_PROVIDER times. Returns a result dict or None."""
    last_exc = None
    for attempt in range(1, MAX_ATTEMPTS_PER_PROVIDER + 1):
        try:
            data = call_fn(prompt)
            return _normalize(data, source=provider_name)
        except Exception as exc:
            last_exc = exc
            if attempt < MAX_ATTEMPTS_PER_PROVIDER:
                time.sleep(1.5 * attempt)
    print(f"    {provider_name} judge failed on {title[:60]!r} after {MAX_ATTEMPTS_PER_PROVIDER} attempts: {last_exc}")
    return None


def judge(title: str, category_hint: str = ""):
    """Return {"matched", "count", "passes", "is_recognizable_brand", "source"}, or None.

    Tries Cerebras first (effectively unlimited daily quota), then Gemini if
    Cerebras is unavailable or fails. None means neither provider could judge
    this candidate - callers should exclude it rather than substitute an
    approximate score.
    """
    prompt = _build_prompt(title, category_hint)

    result = _try_provider("cerebras", _call_cerebras, prompt, title)
    if result is not None:
        return result

    result = _try_provider("gemini", _call_gemini, prompt, title)
    if result is not None:
        return result

    return None
