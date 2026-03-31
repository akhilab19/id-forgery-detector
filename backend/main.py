"""
ID Document Forgery Detection Service
Backend: FastAPI + Anthropic Claude Vision
"""

import base64
import json
import re
from datetime import datetime
from pathlib import Path

import anthropic
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

#App Setup 
app = FastAPI(
    title="ID Forgery Detection API",
    description="Analyzes ID document images for signs of tampering or forgery.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#Constants 
ALLOWED_MIME_TYPES = {
    "image/jpeg": "image/jpeg",
    "image/jpg":  "image/jpeg",
    "image/png":  "image/png",
    "image/webp": "image/webp",
    "image/gif":  "image/gif",
}
MAX_FILE_SIZE_MB = 10

#Analysis Prompt 
FORGERY_ANALYSIS_PROMPT = """
You are an expert forensic document analyst specializing in ID document authentication.
Analyze this ID document image carefully and produce a structured forgery risk assessment.

Examine the following forgery signals:

1. **Font Consistency** – Are fonts uniform across all fields? Mismatched fonts or sizes
   often indicate text substitution.

2. **Alignment & Spacing** – Are text fields and data elements properly aligned?
   Irregular spacing can signal copy-paste tampering.

3. **Photo Integrity** – Does the photo appear naturally embedded? Look for:
   - Hard edges around the photo suggesting it was swapped
   - Lighting inconsistencies between photo and document background
   - Resolution mismatch between photo and surrounding elements

4. **Document Layout** – Does the overall layout match known ID document conventions?
   - Proper placement of security elements (holograms, seals, MRZ zones)
   - Consistent border and background patterns

5. **Print Quality & Artifacts** – Are there:
   - Compression artifacts or blurring in specific regions (sign of digital editing)
   - Inconsistent ink/print density across the document
   - Signs of scan-then-print re-digitization

6. **Security Features** – Can you detect or infer presence/absence of:
   - Microprint or fine-line patterns
   - Guilloche background patterns
   - Machine-readable zone (MRZ) format validity

7. **Metadata & Lighting Coherence** – Are shadows and reflections consistent?
   Inconsistent lighting suggests compositing.

8. **Text Field Tampering** – Do any data fields (name, DOB, ID number, expiry) show:
   - Different background color behind text
   - Slightly different font weight
   - Ghosting or traces of erased text

Based on your analysis respond ONLY with a valid JSON object in this exact structure:
{
  "document_type": "<detected document type, e.g. 'National ID', 'Passport', 'Driver License', 'Unknown'>",
  "overall_risk_level": "<one of: GENUINE | LOW_RISK | MODERATE_RISK | HIGH_RISK | CRITICAL>",
  "confidence_score": <integer 0-100>,
  "summary": "<2-3 sentence plain-English summary of findings>",
  "checks": [
    {
      "check_name": "<name of check>",
      "status": "<PASS | WARN | FAIL | INCONCLUSIVE>",
      "detail": "<specific observation for this check>"
    }
  ],
  "red_flags": ["<list of specific suspicious findings, empty array if none>"],
  "positive_indicators": ["<list of authentic-looking features>"],
  "analyst_notes": "<any additional reasoning or caveats>",
  "disclaimer": "This is an automated AI analysis for prototype/evaluation purposes only. It should not be used as sole evidence in legal or security decisions."
}

Be specific and honest. If you cannot see the image clearly or it does not appear to be an ID document, reflect that in the risk level and notes.
"""

#Helper Functions 
def validate_image(file: UploadFile, content: bytes) -> str:
    """Validate file type and size. Returns the canonical MIME type."""
    mime = file.content_type or ""
    if mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{mime}'. Allowed: JPEG, PNG, WEBP, GIF.",
        )
    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({size_mb:.1f} MB). Maximum allowed: {MAX_FILE_SIZE_MB} MB.",
        )
    return ALLOWED_MIME_TYPES[mime]


def call_claude_vision(image_b64: str, media_type: str) -> dict:
    """Send image to Claude and parse the JSON response."""
    client = anthropic.Anthropic()          # reads ANTHROPIC_API_KEY from env

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1500,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": FORGERY_ANALYSIS_PROMPT,
                    },
                ],
            }
        ],
    )

    raw_text = message.content[0].text.strip()

    # Strip markdown code fences if Claude wraps the JSON
    raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
    raw_text = re.sub(r"\s*```$", "", raw_text)

    return json.loads(raw_text)


#Endpoints 
@app.get("/")
def root():
    return {"service": "ID Forgery Detection API", "status": "running", "version": "1.0.0"}


@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.post("/analyze")
async def analyze_document(file: UploadFile = File(...)):
    """
    Accept an ID document image, run forgery analysis via Claude Vision,
    and return a structured risk report.
    """
    content = await file.read()

    # 1. Validate
    media_type = validate_image(file, content)

    # 2. Encode
    image_b64 = base64.standard_b64encode(content).decode("utf-8")

    # 3. Analyse with Claude
    try:
        report = call_claude_vision(image_b64, media_type)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"AI model returned malformed JSON: {exc}",
        )
    except anthropic.APIError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"AI API error: {exc}",
        )

    # 4. Attach metadata
    report["metadata"] = {
        "filename": file.filename,
        "file_size_kb": round(len(content) / 1024, 1),
        "media_type": media_type,
        "analyzed_at": datetime.utcnow().isoformat() + "Z",
        "model": "claude-opus-4-5",
    }

    return JSONResponse(content=report)