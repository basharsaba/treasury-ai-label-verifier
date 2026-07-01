from __future__ import annotations

import io
import json
import os
import time
from pathlib import Path

import pandas as pd
import streamlit as st
from PIL import Image

from ai.ocr import extract_with_tesseract
from ai.openai_vision import extract_with_openai
from ai.parser import normalize_expected, parse_fields_from_text
from validator.validator import validate, summarize
from demo_manager import list_demo_items, load_expected, make_demo_zip, make_real_label_zip, verify_real_label_folder, download_remote_manifest

ROOT = Path(__file__).parent
DEMO_DIR = ROOT / "demo_data"
SAMPLE_BATCH_DIR = ROOT / "sample_batch"

st.set_page_config(page_title="Treasury AI Label Verifier", page_icon="🏛️", layout="wide")


def read_bytes(uploaded_file) -> bytes:
    return uploaded_file.getvalue()


def render_header():
    st.title("🏛️ Treasury AI Label Verification")
    st.caption("Hybrid AI + OCR prototype for alcohol label review, field extraction, validation, batch processing, and audit-ready reporting.")


def sidebar_settings():
    st.sidebar.header("⚙️ Extraction settings")
    mode = st.sidebar.radio(
        "Extraction mode",
        ["Auto: OpenAI Vision then OCR fallback", "OpenAI Vision only", "Local OCR only"],
        index=0,
    )
    model = st.sidebar.selectbox("OpenAI model", ["gpt-4o-mini", "gpt-4.1-mini"], index=0)
    api_key = st.sidebar.text_input("OpenAI API key (optional)", type="password", value=os.environ.get("OPENAI_API_KEY", ""))
    st.sidebar.caption("Keys are used only for this session and are not saved to disk.")
    return mode, model, api_key


def extract_label(image_bytes: bytes, mode: str, api_key: str, model: str):
    if mode.startswith("Local"):
        result = extract_with_tesseract(image_bytes)
        result.fields = parse_fields_from_text(result.raw_text)
        return result

    if mode.startswith("OpenAI"):
        result = extract_with_openai(image_bytes, api_key, model=model)
        if result.fields:
            return result
        return result

    # Auto mode
    ai_result = extract_with_openai(image_bytes, api_key, model=model)
    if ai_result.fields and not ai_result.error:
        return ai_result
    ocr_result = extract_with_tesseract(image_bytes)
    ocr_result.fields = parse_fields_from_text(ocr_result.raw_text)
    if ai_result.error:
        ocr_result.error = f"OpenAI unavailable; used OCR fallback. OpenAI error: {ai_result.error}"
    return ocr_result


def expected_form(defaults: dict | None = None):
    d = normalize_expected(defaults or {})
    with st.form("expected_form"):
        st.subheader("Expected application data")
        c1, c2 = st.columns(2)
        with c1:
            brand = st.text_input("Brand name", d.get("brand", ""))
            class_type = st.text_input("Class / type", d.get("class_type", ""))
            alcohol_content = st.text_input("Alcohol content / ABV", d.get("alcohol_content", ""))
            net_contents = st.text_input("Net contents", d.get("net_contents", ""))
        with c2:
            producer = st.text_input("Bottler / producer / importer", d.get("producer", ""))
            address = st.text_input("Address", d.get("address", ""))
            country = st.text_input("Country of origin", d.get("country_of_origin", ""))
            warning_required = st.checkbox("Government warning required", bool(d.get("government_warning_required", True)))
        submitted = st.form_submit_button("Save expected data")
    expected = normalize_expected({
        "brand": brand,
        "class_type": class_type,
        "alcohol_content": alcohol_content,
        "net_contents": net_contents,
        "producer": producer,
        "address": address,
        "country_of_origin": country,
        "government_warning_required": warning_required,
    })
    if submitted:
        st.session_state["expected"] = expected
        st.success("Expected data saved.")
    return expected


def render_results(rows, summary, extraction_result, elapsed):
    st.subheader("Review summary")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Overall", summary["overall"])
    m2.metric("Score", f"{summary['score']}%")
    m3.metric("Pass", summary["pass"])
    m4.metric("Review", summary["review"])
    m5.metric("Fail", summary["fail"])
    st.progress(min(summary["score"], 100) / 100)
    st.caption(f"Engine: {extraction_result.engine} | Extraction confidence: {round(extraction_result.confidence * 100)}% | Processing time: {elapsed:.2f}s")
    if extraction_result.error:
        st.warning(extraction_result.error)

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button("Download field-level CSV report", df.to_csv(index=False).encode("utf-8"), "label_verification_report.csv", "text/csv")


