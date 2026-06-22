"""
Document Intelligence Pipeline
A small Streamlit app that classifies a business document and extracts
structured fields from it using the Claude API. Falls back to a mock
extractor when no API key is configured so the app stays fully demoable.
"""

import io
import json
import os
import time
from datetime import datetime

import streamlit as st

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

APP_TITLE = "Document Intelligence Pipeline"
MODEL_ID = "claude-sonnet-4-5"
SAMPLE_DIR = "sample_data"

SAMPLE_FILES = {
    "Invoice (Acme Industrial Supply)": "invoice_acme.txt",
    "Services Agreement (Northbridge / Cascade)": "contract_excerpt.txt",
    "New Client Intake Form (Whitfield Realty)": "intake_form.txt",
}

EXTRACTION_PROMPT = """You are a document intelligence engine. Read the document below and:

1. Classify the document type (e.g. "invoice", "contract", "intake_form", "other").
2. Extract the key structured fields relevant to that document type. For an invoice,
   extract vendor, invoice number, invoice date, due date, line items (description,
   qty, unit price, total), subtotal, tax, and total due. For a contract, extract the
   parties involved, effective date, term/expiration, key obligations, compensation
   terms, and termination conditions. For an intake form, extract the requester's
   contact info, the service requested, key dates, and any budget or priority info.
3. Return ONLY valid JSON with this shape:

{
  "document_type": "...",
  "confidence": 0.0-1.0,
  "fields": { ... extracted fields ... },
  "summary": "one or two sentence plain-English summary"
}

Document:
---
{doc_text}
---

Respond with JSON only, no commentary, no markdown code fences.
"""


# --------------------------------------------------------------------------
# Mock extraction (used whenever ANTHROPIC_API_KEY is not set)
# --------------------------------------------------------------------------

def _mock_extract(doc_text: str) -> dict:
    """Return realistic, hardcoded structured output for known sample docs.

    This keeps the app fully functional and demoable with zero environment
    setup. It matches on a short fingerprint from the document text so each
    bundled sample produces a distinct, on-topic result.
    """
    text_lower = doc_text.lower()

    if "acme industrial supply" in text_lower or "invoice #" in text_lower:
        return {
            "document_type": "invoice",
            "confidence": 0.97,
            "fields": {
                "vendor": "Acme Industrial Supply Co.",
                "invoice_number": "INV-20458",
                "invoice_date": "2026-05-14",
                "due_date": "2026-06-13",
                "terms": "Net 30",
                "bill_to": "Hartwell Manufacturing LLC",
                "line_items": [
                    {"description": "Industrial bearing assembly (Model HB-220)", "qty": 12, "unit_price": 84.50, "total": 1014.00},
                    {"description": "Hex bolt set, stainless steel (Box of 500)", "qty": 6, "unit_price": 39.20, "total": 235.20},
                    {"description": "Replacement gasket kit (Model GK-90)", "qty": 4, "unit_price": 62.75, "total": 251.00},
                    {"description": "Freight and handling", "qty": 1, "unit_price": 145.00, "total": 145.00},
                ],
                "subtotal": 1645.20,
                "tax": 119.28,
                "total_due": 1764.48,
            },
            "summary": "Invoice from Acme Industrial Supply Co. to Hartwell Manufacturing for $1,764.48, due June 13, 2026 under Net 30 terms.",
        }

    if "services agreement" in text_lower or "northbridge consulting" in text_lower:
        return {
            "document_type": "contract",
            "confidence": 0.95,
            "fields": {
                "parties": [
                    {"name": "Northbridge Consulting Group, Inc.", "role": "Provider"},
                    {"name": "Cascade Retail Holdings, LLC", "role": "Client"},
                ],
                "effective_date": "2026-03-01",
                "initial_term": "12 months",
                "expiration_date": "2027-02-28",
                "auto_renewal": "Successive 12-month terms unless 60 days' written notice of non-renewal",
                "compensation": "$7,500/month retainer, $225/hour for advisory work beyond 10 hrs/month",
                "termination": "30 days' notice for uncured material breach; 90 days' notice for convenience by Client",
                "confidentiality_period": "3 years post-termination",
                "key_obligations": [
                    "Provider delivers quarterly operational audits and monthly performance dashboard",
                    "Provider offers on-call advisory support up to 10 hrs/month",
                    "Client provides timely access to financial records and a single point of contact",
                    "Client remits payment within 15 days of invoice receipt",
                ],
            },
            "summary": "12-month services agreement between Northbridge Consulting and Cascade Retail Holdings at a $7,500/month retainer, auto-renewing with a 60-day non-renewal notice window.",
        }

    if "intake form" in text_lower or "whitfield" in text_lower:
        return {
            "document_type": "intake_form",
            "confidence": 0.93,
            "fields": {
                "requester_name": "Dana Whitfield",
                "company": "Whitfield & Co. Realty",
                "email": "dana.whitfield@example.com",
                "phone": "(503) 555-0148",
                "service_requested": "Lease document review and renewal recommendation",
                "property_address": "2210 Birch Hollow Drive, Lake Oswego, OR 97034",
                "lease_expiration": "2026-08-31",
                "urgency": "Medium (response within 5 business days)",
                "budget_range": "$400-$800",
                "preferred_start_date": "2026-04-08",
                "referral_source": "Existing client referral (Margaret Chen)",
            },
            "summary": "Dana Whitfield requests a lease review and renewal recommendation ahead of an August 2026 expiration, budget $400-$800, medium urgency.",
        }

    # Generic fallback for any unrecognized / user-uploaded text
    return {
        "document_type": "unknown",
        "confidence": 0.42,
        "fields": {
            "note": "No structured pattern matched in mock mode. Connect a live API key for real extraction on arbitrary documents.",
            "preview": doc_text[:200].strip() + ("..." if len(doc_text) > 200 else ""),
        },
        "summary": "Document type could not be confidently determined in mock mode.",
    }


