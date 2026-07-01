from __future__ import annotations

from dataclasses import dataclass
import re
from rapidfuzz import fuzz

FIELD_LABELS = {
    "brand": "Brand name",
    "class_type": "Class / type",
    "alcohol_content": "Alcohol content / ABV",
    "net_contents": "Net contents",
    "producer": "Bottler / producer / importer",
    "address": "Bottler / producer / importer address",
    "country_of_origin": "Country of origin",
    "government_warning_required": "Government Health Warning Statement",
}


def clean(value) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def find_best(expected: str, raw_text: str, extracted_value: str | None = None) -> tuple[str, int]:
    expected_clean = clean(expected)
    extracted_clean = clean(extracted_value)
    raw_clean = clean(raw_text)
    if not expected_clean:
        return extracted_clean or "Not provided", 100
    candidates = [extracted_clean, raw_clean]
    scores = [(c, fuzz.partial_ratio(expected_clean.lower(), c.lower()) if c else 0) for c in candidates]
    found, score = max(scores, key=lambda x: x[1])
    return (extracted_clean or (expected_clean if score >= 80 else "Not clearly detected"), int(score))


def status_for_score(score: int) -> str:
    if score >= 85:
        return "✅ Pass"
    if score >= 60:
        return "⚠️ Needs Review"
    return "❌ Fail"


def validate(expected: dict, extracted: dict, raw_text: str) -> list[dict]:
    rows = []
    for key in ["brand", "class_type", "alcohol_content", "net_contents", "producer", "address", "country_of_origin"]:
        exp = clean(expected.get(key, ""))
        if not exp:
            continue
        found, score = find_best(exp, raw_text, extracted.get(key))
        rows.append({
            "field": FIELD_LABELS[key],
            "expected": exp,
            "detected": found,
            "status": status_for_score(score),
            "confidence": score,
            "notes": "Expected value matched." if score >= 85 else "Expected value was not clearly found on the label.",
        })
    warning_required = bool(expected.get("government_warning_required", True))
    if warning_required:
        present = bool(extracted.get("government_warning_present")) or bool(re.search(r"government\s+warning|surgeon\s+general|birth\s+defects", raw_text or "", re.I))
        rows.append({
            "field": FIELD_LABELS["government_warning_required"],
            "expected": "Required warning statement",
            "detected": "Found" if present else "Not detected",
            "status": "✅ Pass" if present else "❌ Fail",
            "confidence": 100 if present else 0,
            "notes": "Government warning statement detected." if present else "Government warning statement was missing or incomplete.",
        })
    return rows


def summarize(rows: list[dict]) -> dict:
    if not rows:
        return {"overall": "No checks", "score": 0, "pass": 0, "review": 0, "fail": 0}
    passed = sum("Pass" in r["status"] for r in rows)
    review = sum("Needs Review" in r["status"] for r in rows)
    fail = sum("Fail" in r["status"] for r in rows)
    score = round(sum(int(r.get("confidence", 0)) for r in rows) / len(rows))
    overall = "PASS" if fail == 0 and review == 0 else ("REVIEW REQUIRED" if fail == 0 else "FAIL")
    return {"overall": overall, "score": score, "pass": passed, "review": review, "fail": fail}
