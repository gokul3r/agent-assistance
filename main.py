import os
import json
import tempfile
from typing import Dict, Any, List

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI

# ---- Configuration ----
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    # We don't crash here to allow /_health to work, but will fail at runtime if missing
    pass

FIELD_NAMES = [
    "email",
    "driver_age",
    "vehicle_registration_number",
    "vehicle_manufacturer",
    "vehicle_model",
    "vehicle_year",
    "type_of_fuel",
    "type_of_cover",
    "no_claim_bonus_years",
    "voluntary_excess",
]

RESPONSE_INSTRUCTIONS = """You are an expert UK motor insurance parser.
Read the uploaded policy/renewal PDF and extract specific fields.

Rules:
- Normalise values sensibly (e.g., 'Comprehensive' not 'comp'; 'Petrol' not 'gas').
- Extract UK registration as printed (e.g., 'VO14 YYR').
- If a value is not present or unsure, set it to null and include the field name in unextraction_section.
- Prefer the policyholder's primary contact when multiple candidates appear.
- Return ONLY JSON that matches the provided schema."""

def build_schema() -> Dict[str, Any]:
    field_props = {
        "email": {"type": ["string", "null"], "description": "Primary contact email"},
        "driver_age": {"type": ["integer", "null"], "minimum": 16, "maximum": 100},
        "vehicle_registration_number": {"type": ["string", "null"], "description": "UK reg (e.g., VO14 YYR)"},
        "vehicle_manufacturer": {"type": ["string", "null"]},
        "vehicle_model": {"type": ["string", "null"]},
        "vehicle_year": {"type": ["integer", "null"], "minimum": 1950, "maximum": 2100},
        "type_of_fuel": {"type": ["string", "null"], "description": "Petrol | Diesel | Hybrid | Electric | LPG | CNG | Other"},
        "type_of_cover": {"type": ["string", "null"], "description": "Comprehensive | Third Party Fire and Theft | Third Party Only"},
        "no_claim_bonus_years": {"type": ["integer", "null"], "minimum": 0, "maximum": 20},
        "voluntary_excess": {"type": ["integer", "null"], "minimum": 0, "maximum": 10000, "description": "GBP numeric, no symbol"},
    }
    return {
        "name": "PolicyExtraction",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "extracted_section": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": field_props,
                    "required": list(field_props.keys()),
                },
                "unextraction_section": {
                    "type": "array",
                    "items": {"type": "string", "enum": FIELD_NAMES},
                },
            },
            "required": ["extracted_section", "unextraction_section"],
        },
    }

class ExtractResponse(BaseModel):
    extracted_section: Dict[str, Any]
    unextraction_section: List[str]

app = FastAPI(title="Policy Renewal Extractor", version="1.0.0")

# CORS: open for now; tighten for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # set your domains in prod
    allow_credentials=True,
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["*"],
)

@app.get("/_health")
def health():
    return {"status": "ok", "model": MODEL, "has_api_key": bool(OPENAI_API_KEY)}

@app.post("/extract", response_model=ExtractResponse)
async def extract_policy(file: UploadFile = File(...)):
    # Basic checks
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not configured")

    if file.content_type not in {"application/pdf", "application/octet-stream"} and not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file")

    # Save file to a temp path (Cloud Run ephemeral disk)
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            contents = await file.read()
            tmp.write(contents)
            tmp_path = tmp.name
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save upload: {e}")

    try:
        client = OpenAI(api_key=OPENAI_API_KEY)

        # Upload the PDF for model access
        with open(tmp_path, "rb") as f:
            uploaded = client.files.create(file=f, purpose="assistants")

        schema = build_schema()

        # Call the Responses API with structured output & file input
        resp = client.responses.create(
            model=MODEL,
            instructions=RESPONSE_INSTRUCTIONS,
            input=[{
                "role": "user",
                "content": [
                    {"type": "input_text", "text": (
                        "Extract these fields from the attached policy/renewal PDF:\n"
                        "1) email\n2) driver_age\n3) vehicle_registration_number\n"
                        "4) vehicle_manufacturer\n5) vehicle_model\n6) vehicle_year\n"
                        "7) type_of_fuel\n8) type_of_cover\n9) no_claim_bonus_years\n"
                        "10) voluntary_excess\n\n"
                        "If a field is not present or uncertain, set it to null and list it in unextraction_section.\n"
                        "Return only the JSON object that matches the schema."
                    )},
                    {"type": "input_file", "file_id": uploaded.id},
                ],
            }],
            response_format={"type": "json_schema", "json_schema": schema},
        )

        data = json.loads(resp.output_text)

        # Defensive check: recompute missing from nulls/empties & merge
        extracted = data.get("extracted_section", {})
        missing = []
        for name in FIELD_NAMES:
            val = extracted.get(name)
            if val is None or (isinstance(val, str) and not val.strip()):
                missing.append(name)

        model_missing = set(data.get("unextraction_section", []))
        final_missing = sorted(set(missing) | model_missing)

        return ExtractResponse(
            extracted_section=extracted,
            unextraction_section=final_missing
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {e}")
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass

if __name__ == "__main__":
    import uvicorn, os
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8080")),
        reload=True
    )
