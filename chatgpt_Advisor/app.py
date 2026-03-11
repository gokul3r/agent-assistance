from __future__ import annotations

import os
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from chatgpt_Advisor.agent import AdvisorAgent


ALFIE_BASE_URL = os.getenv(
    "ALFIE_BASE_URL",
    "https://alfie-657860957693.europe-west4.run.app",
)

app = FastAPI(
    title="ChatGPT Insurance Advisor",
    description="Conversation-first advisor that collects required fields and returns top-5 lowest quotes.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

advisor = AdvisorAgent(complete_analysis_url=ALFIE_BASE_URL, timeout_seconds=120.0)


class AdvisorRequest(BaseModel):
    session_id: str | None = None
    user_message: str | None = None
    insurance_details: dict[str, Any] = Field(default_factory=dict)
    user_preferences: str | None = None


class AdvisorResponse(BaseModel):
    status: str
    session_id: str
    next_question: str | None = None
    questions: list[dict[str, str]] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    top_5_quotes: list[dict[str, Any]] = Field(default_factory=list)
    message: str | None = None


@app.post("/advisor/collect-or-quote", response_model=AdvisorResponse)
async def collect_or_quote(req: AdvisorRequest):
    sid, session = advisor.get_or_create_session(req.session_id)

    first_turn = len(session.insurance_details) == 0 and not session.user_preferences
    advisor.merge_inputs(
        session=session,
        provided_insurance_details=req.insurance_details,
        provided_user_preferences=req.user_preferences,
        user_message=req.user_message,
    )
    missing = advisor.missing_fields(session)

    if missing:
        questions = advisor.next_questions(missing=missing, first_turn=first_turn)
        next_question = questions[0]["question"] if questions else None
        return AdvisorResponse(
            status="collecting",
            session_id=sid,
            next_question=next_question,
            questions=questions,
            missing_fields=missing,
            message="I need a few details to get your quotes.",
        )

    try:
        analysis = await advisor.run_complete_analysis(session)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=f"Alfie API error: {exc.response.text}",
        )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"Cannot reach Alfie API: {str(exc)}")

    top_5 = advisor.top_5_lowest_quotes(analysis)
    return AdvisorResponse(
        status="done",
        session_id=sid,
        missing_fields=[],
        top_5_quotes=top_5,
        message="Here are the 5 lowest quotes.",
    )


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "chatgpt-advisor",
        "alfie_base_url": ALFIE_BASE_URL,
    }


@app.get("/")
async def root():
    return {
        "service": "ChatGPT Insurance Advisor",
        "endpoint": "/advisor/collect-or-quote",
        "mode": "collect then quote",
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8090))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")

