# Document Intelligence Pipeline

A small Streamlit app that classifies a business document and pulls out structured
fields from it (invoice line items, contract terms, intake form details, etc.) using
the Claude API.

## What it does

1. Pick one of the bundled sample documents (invoice, contract excerpt, intake form)
   or upload your own `.txt` file.
2. The app classifies the document type and extracts the relevant structured fields.
3. Results show up as a metric (document type + confidence), a JSON/table view of the
   extracted fields, and a one-line plain-English summary.
4. The "Processing Log" tab shows each step the pipeline took, in order.

## Running it locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

That's it — no environment variables required. Without an `ANTHROPIC_API_KEY` set,
the app runs in demo mode: it returns realistic, hardcoded extraction results for
the bundled sample documents so you can see the full UI and flow end to end.

## Running it with live extraction

Set your API key before launching:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
streamlit run app.py
```

With the key set, uploaded or sample documents are sent to the Claude API
(`claude-sonnet-4-5`) for real classification and extraction instead of the mock
output.

## Files

- `app.py` — the Streamlit app
- `sample_data/` — sample documents (invoice, contract excerpt, intake form)
- `workflow.md` — pipeline diagram (trigger → input → process → output → verify)
- `requirements.txt` — pinned dependencies
