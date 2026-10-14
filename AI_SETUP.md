# Activate AI extraction

1. Create a Gemini API key at https://aistudio.google.com/apikey using a free-tier project without paid billing.
2. Open your Streamlit Community Cloud app settings, then Secrets. Add:

```toml
GEMINI_API_KEY = "your-key-here"
```

Never commit the real key to GitHub. Save secrets and reload the app.

3. Download and unzip the sample packet from the sidebar. Upload the four PDFs in Document intake.
4. Confirm the data-sharing checkbox and click Extract with AI.
5. Review all fields and AI-cited source pages. Confirm values, then Run document checks.

## Scope

Uses Gemini 3.8 Flash generateContent with inline PDF input and structured JSON output. Maximum four PDFs, 8 MB total and 30 pages. One line item and one container only. Unknown fields remain blank. Conflicting returned values are blocked. Page references are range-checked, but quotes and values still require human verification. Face L/C amount is not a tolerance-adjusted or remaining credit amount.

Google controls free-tier access and quotas. This code does not enable billing or switch to paid providers. A billing-enabled key can incur charges. Free-tier content may be used to improve Google products: use fictional or redacted demo documents.

Local Streamlit and mocked-response tests passed. Real provider extraction and accuracy benchmarking remain pending until an API key is configured. No accuracy percentage or complete banking compliance is claimed.

Google limits access to legacy 2.5 models for new projects and recommends 3.8 Flash. If the API returns a country-level free-tier error, changing the model cannot fix regional eligibility.

## OpenRouter free-model alternative

Create an API key at https://openrouter.ai/keys and add `OPENROUTER_API_KEY = "your-key-here"` to Streamlit Secrets. Select **OpenRouter (free models, text PDFs)** in Document intake. This route extracts text locally from uploaded PDFs, sends page-labelled text to OpenRouter's `openrouter/free` model router, and accepts a returned field only when its cited quote occurs on the stated page. Scanned PDFs need Gemini or a future OCR pipeline. Free models may be slow or unavailable and output quality varies. The app never selects OpenRouter paid models or paid OCR plugins. Do not upload confidential trade documents to this public demo.
