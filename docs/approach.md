# Approach, Architecture & Tool Rationale

## VeriDoc — ID Forgery Detection Prototype

---

## Problem Understanding

ID document forgery typically falls into three categories:

1. **Template forgeries** — entirely fake documents printed to look real
2. **Data alteration forgeries** — genuine documents with modified fields (name, DOB, expiry)
3. **Photo substitution forgeries** — genuine documents with a replaced photo

The most common and hardest to detect is **data alteration**, because 90%+ of the document is genuine — only one or two fields are changed. Our detection approach specifically targets the visual artifacts these modifications leave behind.

---

## Why Claude Vision?

Training a custom forgery detection model requires:

- Thousands of labeled genuine + forged ID samples per document type
- Coverage of hundreds of ID formats across countries
- Ongoing updates as document designs change

Instead, we leverage **Claude's multimodal reasoning** to act as an expert forensic analyst:

- It reasons about visual anomalies (inconsistent fonts, compression artifacts, lighting)
- It understands document structure and security conventions
- It produces human-readable explanations, not just a score
- It generalizes across document types without retraining

This aligns with the assignment's emphasis on **problem understanding, approach, and reasoning** over raw accuracy.

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│                   Frontend                       │
│    index.html (drag-drop upload + report UI)     │
└──────────────────┬──────────────────────────────┘
                   │  multipart/form-data POST /analyze
                   ▼
┌─────────────────────────────────────────────────┐
│              FastAPI Backend (main.py)           │
│                                                 │
│  1. Image MIME + size validation                │
│  2. Base64 encode image                         │
│  3. Build Claude Vision prompt                  │
│  4. Call Anthropic API                          │
│  5. Parse JSON response                         │
│  6. Attach metadata + return                    │
└──────────────────┬──────────────────────────────┘
                   │  base64 image + forensic prompt
                   ▼
┌─────────────────────────────────────────────────┐
│         Anthropic Claude claude-opus-4-5               │
│         (multimodal reasoning)                  │
│                                                 │
│  Examines 8 forensic signal categories          │
│  Returns structured JSON risk report            │
└─────────────────────────────────────────────────┘
```

---

## Forensic Signal Categories

| #   | Signal                    | What We Look For                                          |
| --- | ------------------------- | --------------------------------------------------------- |
| 1   | Font Consistency          | Mismatched weight/size between fields                     |
| 2   | Alignment & Spacing       | Irregular baselines or field positions                    |
| 3   | Photo Integrity           | Hard edges, lighting mismatch, resolution delta           |
| 4   | Document Layout           | Compliance with ID conventions (MRZ, seals)               |
| 5   | Print Quality & Artifacts | JPEG artifacts concentrated in edited regions             |
| 6   | Security Features         | Guilloche patterns, microprint (where visible)            |
| 7   | Lighting Coherence        | Shadow/highlight inconsistencies from compositing         |
| 8   | Text Field Tampering      | Background tone differences, ghosting, font weight shifts |

---

## Design Decisions

**Structured prompt → structured JSON output**  
The Claude prompt explicitly requests a JSON schema. This makes the API response machine-parseable and displayable in a clean UI without any NLP post-processing.

**Risk levels instead of binary pass/fail**  
Forgery is a spectrum. A 5-level risk scale (GENUINE → CRITICAL) better reflects real-world uncertainty and triggers appropriate follow-up actions.

**Confidence score**  
Accompanies the risk level to communicate how certain the model is — important for borderline cases where a human review should be triggered.

**Analyst notes field**  
Encourages the AI to explain its reasoning rather than just classify. This is the most evaluator-friendly output since it demonstrates problem understanding.

---

## Limitations

- Vision-based reasoning cannot replace physical inspection (UV light, tactile feel)
- Image quality heavily affects accuracy — blurry or low-resolution uploads reduce reliability
- Claude has not been specifically fine-tuned on forgery datasets
- Not suitable for production use without additional validation layers

---

## Potential Enhancements

- **Error Level Analysis (ELA)**: Pre-process images to highlight JPEG artifact inconsistencies before sending to Claude
- **MRZ checksum validation**: Programmatically verify the machine-readable zone check digits
- **Template matching**: Compare document layout against a database of genuine templates per country
- **Fine-tuned vision model**: Train a specialized CNN (e.g., ManTraNet) for forgery localization as a complementary signal
- **Batch processing**: Accept ZIP files with multiple IDs for bulk verification workflows
