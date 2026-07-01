from __future__ import annotations

import base64
import json
from .ocr import ExtractionResult

PROMPT = """
You are assisting a TTB alcohol-label reviewer. Analyze the image and return ONLY valid JSON.
Extract these fields when visible:
brand, class_type, alcohol_content, net_contents, producer, address, country_of_origin,
government_warning_present, government_warning_text.
Also include confidence from 0 to 1 and a raw_text summary.
Use null when a field is not visible.
"""


def extract_with_openai(image_bytes: bytes, api_key: str | None, model: str = "gpt-4o-mini") -> ExtractionResult:
    if not api_key:
        return ExtractionResult("OpenAI Vision", "", {}, 0.0, "No OpenAI API key provided.")
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Return strict JSON only. No markdown."},
                {"role": "user", "content": [
                    {"type": "text", "text": PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ]},
            ],
            temperature=0,
        )
        content = response.choices[0].message.content or "{}"
        content = content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(content)
        raw_text = data.get("raw_text") or json.dumps(data, ensure_ascii=False)
        confidence = float(data.get("confidence") or 0.85)
        return ExtractionResult("OpenAI Vision", raw_text, data, confidence)
    except Exception as exc:
        return ExtractionResult("OpenAI Vision", "", {}, 0.0, str(exc))
