# PortShield AI — v0.8

Source-linked trade-document review prototype. AI-extracted fields require human confirmation; six deterministic checks do not establish bank or customs compliance.

## Run
```sh
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit secrets
Keep keys in Streamlit settings → Secrets, never GitHub.
```toml
OPENROUTER_API_KEY = "your-key"
GEMINI_API_KEY = "your-key"
# Optional explicit model overrides:
OPENROUTER_MODEL = "dots-studio/dots-3-note-preview:free"
GEMINI_MODEL = "gemini-3.8-flash"
```
OpenRouter requires a specific `:free` model and sets zero prompt/completion price ceilings. Automatic model routers and paid models are rejected. The chosen model can still be unavailable or quota-limited. Gemini access and charges depend on the user's project; no free-tier guarantee is made.

## Connection check and extraction
Document intake → **Check AI connection** checks model metadata and sends a tiny synthetic JSON request. No document is sent by this button. This consumes a small amount of provider quota. Extraction performs the same preflight before sending the packet. Metadata alone is not treated as proof of inference access.

OpenRouter's advertised capabilities select `json_schema`, `json_object`, or `prompt_json`; the selected mode is recorded. All responses are parsed and locally validated regardless of mode. Model identity is checked; the `:free` routing suffix may be absent in the returned model name. A connection test does not establish PDF understanding or extraction accuracy.

## Bounded execution
PDF parsing, metadata, synthetic probe, inference, and response validation run in an isolated subprocess with one **75-second wall-clock budget**, plus brief process cleanup. Each network operation has a 25-second socket timeout. There are no application-level retries or automatic model switches. OpenRouter may route between endpoints of the same model. The parent kills and reaps the worker on timeout; this cannot guarantee cancellation of a request already running at the provider.

Secrets travel through a private stdin pipe, not command-line arguments or temporary files. Each latest diagnostic contains a random request ID, operation, provider, configured model, stage, HTTP request count, output mode, elapsed time, status/category and (when applicable) HTTP status. Diagnostic exports exclude document text, raw provider bodies and keys. Extraction evidence and review exports are separate and do contain document-derived information.

## Failure categories
- Configuration/access: `CONFIGURATION`, `MODEL_UNAVAILABLE`, `UNSUPPORTED_CAPABILITY`, `AUTHENTICATION`, `ACCESS_DENIED`, `CREDITS_REQUIRED`.
- Runtime: `RATE_LIMIT`, `PROVIDER_UNAVAILABLE`, `NETWORK_TIMEOUT`, `NETWORK_ERROR`, `DEADLINE_EXCEEDED`, `WORKER_FAILED`.
- Provider contract: `REQUEST_REJECTED`, `MODEL_OR_ENDPOINT_UNAVAILABLE`, `CAPABILITY_RESPONSE`, `CAPABILITY_PROBE_FAILED`, `MODEL_MISMATCH`, `RESPONSE_ENVELOPE`, `INVALID_RESPONSE_JSON`, `INVALID_MODEL_JSON`, `OUTPUT_TRUNCATED`, `MODEL_REFUSAL`.
- Documents/fields: `INVALID_INPUT`, `PDF_UNREADABLE`, `PDF_ENCRYPTED`, `OCR_REQUIRED`, `FIELD_SCHEMA`, `SOURCE_VALIDATION`.

Failures preserve previous workspace fields and their human-review requirement. They do not imply that previous fields belong to the newly attempted packet. Unreadable text pages block the OpenRouter route, including mixed text/scanned packets; this conservatively also flags blank pages.

## Tests
```sh
python -m unittest discover -s . -p 'test_*.py'
```
Tests exercise error categories, null/malformed responses, model mismatch, capability modes, secret-safe diagnostics, and actual subprocess timeout/cleanup. Mocked API tests are not live AI accuracy evidence. See `BENCHMARK_RESULTS.md` for the earlier extraction baseline and limitations.

## Scope
Fictional/redacted data only on this public prototype. One line item and one container per packet. Scanned-document accuracy, regulatory applicability and financial savings remain unvalidated. The bundled sample supports demonstration without AI; using Streamlit Cloud still requires Internet access.
