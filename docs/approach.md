# Approach, Architecture & Tool Rationale

## VeriDoc — ID Forgery Detection Prototype

### Core Philosophy

1. **Forgery detection is treated as anomaly detection, not classification.**
2. **The system combines rule-based image analysis with AI-generated reasoning (hybrid approach).**
3. **The goal is explainability over raw accuracy.**

---

## Problem Understanding

The objective is to analyze an uploaded ID document image and generate a forgery risk
report indicating whether the document appears genuine or suspicious.

This task is **not** about verifying real-world validity (e.g., whether the ID is
officially government-issued), but about identifying:

- Visual inconsistencies
- Signs of tampering or digital manipulation
- Structural anomalies in layout, fonts, and photo embedding

The problem is therefore treated as **anomaly detection + reasoning**, not a
strict binary classification task.

### Key Design Insight — Forgery Risk vs Document Validity

A crucial distinction is made between two separate concerns:

| Concern               | Question                                              | Example                                        |
| --------------------- | ----------------------------------------------------- | ---------------------------------------------- |
| **Forgery Risk**      | Does the image show signs of editing or manipulation? | Tampered expiry date → HIGH_RISK               |
| **Document Validity** | Is this a real issued ID or a placeholder?            | Specimen card → NOT_VALID but LOW forgery risk |

**Why this matters:**
A specimen ID is not a forgery — it has not been tampered with. A naive system
would flag it as CRITICAL simply because it looks "wrong." Our validity classification
layer handles this separately, preventing misclassification and producing more
honest, explainable results.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                     Frontend                         │
│      index.html  (drag-drop upload + report UI)      │
└───────────────────────┬─────────────────────────────┘
                        │  multipart/form-data POST /analyze
                        ▼
┌─────────────────────────────────────────────────────┐
│             FastAPI Backend  (main.py)               │
│                                                     │
│  Layer 1 ── Input Validation                        │
│             • MIME type check (JPEG/PNG/WEBP only)   │
│             • File size check (max 10 MB)            │
│                        │                            │
│  Layer 2 ── Image Processing  (OpenCV)              │
│             • Blur Detection                        │
│             • Noise Analysis                        │
│             • Edge Density                          │
│             • Color Variance                        │
│             • Compression Artifacts                 │
│             • Text Region Density                   │
│                        │                            │
│  Layer 3 ── Rule-Based Scoring                      │
│             • Threshold evaluation per metric       │
│             • Cumulative risk score                 │
│             • Issue list generation                 │
│                        │                            │
│  Layer 4 ── AI Reasoning  (Gemini 2.5 Flash Vision) │
│             • Receives image + OpenCV signals       │
│             • 8-category forensic prompt            │
│             • Returns structured JSON report        │
│                        │                            │
│  Layer 5 ── Validity Classification                 │
│             • Keyword scan (specimen/sample/not-id) │
│             • Separates validity from forgery risk  │
│                        │                            │
│  Layer 6 ── Report Assembly                         │
│             • Merges all layers into final_report   │
│             • Attaches metadata                     │
└───────────────────────┬─────────────────────────────┘
                        │  JSON response
                        ▼
              Structured Forgery Risk Report
```

---

## Detection Layers — Detailed

### Layer 1 — Input Validation

Before any processing begins, the uploaded file is validated for:

- **MIME type** — only `image/jpeg`, `image/png`, `image/webp` are accepted.
  PDFs are excluded because they are multi-layer containers that require a separate
  extraction pipeline, and they introduce a security risk from embedded executables.
- **File size** — files over 10 MB are rejected to prevent memory issues and
  ensure reasonable API response times.

### Layer 2 — Image Processing (OpenCV)

Six deterministic, measurable signals are extracted from the raw image bytes:

| Function                         | Signal                  | What It Detects                                                       |
| -------------------------------- | ----------------------- | --------------------------------------------------------------------- |
| `detect_blur()`                  | Laplacian variance      | Low sharpness → possible tampering concealment or low-quality forgery |
| `detect_noise()`                 | Grayscale std deviation | High noise → editing artifacts from compositing or re-encoding        |
| `detect_edges()`                 | Canny edge density      | Weak edges → structural breaks; too many edges → noise/artifacts      |
| `detect_color_inconsistency()`   | HSV saturation variance | High variance → mismatched color regions from compositing             |
| `detect_compression_artifacts()` | DCT mean coefficient    | High value → uneven JPEG re-compression typical of edited regions     |
| `detect_text_regions()`          | Thresholded pixel ratio | Abnormal density → missing text (unusual for ID) or overlaid text     |

These signals are **deterministic and explainable** — the same image always
produces the same values, making the system fully auditable.

### Layer 3 — Rule-Based Scoring

`generate_report()` maps each OpenCV metric against empirically chosen thresholds
to produce a human-readable issue list and a cumulative risk score:

```
Blur    < 80  → "Image is blurry"               +2 pts
Blur   80–120 → "Slight blur detected"           +1 pt
Noise   > 60  → "High noise (possible editing)"  +2 pts
Noise  40–60  → "Moderate noise"                 +1 pt
Edges  < 0.03 → "Weak edge structure"            +2 pts
Edges  > 0.15 → "Too many edges"                 +1 pt
Color   > 60  → "High color inconsistency"       +2 pts
DCT     > 0.2 → "Compression artifacts"          +1 pt
Text   < 0.02 → "Low text presence"              +1 pt
Text   > 0.25 → "Abnormal text density"          +1 pt

