FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY policy_cancellation_agent/ ./policy_cancellation_agent/

ENV PORT=8080

CMD exec uvicorn policy_cancellation_agent.app:app --host 0.0.0.0 --port ${PORT}
