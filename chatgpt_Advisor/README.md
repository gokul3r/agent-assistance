# ChatGPT Advisor (Step 1)

This service collects mandatory insurance inputs conversationally and calls Alfie's `/complete-analysis` endpoint when all required fields are available.

## Run locally

From repo root:

```powershell
python -m uvicorn chatgpt_Advisor.app:app --host 0.0.0.0 --port 8090
```

Optional env var (if you want local Alfie instead of Cloud Run):

```powershell
$env:ALFIE_BASE_URL="http://localhost:8080"
python -m uvicorn chatgpt_Advisor.app:app --host 0.0.0.0 --port 8090
```

## Test - first turn (collect mode)

```powershell
curl.exe -X POST "http://localhost:8090/advisor/collect-or-quote" -H "Content-Type: application/json" --data-binary "@chatgpt_Advisor/sample_collect_request.json"
```

## Test - full payload (done mode)

```powershell
curl.exe -X POST "http://localhost:8090/advisor/collect-or-quote" -H "Content-Type: application/json" --data-binary "@chatgpt_Advisor/sample_quote_request.json"
```

## Response behavior

- `status=collecting`: includes `questions`, `next_question`, `missing_fields`
- `status=done`: includes `top_5_quotes` with only:
  - `provider`
  - `cost`

---

## Google ADK Agent (new)

ADK agent path:

- `chatgpt_Advisor/insurance_advisor_agent/agent.py`

It defines:

- `root_agent = Agent(...)`
- tool `get_top_5_quotes(...)` that calls Alfie `/complete-analysis`

### Install ADK

```powershell
pip install google-adk
```

### Run ADK in terminal mode

From repo root:

```powershell
adk run chatgpt_Advisor/insurance_advisor_agent
```

### Run ADK web UI

```powershell
adk web
```

Then open the agent package from the UI and chat with it.
