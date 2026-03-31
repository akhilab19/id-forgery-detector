# 🔍 VeriDoc — ID Document Forgery Detection

A prototype service that uses **Claude Vision AI** to analyze ID document images and
generate structured forgery risk reports.

---

## Architecture

```
User (Browser or CLI)
        │
        ▼
  Frontend  ──── multipart/form-data ────►  FastAPI Backend
 (HTML/JS)                                    (main.py)
                                                  │
                                    base64 image  │
                                                  ▼
                                        Anthropic Claude
                                        Vision API (claude-opus-4-5)
                                                  │
                                     JSON report  │
                                                  ▼
                                         Structured Response
```

## Tools & Technologies

| Layer      | Technology                          | Why chosen                                                                                             |
| ---------- | ----------------------------------- | ------------------------------------------------------------------------------------------------------ |
| Backend    | **FastAPI**                         | Async Python, auto-generated OpenAPI docs, ideal for ML services                                       |
| AI Model   | **Claude claude-opus-4-5 (Vision)** | State-of-the-art multimodal reasoning; can detect visual anomalies and reason about document structure |
| Frontend   | **Vanilla HTML/CSS/JS**             | Zero dependencies, runs anywhere, fast to demo                                                         |
| Validation | Built-in MIME + size checks         | Prevents invalid uploads before reaching the AI                                                        |

---

## Fraud Detection Approach

Rather than training a custom ML model (which would require large labeled datasets),
this prototype uses **Claude's visual reasoning** to act as a forensic analyst.

### Signals Checked

1. **Font Consistency** — Mismatched typefaces often indicate text substitution
2. **Alignment & Spacing** — Irregular spacing signals copy-paste tampering
3. **Photo Integrity** — Hard edges, lighting mismatch, or resolution inconsistency
4. **Document Layout** — Compliance with known ID conventions (MRZ zone, seals)
5. **Print Quality & Artifacts** — JPEG artifacts concentrated in edited regions
6. **Security Features** — Presence/absence of guilloche patterns, microprint
7. **Lighting Coherence** — Inconsistent shadows suggest compositing
8. **Text Field Tampering** — Ghosting, background color differences, font weight

### Output Risk Levels

| Level           | Meaning                                      |
| --------------- | -------------------------------------------- |
| `GENUINE`       | No suspicious signals found                  |
| `LOW_RISK`      | Minor anomalies, likely authentic            |
| `MODERATE_RISK` | Notable anomalies; manual review recommended |
| `HIGH_RISK`     | Strong indicators of tampering               |
| `CRITICAL`      | Near-certain forgery signals                 |

---

## Setup & Run

### Prerequisites

- Python 3.10+
- An [Anthropic API key](https://console.anthropic.com/)

### 1. Clone & Install

```bash
git clone <your-repo-url>
cd id-forgery-detector

pip install -r backend/requirements.txt
```

### 2. Set API Key

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

### 3. Start the Backend

```bash
cd backend
uvicorn main:app --reload --port 8000
```

The API will be live at `http://localhost:8000`  
Interactive API docs: `http://localhost:8000/docs`

### 4. Open the Frontend

```bash
# From project root — just open the file in your browser:
open frontend/index.html
# or on Linux:
xdg-open frontend/index.html
```

### 5. Test via CLI

```bash
python test_api.py samples/sample_id.jpg
```

---

## API Reference

### `POST /analyze`

Upload an ID document image and receive a forgery risk report.

**Request:** `multipart/form-data` with `file` field  
**Accepted types:** `image/jpeg`, `image/png`, `image/webp`, `image/gif`  
**Max size:** 10 MB

**Response:**

```json
{
  "document_type": "National ID",
  "overall_risk_level": "MODERATE_RISK",
  "confidence_score": 72,
  "summary": "The document shows several inconsistencies...",
  "checks": [
    { "check_name": "Font Consistency", "status": "WARN", "detail": "..." },
    ...
  ],
  "red_flags": ["Irregular background behind DOB field"],
  "positive_indicators": ["MRZ zone appears properly formatted"],
  "analyst_notes": "...",
  "disclaimer": "...",
  "metadata": {
    "filename": "id.jpg",
    "file_size_kb": 245.3,
    "media_type": "image/jpeg",
    "analyzed_at": "2024-01-15T10:30:00Z",
    "model": "claude-opus-4-5"
  }
}
```

### `GET /health`

Returns `{ "status": "ok", "timestamp": "..." }`

---

## Sample Output

See `samples/` folder for example inputs and `samples/sample_report.json` for a
full JSON output.

---

## Limitations & Disclaimer

- This is a **prototype** for evaluation purposes only
- Claude Vision is reasoning-based, not a dedicated forensic tool
- Should **not** be used as sole evidence in legal or security decisions
- Accuracy depends on image quality and document type familiarity

---

## Future Improvements

- Add support for PDF documents
- Fine-tune a dedicated CNN for forgery artifact detection (e.g. ManTraNet, Noiseprint)
- Integrate ELA (Error Level Analysis) as a pre-processing signal
- Add MRZ checksum validation
- Build a database of known genuine document templates per country
