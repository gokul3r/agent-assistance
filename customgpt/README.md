# CustomGPT Admiral API

Standalone Cloud Run API for Admiral quote calculation using only 10 user fields.

## HTTP API Endpoints
- `POST /quote/admiral`
- `GET /health`

## Run locally (HTTP API)
```bash
cd customgpt
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8080
```

## Deploy API to Cloud Run
From repo root:
```bash
gcloud run deploy customgpt-admiral \
  --source customgpt \
  --region europe-west4 \
  --allow-unauthenticated \
  --set-build-env-vars GOOGLE_RUNTIME_VERSION=3.13
```

## MCP Wrapper (for ChatGPT App)
`mcp_wrapper.py` exposes MCP tools and forwards to the deployed API.

Tools:
- `get_admiral_quote`
- `get_quote_service_health`

Default upstream API URL:
- `https://customgpt-admiral-657860957693.europe-west4.run.app`

Config env vars:
- `ADMIRAL_API_BASE_URL` (upstream API base URL)
- `MCP_PATH` (default `/mcp`)

Run locally (HTTP transport):
```bash
cd customgpt
pip install -r requirements.txt
python mcp_wrapper.py
```

PowerShell:
```powershell
cd customgpt
pip install -r requirements.txt
$env:ADMIRAL_API_BASE_URL="https://customgpt-admiral-657860957693.europe-west4.run.app"
$env:MCP_PATH="/mcp"
python mcp_wrapper.py
```

Deploy MCP wrapper to Cloud Run as a separate service:
```bash
gcloud run deploy customgpt-admiral-mcp \
  --source customgpt \
  --region europe-west4 \
  --allow-unauthenticated \
  --set-build-env-vars GOOGLE_RUNTIME_VERSION=3.13 \
  --set-env-vars ADMIRAL_API_BASE_URL=https://customgpt-admiral-657860957693.europe-west4.run.app,MCP_PATH=/mcp \
 
```

Smoke tests after MCP deploy:
- Health: `GET https://<MCP_SERVICE_URL>/health`
- MCP endpoint base path: `https://<MCP_SERVICE_URL>/mcp`

In ChatGPT connector/app config, use the MCP server URL:
- `https://<MCP_SERVICE_URL>/mcp`