Score ≥ 6  →  suspicious
Score ≥ 3  →  review
Score  < 3  →  likely_genuine
```

This layer catches cases that pure visual AI might miss — for example, a
high-quality forgery with consistent appearance but anomalous noise patterns.

### Layer 4 — AI Reasoning (Gemini 2.5 Flash Vision)

Gemini Vision receives both the raw image and the computed OpenCV signals,
grounding its reasoning with measurable data:

```python
prompt = f"""
  Blur score:    {manual_results["blur"]}
  Noise level:   {manual_results["noise"]}
  Edge density:  {manual_results["edges"]}
  ...
  {FORGERY_ANALYSIS_PROMPT}
"""
```

The forensic prompt instructs Gemini to evaluate 8 high-level semantic signals
that OpenCV cannot measure on its own:

| #   | Signal               | Why AI is Needed                                  |
| --- | -------------------- | ------------------------------------------------- |
| 1   | Font Consistency     | Requires reading and comparing typefaces          |
| 2   | Alignment & Spacing  | Requires understanding ID layout conventions      |
| 3   | Photo Integrity      | Requires detecting lighting/resolution mismatches |
| 4   | Document Layout      | Requires knowledge of MRZ zones, seals, holograms |
| 5   | Print Quality        | Requires reasoning about ink density patterns     |
| 6   | Security Features    | Requires knowledge of guilloche, microprint       |
| 7   | Lighting Coherence   | Requires reasoning about shadow direction         |
| 8   | Text Field Tampering | Requires detecting ghosting and background shifts |

The model is configured with:

- `response_mime_type="application/json"` — forces clean JSON output with no markdown wrapping
- `max_output_tokens=8192` — enough room for detailed per-check analysis
- `temperature=0.2` — low temperature for consistent, deterministic responses

### Layer 5 — Validity Classification

`classify_validity()` performs a keyword scan over the AI report content to
classify the document's validity status separately from its forgery risk:

| Status               | Trigger                                      |
| -------------------- | -------------------------------------------- |
| `SPECIMEN_DOCUMENT`  | Report contains "specimen"                   |
| `SAMPLE_DOCUMENT`    | Report contains "sample"                     |
| `NOT_VALID_DOCUMENT` | Report contains "not a valid" or "not valid" |
| `NOT_AN_ID`          | Report contains "not an id"                  |
| `LIKELY_VALID`       | None of the above matched                    |

This prevents a specimen card from being misclassified as a HIGH_RISK forgery —
it is not tampered, it is simply not a real document.

### Layer 6 — Report Assembly

The final report merges all layers into a single structured response:

```json
{
  "document_type": "from Gemini",
  "overall_risk_level": "from Gemini",
  "confidence_score": "from Gemini",
  "summary": "from Gemini",
  "checks": "from Gemini (per-signal breakdown)",
  "red_flags": "from Gemini",
  "positive_indicators": "from Gemini",
  "analyst_notes": "from Gemini",
  "disclaimer": "from Gemini",
  "manual_analysis": "from OpenCV (6 raw metrics)",
  "rule_based": "from rule engine (status + issues + confidence)",
  "validity_status": "from validity classifier",
  "metadata": "filename, size, model, timestamp"
}
```

---

## Why This Hybrid Approach?

| Approach                 | Pros                                       | Cons                                  |
| ------------------------ | ------------------------------------------ | ------------------------------------- |
| **AI only**              | Understands semantics, fonts, layout       | Can hallucinate; not auditable        |
| **OpenCV only**          | Deterministic, fast, fully auditable       | Cannot read text or understand layout |
| **Hybrid (this system)** | Deterministic signals + semantic reasoning | Slightly more complex pipeline        |

The hybrid approach is the most robust choice for a prototype because:

1. OpenCV signals **ground** the AI reasoning with hard, measurable numbers
2. AI reasoning **interprets** signals that pixel math alone cannot explain
3. Rule-based scoring **provides a safety net** independent of the AI
4. Validity classification **prevents category errors** on specimen/sample IDs

---

## Tools & Technologies

| Layer            | Technology                              | Why Chosen                                                       |
| ---------------- | --------------------------------------- | ---------------------------------------------------------------- |
| Backend          | **FastAPI**                             | Async Python, auto-generated OpenAPI docs, ideal for ML services |
| Image Processing | **OpenCV + NumPy**                      | Industry-standard computer vision; deterministic and fast        |
| AI Model         | **Gemini 2.5 Flash Vision (free tier)** | No cost, multimodal, strong visual reasoning                     |
| Frontend         | **Vanilla HTML/CSS/JS**                 | Zero dependencies, runs anywhere, fast to demo                   |
| Env Management   | **python-dotenv**                       | Secure API key handling without hardcoding                       |

---

## Limitations

- Vision-based reasoning cannot replace physical inspection (UV light, tactile feel)
- OpenCV thresholds are heuristic — not trained on a labeled forgery dataset
- Gemini has not been fine-tuned specifically on ID forgery datasets
- Image quality heavily affects accuracy — blurry or low-resolution uploads reduce reliability
- Not suitable for production use without additional validation layers

---

## Future Improvements

- **Pass all 6 OpenCV signals to Gemini** — currently only blur, noise, edges are passed; color variance, compression, and text density should also be included for richer grounding
- **Error Level Analysis (ELA)** — highlight JPEG artifact inconsistencies as a dedicated pre-processing step
- **MRZ checksum validation** — programmatically verify machine-readable zone check digits
- **Template matching** — compare layout against a database of genuine templates per country
- **Fine-tuned CNN** — train a specialized model (e.g., ManTraNet, Noiseprint) for forgery localization
- **PDF support** — extract embedded images from PDFs before analysis
- **Batch processing** — accept ZIP files with multiple IDs for bulk verification
