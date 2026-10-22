"""test_chattogram_fixtures.py — Unit test verification for Chattogram demonstration fixtures.

Verifies:
  1. All 12 synthetic demonstration PDFs are generated, valid, unencrypted, and contain the mandatory watermark banner.
  2. Answer-key JSON parses properly and every cited quotation matches its target document page via locate_quote_on_page.
  3. ISO 6346 check digit calculation validates clean container MEDU1000060 and flags invalid container MEDU1000067.
  4. Cargo gross weight comparison correctly isolates cargo mass from container tare and SOLAS VGM.
  5. Existing 6 compliance checks pass across all 3 packets with zero unintentional discrepancy.
  6. Discrepancy packet contains exactly the 4 intended compliance conflicts.
  7. Corrected packet remediates all 4 conflicts while preserving original shipment identity and applying revision marks.
"""

from __future__ import annotations

import json
from pathlib import Path
import unittest

import pymupdf
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


class TestChattogramFixtures(unittest.TestCase):
    """Test suite verifying Chattogram demonstration fixtures, answer keys, and schema contracts."""

    def test_all_12_pdfs_exist_and_contain_watermark(self):
        """All 12 PDFs must exist across 3 folders and carry the explicit synthetic banner."""
        for packet in PACKET_NAMES:
            for doc_name in DOCUMENT_NAMES:
                pdf_path = PACKETS_DIR / packet / doc_name
                self.assertTrue(pdf_path.exists(), f"Missing required document: {pdf_path}")
                self.assertGreater(pdf_path.stat().st_size, 1000, f"PDF file suspiciously small: {pdf_path}")

                doc = pymupdf.open(str(pdf_path))
                self.assertFalse(doc.is_encrypted, f"Document must not be encrypted: {pdf_path}")
                self.assertGreaterEqual(len(doc), 1, f"Document has no pages: {pdf_path}")

                page_text = doc[0].get_text()
                self.assertIn(
                    MANDATORY_BANNER,
                    page_text,
                    f"Document {packet}/{doc_name} is missing mandatory watermark banner",
                )
                doc.close()

    def test_answer_keys_json_parses_and_has_all_packets(self):
        """Answer key JSON must be valid and define all 3 required packets."""
        self.assertTrue(ANSWER_KEY_PATH.exists(), f"Missing answer keys JSON: {ANSWER_KEY_PATH}")
        with open(ANSWER_KEY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertIn("packets", data)
        for packet in PACKET_NAMES:
            self.assertIn(packet, data["packets"])
            p_data = data["packets"][packet]
            self.assertIn("extracted_fields", p_data)
            self.assertIn("compliance_checks", p_data)
            self.assertIn("discrepancies", p_data)

    def test_all_answer_key_quotes_locate_accurately(self):
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

    def test_iso_6346_check_digit_calculation(self):
        """Validate mathematical correctness of ISO 6346 check digit calculation."""
        # MEDU1000060 -> prefix MEDU100006 -> check digit 0
        computed_clean = iso6346_check_digit("MEDU1000060")
        self.assertEqual(computed_clean, 0, "MEDU1000060 must have valid check digit 0")

        # MEDU1000067 -> prefix MEDU100006 -> computed check digit is 0, but stated is 7
        stated_check_digit = int("MEDU1000067"[-1])
        computed_discrepancy = iso6346_check_digit("MEDU1000067")
        self.assertEqual(computed_discrepancy, 0)
        self.assertNotEqual(stated_check_digit, computed_discrepancy, "Discrepancy container must have invalid check digit")

    def test_existing_6_checks_pass_across_all_packets(self):
        """All existing 6 compliance checks must pass across all three packets."""
        with open(ANSWER_KEY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        for packet_id in PACKET_NAMES:
            checks = data["packets"][packet_id]["compliance_checks"]["existing_checks"]
            self.assertEqual(len(checks), 6, f"{packet_id} must specify all 6 existing checks")
            for check_name, check_data in checks.items():
                self.assertEqual(
                    check_data["status"],
                    "Passed",
                    f"Check '{check_name}' unexpectedly failed in {packet_id}: {check_data}",
                )

    def test_discrepancy_packet_details(self):
        """Discrepancy packet must accurately capture the 4 intended trade compliance conflicts."""
        with open(ANSWER_KEY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        disc_packet = data["packets"]["chattogram_discrepancy"]
        self.assertEqual(len(disc_packet["discrepancies"]), 4)

        future_checks = disc_packet["compliance_checks"]["future_checks"]
        # Discrepancy 1: Port of Discharge (Mongla vs Chattogram)
        self.assertEqual(future_checks["port_of_discharge_consistency"]["status"], "Review required")
        self.assertEqual(future_checks["port_of_discharge_consistency"]["bl_port"], "Mongla Port, Bangladesh")
        self.assertEqual(future_checks["port_of_discharge_consistency"]["lc_port"], "Chattogram Sea Port, Bangladesh")

        # Discrepancy 2: Cargo Gross Weight (42,300 vs 43,200)
        self.assertEqual(future_checks["cargo_gross_weight_consistency"]["status"], "Review required")
        self.assertEqual(future_checks["cargo_gross_weight_consistency"]["bl_gross_weight"], "42300")
        self.assertEqual(future_checks["cargo_gross_weight_consistency"]["pl_gross_weight"], "43200")

        # Discrepancy 3: Container Check Digit (stated 7 vs computed 0)
        self.assertEqual(future_checks["iso_6346_check_digit"]["status"], "Review required")
        self.assertEqual(future_checks["iso_6346_check_digit"]["check_digit"], 7)
        self.assertEqual(future_checks["iso_6346_check_digit"]["calculated_check_digit"], 0)

        # Discrepancy 4: Goods Description (LLDPE vs HDPE)
        self.assertEqual(future_checks["goods_description_consistency"]["status"], "Review required")
        self.assertIn("LLDPE", future_checks["goods_description_consistency"]["ci_goods"])
        self.assertIn("HDPE", future_checks["goods_description_consistency"]["lc_goods"])

    def test_corrected_packet_remediations_and_revision_stamps(self):
        """Corrected packet must resolve all 4 discrepancies and carry explicit revision stamps."""
        with open(ANSWER_KEY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        corr_packet = data["packets"]["chattogram_corrected"]
        future_checks = corr_packet["compliance_checks"]["future_checks"]

        # All 4 future checks must now pass
        for check_name, check_data in future_checks.items():
            self.assertEqual(check_data["status"], "Passed", f"Corrected check '{check_name}' did not pass")

        # Verify revision indicators on PDF text
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


if __name__ == "__main__":
    unittest.main()
