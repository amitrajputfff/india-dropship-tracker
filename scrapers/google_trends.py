"""Google Trends India - the one genuinely free, unlimited, unofficial-API source.

pytrends' `trending_searches()` call hits an endpoint Google has repeatedly
changed/removed (it 404s as of mid-2026), so this uses Google's daily-trends
RSS feed instead - it's unofficial too, but has stayed stable far longer.
"""

import requests
import xml.etree.ElementTree as ET

from config import REQUEST_HEADERS, REQUEST_TIMEOUT_SECONDS

RSS_URL = "https://trends.google.com/trending/rss?geo=IN"


def fetch_trending_searches(country: str = "IN"):
    """Return today's top trending search terms for India."""
    resp = requests.get(RSS_URL, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT_SECONDS)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    titles = [item.findtext("title") for item in root.iter("item")]
    return [t for t in titles if t]
