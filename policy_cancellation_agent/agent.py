from google.adk.agents import Agent
from .prompt import CANCELLATION_SYSTEM_PROMPT
from .schema import CancellationInput

cancellation_agent = Agent(
    name="Policy_Cancellation_Assistant",
    model="gemini-2.5-flash",
    description=(
        "Real-time next-best-action advisor for insurance contact center agents "
        "handling midterm policy cancellations. Strictly follows the 6-step "
        "cancellation script and outputs structured JSON guidance."
    ),
    instruction=CANCELLATION_SYSTEM_PROMPT,
)


def build_input_message(data: CancellationInput) -> str:
    """Format the three context inputs into the structured prompt message."""
    return (
        f"CUSTOMER NAME : {data.customer_name or 'Unknown'}\n"
        f"CUSTOMER ID   : {data.customer_id or 'Unknown'}\n\n"
        f"HISTORICAL CONTEXT:\n"
        f"{data.historical_context or 'No previous history available.'}\n\n"
        f"CALL GIST (running summary of this call so far):\n"
        f"{data.call_gist or 'Call has just started — no gist yet.'}\n\n"
        f"CURRENT TRANSCRIPT (last 15 seconds):\n"
        f"{data.current_transcript}\n\n"
        f"Determine the current cancellation step and return the next best action as JSON."
    )
