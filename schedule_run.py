"""
Schedule runner for weekly insurance quote checks.

This script:
- Loads a single JSON request containing insurance details, user preference text,
  start date, and number of iterations.
- Extracts budget and required features from the free-text preference string
  (stubbed LLM-style extractor with simple parsing + aliasing).
- Fetches quotes via a stubbed fetch_quotes() (replace with real API call later).
- For each scheduled run date (every 7 days), reports whether a matching quote
  meets budget and contains all requested features.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional

import httpx


# Lightweight alias map to normalize feature names after extraction.
ALIAS_MAP = {
    "windshield": "windshield_cover",
    "windscreen": "windshield_cover",
    "windshield cover": "windshield_cover",
    "windscreen cover": "windshield_cover",
    "windshield_cover": "windshield_cover",
    "windscreen_cover": "windshield_cover",
    "legal": "legal_cover",
    "legal cover": "legal_cover",
    "legul cover": "legal_cover",
    "courtesy car": "courtesy_car",
    "courtesy_car": "courtesy_car",
    "breakdown": "breakdown_cover",
    "breakdown cover": "breakdown_cover",
    "breakdown_cover": "breakdown_cover",
    "european": "european_cover",
    "european cover": "european_cover",
    "european_cover": "european_cover",
    "europe": "european_cover",
}


@dataclass
class ExtractedPreferences:
    budget: Optional[float]
    features: List[str]
    raw_text: str


@dataclass
class Quote:
    insurer: str
    price: float
    features: List[str]


def call_llm_to_extract_preferences(user_preferences: str) -> ExtractedPreferences:
    """
    Stubbed LLM-style extractor:
    - Picks the first number as budget (assumes GBP).
    - Pulls features by scanning the text for known aliases/typos and normalizing.
    Replace this with a real LLM call that returns JSON
    {"budget": number|null, "features": [strings]} for production.
    """
    budget = None
    number_match = re.search(r"([0-9]+(?:\\.[0-9]+)?)", user_preferences.replace(",", ""))
    if number_match:
        try:
            budget = float(number_match.group(1))
        except ValueError:
            budget = None

    lower_text = user_preferences.lower()
    normalized_features: List[str] = []

    # Scan for known aliases/typos as whole words to reduce false positives.
    for alias, normalized in ALIAS_MAP.items():
        pattern = r"\\b" + re.escape(alias) + r"\\b"
        if re.search(pattern, lower_text):
            if normalized not in normalized_features:
                normalized_features.append(normalized)

    return ExtractedPreferences(budget=budget, features=normalized_features, raw_text=user_preferences)


def normalize_feature_name(feature: str) -> str:
    """
    Normalize feature keys from the API (e.g., legal_cover_included -> legal_cover).
    """
    f = feature.lower().strip()
    if f.endswith("_included"):
        f = f[: -len("_included")]
    return f


def ensure_insurance_fields(insurance_details: Dict) -> Dict:
    """
    Ensure required fields exist for the API; fill minimal placeholders if missing.
    """
    defaults = {
        "current_insurance_provider": "Unknown",
        "policy_id": "UNKNOWN",
        "policy_type": "car",
        "policy_start_date": None,
        "policy_end_date": None,
    }
    result = {**defaults, **insurance_details}
    return result


def fetch_quotes(insurance_details: Dict, user_preferences: str) -> List[Quote]:
    """
    Call the Alfie intelligent API (local service) and map the response to Quote objects.
    """
    api_url = os.getenv("ALFIE_API_URL", "http://localhost:8080/complete-analysis")
    payload = {
        "insurance_details": ensure_insurance_fields(insurance_details),
        "user_preferences": user_preferences,
        "conversation_history": [],
    }

    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(api_url, json=payload)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Failed to fetch quotes from {api_url}: {exc}") from exc

    quotes_raw = data.get("quotes_with_insights", [])
    quotes: List[Quote] = []
    for q in quotes_raw:
        insurer = q.get("insurer_name") or q.get("original_quote", {}).get("output", {}).get("insurer_name", "Unknown")
        price = (
            q.get("price_analysis", {}).get("quote_price")
            or q.get("original_quote", {}).get("output", {}).get("policy_cost")
        )
        available_features = q.get("available_features", [])
        normalized = [normalize_feature_name(f) for f in available_features]

        if price is None:
            continue

        quotes.append(Quote(insurer=insurer, price=float(price), features=normalized))

    return quotes


def matches_requirements(quote: Quote, budget: Optional[float], required_features: List[str]) -> bool:
    if budget is not None and quote.price > budget:
        return False
    if required_features:
        missing = [f for f in required_features if f not in quote.features]
        if missing:
            return False
    return True


def find_best_match(quotes: List[Quote], budget: Optional[float], required_features: List[str]) -> Optional[Quote]:
    candidates = [q for q in quotes if matches_requirements(q, budget, required_features)]
    if not candidates:
        return None
    return min(candidates, key=lambda q: q.price)


def parse_date(date_str: str) -> dt.date:
    return dt.datetime.strptime(date_str, "%Y-%m-%d").date()


def load_request(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_schedule(request_path: str) -> None:
    data = load_request(request_path)
    insurance_details = data.get("insurance_details", {})
    user_pref_text = data.get("user_preferences", "")
    iterations = int(data.get("iterations", 10))
    start_date_str = data.get("start_date", "2025-11-23")

    prefs = call_llm_to_extract_preferences(user_pref_text)
    required_features = prefs.features
    budget = prefs.budget

    start_date = parse_date(start_date_str)
    interval_days = 7

    for i in range(iterations):
        run_date = start_date + dt.timedelta(days=i * interval_days)
        quotes = fetch_quotes(insurance_details, user_pref_text)
        match = find_best_match(quotes, budget, required_features)

        if match:
            message = (
                f"found {match.insurer} quote for £{match.price:.2f}, below budget £{budget:.2f} "
                f"with all requested features"
                if budget is not None
                else f"found {match.insurer} quote for £{match.price:.2f} with requested features"
            )
            print(f"date: {run_date.isoformat()}, match_found: yes, message: {message}")
        else:
            reason = []
            if budget is not None:
                reason.append("no quote within budget")
            if required_features:
                reason.append("missing required features")
            reason_text = " and ".join(reason) if reason else "no quotes available"
            print(f"date: {run_date.isoformat()}, match_found: no, message: {reason_text}")


if __name__ == "__main__":
    request_file = sys.argv[1] if len(sys.argv) > 1 else "request.json"
    run_schedule(request_file)
