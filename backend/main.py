"""
ID Document Forgery Detection Service
Backend: FastAPI + Google Gemini Vision (FREE tier) + OpenCV Hybrid Pipeline
"""

import json
import os
import re
import cv2
import numpy as np
from datetime import datetime

from dotenv import load_dotenv
from google import genai
from google.genai import types
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

load_dotenv(dotenv_path=".env")

#App Setup 
app = FastAPI(
    title="ID Forgery Detection API",
    description="Analyzes ID document images for signs of tampering or forgery.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
}
MAX_FILE_SIZE_MB = 10

#Analysis Prompt 
FORGERY_ANALYSIS_PROMPT = """
You are an expert forensic document analyst specializing in ID document authentication.
Analyze this ID document image carefully and produce a structured forgery risk assessment.

Examine the following forgery signals:

1. **Font Consistency** - Are fonts uniform across all fields? Mismatched fonts or sizes
   often indicate text substitution.

2. **Alignment & Spacing** - Are text fields and data elements properly aligned?
   Irregular spacing can signal copy-paste tampering.

3. **Photo Integrity** - Does the photo appear naturally embedded? Look for:
   - Hard edges around the photo suggesting it was swapped
   - Lighting inconsistencies between photo and document background
   - Resolution mismatch between photo and surrounding elements

4. **Document Layout** - Does the overall layout match known ID document conventions?
   - Proper placement of security elements (holograms, seals, MRZ zones)
   - Consistent border and background patterns

5. **Print Quality & Artifacts** - Are there:
   - Compression artifacts or blurring in specific regions (sign of digital editing)
   - Inconsistent ink/print density across the document
   - Signs of scan-then-print re-digitization

6. **Security Features** - Can you detect or infer presence/absence of:
   - Microprint or fine-line patterns
   - Guilloche background patterns
   - Machine-readable zone (MRZ) format validity

7. **Metadata & Lighting Coherence** - Are shadows and reflections consistent?
   Inconsistent lighting suggests compositing.

8. **Text Field Tampering** - Do any data fields (name, DOB, ID number, expiry) show:
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
            detail=f"Unsupported file type '{mime}'. Allowed: JPEG, PNG, WEBP.",
        )
    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({size_mb:.1f} MB). Maximum allowed: {MAX_FILE_SIZE_MB} MB.",
        )
    return ALLOWED_MIME_TYPES[mime]


def read_image(content: bytes) -> np.ndarray:
    """Decode raw image bytes into an OpenCV ndarray.
    Raises HTTP 422 if the file is corrupted or unreadable."""
    np_arr = np.frombuffer(content, np.uint8)
    image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    # FIX 2: cv2.imdecode returns None silently on corrupt files — handle it explicitly
    if image is None:
        raise HTTPException(
            status_code=422,
            detail="Image could not be decoded. The file may be corrupted or unsupported.",
        )
    return image


#OpenCV Feature Extractors 

def detect_blur(image: np.ndarray) -> float:
    """Laplacian variance — low score = blurry image.
    Blurring can indicate tampering concealment or a low-quality forgery."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def detect_noise(image: np.ndarray) -> float:
    """Grayscale std deviation — high score = high noise.
    Inconsistent noise patterns indicate compositing or digital editing."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return float(np.std(gray))


def detect_edges(image: np.ndarray) -> float:
    """Canny edge pixel density — very low or very high is suspicious.
    Copy-paste tampering produces broken or abnormally dense edges."""
    edges = cv2.Canny(image, 100, 200)
    return float(np.sum(edges > 0) / edges.size)


def detect_color_inconsistency(image: np.ndarray) -> float:
    """HSV saturation std deviation — high variance suggests compositing.
    Regions pasted from different sources have mismatched color tones."""
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    return float(np.std(hsv[:, :, 1]))


def detect_compression_artifacts(image: np.ndarray) -> float:
    """DCT mean absolute coefficient — high value = uneven JPEG re-compression.
    Edited regions are often re-encoded, leaving a different compression signature."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    dct = cv2.dct(np.float32(gray) / 255.0)
    return float(np.mean(np.abs(dct)))


