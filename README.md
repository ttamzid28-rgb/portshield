# PortShield AI — Summit prototype
Working rules-first document readiness demonstrator. AI extraction is planned, not enabled.

## Deploy on Streamlit Community Cloud
1. Create a GitHub repository named `portshield` and upload the contents of this folder to its root, including sample_documents.zip.
2. Sign in at https://share.streamlit.io/ and select Create app.
3. Select the repository, main branch and app.py entry point.
4. Deploy and copy the actual live URL after checking it.

## Run locally
pip install -r requirements.txt
streamlit run app.py

## Demo
Run checks on Problem shipment. Load Corrected shipment and run again: arithmetic, limit and identifier issues resolve while the shipment-date issue remains. Load Unreadable field to show an incomplete check. Download sample PDFs, upload them and run actual labelled-text extraction.

## Limitations
Fictional data only. Text-PDF extraction is deliberately limited to labelled sample layouts. No OCR or LLM is active. Six rules do not establish bank/customs compliance. Amount limit must be configured with applicable tolerance; partial shipment utilisation is unsupported. Human confirmation required. No savings or accuracy claim.
