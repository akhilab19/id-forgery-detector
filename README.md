# 🔍 VeriDoc — ID Document Forgery Detection

A prototype service that uses a **hybrid OpenCV + Gemini Vision AI pipeline** to analyze
ID document images and generate structured forgery risk reports.

---

## Architecture

```
User (Browser or CLI)
        │
        ▼
  Frontend (HTML/JS)
  drag-drop upload
        │  multipart/form-data
        ▼
  FastAPI Backend (main.py)
        │
        ├─► Layer 1: Input Validation       (MIME type + file size)
        │
        ├─► Layer 2: OpenCV Processing      (blur, noise, edges,
        │                                    color, compression, text)
        │
        ├─► Layer 3: Rule-Based Scoring     (threshold evaluation
        │                                    → risk score + issues)
        │
        ├─► Layer 4: Gemini 2.5 Flash       (image + OpenCV signals
        │            Vision API              → structured JSON report)
        │
        ├─► Layer 5: Validity Classification (specimen/sample/not-id
        │                                     keyword detection)
        │
        └─► Layer 6: Report Assembly        (merged final_report)
                │
                ▼
        Structured JSON Response
```

---

## Tools & Technologies

| Layer            | Technology                  | Why Chosen                                                       |
| ---------------- | --------------------------- | ---------------------------------------------------------------- |
| Backend          | **FastAPI**                 | Async Python, auto-generated OpenAPI docs, ideal for ML services |
| Image Processing | **OpenCV + NumPy**          | Deterministic, auditable, industry-standard computer vision      |
| AI Model         | **Gemini 2.5 Flash Vision** | Free tier, multimodal, strong visual and semantic reasoning      |
| Frontend         | **Vanilla HTML/CSS/JS**     | Zero dependencies, runs anywhere, fast to demo                   |
| Env Management   | **python-dotenv**           | Secure API key management                                        |

---

## Fraud Detection Approach

Rather than training a custom ML model (which would require large labeled datasets),
this prototype uses a **hybrid pipeline** combining deterministic image processing
with AI-powered visual reasoning.

### OpenCV Signals (Layer 2)

Six measurable image features are extracted before the AI is involved:

| Signal                | Method                  | Detects                                    |
| --------------------- | ----------------------- | ------------------------------------------ |
| Blur                  | Laplacian variance      | Tampering concealment, low-quality forgery |
| Noise                 | Grayscale std deviation | Editing artifacts, compositing             |
| Edge Density          | Canny edge detection    | Structural breaks, copy-paste regions      |
| Color Variance        | HSV saturation std      | Mismatched color tones from compositing    |
| Compression Artifacts | DCT mean coefficient    | Uneven JPEG re-encoding in edited areas    |
| Text Density          | Thresholded pixel ratio | Missing or overlaid text                   |

### AI Forensic Signals (Layer 4 — Gemini Vision)

Eight semantic signals that only a vision model can evaluate:

1. **Font Consistency** — Mismatched typefaces indicate text substitution
2. **Alignment & Spacing** — Irregular spacing signals copy-paste tampering
3. **Photo Integrity** — Hard edges, lighting mismatch, resolution delta
4. **Document Layout** — Compliance with MRZ zones, seals, hologram placement
5. **Print Quality & Artifacts** — JPEG artifacts concentrated in edited regions
6. **Security Features** — Presence/absence of guilloche patterns, microprint
7. **Lighting Coherence** — Inconsistent shadows suggest compositing
8. **Text Field Tampering** — Ghosting, background color differences, font weight shifts

### Key Design Insight — Forgery Risk vs Document Validity

The system separately classifies two concerns that naive systems conflate:

| Concern               | Meaning                       | Example                                        |
| --------------------- | ----------------------------- | ---------------------------------------------- |
| **Forgery Risk**      | Signs of tampering/editing    | Altered expiry date → HIGH_RISK                |
| **Document Validity** | Whether the ID is real/issued | Specimen card → NOT_VALID but LOW forgery risk |

This prevents specimen or sample IDs from being wrongly flagged as CRITICAL.

### Output Risk Levels

