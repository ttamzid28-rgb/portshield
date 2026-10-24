# Container identifier integrity — Check 3

Checks one Packing List identifier and one Bill of Lading identifier independently.
This prototype does not handle lists of containers; multiple identifiers in a field require review.
The existing cross-document equality rule remains separate.

## Contract

- Passed: both identifiers have valid format and check digits.
- Review required: a populated, confirmed identifier has invalid format/check digit.
- Insufficient data: either identifier is absent, pending, unresolved or edited since confirmation. Evidence still reports a known failure on the other document.
- With no field states, values are treated as supplied/manual demo input, matching existing audit compatibility. Extracted packets must pass their field states.
- ASCII case, whitespace and hyphens are presentation-normalized for this check only; source values and candidates remain unchanged. No OCR substitutions or automatic correction.
- Shape: three owner letters, U/J/Z equipment category, six serial digits and one check digit. J/Z are category-valid identifiers, not an assertion that they denote freight containers.
- Calculate over the first ten characters. Letters use values 10–38 skipping 11, 22, 33; digits retain their value. Multiply each by successive powers of two starting at 1, sum, take remainder modulo 11, map remainder 10 to digit 0.
- Reports show stated and calculated digits. A passing checksum does not establish registration, existence, ownership, customs acceptance or clearance readiness.

## References and review scope

- BIC identifier structure and purpose: https://www.bic-code.org/check-digit-calculator/
- ISO 6346:2022, corrected version August 2022, Annex A is the normative check-digit reference: https://www.iso.org/standard/83558.html
- Public ISO preview confirms corrected letter values; it does not expose the full Annex A: https://preview.sist.si/sist-preview/83558/4d7a119e475c4dce901481c70d3f8a1b/ISO-6346-2022.pdf

No claim of ISO certification or comprehensive standard compliance. Independent review against the full standard remains appropriate before commercial release.

## Verification / Gemini handoff

Run `python -m unittest discover -s . -p 'test_*.py'`.
Review same-invalid-number equality bypass, different valid identifiers, remainder 10 to 0, malformed and Unicode inputs, presentation normalization, missing/pending/stale review, and preserved source candidates after manual correction.
Fixture expectations: clean/corrected pass; discrepancy states 7 versus calculated 0.
Streamlit review submission, correction guidance and report rendering were smoke-tested with AppTest.
The extraction pipeline and field lifecycle implementation are unchanged.
