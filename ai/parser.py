from __future__ import annotations

import re


def normalize_expected(data: dict) -> dict:
    aliases = {
        "brand": "brand",
        "brand_name": "brand",
        "class": "class_type",
        "type": "class_type",
        "class_type": "class_type",
        "abv": "alcohol_content",
        "alcohol": "alcohol_content",
        "alcohol_content": "alcohol_content",
        "volume": "net_contents",
        "net_contents": "net_contents",
        "producer": "producer",
        "bottler": "producer",
        "importer": "producer",
        "address": "address",
        "origin": "country_of_origin",
        "country": "country_of_origin",
        "country_of_origin": "country_of_origin",
        "government_warning": "government_warning_required",
        "government_warning_required": "government_warning_required",
        "file_name": "file_name",
        "record_id": "record_id",
    }
    out = {}
    for k, v in (data or {}).items():
        key = aliases.get(str(k).strip().lower(), str(k).strip().lower())
        out[key] = v
    if "government_warning_required" not in out:
        out["government_warning_required"] = True
    return out


def parse_fields_from_text(text: str) -> dict:
    t = text or ""
    fields: dict[str, object] = {}
    abv = re.search(r"(\d{1,2}(?:\.\d+)?)\s*%\s*(?:alc\.?\s*/?\s*vol\.?|abv|alcohol)?", t, re.I)
    if abv:
        fields["alcohol_content"] = f"{abv.group(1)}% ABV"
    vol = re.search(r"(\d+(?:\.\d+)?)\s*(ml|mL|ML|l|L|liters?|ounces?|oz|fl\.?\s*oz\.?)", t, re.I)
    if vol:
        fields["net_contents"] = f"{vol.group(1)} {vol.group(2)}"
    country = re.search(r"(?:produced|product|bottled|made)\s+(?:and\s+bottled\s+)?(?:in|of)\s+([A-Z][A-Za-z ]+)", t, re.I)
    if country:
        fields["country_of_origin"] = country.group(1).strip()
    fields["government_warning_present"] = bool(re.search(r"government\s+warning|according\s+to\s+the\s+surgeon\s+general|birth\s+defects", t, re.I))
    return fields
