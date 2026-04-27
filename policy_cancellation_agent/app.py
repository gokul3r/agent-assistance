import json
import os
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk import types

from .agent import cancellation_agent, build_input_message
from .schema import CancellationInput, NextBestAction

app = FastAPI(
    title="Policy Cancellation Assistant",
    description="Next-best-action advisor for insurance contact center agents — cancellation flow",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

_session_service = InMemorySessionService()
_runner = Runner(
    agent=cancellation_agent,
    app_name="policy_cancellation",
    session_service=_session_service,
)


@app.get("/_health")
def health():
    return {"status": "ok", "agent": "Policy_Cancellation_Assistant", "version": "1.0.0"}


@app.post("/cancellation/next-best-action", response_model=NextBestAction)
async def next_best_action(payload: CancellationInput):
    """
    Called by the Master Agent every ~15 seconds when cancellation intent is active.
    Returns the next best action JSON for display in the Genesys NBA Widget.
    """
    user_id = payload.customer_id or f"anon_{uuid.uuid4().hex[:8]}"
    session_id = f"session_{uuid.uuid4().hex}"

    try:
        await _session_service.create_session(
            app_name="policy_cancellation",
            user_id=user_id,
            session_id=session_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Session creation failed: {e}")

    message = build_input_message(payload)

    response_text = ""
    try:
        async for event in _runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=types.Content(
                role="user",
                parts=[types.Part(text=message)],
            ),
        ):
            if event.is_final_response():
                if event.content and event.content.parts:
                    response_text = event.content.parts[0].text
                break
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {e}")

    if not response_text:
        raise HTTPException(status_code=500, detail="Agent returned an empty response")

    # Strip markdown code fences if the model wraps the JSON
    cleaned = response_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Agent returned invalid JSON: {e}. Raw: {response_text[:300]}",
        )

    try:
        return NextBestAction(**data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Response schema mismatch: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "policy_cancellation_agent.app:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8081")),
        reload=True,
    )
