"""
Quick CLI test — no browser needed.
Usage:  python test_api.py path/to/id_image.jpg
"""
import json
import sys
import requests


def analyze(image_path: str):
    url = "http://localhost:8000/analyze"
    with open(image_path, "rb") as f:
        files = {"file": (image_path, f, "image/jpeg")}
        print(f"→ Sending {image_path} to {url} …")
        resp = requests.post(url, files=files, timeout=60)

    resp.raise_for_status()
    data = resp.json()
    print("\n" + "═" * 60)
    print(f"  RISK LEVEL  : {data.get('overall_risk_level')}")
    print(f"  DOC TYPE    : {data.get('document_type')}")
    print(f"  CONFIDENCE  : {data.get('confidence_score')}%")
    print("═" * 60)
    print(f"\nSUMMARY:\n  {data.get('summary')}")

    print("\nCHECKS:")
    for c in data.get("checks", []):
        icon = {"PASS": "✓", "WARN": "!", "FAIL": "✗", "INCONCLUSIVE": "?"}.get(c["status"], "•")
        print(f"  [{icon}] {c['check_name']}: {c['detail']}")

    flags = data.get("red_flags", [])
    if flags:
        print("\nRED FLAGS:")
        for f in flags:
            print(f"  ⚑ {f}")

    positives = data.get("positive_indicators", [])
    if positives:
        print("\nPOSITIVE INDICATORS:")
        for p in positives:
            print(f"  ✓ {p}")

    print(f"\nNOTES:\n  {data.get('analyst_notes')}")
    print(f"\nDISCLAIMER:\n  {data.get('disclaimer')}")
    print("\n--- Raw JSON saved to report_output.json ---")

    with open("report_output.json", "w") as out:
        json.dump(data, out, indent=2)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_api.py <image_path>")
        sys.exit(1)
    analyze(sys.argv[1])