# --------------------------------------------------------------------------
# Real extraction via Claude API
# --------------------------------------------------------------------------

def _real_extract(doc_text: str, api_key: str) -> dict:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    prompt = EXTRACTION_PROMPT.format(doc_text=doc_text)

    response = client.messages.create(
        model=MODEL_ID,
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_text = response.content[0].text.strip()

    # Defensive cleanup in case the model wraps the JSON in a code fence anyway
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.lower().startswith("json"):
            raw_text = raw_text[4:].strip()

    return json.loads(raw_text)


def extract(doc_text: str, api_key: str) -> dict:
    """Public entry point. Routes to mock or real extraction."""
    if not api_key:
        return _mock_extract(doc_text)
    try:
        return _real_extract(doc_text, api_key)
    except Exception as exc:  # noqa: BLE001 - surface any API error to the log/UI
        raise RuntimeError(f"Live extraction failed: {exc}") from exc


# --------------------------------------------------------------------------
# Streamlit UI
# --------------------------------------------------------------------------

def load_sample(filename: str) -> str:
    path = os.path.join(SAMPLE_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def init_log():
    if "log" not in st.session_state:
        st.session_state.log = []


def log_step(message: str):
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.log.append(f"[{timestamp}] {message}")


def main():
    st.set_page_config(page_title=APP_TITLE, page_icon="\U0001F4C4", layout="wide")
    init_log()

    st.title(APP_TITLE)
    st.write(
        "Upload a business document or pick a sample, and the pipeline will "
        "classify it and pull out structured fields."
    )

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    mock_mode = not bool(api_key)

    tab_run, tab_log = st.tabs(["Run Pipeline", "Processing Log"])

    with tab_run:
        col_input, col_output = st.columns([1, 1.4])

        with col_input:
            st.subheader("1. Input")
            source = st.radio(
                "Document source",
                ["Use a sample document", "Upload a document"],
                horizontal=True,
            )

            doc_text = None
            doc_label = None

            if source == "Use a sample document":
                choice = st.selectbox("Sample document", list(SAMPLE_FILES.keys()))
                doc_text = load_sample(SAMPLE_FILES[choice])
                doc_label = choice
            else:
                uploaded = st.file_uploader("Upload a .txt document", type=["txt"])
                if uploaded is not None:
                    doc_text = io.TextIOWrapper(uploaded, encoding="utf-8").read()
                    doc_label = uploaded.name

            if doc_text:
                st.text_area("Document preview", doc_text, height=320)

            run_clicked = st.button("Run extraction", type="primary", disabled=doc_text is None)

        with col_output:
            st.subheader("2. Extracted Output")

            if run_clicked and doc_text:
                log_step(f"Received document: {doc_label}")
                with st.spinner("Classifying and extracting structured data..."):
                    log_step(f"Routing to {'mock extractor (no API key set)' if mock_mode else f'Claude API ({MODEL_ID})'}")
                    start = time.time()
                    try:
                        result = extract(doc_text, api_key)
                        elapsed = time.time() - start
                        log_step(f"Extraction completed in {elapsed:.2f}s")
                        log_step(f"Classified as: {result.get('document_type', 'unknown')}")
                        st.session_state.last_result = result
                    except Exception as exc:  # noqa: BLE001
                        log_step(f"ERROR: {exc}")
                        st.error(f"Extraction failed: {exc}")
                        st.session_state.last_result = None

            result = st.session_state.get("last_result")

            if result:
                doc_type = result.get("document_type", "unknown")
                confidence = result.get("fields", {}).get("confidence") or result.get("confidence", 0)

                badge_col1, badge_col2 = st.columns([1, 1])
                with badge_col1:
                    st.metric("Document Type", doc_type.replace("_", " ").title())
                with badge_col2:
                    st.metric("Confidence", f"{confidence * 100:.0f}%")
                st.progress(min(max(confidence, 0.0), 1.0))

                st.markdown("**Summary**")
                st.write(result.get("summary", ""))

                st.markdown("**Extracted Fields**")
                fields = result.get("fields", {})

                line_items = fields.get("line_items")
                if line_items:
                    other_fields = {k: v for k, v in fields.items() if k != "line_items"}
                    st.json(other_fields)
                    st.markdown("**Line Items**")
                    st.table(line_items)
                else:
                    st.json(fields)

                with st.expander("Raw JSON"):
                    st.code(json.dumps(result, indent=2), language="json")

                if mock_mode:
                    st.caption("Sample output — connect your API key for live results.")
            else:
                st.info("Pick a document and click 'Run extraction' to see results.")

    with tab_log:
        st.subheader("Processing Log")
        if st.session_state.log:
            st.code("\n".join(st.session_state.log), language="text")
            if st.button("Clear log"):
                st.session_state.log = []
        else:
            st.write("No steps logged yet. Run an extraction to populate this tab.")


if __name__ == "__main__":
    main()
