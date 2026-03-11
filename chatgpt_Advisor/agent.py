from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

import httpx


MANDATORY_INSURANCE_FIELDS = [
    "email_id",
    "driver_age",
    "vehicle_registration_number",
    "vehicle_manufacturer_name",
    "vehicle_model",
    "vehicle_year",
    "type_of_fuel",
    "type_of_Cover_needed",
    "No_Claim_bonus_years",
    "Voluntary_Excess",
    "current_insurance_provider",
    "policy_id",
    "policy_type",
    "current_date",
]


FIELD_QUESTIONS = {
    "email_id": "What email should I use for your quote?",
    "driver_age": "How old is the main driver?",
    "vehicle_registration_number": "What is the vehicle registration number?",
    "vehicle_manufacturer_name": "Which vehicle manufacturer is it? (e.g., Toyota)",
    "vehicle_model": "What is the vehicle model? (e.g., Corolla)",
    "vehicle_year": "What is the vehicle year of manufacture? (e.g., 2019)",
    "type_of_fuel": "What is the fuel type? Choose one: Electric, Hybrid, Petrol, Diesel.",
    "type_of_Cover_needed": "Which cover do you need? Choose one: comprehensive, third_party_and_fire, third_party_only.",
    "No_Claim_bonus_years": "How many no-claim bonus years do you have? (0-20)",
    "Voluntary_Excess": "What voluntary excess amount (£) do you want?",
    "current_insurance_provider": "Who is your current insurance provider?",
    "policy_id": "What is your current policy ID?",
    "policy_type": "What is the policy type? (e.g., car)",
    "current_date": "What is today's date for this search? Use YYYY-MM-DD format.",
    "user_preferences": "Tell me your preference in one line (budget + must-have features).",
}


@dataclass
class SessionState:
    insurance_details: dict[str, Any]
    user_preferences: str | None
    conversation_history: list[dict[str, str]]


class AdvisorAgent:
    """
    Conversational quote advisor:
    - Collects mandatory fields in a natural sequence (3 first, then 2).
    - Calls Alfie /complete-analysis once all mandatory fields are present.
    - Returns only top-5 lowest quotes: provider + cost.
    """

    def __init__(self, complete_analysis_url: str, timeout_seconds: float = 120.0):
        self.complete_analysis_url = complete_analysis_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._sessions: dict[str, SessionState] = {}

    def get_or_create_session(self, session_id: str | None) -> tuple[str, SessionState]:
        sid = session_id or str(uuid.uuid4())
        if sid not in self._sessions:
            self._sessions[sid] = SessionState(
                insurance_details={},
                user_preferences=None,
                conversation_history=[],
            )
        return sid, self._sessions[sid]

    def merge_inputs(
        self,
        session: SessionState,
        provided_insurance_details: dict[str, Any] | None,
        provided_user_preferences: str | None,
        user_message: str | None,
    ) -> None:
        if provided_insurance_details:
            session.insurance_details.update(
                {k: v for k, v in provided_insurance_details.items() if v is not None}
            )
        if provided_user_preferences:
            session.user_preferences = provided_user_preferences
        if user_message:
            session.conversation_history.append({"role": "user", "content": user_message})

    def missing_fields(self, session: SessionState) -> list[str]:
        missing = [f for f in MANDATORY_INSURANCE_FIELDS if not session.insurance_details.get(f)]
        if not session.user_preferences:
            missing.append("user_preferences")
        return missing

    def next_questions(self, missing: list[str], first_turn: bool) -> list[dict[str, str]]:
        if not missing:
            return []
        count = 3 if first_turn else 2
        ask = missing[:count]
        return [{"field": field, "question": FIELD_QUESTIONS[field]} for field in ask]

    async def run_complete_analysis(self, session: SessionState) -> dict[str, Any]:
        payload = {
            "insurance_details": session.insurance_details,
            "user_preferences": session.user_preferences,
            "conversation_history": session.conversation_history,
            "trust_pilot_data": None,
            "defacto_ratings": None,
        }
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{self.complete_analysis_url}/complete-analysis",
                json=payload,
            )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def top_5_lowest_quotes(complete_analysis_response: dict[str, Any]) -> list[dict[str, Any]]:
        quotes = complete_analysis_response.get("quotes_with_insights", [])
        ranked = []
        for quote in quotes:
            provider = quote.get("insurer_name")
            cost = quote.get("price_analysis", {}).get("quote_price")
            if provider is not None and cost is not None:
                ranked.append({"provider": provider, "cost": float(cost)})
        ranked.sort(key=lambda x: x["cost"])
        return ranked[:5]

