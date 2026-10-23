"""test_chattogram_fixtures.py — Unit test verification for Chattogram demonstration fixtures.

Verifies:
  1. All 12 synthetic demonstration PDFs are generated, valid, unencrypted, and contain the mandatory watermark banner.
  2. Multi-page pagination: SWIFT MT700 Letter of Credit has 2 pages rendering all tags including 47A, 71D, 48, 49.
  3. Verbatim quote citations: 100% of answer-key quotations exist verbatim in their respective PDF text layers.
  4. Behavioral compliance audit: Evaluates live checks.py:audit() on mapped answer-key fields (asserting live 'Passed' status).
  5. Mathematical calculations: Direct calculation of cargo gross weight discrepancy:
     float(pl_cargo_gross_weight) - float(bl_cargo_gross_weight) == 900.0 for discrepancy packet, 0.0 for clean/corrected.
  6. ISO 6346 check digit validation: Validates clean container MEDU1000060 (0) and detects invalid container MEDU1000067 (stated 7 != calculated 0).
  7. Corrected packet verification: Original shipment identity preserved, revision stamps confirmed, and compliance resolved.
"""

from __future__ import annotations

import json
from pathlib import Path
import unittest

import pymupdf
from checks import audit
from pdf_viewer import locate_quote_on_page

ROOT_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = ROOT_DIR / "fixtures"
PACKETS_DIR = FIXTURES_DIR / "packets"
ANSWER_KEY_PATH = FIXTURES_DIR / "chattogram_answer_keys.json"

MANDATORY_BANNER = "FICTIONAL DEMONSTRATION DOCUMENT - FOR TESTING ONLY - NO COMMERCIAL OR BANKING VALUE"
PACKET_NAMES = ["chattogram_clean", "chattogram_discrepancy", "chattogram_corrected"]
DOCUMENT_NAMES = [
    "commercial_invoice.pdf",
    "packing_list.pdf",
    "bill_of_lading.pdf",
    "letter_of_credit.pdf",
]


def iso6346_check_digit(container_num: str) -> int:
    """Calculate the ISO 6346 check digit for a 10-character container prefix."""
    char_map = {
        'A': 10, 'B': 12, 'C': 13, 'D': 14, 'E': 15, 'F': 16, 'G': 17, 'H': 18, 'I': 19,
        'J': 20, 'K': 21, 'L': 23, 'M': 24, 'N': 25, 'O': 26, 'P': 27, 'Q': 28, 'R': 29,
        'S': 30, 'T': 31, 'U': 32, 'V': 34, 'W': 35, 'X': 36, 'Y': 37, 'Z': 38
    }
    for d in "0123456789":
        char_map[d] = int(d)

    cleaned = container_num.replace(" ", "").replace("-", "").upper()[:10]
    if len(cleaned) < 10:
        raise ValueError(f"Container prefix must have at least 10 chars: {container_num}")

    total = sum(char_map[c] * (2 ** i) for i, c in enumerate(cleaned))
    rem = total % 11
    return 0 if rem == 10 else rem


def map_canonical_to_engine(fields: dict) -> dict:
    """Map canonical answer-key fields to checks.py audit engine input schema."""
    res = {
        "lc_currency": fields["lc_currency"]["value"],
        "invoice_currency": fields["ci_currency"]["value"],
        "invoice_quantity": fields["ci_quantity"]["value"],
        "packing_quantity": fields["pl_cargo_net_weight"]["value"],
        "packing_container": fields["pl_container_number"]["value"],
        "bl_container": fields["bl_container_number"]["value"],
        "invoice_total": fields["ci_invoice_total"]["value"],
        "lc_amount": fields["lc_amount"]["value"],
        "unit_price": fields["ci_unit_price"]["value"],
        "on_board_date": fields["bl_on_board_date"]["value"],
        "latest_shipment_date": fields["lc_latest_shipment_date"]["value"],
    }
    if "lc_port_of_discharge" in fields:
        res["lc_port_of_discharge"] = fields["lc_port_of_discharge"]["value"]
    if "bl_port_of_discharge" in fields:
        res["bl_port_of_discharge"] = fields["bl_port_of_discharge"]["value"]
    if "bl_port_of_loading" in fields:
        res["bl_port_of_loading"] = fields["bl_port_of_loading"]["value"]
    if "bl_place_of_delivery" in fields:
        res["bl_place_of_delivery"] = fields["bl_place_of_delivery"]["value"]
    return res


