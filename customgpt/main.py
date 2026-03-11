from datetime import date
from typing import Literal
import random

from fastapi import FastAPI
from pydantic import BaseModel, EmailStr, Field

app = FastAPI(
    title="CustomGPT Admiral Quote Service",
    description="Standalone Admiral premium quote API using 10 user fields",
    version="1.0.0",
)


class AdmiralQuoteRequest(BaseModel):
    email_id: EmailStr
    driver_age: int = Field(..., ge=18, le=100)
    vehicle_registration_number: str
    vehicle_manufacturer_name: str
    vehicle_model: str
    vehicle_year: int = Field(..., ge=1980, le=2025)
    type_of_fuel: Literal["Electric", "Hybrid", "Petrol", "Diesel"]
    type_of_Cover_needed: Literal[
        "comprehensive", "third_party_and_fire", "third_party_only"
    ]
    No_Claim_bonus_years: int = Field(..., ge=0, le=20)
    Voluntary_Excess: float = Field(..., ge=0)


class QuoteOutput(BaseModel):
    quote_reference_number: str
    insurer_name: str
    policy_cost: float
    pre_discount_cost: float
    post_discount_cost: float
    type_of_policy: str
    total_excess_amount: float
    legal_cover_included: Literal["yes", "no"]
    windshield_cover_included: Literal["yes", "no"]
    courtesy_car_included: Literal["yes", "no"]
    breakdown_cover_included: Literal["yes", "no"]
    personal_Accident_cover_included: Literal["yes", "no"]
    european_cover_included: Literal["yes", "no"]
    no_claim_bonus_protection_included: Literal["yes", "no"]
    discount_applied: Literal["yes", "no"]


class InsuranceQuoteResponse(BaseModel):
    input: dict
    output: QuoteOutput


UK_MONTHLY_AVERAGE_PREMIUMS = {
    1: 668.05,
    2: 625.32,
    3: 656.97,
    4: 668.47,
    5: 676.23,
    6: 648.74,
    7: 614.48,
    8: 578.33,
    9: 579.25,
    10: 586.89,
    11: 633.92,
    12: 610.84,
}
UK_ANNUAL_AVERAGE_PREMIUM = sum(UK_MONTHLY_AVERAGE_PREMIUMS.values()) / len(
    UK_MONTHLY_AVERAGE_PREMIUMS
)

ADMRIAL_BIAS_RANGE = (0.96, 0.99)


def calculate_base_price(req: AdmiralQuoteRequest) -> float:
    base = 650

    car_age = 2025 - req.vehicle_year
    if car_age > 15:
        base += 180
    elif car_age > 10:
        base += 120
    elif car_age > 5:
        base += 60
    elif car_age <= 2:
        base -= 40

    fuel_adjustments = {
        "Electric": -120,
        "Hybrid": -60,
        "Petrol": 20,
        "Diesel": 60,
    }
    base += fuel_adjustments[req.type_of_fuel]

    premium_brands = [
        "bmw",
        "mercedes",
        "audi",
        "porsche",
        "jaguar",
        "land rover",
        "lexus",
        "maserati",
        "bentley",
        "ferrari",
        "lamborghini",
    ]
    budget_brands = ["dacia", "skoda", "seat", "suzuki", "kia", "hyundai"]

    brand_lower = req.vehicle_manufacturer_name.lower()
    if any(brand in brand_lower for brand in premium_brands):
        base += 140
    elif any(brand in brand_lower for brand in budget_brands):
        base -= 50

    if req.driver_age < 25:
        base += 250
    elif req.driver_age < 30:
        base += 120
    elif req.driver_age > 75:
        base += 180
    elif req.driver_age > 70:
        base += 100
    elif 30 <= req.driver_age <= 50:
        base -= 40

    coverage_multipliers = {
        "comprehensive": 1.0,
        "third_party_and_fire": 0.70,
        "third_party_only": 0.45,
    }
    base *= coverage_multipliers[req.type_of_Cover_needed]

    ncb_discount = min(req.No_Claim_bonus_years * 0.07, 0.50)
    base *= 1 - ncb_discount

    excess_discount = min(req.Voluntary_Excess / 1000 * 0.12, 0.25)
    base *= 1 - excess_discount

    low, high = ADMRIAL_BIAS_RANGE
    base *= random.uniform(low, high)

    base = max(400, min(1700, base))
    return round(base, 2)


def apply_discount(price: float) -> tuple[float, bool, float]:
    discounted = random.randint(1, 30) == 1
    original_price = price
    if discounted:
        price *= random.uniform(0.98, 0.99)
    return round(price, 2), discounted, round(original_price, 2)


def apply_uk_market_movement(price: float, current_date: date) -> float:
    month_avg = UK_MONTHLY_AVERAGE_PREMIUMS[current_date.month]
    market_factor = month_avg / UK_ANNUAL_AVERAGE_PREMIUM
    return round(price * market_factor, 2)


def get_features() -> dict:
    all_features = {
        "legal_cover_included": "yes",
        "windshield_cover_included": "yes",
        "courtesy_car_included": "yes",
        "breakdown_cover_included": "yes",
        "personal_Accident_cover_included": "yes",
        "european_cover_included": "yes",
        "no_claim_bonus_protection_included": "yes",
    }

    enabled_count = random.randint(5, 6)
    selected = random.sample(list(all_features.keys()), enabled_count)
    return {k: ("yes" if k in selected else "no") for k in all_features}


@app.post("/quote/admiral", response_model=InsuranceQuoteResponse)
async def admiral_quote(req: AdmiralQuoteRequest):
    current_date = date.today()

    price = calculate_base_price(req)
    price = apply_uk_market_movement(price, current_date)
    price, discount_applied, original_price = apply_discount(price)
    features = get_features()

    return {
        "input": {
            **req.model_dump(mode="json"),
            "current_date": current_date.isoformat(),
            "current_insurance_provider": "unknown",
            "policy_id": "NA",
            "policy_type": "motor",
        },
        "output": {
            "quote_reference_number": f"Q_Admiral_{random.randint(10000, 99999)}",
            "insurer_name": "Admiral",
            "policy_cost": price,
            "pre_discount_cost": original_price,
            "post_discount_cost": price,
            "type_of_policy": req.type_of_Cover_needed,
            "total_excess_amount": req.Voluntary_Excess,
            "discount_applied": "yes" if discount_applied else "no",
            **features,
        },
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "customgpt-admiral", "version": "1.0.0"}


@app.get("/")
async def root():
    return {
        "service": "CustomGPT Admiral Quote Service",
        "endpoint": "/quote/admiral",
        "method": "POST",
    }