def single_label_page(mode, model, api_key):
    st.header("Single label review")
    template_options = {"Blank / custom": None}
    for item in list_demo_items():
        label = f"{item.get('category', 'Demo')} — {item.get('name', item.get('id'))}"
        template_options[label] = item

    selected = st.selectbox("Load optional demo / template", list(template_options.keys()))
    defaults = {}
    selected_item = template_options[selected]
    if selected_item:
        json_path = DEMO_DIR / selected_item["expected_json"]
        if json_path.exists():
            defaults = load_expected(json_path)
        st.info(selected_item.get("notes", "Demo expected values loaded."))

    expected_json_file = st.file_uploader("Optional: upload expected application JSON", type=["json"], key="single_json")
    if expected_json_file is not None:
        defaults = json.loads(expected_json_file.getvalue().decode("utf-8"))

    expected = expected_form(defaults)
    image_file = st.file_uploader("Upload alcohol label image", type=["png", "jpg", "jpeg", "webp"], key="single_image")

    if image_file:
        col_img, col_action = st.columns([1, 1])
        with col_img:
            st.image(Image.open(io.BytesIO(image_file.getvalue())), caption=image_file.name, use_container_width=True)
        with col_action:
            st.write("Click Analyze to extract label fields and compare them against expected application data.")
            analyze = st.button("Analyze label", type="primary")
        if analyze:
            start = time.perf_counter()
            result = extract_label(read_bytes(image_file), mode, api_key, model)
            extracted = dict(parse_fields_from_text(result.raw_text))
            extracted.update(result.fields or {})
            rows = validate(expected, extracted, result.raw_text)
            elapsed = time.perf_counter() - start
            summary = summarize(rows)
            tabs = st.tabs(["Results", "Extracted fields", "Raw text", "Reviewer notes"])
            with tabs[0]:
                render_results(rows, summary, result, elapsed)
            with tabs[1]:
                st.json(extracted)
            with tabs[2]:
                st.text_area("Raw extracted text", result.raw_text, height=250)
            with tabs[3]:
                st.text_area("Human reviewer notes", placeholder="Document any mismatch explanation, override decision, or follow-up required.", height=160)


def batch_page(mode, model, api_key):
    st.header("Batch processing")
    st.write("Upload multiple label images and a CSV of expected application data. Match records by `file_name` or `record_id`.")
    expected_csv = st.file_uploader("Upload expected-data CSV", type=["csv"], key="batch_csv")
    image_files = st.file_uploader("Upload label images", type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=True, key="batch_images")
    if st.button("Use bundled sample batch"):
        st.info(f"Sample batch files are included in: {SAMPLE_BATCH_DIR}")
        st.write("Use these files when running locally, or download the project ZIP demo data from the Demo Data Manager page.")

    if expected_csv is not None and image_files and st.button("Run batch verification", type="primary"):
        expected_df = pd.read_csv(expected_csv)
        all_rows = []
        batch_summary = []
        for img in image_files:
            start = time.perf_counter()
            img_name = img.name
            matches = expected_df[expected_df.get("file_name", "") == img_name] if "file_name" in expected_df.columns else pd.DataFrame()
            if matches.empty and "record_id" in expected_df.columns:
                stem = Path(img_name).stem
                matches = expected_df[expected_df["record_id"].astype(str) == stem]
            expected = normalize_expected(matches.iloc[0].to_dict() if not matches.empty else {})
            result = extract_label(read_bytes(img), mode, api_key, model)
            extracted = dict(parse_fields_from_text(result.raw_text))
            extracted.update(result.fields or {})
            rows = validate(expected, extracted, result.raw_text)
            elapsed = time.perf_counter() - start
            s = summarize(rows)
            batch_summary.append({"file_name": img_name, "overall": s["overall"], "score": s["score"], "engine": result.engine, "processing_seconds": round(elapsed, 2)})
            for row in rows:
                all_rows.append({"file_name": img_name, **row})
        st.subheader("Batch summary")
        summary_df = pd.DataFrame(batch_summary)
        detail_df = pd.DataFrame(all_rows)
        st.dataframe(summary_df, use_container_width=True, hide_index=True)
        st.download_button("Download batch summary CSV", summary_df.to_csv(index=False).encode("utf-8"), "batch_summary.csv", "text/csv")
        st.subheader("Field-level details")
        st.dataframe(detail_df, use_container_width=True, hide_index=True)
        st.download_button("Download field-level batch CSV", detail_df.to_csv(index=False).encode("utf-8"), "batch_field_report.csv", "text/csv")


