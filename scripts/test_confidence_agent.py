import json
import os
import sys
import urllib.request


def load_payload(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def post_json(url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    url = os.getenv("ALFIE_URL", "http://localhost:8080/complete-analysis")
    payload_path = sys.argv[1] if len(sys.argv) > 1 else (
        "InsureThat/auto_annie/ai_agent/sample_request_complete.json"
    )
    output_path = "confidence_Scores.json"

    try:
        payload = load_payload(payload_path)
    except Exception as exc:
        print(f"FAIL: could not load payload from {payload_path}: {exc}")
        return 1

    try:
        response = post_json(url, payload)
    except Exception as exc:
        print(f"FAIL: request to {url} failed: {exc}")
        return 1

    try:
        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump(response, handle, indent=2)
    except Exception as exc:
        print(f"FAIL: could not write output file {output_path}: {exc}")
        return 1

    quotes = response.get("quotes_with_insights", [])
    if not isinstance(quotes, list) or not quotes:
        print("FAIL: quotes_with_insights missing or empty")
        return 1

    missing_autoannie = 0
    missing_confidence = 0
    for quote in quotes:
        if "autoannie_message" not in quote:
            missing_autoannie += 1
        if "confidence_insights" not in quote or not isinstance(quote["confidence_insights"], list):
            missing_confidence += 1

    if missing_autoannie or missing_confidence:
        print("FAIL: missing fields in quotes")
        print(f"  autoannie_message missing: {missing_autoannie}")
        print(f"  confidence_insights missing or invalid: {missing_confidence}")
        return 1

    print("PASS: confidence fields present on all quotes")
    print(f"Quotes returned: {len(quotes)}")
    print(f"Saved full response to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
