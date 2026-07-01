from __future__ import annotations

import json
import zipfile
from pathlib import Path
from io import BytesIO
import requests

ROOT = Path(__file__).parent
DEMO_DIR = ROOT / "demo_data"


def load_manifest() -> dict:
    path = DEMO_DIR / "manifest.json"
    if not path.exists():
        return {"items": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    # Support either {"items": [...]} or a plain list from older demo packs.
    if isinstance(data, list):
        items = []
        for item in data:
            normalized = dict(item)
            normalized.setdefault("name", item.get("brand_name", item.get("id", "Demo label")))
            json_path = item.get("expected_json") or item.get("json") or f"demo_data/{item.get('id')}.json"
            image_path = item.get("image")
            normalized["expected_json"] = str(json_path).replace("demo_data/", "")
            if image_path:
                normalized["image"] = str(image_path).replace("demo_data/", "")
            normalized.setdefault("notes", f"Synthetic demo template for {normalized.get('category', 'label')}.")
            items.append(normalized)
        return {"items": items}
    return data


def list_demo_items() -> list[dict]:
    manifest = load_manifest()
    return manifest.get("items", [])


def load_expected(json_path: str | Path) -> dict:
    path = Path(json_path)
    return json.loads(path.read_text(encoding="utf-8"))


def make_demo_zip() -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p in DEMO_DIR.rglob("*"):
            if p.is_file():
                z.write(p, p.relative_to(ROOT))
    return buf.getvalue()



def verify_real_label_folder(folder: Path, expected_files: list[str]) -> list[dict]:
    folder.mkdir(parents=True, exist_ok=True)
    rows = []
    for file_name in expected_files:
        path = folder / file_name
        rows.append({
            "file_name": file_name,
            "found": path.exists(),
            "path": str(path) if path.exists() else "Not found",
        })
    return rows


def make_real_label_zip(folder: Path) -> bytes:
    buf = BytesIO()
    folder.mkdir(parents=True, exist_ok=True)
    allowed = {".png", ".jpg", ".jpeg", ".webp", ".json", ".csv"}
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p in folder.rglob("*"):
            if p.is_file() and p.suffix.lower() in allowed:
                z.write(p, p.relative_to(ROOT))
    return buf.getvalue()

def download_remote_manifest(manifest_url: str, target_dir: Path | None = None) -> tuple[int, list[str]]:
    target_dir = target_dir or DEMO_DIR / "downloaded"
    target_dir.mkdir(parents=True, exist_ok=True)
    manifest = requests.get(manifest_url, timeout=20).json()
    downloaded = []
    for item in manifest.get("items", []):
        image_url = item.get("image_url")
        if not image_url:
            continue
        name = item.get("id", "label") + Path(image_url.split("?")[0]).suffix
        out = target_dir / name
        resp = requests.get(image_url, timeout=30)
        resp.raise_for_status()
        out.write_bytes(resp.content)
        expected = item.get("expected", {})
        (target_dir / f"{item.get('id','label')}.json").write_text(json.dumps(expected, indent=2), encoding="utf-8")
        downloaded.append(str(out))
    return len(downloaded), downloaded