def demo_data_page():
    st.header("Demo Data Manager")
    st.write(
        "Use the synthetic bundled dataset for instant testing, or create a local real-label dataset from official/public label sources without committing brand artwork to GitHub."
    )

    items = list_demo_items()
    st.subheader("1) Bundled synthetic dataset")
    st.caption(
        "These labels are safe to redistribute in the repository and are useful for quick reviewer testing. They are not official brand artwork."
    )
    if items:
        st.dataframe(pd.DataFrame(items), use_container_width=True, hide_index=True)
        st.download_button("Download synthetic demo dataset ZIP", make_demo_zip(), "synthetic_demo_data.zip", "application/zip")
    else:
        st.info("No bundled demo templates were found.")

    st.divider()
    st.subheader("2) Real COLA label dataset setup")
    st.caption(
        "Recommended approach: keep real brand/TTB label images outside GitHub, place them locally, and let the app verify/load them."
    )

    recommended_rows = [
        {"Category": "Beer", "Suggested search": "Corona Extra", "File name": "corona_extra.png"},
        {"Category": "Craft beer", "Suggested search": "Sierra Nevada Pale Ale", "File name": "sierra_nevada_pale_ale.png"},
        {"Category": "Red wine", "Suggested search": "Robert Mondavi Cabernet Sauvignon", "File name": "robert_mondavi_cabernet.png"},
        {"Category": "White wine", "Suggested search": "Kendall-Jackson Chardonnay", "File name": "kendall_jackson_chardonnay.png"},
        {"Category": "Bourbon", "Suggested search": "Maker's Mark Bourbon", "File name": "makers_mark.png"},
        {"Category": "Scotch whisky", "Suggested search": "Johnnie Walker Black Label", "File name": "johnnie_walker_black.png"},
        {"Category": "Vodka", "Suggested search": "Tito's Handmade Vodka", "File name": "titos_handmade_vodka.png"},
        {"Category": "Tequila", "Suggested search": "Patrón Silver", "File name": "patron_silver.png"},
        {"Category": "Rum", "Suggested search": "Bacardi Superior", "File name": "bacardi_superior.png"},
        {"Category": "Gin", "Suggested search": "Bombay Sapphire", "File name": "bombay_sapphire.png"},
    ]
    st.markdown(
        """
        **How to use real label artwork safely**

        1. Open the official **TTB COLAs Online Public Registry** below.
        2. Search for one of the suggested products.
        3. Download the front/back label image to your local machine.
        4. Save the files into `demo_data/real_labels/` using the suggested file names below.
        5. Do **not** commit those real brand images to a public GitHub repository unless you have permission.
        6. Use the verifier below to confirm the app can find your local images.
        """
    )
    st.link_button("Open TTB COLAs Online Public Registry", "https://www.ttbonline.gov/colasonline/publicSearchColasBasic.do")
    st.caption("Official TTB registry link for searching approved COLA records and label images. The app links to the registry instead of redistributing third-party brand artwork.")
    st.dataframe(pd.DataFrame(recommended_rows), use_container_width=True, hide_index=True)

    real_dir = DEMO_DIR / "real_labels"
    real_dir.mkdir(parents=True, exist_ok=True)
    found = verify_real_label_folder(real_dir, [row["File name"] for row in recommended_rows])
    found_df = pd.DataFrame(found)
    st.subheader("Local real-label folder check")
    st.code(str(real_dir), language="text")
    st.dataframe(found_df, use_container_width=True, hide_index=True)
    found_count = int(found_df["found"].sum()) if not found_df.empty else 0
    st.metric("Real label images found", f"{found_count}/10")

    if found_count:
        st.download_button(
            "Package local real-label dataset ZIP",
            make_real_label_zip(real_dir),
            "local_real_label_dataset.zip",
            "application/zip",
            help="This packages only files that you placed locally in demo_data/real_labels. Use caution before sharing real brand artwork.",
        )
    else:
        st.info("No local real-label images found yet. Add images to the folder above and refresh this page.")

    st.divider()
    st.subheader("3) Optional manifest-based downloader")
    st.caption(
        "Advanced option: provide your own JSON manifest with image URLs and expected fields. This keeps artwork out of the repository while allowing repeatable dataset setup."
    )
    with st.expander("Expected manifest format"):
        st.code('{\n  "items": [\n    {\n      "id": "sample_label",\n      "name": "Sample Label",\n      "category": "Beer",\n      "image_url": "https://example.com/sample_label.png",\n      "expected": {\n        "brand": "Sample Brand",\n        "class_type": "Lager",\n        "alcohol_content": "4.5% ABV",\n        "net_contents": "355 ml",\n        "country_of_origin": "Mexico",\n        "government_warning_required": true\n      }\n    }\n  ]\n}', language="json")
    manifest_url = st.text_input("Remote manifest URL")
    if st.button("Download dataset from manifest"):
        if not manifest_url.strip():
            st.error("Enter a manifest URL first.")
        else:
            try:
                count, files = download_remote_manifest(manifest_url.strip())
                st.success(f"Downloaded {count} image(s).")
                st.write(files)
            except Exception as exc:
                st.error(f"Download failed: {exc}")


def about_page():
    st.header("Architecture and assumptions")
    st.markdown(
        """
        **Architecture:** image upload → AI Vision or OCR extraction → field parser → validation engine → human review dashboard → CSV audit export.

        **Security:** API keys are never stored in source code or written to disk. The app works without external services through Tesseract OCR fallback.

        **Tradeoffs:** local OCR is free and easy to run but less accurate on complex labels. AI Vision is more robust but requires an API key and network access.
        """
    )


def main():
    render_header()
    mode, model, api_key = sidebar_settings()
    page = st.sidebar.radio("Navigation", ["Single label", "Batch processing", "Demo Data Manager", "About"], index=0)
    if page == "Single label":
        single_label_page(mode, model, api_key)
    elif page == "Batch processing":
        batch_page(mode, model, api_key)
    elif page == "Demo Data Manager":
        demo_data_page()
    else:
        about_page()


if __name__ == "__main__":
    main()
