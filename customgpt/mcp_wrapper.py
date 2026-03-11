import os
from typing import Any, Literal

import httpx
from fastmcp import FastMCP

from main import AdmiralQuoteRequest

mcp = FastMCP("AdmiralQuoteMCP")

API_BASE_URL = os.getenv(
    "ADMIRAL_API_BASE_URL",
    "https://customgpt-admiral-657860957693.europe-west4.run.app",
).rstrip("/")
MCP_PATH = os.getenv("MCP_PATH", "/mcp")


@mcp.tool()
async def get_admiral_quote(
    email_id: str,
    driver_age: int,
    vehicle_registration_number: str,
    vehicle_manufacturer_name: str,
    vehicle_model: str,
    vehicle_year: int,
    type_of_fuel: Literal["Electric", "Hybrid", "Petrol", "Diesel"],
    type_of_Cover_needed: Literal[
        "comprehensive", "third_party_and_fire", "third_party_only"
    ],
    No_Claim_bonus_years: int,
    Voluntary_Excess: float,
) -> dict[str, Any]:
    """Fetch an Admiral quote by forwarding the 10-field request to /quote/admiral."""
    request_payload = AdmiralQuoteRequest(
        email_id=email_id,
        driver_age=driver_age,
        vehicle_registration_number=vehicle_registration_number,
        vehicle_manufacturer_name=vehicle_manufacturer_name,
        vehicle_model=vehicle_model,
        vehicle_year=vehicle_year,
        type_of_fuel=type_of_fuel,
        type_of_Cover_needed=type_of_Cover_needed,
        No_Claim_bonus_years=No_Claim_bonus_years,
        Voluntary_Excess=Voluntary_Excess,
    )

    endpoint = f"{API_BASE_URL}/quote/admiral"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(endpoint, json=request_payload.model_dump(mode="json"))

    if response.status_code != 200:
        return {
            "status": "error",
            "message": "Quote service returned non-200 response",
            "status_code": response.status_code,
            "details": response.text,
            "endpoint": endpoint,
        }

    return {
        "status": "success",
        "source": endpoint,
        "quote": response.json(),
    }


@mcp.tool()
async def get_quote_service_health() -> dict[str, Any]:
    """Check health of the backing Admiral quote API."""
    endpoint = f"{API_BASE_URL}/health"
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(endpoint)

    if response.status_code != 200:
        return {
            "status": "error",
            "status_code": response.status_code,
            "endpoint": endpoint,
            "details": response.text,
        }

    return {
        "status": "success",
        "endpoint": endpoint,
        "health": response.json(),
    }


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))
    mcp.run(
        transport="http",
        host=host,
        port=port,
        path=MCP_PATH,
    )