| Level           | Meaning                                      |
| --------------- | -------------------------------------------- |
| `GENUINE`       | No suspicious signals found                  |
| `LOW_RISK`      | Minor anomalies, likely authentic            |
| `MODERATE_RISK` | Notable anomalies; manual review recommended |
| `HIGH_RISK`     | Strong indicators of tampering               |
| `CRITICAL`      | Near-certain forgery signals                 |

### Validity Status (separate from risk level)

| Status               | Meaning                            |
| -------------------- | ---------------------------------- |
| `LIKELY_VALID`       | Appears to be a real issued ID     |
| `SPECIMEN_DOCUMENT`  | Detected as a specimen card        |
| `SAMPLE_DOCUMENT`    | Detected as a sample/placeholder   |
| `NOT_VALID_DOCUMENT` | Explicitly identified as not valid |
| `NOT_AN_ID`          | Not an ID document at all          |

---

## Setup & Run

### Prerequisites

- Python 3.10+
- A free Gemini API key from [aistudio.google.com](https://aistudio.google.com)

### 1. Clone & Install

```bash
git clone <your-repo-url>
cd id-forgery-detector
pip install -r backend/requirements.txt
```

### 2. Get a Free API Key

1. Go to [aistudio.google.com](https://aistudio.google.com)
2. Sign in with your Google account
3. Click **"Get API Key"** → **"Create API key"**
4. Copy the key (starts with `AIza...`)

### 3. Create a `.env` file in the `backend/` folder

```
GEMINI_API_KEY=Your-key-here
```

### 4. Start the Backend

```powershell
# Windows
cd backend
uvicorn main:app --reload --port 8000
```

```bash
# Mac / Linux
cd backend
uvicorn main:app --reload --port 8000
```

The API will be live at `http://localhost:8000`
Interactive API docs: `http://localhost:8000/docs`

### 5. Open the Frontend

Simply open `frontend/index.html` in your browser, or serve it locally:

```bash
cd frontend
python -m http.server 3000
# then open http://localhost:3000
```

### 6. Test via CLI

```bash
python test_api.py samples/sample_id.jpg
```

---

## API Reference

### `POST /analyze`

Upload an ID document image and receive a full forgery risk report.

**Request:** `multipart/form-data` with `file` field
**Accepted types:** `image/jpeg`, `image/png`, `image/webp`
**Max size:** 10 MB

**Response:**

```json
{
  "document_type": "National ID",
  "overall_risk_level": "MODERATE_RISK",
  "confidence_score": 72,
  "summary": "The document shows several inconsistencies...",
  "checks": [
    { "check_name": "Font Consistency", "status": "WARN", "detail": "..." }
  ],
  "red_flags": ["Irregular background behind DOB field"],
  "positive_indicators": ["MRZ zone appears properly formatted"],
  "analyst_notes": "...",
  "disclaimer": "...",
  "manual_analysis": {
    "blur": 145.3,
    "noise": 38.2,
    "edges": 0.07,
    "color_variance": 42.1,
    "compression": 0.15,
    "text_density": 0.09
  },
  "rule_based": {
    "status": "likely_genuine",
    "issues": [],
    "confidence": 0.12
  },
  "validity_status": "LIKELY_VALID",
  "metadata": {
    "filename": "id.jpg",
    "file_size_kb": 245.3,
    "media_type": "image/jpeg",
    "analyzed_at": "2024-01-15T10:30:00Z",
    "model": "gemini-2.5-flash + OpenCV hybrid"
  }
}
```

### `GET /health`

Returns `{ "status": "ok", "timestamp": "..." }`

---

## Sample Output

See `samples/` folder for example inputs and `samples/sample_report.json` for a
full annotated JSON output.

---

## Limitations & Disclaimer

- This is a **prototype** for evaluation purposes only
- OpenCV thresholds are heuristic, not trained on a labeled forgery dataset
- Gemini Vision has not been fine-tuned on ID forgery datasets
- Should **not** be used as sole evidence in legal or security decisions
- Accuracy depends on image quality and document type familiarity

---

## Future Improvements

- Pass all 6 OpenCV signals to Gemini (currently only blur, noise, edges)
- Error Level Analysis (ELA) as a dedicated pre-processing step
- MRZ checksum validation
- Template matching against a per-country genuine document database
- Fine-tuned CNN (e.g., ManTraNet) for forgery localization
- PDF support via image extraction pipeline
- Batch processing via ZIP upload
