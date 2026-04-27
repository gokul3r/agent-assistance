"""
Quick test runner for Policy_Cancellation_Assistant.
Usage:
    GOOGLE_API_KEY=your_key python test_cancellation_agent.py
"""

import asyncio
import json
import os
import sys

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from policy_cancellation_agent.agent import cancellation_agent, build_input_message
from policy_cancellation_agent.schema import CancellationInput


async def run_test(runner: Runner, session_service: InMemorySessionService, label: str, payload: dict):
    data = CancellationInput(**payload)
    user_id = data.customer_id or "test_user"
    session_id = f"test_session_{label[:10].replace(' ', '_')}"

    await session_service.create_session(
        app_name="policy_cancellation",
        user_id=user_id,
        session_id=session_id,
    )

    message = build_input_message(data)
    response_text = ""

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=types.Content(role="user", parts=[types.Part(text=message)]),
    ):
        if event.is_final_response():
            if event.content and event.content.parts:
                response_text = event.content.parts[0].text
            break

    # Strip markdown fences if present
    cleaned = response_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    cleaned = cleaned.strip()

    try:
        result = json.loads(cleaned)
        return result
    except json.JSONDecodeError:
        return {"error": "Invalid JSON", "raw": response_text[:300]}


async def main():
    if not os.getenv("GOOGLE_API_KEY"):
        print("ERROR: GOOGLE_API_KEY environment variable is not set.")
        print("Get one at: https://aistudio.google.com/apikey")
        sys.exit(1)

    with open("sample_cancellation_inputs.json") as f:
        test_cases = json.load(f)

    session_service = InMemorySessionService()
    runner = Runner(
        agent=cancellation_agent,
        app_name="policy_cancellation",
        session_service=session_service,
    )

    print("=" * 70)
    print("  Policy_Cancellation_Assistant — Test Run")
    print("=" * 70)

    passed = 0
    failed = 0

    for i, case in enumerate(test_cases, 1):
        label = case["label"]
        payload = case["payload"]
        expected_step = i  # sample inputs are ordered step 1–6

        print(f"\n[TEST {i}] {label}")
        print("-" * 70)

        result = await run_test(runner, session_service, label, payload)

        if "error" in result:
            print(f"  FAIL — {result['error']}")
            print(f"  Raw: {result.get('raw', '')}")
            failed += 1
            continue

        step = result.get("current_step")
        match = "PASS" if step == expected_step else "WARN"
        if step == expected_step:
            passed += 1
        else:
            failed += 1

        print(f"  [{match}] Detected step : {step} (expected {expected_step})")
        print(f"  Step name       : {result.get('step_name')}")
        print(f"  Agent instruction: {result.get('agent_instruction')}")
        print(f"  Customer script : {result.get('customer_script')}")
        if result.get("notes"):
            print(f"  Notes           : {result.get('notes')}")
        print(f"  Next step preview: {result.get('next_step_preview')}")

    print("\n" + "=" * 70)
    print(f"  Results: {passed}/{len(test_cases)} passed")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
