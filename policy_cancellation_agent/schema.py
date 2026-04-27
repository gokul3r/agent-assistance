from pydantic import BaseModel, Field


class CancellationInput(BaseModel):
    customer_id: str = Field(default="", description="Unique customer identifier from Genesys")
    customer_name: str = Field(default="", description="Customer full name")
    historical_context: str = Field(
        default="",
        description="Condensed history of past interactions with this customer"
    )
    call_gist: str = Field(
        default="",
        description="Running summary of the current call so far (updated every 15s)"
    )
    current_transcript: str = Field(
        description="Last 15 seconds of conversation, already transcribed"
    )


class NextBestAction(BaseModel):
    current_step: int = Field(description="Current step in the 6-step cancellation flow (1–6)")
    step_name: str = Field(description="Short label for the current step")
    agent_instruction: str = Field(description="Precise action the human agent must take right now")
    customer_script: str = Field(description="Exact words the human agent should say to the customer")
    notes: str = Field(description="Warnings, exceptions, or compliance reminders")
    next_step_preview: str = Field(description="Brief description of what comes next")