def detect_text_regions(image: np.ndarray) -> float:
    """Thresholded dark-pixel ratio — abnormal values suggest missing or overlaid text.
    Genuine ID documents have a predictable range of text pixel coverage."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)
    return float(np.sum(thresh > 0) / thresh.size)


def analyze_image(image: np.ndarray) -> dict:
    """Run all six OpenCV feature extractors and return a metrics dictionary."""
    return {
        "blur":           detect_blur(image),
        "noise":          detect_noise(image),
        "edges":          detect_edges(image),
        "color_variance": detect_color_inconsistency(image),
        "compression":    detect_compression_artifacts(image),
        "text_density":   detect_text_regions(image),
    }


#Rule-Based Scoring 

def generate_report(results: dict) -> dict:
    """Generate a rule-based forgery risk report from extracted image features.

    Interprets low-level image metrics (blur, noise, edge density, color variance,
    compression artifacts, text density) and maps them to human-understandable
    forgery indicators via empirically chosen thresholds.

    A cumulative risk score determines the overall status:
        score >= 6  ->  suspicious
        score >= 3  ->  review
        score  < 3  ->  likely_genuine
    """
    issues = []
    score = 0

    # BLUR
    if results["blur"] < 80:
        issues.append("Image is blurry (low sharpness)")
        score += 2
    elif results["blur"] < 120:
        issues.append("Slight blur detected")
        score += 1

    # NOISE
    if results["noise"] > 60:
        issues.append("High noise level (possible editing)")
        score += 2
    elif results["noise"] > 40:
        issues.append("Moderate noise detected")
        score += 1

    # EDGES
    if results["edges"] < 0.03:
        issues.append("Weak edge structure (possible tampering or blur)")
        score += 2
    elif results["edges"] > 0.15:
        issues.append("Too many edges (possible noise or artifacts)")
        score += 1

    # COLOR VARIANCE
    if results["color_variance"] > 60:
        issues.append("High color inconsistency (possible compositing)")
        score += 2

    # COMPRESSION
    if results["compression"] > 0.2:
        issues.append("Compression artifacts detected")
        score += 1

    # TEXT DENSITY
    if results["text_density"] < 0.02:
        issues.append("Low text presence (unusual for ID)")
        score += 1
    elif results["text_density"] > 0.25:
        issues.append("Abnormal text density (possible overlay)")
        score += 1

    # FINAL DECISION
    if score >= 6:
        status = "suspicious"
    elif score >= 3:
        status = "review"
    else:
        status = "likely_genuine"

    confidence = min(score / 8, 1.0)

    return {
        "status":     status,
        "issues":     issues,
        "confidence": round(confidence, 2),
    }


#Validity Classification 

def classify_validity(report: dict) -> str:
    """Scan the AI report for keywords indicating a non-genuine document.

    Separates document validity (is this a real issued ID?) from forgery risk
    (has this image been tampered with?) — these are two distinct concerns.
    """
    text_blob = json.dumps(report).lower()

    if "specimen" in text_blob:
        logging.info("Document classified as SPECIMEN based on report content.")
        return "SPECIMEN_DOCUMENT"

    # e.g. "sample the image" or "for example" no longer trigger this branch
    if '"sample"' in text_blob or "sample id" in text_blob or "sample document" in text_blob:
        logging.info("Document classified as SAMPLE based on report content.")
        return "SAMPLE_DOCUMENT"

    if "not a valid" in text_blob or "not valid" in text_blob:
        logging.info("Document classified as NOT_VALID based on report content.")
        return "NOT_VALID_DOCUMENT"

    if "not an id" in text_blob:
        logging.info("Document classified as NOT_AN_ID based on report content.")
        return "NOT_AN_ID"

    logging.info("No explicit specimen/sample/invalid indicators found; classifying as LIKELY_VALID.")
    return "LIKELY_VALID"


#Gemini Vision Call 

def call_gemini_vision(image_bytes: bytes, media_type: str, manual_results: dict) -> dict:
    """Send the image and OpenCV signals to Gemini Vision; return parsed JSON report."""
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    image_part = types.Part.from_bytes(data=image_bytes, mime_type=media_type)

    prompt = f"""
    You are an expert forensic document analyst.

    Here are computed image signals from OpenCV analysis:
    - Blur score:            {manual_results["blur"]:.2f}
    - Noise level:           {manual_results["noise"]:.2f}
    - Edge density:          {manual_results["edges"]:.4f}
    - Color variance:        {manual_results["color_variance"]:.2f}
    - Compression artifacts: {manual_results["compression"]:.4f}
    - Text density:          {manual_results["text_density"]:.4f}

    IMPORTANT DISTINCTION:
    - "Forgery risk" refers to signs of tampering, manipulation, or editing.
    - A document may be structurally genuine but still not valid (e.g., specimen/sample).

    If the document is a specimen/sample:
    - Do NOT classify it as HIGH_RISK or CRITICAL unless tampering is also present.
    - Classify risk based on tampering signals only.
    - Clearly mention that it is not a valid ID in summary and red_flags.

    {FORGERY_ANALYSIS_PROMPT}
    """

    text_part = types.Part.from_text(text=prompt)

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[types.Content(role="user", parts=[image_part, text_part])],
        config=types.GenerateContentConfig(
            max_output_tokens=8192,
            temperature=0.2,
            response_mime_type="application/json",
        ),
    )

    raw_text = response.text.strip()

    print("===== GEMINI RAW RESPONSE (first 500 chars) =====")
    print(raw_text[:500], "..." if len(raw_text) > 500 else "")
    print("=================================================")

    # Strip markdown fences (belt-and-suspenders)
    raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
    raw_text = re.sub(r"\s*```$", "", raw_text.strip())

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
    """Accept an ID document image, run the hybrid forgery analysis pipeline,
    and return a structured risk report."""
    content = await file.read()


    # Step 1 — Validate MIME type and file size
    media_type = validate_image(file, content)

    # Step 2 — Decode image bytes into OpenCV array
    image = read_image(content)

    # Step 3 — Extract image metrics via OpenCV
    manual_results = analyze_image(image)

    # Step 4 — Generate rule-based risk score from metrics
    rule_report = generate_report(manual_results)

    # Step 5 — Run Gemini Vision analysis (image + OpenCV signals)
    try:
        report = call_gemini_vision(content, media_type, manual_results)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"AI model returned malformed JSON: {exc}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"AI API error: {exc}",
        )

    # Step 6 — Assemble final merged report
    final_report = report
    final_report["manual_analysis"] = manual_results
    final_report["rule_based"]      = rule_report
    final_report["validity_status"] = classify_validity(report)
    final_report["metadata"] = {
        "filename":     file.filename,
        "file_size_kb": round(len(content) / 1024, 1),
        "media_type":   media_type,
        "analyzed_at":  datetime.utcnow().isoformat() + "Z",
        "model":        "gemini-2.5-flash + OpenCV hybrid",
    }

    return JSONResponse(content=final_report)