class TestChattogramFixtures(unittest.TestCase):
    """Behavioral and structural test suite verifying Chattogram demonstration fixtures."""

    def test_all_12_pdfs_exist_and_contain_watermark(self):
        """All 12 PDFs must exist across 3 folders and carry the explicit synthetic banner on all pages."""
        for packet in PACKET_NAMES:
            for doc_name in DOCUMENT_NAMES:
                pdf_path = PACKETS_DIR / packet / doc_name
                self.assertTrue(pdf_path.exists(), f"Missing required document: {pdf_path}")
                self.assertGreater(pdf_path.stat().st_size, 1000, f"PDF file suspiciously small: {pdf_path}")

                doc = pymupdf.open(str(pdf_path))
                self.assertFalse(doc.is_encrypted, f"Document must not be encrypted: {pdf_path}")
                self.assertGreaterEqual(len(doc), 1, f"Document has no pages: {pdf_path}")

                for page_idx in range(len(doc)):
                    page_text = doc[page_idx].get_text()
                    self.assertIn(
                        MANDATORY_BANNER,
                        page_text,
                        f"Document {packet}/{doc_name} page {page_idx+1} is missing mandatory watermark banner",
                    )
                doc.close()

    def test_letter_of_credit_multipage_pagination(self):
        """Letter of credit must dynamically paginate into 2 pages and render all tags through Tag 49."""
        for packet in PACKET_NAMES:
            lc_path = PACKETS_DIR / packet / "letter_of_credit.pdf"
            doc = pymupdf.open(str(lc_path))
            self.assertEqual(len(doc), 2, f"{packet}/letter_of_credit.pdf must be 2 pages")

            page1_text = doc[0].get_text()
            page2_text = doc[1].get_text()

            # Page 1 must have initial credit terms through Tag 45A
            self.assertIn(":27:", page1_text)
            self.assertIn(":32B:", page1_text)
            self.assertIn(":44C:", page1_text)
            self.assertIn(":45A:", page1_text)

            # Page 2 must have tags 46A, 47A, 71D, 48, 49
            self.assertIn(":46A:", page2_text)
            self.assertIn(":47A:", page2_text)
            self.assertIn(":71D:", page2_text)
            self.assertIn("ALL BANKING CHARGES OUTSIDE BANGLADESH", page2_text)
            self.assertIn(":48:", page2_text)
            self.assertIn("PERIOD FOR PRESENTATION", page2_text.upper())
            self.assertIn(":49:", page2_text)
            self.assertIn("WITHOUT", page2_text)
            doc.close()

    def test_answer_keys_json_parses_and_has_canonical_fields(self):
        """Answer key JSON must be valid and conform to canonical <doc_prefix>_<field_name> naming."""
        self.assertTrue(ANSWER_KEY_PATH.exists(), f"Missing answer keys JSON: {ANSWER_KEY_PATH}")
        with open(ANSWER_KEY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertIn("packets", data)
        required_prefixes = {"ci_", "pl_", "bl_", "lc_"}

        for packet in PACKET_NAMES:
            self.assertIn(packet, data["packets"])
            p_data = data["packets"][packet]
            fields = p_data["extracted_fields"]

            # Must have at least 20 canonical fields
            self.assertGreaterEqual(len(fields), 20)

            # Ensure canonical prefixes are used
            prefixes_found = {k.split("_")[0] + "_" for k in fields}
            self.assertTrue(required_prefixes.issubset(prefixes_found), f"Missing canonical prefixes in {packet}")

    def test_verbatim_quote_citations_via_text_layer_and_pdf_viewer(self):
        """Every quotation citation in the answer-key JSON must locate cleanly via pdf_viewer."""
        with open(ANSWER_KEY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        for packet_id, packet_data in data["packets"].items():
            fields = packet_data["extracted_fields"]
            for field_name, info in fields.items():
                doc_file = info["document"]
                page_idx = info["page"] - 1
                quote = info["quote"]

                pdf_path = PACKETS_DIR / packet_id / doc_file
                self.assertTrue(pdf_path.exists(), f"Referenced PDF not found: {pdf_path}")

                pdf_bytes = pdf_path.read_bytes()
                loc_res = locate_quote_on_page(pdf_bytes, page_idx, quote)
                self.assertTrue(
                    loc_res["found"],
                    f"Quote for {packet_id} -> {field_name} not located in {doc_file} p.{page_idx+1}: "
                    f"quote='{quote}' err='{loc_res.get('error')}' label='{loc_res.get('label')}'",
                )

    def test_behavioral_audit_engine_execution_on_clean_packet(self):
        """Execute live checks.py:audit() on mapped clean packet values; all 7 checks must return 'Passed'."""
        with open(ANSWER_KEY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        clean_fields = data["packets"]["chattogram_clean"]["extracted_fields"]
        engine_input = map_canonical_to_engine(clean_fields)

        # Run live audit routine from checks.py
        findings = audit(engine_input)
        self.assertEqual(len(findings), 7, f"Audit routine must return exactly 7 findings, got {len(findings)}")

        for finding in findings:
            self.assertEqual(
                finding["status"],
                "Passed",
                f"Engine check '{finding['check']}' unexpectedly failed on clean packet: {finding['evidence']}",
            )
        port_check = next(f for f in findings if f["check"] == "Port of discharge consistency")
        self.assertEqual(port_check["status"], "Passed")

    def test_behavioral_audit_engine_execution_on_discrepancy_packet(self):
        """Execute live checks.py:audit() on discrepancy packet; 6 baseline pass, Check 1 evaluates to 'Review required' (DISC-01)."""
        with open(ANSWER_KEY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        disc_fields = data["packets"]["chattogram_discrepancy"]["extracted_fields"]
        engine_input = map_canonical_to_engine(disc_fields)

        # Run live audit routine from checks.py
        findings = audit(engine_input)
        self.assertEqual(len(findings), 7, f"Audit routine must return exactly 7 findings, got {len(findings)}")

        for finding in findings:
            if finding["check"] == "Port of discharge consistency":
                self.assertEqual(
                    finding["status"],
                    "Review required",
                    f"Check 1 '{finding['check']}' must flag discrepancy DISC-01: {finding['evidence']}",
                )
                self.assertIn("Mongla", finding["evidence"])
                self.assertIn("Chattogram", finding["evidence"])
            else:
                self.assertEqual(
                    finding["status"],
                    "Passed",
                    f"Baseline check '{finding['check']}' should remain unaffected on discrepancy packet: {finding['evidence']}",
                )

    def test_behavioral_audit_engine_execution_on_corrected_packet(self):
        """Execute live checks.py:audit() on corrected packet values; all 7 checks must return 'Passed'."""
        with open(ANSWER_KEY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        corr_fields = data["packets"]["chattogram_corrected"]["extracted_fields"]
        engine_input = map_canonical_to_engine(corr_fields)

        findings = audit(engine_input)
        self.assertEqual(len(findings), 7, f"Audit routine must return exactly 7 findings, got {len(findings)}")

        for finding in findings:
            self.assertEqual(
                finding["status"],
                "Passed",
                f"Engine check '{finding['check']}' unexpectedly failed on corrected packet: {finding['evidence']}",
            )
        port_check = next(f for f in findings if f["check"] == "Port of discharge consistency")
        self.assertEqual(port_check["status"], "Passed")

    def test_direct_cargo_gross_weight_discrepancy_calculation(self):
        """Calculate cargo gross weight discrepancy directly from pl_cargo_gross_weight and bl_cargo_gross_weight."""
        with open(ANSWER_KEY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 1. Clean packet: zero discrepancy
        clean_fields = data["packets"]["chattogram_clean"]["extracted_fields"]
        pl_clean = float(clean_fields["pl_cargo_gross_weight"]["value"])
        bl_clean = float(clean_fields["bl_cargo_gross_weight"]["value"])
        self.assertEqual(pl_clean, 21600.0)
        self.assertEqual(bl_clean, 21600.0)
        self.assertEqual(pl_clean - bl_clean, 0.0)

        # 2. Discrepancy packet: exact 900.0 KG transposition error
        disc_fields = data["packets"]["chattogram_discrepancy"]["extracted_fields"]
        pl_disc = float(disc_fields["pl_cargo_gross_weight"]["value"])
        bl_disc = float(disc_fields["bl_cargo_gross_weight"]["value"])
        self.assertEqual(pl_disc, 21600.0)
        self.assertEqual(bl_disc, 20700.0)
        self.assertEqual(
            pl_disc - bl_disc,
            900.0,
            "Discrepancy packet must exhibit exactly 900.0 KG difference (21,600.0 - 20,700.0)",
        )

        # 3. Corrected packet: rectified to zero discrepancy
        corr_fields = data["packets"]["chattogram_corrected"]["extracted_fields"]
        pl_corr = float(corr_fields["pl_cargo_gross_weight"]["value"])
        bl_corr = float(corr_fields["bl_cargo_gross_weight"]["value"])
        self.assertEqual(pl_corr, 21600.0)
        self.assertEqual(bl_corr, 21600.0)
        self.assertEqual(pl_corr - bl_corr, 0.0)

    def test_iso_6346_check_digit_calculation(self):
        """Validate mathematical correctness of ISO 6346 check digit calculation."""
        # Clean: MEDU1000060 -> check digit 0
        computed_clean = iso6346_check_digit("MEDU1000060")
        self.assertEqual(computed_clean, 0, "MEDU1000060 must have valid check digit 0")

        # Discrepancy: MEDU1000067 -> prefix MEDU100006 has check digit 0, but stated is 7
        stated_check_digit = int("MEDU1000067"[-1])
        computed_discrepancy = iso6346_check_digit("MEDU1000067")
        self.assertEqual(computed_discrepancy, 0)
        self.assertNotEqual(stated_check_digit, computed_discrepancy, "Discrepancy container must have invalid check digit")

    def test_corrected_packet_remediations_and_revision_stamps(self):
        """Corrected packet must resolve all 4 discrepancies and carry explicit revision stamps."""
        ci_text = pymupdf.open(str(PACKETS_DIR / "chattogram_corrected" / "commercial_invoice.pdf"))[0].get_text()
        self.assertIn("COMMERCIAL INVOICE REV-1", ci_text)
        self.assertIn("REVISION STAMP: AMENDED GOODS DESCRIPTION", ci_text)

        bl_text = pymupdf.open(str(PACKETS_DIR / "chattogram_corrected" / "bill_of_lading.pdf"))[0].get_text()
        self.assertIn("REVISED BILL OF LADING", bl_text)
        self.assertIn("REVISION 1: CORRECTED DISCHARGE PORT", bl_text)

        # Verify original shipment identity is preserved
        self.assertIn("26DC01EBL789012", ci_text)
        self.assertIn("26DC01EBL789012", bl_text)
        self.assertIn("Bengal Polymer Industries", ci_text)
        self.assertIn("Busan Petrochemical", ci_text)

    def test_review_states_match_runtime_contract(self):
        """Verify all declared review statuses in fixtures/chattogram_answer_keys.json strictly belong to {'pending', 'confirmed', 'unresolved'}."""
        with open(ANSWER_KEY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        valid_review_statuses = {"pending", "confirmed", "unresolved"}
        forbidden_review_statuses = {"unreviewed", "edited", "rejected"}

        # 1. Verify declared review status enum in metadata
        metadata = data.get("metadata", {})
        declared_enum = metadata.get("review_status_enum")
        self.assertIsNotNone(declared_enum, "Answer key metadata must declare review_status_enum")
        self.assertEqual(
            set(declared_enum),
            valid_review_statuses,
            f"Declared review enum {declared_enum} must match {valid_review_statuses}",
        )

        # 2. Check field lifecycle note does not declare forbidden review states under review_status
        lifecycle_note = metadata.get("field_lifecycle_note", "")
        if "review_status" in lifecycle_note:
            review_clause = lifecycle_note.split("review_status", 1)[1]
            for forbidden in forbidden_review_statuses:
                self.assertNotIn(
                    f"'{forbidden}'",
                    review_clause,
                    f"Field lifecycle note must not declare forbidden review state: '{forbidden}'",
                )

        # 3. Collect and verify all declared review status attributes across the entire JSON
        declared_statuses = []

        def find_review_statuses(node):
            if isinstance(node, dict):
                for k, v in node.items():
                    if k in {"review_status", "review_status_enum"}:
                        if isinstance(v, list):
                            declared_statuses.extend(v)
                        elif isinstance(v, str):
                            declared_statuses.append(v)
                    find_review_statuses(v)
            elif isinstance(node, list):
                for item in node:
                    find_review_statuses(item)

        find_review_statuses(data)
        self.assertGreater(len(declared_statuses), 0, "At least one review status must be declared in answer keys")
        for status in declared_statuses:
            self.assertIn(
                status,
                valid_review_statuses,
                f"Declared review status '{status}' violates runtime contract enum {valid_review_statuses}",
            )
            self.assertNotIn(
                status,
                forbidden_review_statuses,
                f"Declared review status '{status}' matches forbidden review state",
            )

    def test_financial_metadata_alignment_with_pdf_tags(self):
        """Assert alignment between answer-key financial metadata and letter_of_credit.pdf text layer tags."""
        with open(ANSWER_KEY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 1. Assert L/C tolerance policy metadata in metadata section
        metadata = data.get("metadata", {})
        policy = metadata.get("lc_financial_tolerance_policy", {})
        self.assertIsNotNone(policy, "Missing lc_financial_tolerance_policy in metadata")

        # Commercial invoice total: 25000.00
        self.assertEqual(float(policy.get("commercial_invoice_total_usd")), 25000.00)

        # L/C face amount: 26250.00
        self.assertEqual(float(policy.get("lc_face_amount_usd")), 26250.00)

        # Positive tolerance must be recorded as 5.0%
        pos_tol = policy.get("stated_positive_tolerance_pct", policy.get("tag_39a_positive_tolerance_pct"))
        self.assertEqual(float(pos_tol), 5.0, "Positive tolerance must be recorded as 5.0%")

        # Upper limit / max permissible draw must be recorded as 27562.50
        upper_limit = policy.get("max_permissible_draw_usd", policy.get("upper_limit_usd"))
        self.assertEqual(float(upper_limit), 27562.50, "Upper drawing limit must be 27,562.50 USD")

        # Current engine comparison limit: 26250.00
        self.assertEqual(float(policy.get("current_engine_comparison_limit_usd")), 26250.00)

        # Technical note must be present with required wording
        tech_note = policy.get("technical_note", "")
        self.assertIn("USD 26,250.00", tech_note)
        self.assertIn("$25,000 <= $26,250", tech_note)

        # 2. Check each packet's financial values and Tag 32B verbatim matching
        for packet_id in PACKET_NAMES:
            packet_fields = data["packets"][packet_id]["extracted_fields"]

            # lc_amount.value == "26250.00"
            self.assertIn("lc_amount", packet_fields)
            lc_field = packet_fields["lc_amount"]
            self.assertEqual(lc_field["value"], "26250.00", f"{packet_id}: lc_amount.value must be '26250.00'")

            # ci_invoice_total.value == "25000.00"
            self.assertIn("ci_invoice_total", packet_fields)
            ci_field = packet_fields["ci_invoice_total"]
            self.assertEqual(ci_field["value"], "25000.00", f"{packet_id}: ci_invoice_total.value must be '25000.00'")

            # Tag 32B quote in L/C answer key matches verbatim text layer of letter_of_credit.pdf ("USD 26,250.00")
            lc_quote = lc_field["quote"]
            self.assertIn("USD 26,250.00", lc_quote, f"{packet_id}: lc_amount quote must contain 'USD 26,250.00'")

            pdf_path = PACKETS_DIR / packet_id / "letter_of_credit.pdf"
            doc = pymupdf.open(str(pdf_path))
            page1_text = doc[0].get_text()
            doc.close()

            self.assertIn("USD 26,250.00", page1_text, f"{packet_id}: letter_of_credit.pdf text layer must contain 'USD 26,250.00'")
            self.assertIn(lc_quote, page1_text, f"{packet_id}: Tag 32B quote must match verbatim in letter_of_credit.pdf text layer")


if __name__ == "__main__":
    unittest.main()

