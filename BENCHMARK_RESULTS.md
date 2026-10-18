# Extraction validation status — v0.7

## Changes
- Preserve PDF text layout for OpenRouter inputs.
- Explicit field-source instructions distinguish goods quantities from package counts and container numbers from packaging descriptions.
- Validate quoted numeric values, currency codes, container identifier format and date syntax before accepting fields.
- Check quotations against available PDF page text for either provider.
- Omit malformed individual entries without discarding otherwise valid sourced fields; expose rejection reasons for review.

## Verification
- Eight validation regression tests pass (`python -m unittest discover -s . -p 'test_extraction_validation.py'`).
- A local mocked provider test exercised the complete extraction parser: 11 source-backed fields accepted, string page/document indexes normalized and a malformed entry omitted. This is not an AI accuracy result.
- 75 source-backed development-case values passed quote and value guards. This is not an AI accuracy result.
- Streamlit v0.7 was observed live.
- Earlier v0.6 PSB-01 live baseline: 8/11 fields correct, 23.36 seconds. Packing quantity was 720 instead of 18000; packing container was packaging text; B/L container was absent.
- Initial v0.7 live attempt failed field-schema validation. Parser robustness was subsequently patched. The subsequent live request stalled during verification; no post-change accuracy score is established.

## Limits and next gate
Synthetic packets are engineering fixtures, not expert validation or real-world accuracy evidence. The model selected by the free router can vary. Passing format/source guards does not establish correct semantic field assignment, unit consistency or regulatory compliance. Date validation currently checks syntax, not equivalence to the cited date. Scanned-PDF accuracy remains unmeasured.

Next gate: complete repeated live development tests, record accepted/incorrect/missing fields and provider model, then evaluate untouched holdout cases before claiming an accuracy improvement. Require human verification of extracted fields.
