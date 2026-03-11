"""
Google ADK Insurance Advisor Agent

This agent:
1. Collects required insurance inputs conversationally.
2. Calls Alfie /complete-analysis endpoint.
3. Returns top 5 lowest quotes with provider and cost only.
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from google.adk.agents import Agent


ALFIE_BASE_URL = os.getenv(
    "ALFIE_BASE_URL",
    "https://alfie-657860957693.europe-west4.run.app",
)


def get_top_5_quotes(
    email_id: str,
    driver_age: int,
    vehicle_registration_number: str,
    vehicle_manufacturer_name: str,
    vehicle_model: str,
    vehicle_year: int,
    type_of_fuel: str,
    type_of_Cover_needed: str,
    No_Claim_bonus_years: int,
    Voluntary_Excess: float,
    current_insurance_provider: str,
    policy_id: str,
    policy_type: str,
    current_date: str,
    user_preferences: str,
) -> dict[str, Any]:
    """
    Get insurance analysis and return the top 5 lowest-price quotes.

    Args are mandatory fields required by the underlying insurance API.
    """
    payload = {
        "insurance_details": {
            "email_id": email_id,
            "driver_age": driver_age,
            "vehicle_registration_number": vehicle_registration_number,
            "vehicle_manufacturer_name": vehicle_manufacturer_name,
            "vehicle_model": vehicle_model,
            "vehicle_year": vehicle_year,
            "type_of_fuel": type_of_fuel,
            "type_of_Cover_needed": type_of_Cover_needed,
            "No_Claim_bonus_years": No_Claim_bonus_years,
            "Voluntary_Excess": Voluntary_Excess,
            "current_insurance_provider": current_insurance_provider,
            "policy_id": policy_id,
            "policy_type": policy_type,
            "current_date": current_date,
        },
        "user_preferences": user_preferences,
        "conversation_history": [],
        "trust_pilot_data": None,
        "defacto_ratings": None,
    }

    try:
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{ALFIE_BASE_URL.rstrip('/')}/complete-analysis",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as exc:
        return {
            "status": "error",
            "message": f"Alfie API error: {exc.response.status_code}",
            "detail": exc.response.text,
        }
    except httpx.RequestError as exc:
        return {
            "status": "error",
            "message": "Failed to reach Alfie API",
            "detail": str(exc),
        }

    ranked: list[dict[str, Any]] = []
    for quote in data.get("quotes_with_insights", []):
        provider = quote.get("insurer_name")
        cost = quote.get("price_analysis", {}).get("quote_price")
        if provider is not None and cost is not None:
            ranked.append({"provider": provider, "cost": float(cost)})

    ranked.sort(key=lambda x: x["cost"])
    return {
        "status": "ok",
        "top_5_quotes": ranked[:5],
        "total_quotes_received": len(ranked),
    }


root_agent = Agent(
    name="insurance_quote_advisor",
    model="gemini-2.5-flash",
    description="Personal insurance advisor that collects required details and returns top 5 lowest quotes.",
    instruction=(
        "You are a personal insurance advisor. Keep the conversation natural and concise. "
        "Collect missing mandatory fields progressively (start by asking around 3 questions, then 2). "
        "When all required details are available, call the get_top_5_quotes tool. "
        "Return only provider and cost for top 5 lowest quotes."
    ),
    tools=[get_top_5_quotes],
)

