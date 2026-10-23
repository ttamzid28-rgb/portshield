"""test_checks.py — Unit test verification for checks.py including Check 1 (Port of Discharge Consistency).

Verifies:
  1. Equivalent aliases: Chattogram cluster (Chattogram, Chittagong, BDCGP) and Mongla cluster (Mongla, Chalna, BDMGL) -> Passed.
  2. Discrepancy detection: Chattogram vs Mongla -> Review required, strictly documentary phrasing.
  3. Contradictory country & multi-location: e.g. "Chattogram, Malaysia", "Chattogram / Singapore" -> Review required.
  4. Unknown port authority / UN/LOCODE: e.g., 'Atlantis Port' -> Review required.
  5. Missing, unreadable, conflicting, or unconfirmed field states -> Insufficient data.
  6. Field disentanglement: Place of Delivery (Dhaka) and Port of Loading (Busan) never cross-match or confound the discharge port check.
  7. Strict review contract: review_status="pending" cannot pass; human correction of missing field is usable and evaluates to Passed.
  8. Plain string status equality: No wrapper class anomalies.
  9. Quotation role boundaries: B/L Loading section rejected as evidence for Port of Discharge (unit test + PDF-backed synthetic fixture).
 10. Audit pipeline integration: All 7 deterministic checks executed.
"""

from __future__ import annotations

import unittest
import pymupdf
from decimal import Decimal
from checks import (
    audit,
    check_port_of_discharge,
    check_cargo_gross_weight,
    resolve_canonical_port,
    normalize_port_name,
)
from extraction_validation import validate_value
from field_states import collect_fields, review_fields


class TestPortOfDischargeConsistency(unittest.TestCase):
    """Unit tests for deterministic Port of Discharge check."""

    def test_normalize_port_name(self):
        self.assertEqual(normalize_port_name("  Chattogram Sea Port, Bangladesh  "), "chattogram sea port bangladesh")
        self.assertEqual(normalize_port_name("Port of Mongla/Chalna"), "port of mongla chalna")
        self.assertEqual(normalize_port_name(""), "")

    def test_canonical_resolution_chattogram_cluster(self):
        for raw in [
            "Chattogram",
            "chittagong",
            "Chattogram Sea Port",
            "port of chattogram",
            "PORT OF CHITTAGONG",
            "bdcgp",
            "BDCGP / Chattogram",
            "Chattogram Sea Port, Bangladesh",
            "Chittagong, Bangladesh",
        ]:
            with self.subTest(raw=raw):
                canon, _ = resolve_canonical_port(raw)
                self.assertEqual(canon, "BDCGP / Chattogram")

    def test_canonical_resolution_mongla_cluster(self):
        for raw in [
            "Mongla",
            "mongla port",
            "Port of Mongla",
            "chalna",
            "Chalna Port",
            "bdmgl",
            "BDMGL / Mongla",
            "Mongla Port, Bangladesh",
        ]:
            with self.subTest(raw=raw):
                canon, _ = resolve_canonical_port(raw)
                self.assertEqual(canon, "BDMGL / Mongla")

    def test_equivalent_aliases_evaluation_passed(self):
        pairs = [
            ("Chattogram Sea Port", "Chittagong"),
            ("Chattogram", "BDCGP"),
            ("Port of Chattogram", "Chattogram Sea Port, Bangladesh"),
            ("Mongla Port", "Chalna"),
            ("Mongla", "BDMGL"),
            ("Port of Mongla", "Mongla Port, Bangladesh"),
        ]
        for lc, bl in pairs:
            with self.subTest(lc=lc, bl=bl):
                res = check_port_of_discharge({"lc_port_of_discharge": lc, "bl_port_of_discharge": bl})
                self.assertEqual(res["status"], "Passed")
                self.assertIn("harmonized", res["evidence"].lower())

    def test_mismatch_evaluates_to_review_required(self):
        res = check_port_of_discharge({
            "lc_port_of_discharge": "Chattogram Sea Port, Bangladesh",
            "bl_port_of_discharge": "Mongla Port, Bangladesh",
        })
        self.assertEqual(res["status"], "Review required")
        # Assert strictly documentary trade discrepancy phrasing
        self.assertIn("Discrepancy: Bill of Lading states Port of Discharge as 'Mongla Port, Bangladesh'", res["evidence"])
        self.assertIn("Letter of Credit Field 44F stipulates 'Chattogram Sea Port, Bangladesh'", res["evidence"])
        # Ensure no speculative customs or penalty claims
        self.assertNotIn("red-channel", res["evidence"].lower())
        self.assertNotIn("demurrage", res["evidence"].lower())
        self.assertNotIn("fine", res["evidence"].lower())

    def test_contradictory_country_requires_review(self):
        """Contradictory country binding (Chattogram, Malaysia) and multi-location (Chattogram / Singapore) yield Review required."""
        # 1. Contradictory country: "Chattogram, Malaysia"
        canon1, _ = resolve_canonical_port("Chattogram, Malaysia")
        self.assertIsNone(canon1, "Chattogram, Malaysia must not resolve to Chattogram")
        res1 = check_port_of_discharge({
            "lc_port_of_discharge": "Chattogram Sea Port, Bangladesh",
            "bl_port_of_discharge": "Chattogram, Malaysia",
        })
        self.assertEqual(res1["status"], "Review required")
        self.assertIn("Chattogram, Malaysia", res1["evidence"])

        # 2. Conflicting multi-location: "Chattogram / Singapore"
        canon2, _ = resolve_canonical_port("Chattogram / Singapore")
        self.assertIsNone(canon2, "Chattogram / Singapore must not resolve to a single port")
        res2 = check_port_of_discharge({
            "lc_port_of_discharge": "Chattogram Sea Port, Bangladesh",
            "bl_port_of_discharge": "Chattogram / Singapore",
        })
        self.assertEqual(res2["status"], "Review required")
        self.assertIn("Chattogram / Singapore", res2["evidence"])

        # 3. Contradictory country on L/C side
        canon3, _ = resolve_canonical_port("Chittagong, India")
        self.assertIsNone(canon3, "Chittagong, India must not resolve to Chattogram")
        res3 = check_port_of_discharge({
            "lc_port_of_discharge": "Chittagong, India",
            "bl_port_of_discharge": "Chattogram Sea Port, Bangladesh",
        })
        self.assertEqual(res3["status"], "Review required")

    def test_unknown_port_evaluates_to_review_required(self):
        res = check_port_of_discharge({
            "lc_port_of_discharge": "Chattogram Sea Port",
            "bl_port_of_discharge": "Atlantis Port",
        })
        self.assertEqual(res["status"], "Review required")
        self.assertIn("Discrepancy: Bill of Lading states Port of Discharge as 'Atlantis Port'", res["evidence"])

    def test_missing_fields_evaluate_to_insufficient_data(self):
        # Missing B/L port
        res1 = check_port_of_discharge({"lc_port_of_discharge": "Chattogram Sea Port"})
        self.assertEqual(res1["status"], "Insufficient data")

        # Missing L/C port
        res2 = check_port_of_discharge({"bl_port_of_discharge": "Chattogram Sea Port"})
        self.assertEqual(res2["status"], "Insufficient data")

        # Empty strings
        res3 = check_port_of_discharge({"lc_port_of_discharge": "", "bl_port_of_discharge": "   "})
        self.assertEqual(res3["status"], "Insufficient data")

    def test_status_string_equality(self):
        """Confirm plain string equality and set membership work predictably without CheckStatus wrapper."""
        res = check_port_of_discharge({"lc_port_of_discharge": "Chattogram Sea Port"})
        self.assertEqual(res["status"], "Insufficient data")
        self.assertIs(type(res["status"]), str)
        self.assertNotEqual(res["status"], "Incomplete")
        self.assertIn(res["status"], {"Insufficient data", "Incomplete", "Passed", "Review required"})

    def test_pending_review_cannot_pass(self):
        """review_status='pending' even with status='confirmed' must NOT pass audit."""
        d = {
            "lc_port_of_discharge": "Chattogram Sea Port",
            "bl_port_of_discharge": "Chattogram Sea Port",
        }
        # Payload where extraction status claims 'confirmed' but review_status is 'pending'
        states = {
            "lc_port_of_discharge": {"status": "confirmed", "review_status": "pending", "reviewed_value": "Chattogram Sea Port"},
            "bl_port_of_discharge": {"status": "confirmed", "review_status": "confirmed", "reviewed_value": "Chattogram Sea Port"},
        }
        res = check_port_of_discharge(d, states)
        self.assertEqual(res["status"], "Insufficient data")

        # Full audit pipeline test
        full_input = {
            "lc_currency": "USD", "invoice_currency": "USD",
            "invoice_quantity": "100", "packing_quantity": "100",
            "packing_container": "MEDU1000060", "bl_container": "MEDU1000060",
            "invoice_total": "25000", "lc_amount": "25000",
            "unit_price": "250", "on_board_date": "2026-11-10",
            "latest_shipment_date": "2026-11-15",
            "lc_port_of_discharge": "Chattogram Sea Port",
            "bl_port_of_discharge": "Chattogram Sea Port",
        }
        full_states = {k: {"status": "extracted", "review_status": "confirmed", "reviewed_value": v} for k, v in full_input.items()}
        full_states["lc_port_of_discharge"]["review_status"] = "pending"
        full_states["lc_port_of_discharge"]["status"] = "confirmed"

        findings = audit(full_input, full_states)
        port_finding = next(f for f in findings if f["check"] == "Port of discharge consistency")
        self.assertEqual(port_finding["status"], "Insufficient data")

    def test_missing_field_human_correction_passes(self):
        """Initially missing or unreadable port field, subsequently human-confirmed, evaluates to Passed."""
        initial_states = {
            "lc_port_of_discharge": {
                "status": "missing",
                "reason": "No value returned; source absence is not established.",
                "candidates": [],
                "review_status": "pending",
            },
            "bl_port_of_discharge": {
                "status": "extracted",
                "reason": "Source-linked candidate",
                "candidates": [{"value": "Chattogram Sea Port", "status": "extracted"}],
                "review_status": "pending",
            },
        }

        user_entered_values = {
            "lc_port_of_discharge": "Chattogram Sea Port, Bangladesh",
            "bl_port_of_discharge": "Chattogram Sea Port, Bangladesh",
        }
        reviewed = review_fields(user_entered_values, initial_states)

        # Verify extraction status 'missing' is preserved for audit history
        self.assertEqual(reviewed["lc_port_of_discharge"]["status"], "missing")
        self.assertEqual(reviewed["lc_port_of_discharge"]["review_status"], "confirmed")
        self.assertEqual(reviewed["lc_port_of_discharge"]["reviewed_value"], "Chattogram Sea Port, Bangladesh")

        # Audit evaluation must use the confirmed value and return Passed
        res = check_port_of_discharge(user_entered_values, reviewed)
        self.assertEqual(res["status"], "Passed")
        self.assertIn("harmonized", res["evidence"].lower())

    def test_place_of_delivery_distinction(self):
        """B/L Port of Discharge = Chattogram, Place of Delivery = Dhaka -> Dhaka does not cause false mismatch."""
        d = {
            "lc_port_of_discharge": "Chattogram Sea Port, Bangladesh",
            "bl_port_of_discharge": "Chattogram Sea Port, Bangladesh",
            "bl_place_of_delivery": "Dhaka, Bangladesh",
        }
        res = check_port_of_discharge(d)
        self.assertEqual(res["status"], "Passed")

    def test_port_of_loading_distinction(self):
        """B/L Port of Discharge = Chattogram, Port of Loading = Busan -> Busan does not interfere."""
        d = {
            "lc_port_of_discharge": "Chattogram Sea Port, Bangladesh",
            "bl_port_of_discharge": "Chattogram Sea Port, Bangladesh",
            "bl_port_of_loading": "Busan, South Korea",
        }
        res = check_port_of_discharge(d)
        self.assertEqual(res["status"], "Passed")

    def test_quotation_mismatch_rejection_in_validator(self):
        # Mismatched candidate text not in quote
        val, err = validate_value(
            "lc_port_of_discharge",
            "Mongla Port",
            "44F: Port of Discharge: Chattogram Sea Port, Bangladesh",
        )
        self.assertFalse(val)
        self.assertIn("absent from or not contained", err)

        # Matched candidate text in quote
        val, err = validate_value(
            "lc_port_of_discharge",
            "Chattogram Sea Port",
            "44F: Port of Discharge: Chattogram Sea Port, Bangladesh",
        )
        self.assertEqual(val, "Chattogram Sea Port")
        self.assertEqual(err, "")

    def test_wrong_role_quotation_rejected(self):
        """B/L with Loading: Chattogram, Discharge: Mongla. Reject Chattogram as discharge port evidence."""
        # Case 1: Quoted text from loading label rejected for bl_port_of_discharge
        val, err = validate_value(
            "bl_port_of_discharge",
            "Chattogram",
            "Port of Loading: Chattogram Sea Port, Bangladesh",
        )
        self.assertFalse(val)
        self.assertIn("Port of Loading context", err)

        # Case 2: Multi-field line quote where Chattogram is under Port of Loading
        multi_quote = "Port of Loading: Chattogram Sea Port | Port of Discharge: Mongla Port"
        val_cgp, err_cgp = validate_value("bl_port_of_discharge", "Chattogram Sea Port", multi_quote)
        self.assertFalse(val_cgp)
        self.assertIn("conflicting role label", err_cgp)

        # Case 3: Mongla is under Port of Discharge in same multi_quote -> accepted
        val_mgl, err_mgl = validate_value("bl_port_of_discharge", "Mongla Port", multi_quote)
        self.assertEqual(val_mgl, "Mongla Port")
        self.assertEqual(err_mgl, "")

        # Case 4: L/C Tag 44E (loading) quote rejected for lc_port_of_discharge
        val_lc, err_lc = validate_value(
            "lc_port_of_discharge",
            "Busan",
            ":44E: Port of Loading: Busan, South Korea",
        )
        self.assertFalse(val_lc)
        self.assertIn("Port of Loading context", err_lc)

        # Case 5: Place of Delivery quote rejected for bl_port_of_discharge
        val_del, err_del = validate_value(
            "bl_port_of_discharge",
            "Dhaka",
            "Place of Delivery: Dhaka, Bangladesh",
        )
        self.assertFalse(val_del)
        self.assertIn("Place of Delivery context", err_del)

    def test_pdf_backed_role_boundary_synthetic_fixture(self):
        """Synthetic PDF fixture with Loading: Chattogram and Discharge: Mongla. Verify role isolation via collect_fields."""
        doc = pymupdf.open()
        page = doc.new_page(width=595, height=842)
        page.insert_text(pymupdf.Point(50, 100), "OCEAN BILL OF LADING", fontsize=14)
        page.insert_text(pymupdf.Point(50, 150), "Port of Loading: Chattogram Sea Port, Bangladesh", fontsize=10)
        page.insert_text(pymupdf.Point(50, 200), "Port of Discharge: Mongla Port, Bangladesh", fontsize=10)
        page.insert_text(pymupdf.Point(50, 250), "Place of Delivery: Dhaka, Bangladesh", fontsize=10)
        pdf_bytes = doc.tobytes()
        doc.close()

        packet = [("bill_of_lading.pdf", pdf_bytes)]
        page_text = {
            (1, 1): (
                "OCEAN BILL OF LADING\n"
                "Port of Loading: Chattogram Sea Port, Bangladesh\n"
                "Port of Discharge: Mongla Port, Bangladesh\n"
                "Place of Delivery: Dhaka, Bangladesh"
            )
        }

        # 1. Attacker/Model extracts bl_port_of_discharge citing Loading text
        invalid_entry = {
            "field": "bl_port_of_discharge",
            "value": "Chattogram Sea Port, Bangladesh",
            "quote": "Port of Loading: Chattogram Sea Port, Bangladesh",
            "document": 1,
            "page": 1,
        }
        values, evidence = collect_fields([invalid_entry], ["bl_port_of_discharge"], packet, page_text)
        self.assertEqual(evidence["_field_states"]["bl_port_of_discharge"]["status"], "rejected")
        self.assertEqual(values["bl_port_of_discharge"], "")

        # 2. Honest extraction citing Discharge text
        valid_entry = {
            "field": "bl_port_of_discharge",
            "value": "Mongla Port, Bangladesh",
            "quote": "Port of Discharge: Mongla Port, Bangladesh",
            "document": 1,
            "page": 1,
        }
        values_ok, evidence_ok = collect_fields([valid_entry], ["bl_port_of_discharge"], packet, page_text)
        self.assertEqual(evidence_ok["_field_states"]["bl_port_of_discharge"]["status"], "extracted")
        self.assertEqual(values_ok["bl_port_of_discharge"], "Mongla Port, Bangladesh")

    def test_wrapped_discharge_port_role_validation(self):
        """Wrapped candidate text (e.g. Port of Discharge: Chattogram\\nSea Port) matches properly and returns valid extracted status."""
        quote_text = "Port of Discharge: Chattogram\nSea Port"
        candidate_val = "Chattogram Sea Port"

        # 1. Direct validate_value test
        val, err = validate_value("bl_port_of_discharge", candidate_val, quote_text)
        self.assertEqual(val, "Chattogram Sea Port")
        self.assertEqual(err, "")

        # 2. PDF-backed collect_fields test
        doc = pymupdf.open()
        page = doc.new_page(width=595, height=842)
        page.insert_text(pymupdf.Point(50, 100), "OCEAN BILL OF LADING", fontsize=14)
        page.insert_text(pymupdf.Point(50, 150), quote_text, fontsize=10)
        pdf_bytes = doc.tobytes()
        doc.close()

        packet = [("bill_of_lading.pdf", pdf_bytes)]
        page_text = {(1, 1): f"OCEAN BILL OF LADING\n{quote_text}"}

        entry = {
            "field": "bl_port_of_discharge",
            "value": candidate_val,
            "quote": quote_text,
            "document": 1,
            "page": 1,
        }
        values, evidence = collect_fields([entry], ["bl_port_of_discharge"], packet, page_text)
        field_state = evidence["_field_states"]["bl_port_of_discharge"]
        self.assertEqual(field_state["status"], "extracted")
        self.assertEqual(values["bl_port_of_discharge"], "Chattogram Sea Port")

    def test_candidate_before_discharge_label_rejected(self):
        """Input 'Chattogram | Port of Discharge: Mongla Port' rejects 'Chattogram' as bl_port_of_discharge."""
        quote_text = "Chattogram | Port of Discharge: Mongla Port"
        candidate_val = "Chattogram"

        # 1. Direct validate_value test
        val, err = validate_value("bl_port_of_discharge", candidate_val, quote_text)
        self.assertEqual(val, "")
        self.assertTrue("before the Port of Discharge label" in err or "preceding field context" in err)

        # 2. PDF-backed collect_fields test
        doc = pymupdf.open()
        page = doc.new_page(width=595, height=842)
        page.insert_text(pymupdf.Point(50, 100), "OCEAN BILL OF LADING", fontsize=14)
        page.insert_text(pymupdf.Point(50, 150), quote_text, fontsize=10)
        pdf_bytes = doc.tobytes()
        doc.close()

        packet = [("bill_of_lading.pdf", pdf_bytes)]
        page_text = {(1, 1): f"OCEAN BILL OF LADING\n{quote_text}"}

        entry = {
            "field": "bl_port_of_discharge",
            "value": candidate_val,
            "quote": quote_text,
            "document": 1,
            "page": 1,
        }
        values, evidence = collect_fields([entry], ["bl_port_of_discharge"], packet, page_text)
        field_state = evidence["_field_states"]["bl_port_of_discharge"]
        self.assertEqual(field_state["status"], "rejected")
        self.assertEqual(values["bl_port_of_discharge"], "")

    def test_multi_field_quotation_role_isolation(self):
        """Input 'Port of Loading: Chattogram Sea Port | Port of Discharge: Mongla Port' rejects 'Chattogram Sea Port' for discharge, while accepting 'Mongla Port'."""
        quote_text = "Port of Loading: Chattogram\nSea Port | Port of Discharge: Mongla Port"

        # 1. Direct validate_value test
        val_cgp, err_cgp = validate_value("bl_port_of_discharge", "Chattogram Sea Port", quote_text)
        self.assertEqual(val_cgp, "")
        self.assertIn("conflicting role label", err_cgp)

        val_mgl, err_mgl = validate_value("bl_port_of_discharge", "Mongla Port", quote_text)
        self.assertEqual(val_mgl, "Mongla Port")
        self.assertEqual(err_mgl, "")

        # 2. PDF-backed collect_fields test
        doc = pymupdf.open()
        page = doc.new_page(width=595, height=842)
        page.insert_text(pymupdf.Point(50, 100), "OCEAN BILL OF LADING", fontsize=14)
        page.insert_text(pymupdf.Point(50, 150), quote_text, fontsize=10)
        pdf_bytes = doc.tobytes()
        doc.close()

        packet = [("bill_of_lading.pdf", pdf_bytes)]
        page_text = {(1, 1): f"OCEAN BILL OF LADING\n{quote_text}"}

        # Candidate under loading role is rejected
        entry_cgp = {
            "field": "bl_port_of_discharge",
            "value": "Chattogram Sea Port",
            "quote": quote_text,
            "document": 1,
            "page": 1,
        }
        values_cgp, evidence_cgp = collect_fields([entry_cgp], ["bl_port_of_discharge"], packet, page_text)
        self.assertEqual(evidence_cgp["_field_states"]["bl_port_of_discharge"]["status"], "rejected")
        self.assertEqual(values_cgp["bl_port_of_discharge"], "")

        # Candidate under discharge role is accepted
        entry_mgl = {
            "field": "bl_port_of_discharge",
            "value": "Mongla Port",
            "quote": quote_text,
            "document": 1,
            "page": 1,
        }
        values_mgl, evidence_mgl = collect_fields([entry_mgl], ["bl_port_of_discharge"], packet, page_text)
        self.assertEqual(evidence_mgl["_field_states"]["bl_port_of_discharge"]["status"], "extracted")
        self.assertEqual(values_mgl["bl_port_of_discharge"], "Mongla Port")

    def test_collect_fields_pipeline_field_role_governance(self):
        """Run full collect_fields() on documents with conflicting headers and assert that bl_port_of_discharge is strictly governed by the discharge span."""
        doc = pymupdf.open()
        page = doc.new_page(width=595, height=842)
        page.insert_text(pymupdf.Point(50, 100), "OCEAN BILL OF LADING", fontsize=14)
        page.insert_text(pymupdf.Point(50, 150), "Port of Loading: Busan, South Korea", fontsize=10)
        page.insert_text(pymupdf.Point(50, 180), "Port of Discharge: Mongla Port, Bangladesh", fontsize=10)
        page.insert_text(pymupdf.Point(50, 210), "Place of Delivery: Dhaka, Bangladesh", fontsize=10)
        pdf_bytes = doc.tobytes()
        doc.close()

        packet = [("bill_of_lading.pdf", pdf_bytes)]
        page_text = {
            (1, 1): (
                "OCEAN BILL OF LADING\n"
                "Port of Loading: Busan, South Korea\n"
                "Port of Discharge: Mongla Port, Bangladesh\n"
                "Place of Delivery: Dhaka, Bangladesh"
            )
        }

        # 1. Proposing Loading candidate as Discharge port is rejected
        entry_loading = {
            "field": "bl_port_of_discharge",
            "value": "Busan, South Korea",
            "quote": "Port of Loading: Busan, South Korea",
            "document": 1,
            "page": 1,
        }
        values_load, evidence_load = collect_fields([entry_loading], ["bl_port_of_discharge"], packet, page_text)
        self.assertEqual(evidence_load["_field_states"]["bl_port_of_discharge"]["status"], "rejected")
        self.assertEqual(values_load["bl_port_of_discharge"], "")

        # 2. Proposing Delivery candidate as Discharge port is rejected
        entry_delivery = {
            "field": "bl_port_of_discharge",
            "value": "Dhaka, Bangladesh",
            "quote": "Place of Delivery: Dhaka, Bangladesh",
            "document": 1,
            "page": 1,
        }
        values_del, evidence_del = collect_fields([entry_delivery], ["bl_port_of_discharge"], packet, page_text)
        self.assertEqual(evidence_del["_field_states"]["bl_port_of_discharge"]["status"], "rejected")
        self.assertEqual(values_del["bl_port_of_discharge"], "")

        # 3. Legitimate Discharge candidate is accepted and governs bl_port_of_discharge
        entry_discharge = {
            "field": "bl_port_of_discharge",
            "value": "Mongla Port, Bangladesh",
            "quote": "Port of Discharge: Mongla Port, Bangladesh",
            "document": 1,
            "page": 1,
        }
        values_dis, evidence_dis = collect_fields([entry_discharge], ["bl_port_of_discharge"], packet, page_text)
        self.assertEqual(evidence_dis["_field_states"]["bl_port_of_discharge"]["status"], "extracted")
        self.assertEqual(values_dis["bl_port_of_discharge"], "Mongla Port, Bangladesh")


class TestCargoGrossWeightConsistency(unittest.TestCase):
    """Unit tests for deterministic Cargo Gross Weight consistency check (Check 2)."""

    def test_clean_packet_weight_harmonized_passed(self):
        """Clean packet: 21,600 KG vs 21,600 KG -> Passed (delta 0 KG)."""
        d = {
            "pl_cargo_gross_weight": "21600",
            "pl_cargo_gross_weight_unit": "KGS",
            "bl_cargo_gross_weight": "21600",
            "bl_cargo_gross_weight_unit": "KGS",
        }
        res = check_cargo_gross_weight(d)
        self.assertEqual(res["status"], "Passed")
        self.assertIn("Cargo gross weight harmonized", res["evidence"])
        self.assertIn("Packing List (21600 KG) matches Bill of Lading (21600 KG)", res["evidence"])
        self.assertIn("delta 0 KG <= 10 KG", res["evidence"])
        self.assertIn("demo review tolerance", res["evidence"])

    def test_discrepancy_packet_weight_evaluation_review_required(self):
        """Discrepancy packet: 21,600 KG vs 20,700 KG -> Review required (delta 900 KG)."""
        d = {
            "pl_cargo_gross_weight": "21600",
            "pl_cargo_gross_weight_unit": "KGS",
            "bl_cargo_gross_weight": "20700",
            "bl_cargo_gross_weight_unit": "KGS",
        }
        res = check_cargo_gross_weight(d)
        self.assertEqual(res["status"], "Review required")
        self.assertIn("Discrepancy: Packing List states Cargo Gross Weight as '21600 KGS' (21600 KG)", res["evidence"])
        self.assertIn("Bill of Lading states '20700 KGS' (20700 KG)", res["evidence"])
        self.assertIn("delta 900 KG > 10 KG", res["evidence"])
        self.assertIn("demo review tolerance", res["evidence"])

    def test_corrected_packet_weight_harmonized_passed(self):
        """Corrected packet: 21,600 KG vs 21,600 KG -> Passed (delta 0 KG)."""
        d = {
            "pl_cargo_gross_weight": "21600.00",
            "pl_cargo_gross_weight_unit": "KGS",
            "bl_cargo_gross_weight": "21600",
            "bl_cargo_gross_weight_unit": "KG",
        }
        res = check_cargo_gross_weight(d)
        self.assertEqual(res["status"], "Passed")
        self.assertIn("Cargo gross weight harmonized", res["evidence"])

    def test_unit_conversion_mt_to_kg_passed(self):
        """Unit conversion: 21.6 MT vs 21,600 KG -> Passed (delta 0 KG)."""
        units_mt = ["MT", "M/T", "METRIC TON", "METRIC TONS"]
        units_kg = ["KG", "KGS", "KILOGRAM", "KILOGRAMS"]
        for mt in units_mt:
            for kg in units_kg:
                with self.subTest(mt=mt, kg=kg):
                    d = {
                        "pl_cargo_gross_weight": "21.6",
                        "pl_cargo_gross_weight_unit": mt,
                        "bl_cargo_gross_weight": "21600",
                        "bl_cargo_gross_weight_unit": kg,
                    }
                    res = check_cargo_gross_weight(d)
                    self.assertEqual(res["status"], "Passed")
                    self.assertIn("21600 KG", res["evidence"])
                    self.assertIn("delta 0 KG <= 10 KG", res["evidence"])

    def test_boundary_tolerance_exact_and_exceeded(self):
        """Boundary tolerance: Exactly 10 KG delta -> Passed; 10.001 / 11 KG delta -> Review required."""
        # 1. Delta exactly 10 KG (positive)
        res_10 = check_cargo_gross_weight({
            "pl_cargo_gross_weight": "21610",
            "pl_cargo_gross_weight_unit": "KG",
            "bl_cargo_gross_weight": "21600",
            "bl_cargo_gross_weight_unit": "KG",
        })
        self.assertEqual(res_10["status"], "Passed")
        self.assertIn("delta 10 KG <= 10 KG", res_10["evidence"])

        # 2. Delta exactly 10 KG (negative)
        res_neg_10 = check_cargo_gross_weight({
            "pl_cargo_gross_weight": "21590",
            "pl_cargo_gross_weight_unit": "KG",
            "bl_cargo_gross_weight": "21600",
            "bl_cargo_gross_weight_unit": "KG",
        })
        self.assertEqual(res_neg_10["status"], "Passed")
        self.assertIn("delta 10 KG <= 10 KG", res_neg_10["evidence"])

        # 3. Delta 10.001 KG -> Review required
        res_10_001 = check_cargo_gross_weight({
            "pl_cargo_gross_weight": "21610.001",
            "pl_cargo_gross_weight_unit": "KG",
            "bl_cargo_gross_weight": "21600",
            "bl_cargo_gross_weight_unit": "KG",
        })
        self.assertEqual(res_10_001["status"], "Review required")
        self.assertIn("delta 10.001 KG > 10 KG", res_10_001["evidence"])

        # 4. Delta 11 KG -> Review required
        res_11 = check_cargo_gross_weight({
            "pl_cargo_gross_weight": "21611",
            "pl_cargo_gross_weight_unit": "KG",
            "bl_cargo_gross_weight": "21600",
            "bl_cargo_gross_weight_unit": "KG",
        })
        self.assertEqual(res_11["status"], "Review required")
        self.assertIn("delta 11 KG > 10 KG", res_11["evidence"])

    def test_configurable_tolerance(self):
        """Custom configurable tolerance parameter operates accurately."""
        d = {
            "pl_cargo_gross_weight": "21605",
            "pl_cargo_gross_weight_unit": "KG",
            "bl_cargo_gross_weight": "21600",
            "bl_cargo_gross_weight_unit": "KG",
        }
        res_passed = check_cargo_gross_weight(d, max_weight_delta_kg=Decimal('5'))
        self.assertEqual(res_passed["status"], "Passed")

        res_review = check_cargo_gross_weight(d, max_weight_delta_kg=Decimal('4'))
        self.assertEqual(res_review["status"], "Review required")

    def test_unit_validation_missing_or_unsupported(self):
        """Missing unit or unsupported unit (e.g. LBS) -> Insufficient data."""
        # 1. Missing unit
        res_no_unit = check_cargo_gross_weight({
            "pl_cargo_gross_weight": "21600",
            "pl_cargo_gross_weight_unit": "",
            "bl_cargo_gross_weight": "21600",
            "bl_cargo_gross_weight_unit": "KG",
        })
        self.assertEqual(res_no_unit["status"], "Insufficient data")
        self.assertIn("Missing cargo gross weight or unit", res_no_unit["evidence"])

        # 2. Unsupported unit: LBS
        res_lbs = check_cargo_gross_weight({
            "pl_cargo_gross_weight": "47600",
            "pl_cargo_gross_weight_unit": "LBS",
            "bl_cargo_gross_weight": "21600",
            "bl_cargo_gross_weight_unit": "KG",
        })
        self.assertEqual(res_lbs["status"], "Insufficient data")
        self.assertIn("Unsupported weight unit", res_lbs["evidence"])

    def test_missing_or_invalid_weight_numeric(self):
        """Missing, zero, negative, or non-numeric weight values -> Insufficient data."""
        cases = [
            {"pl_cargo_gross_weight": "", "pl_cargo_gross_weight_unit": "KG", "bl_cargo_gross_weight": "21600", "bl_cargo_gross_weight_unit": "KG"},
            {"pl_cargo_gross_weight": "0", "pl_cargo_gross_weight_unit": "KG", "bl_cargo_gross_weight": "21600", "bl_cargo_gross_weight_unit": "KG"},
            {"pl_cargo_gross_weight": "-100", "pl_cargo_gross_weight_unit": "KG", "bl_cargo_gross_weight": "21600", "bl_cargo_gross_weight_unit": "KG"},
            {"pl_cargo_gross_weight": "ABC", "pl_cargo_gross_weight_unit": "KG", "bl_cargo_gross_weight": "21600", "bl_cargo_gross_weight_unit": "KG"},
        ]
        for c in cases:
            with self.subTest(c=c):
                res = check_cargo_gross_weight(c)
                self.assertEqual(res["status"], "Insufficient data")

    def test_status_string_equality(self):
        """Confirm plain string equality for cargo gross weight check."""
        res = check_cargo_gross_weight({
            "pl_cargo_gross_weight": "21600",
            "pl_cargo_gross_weight_unit": "KG",
            "bl_cargo_gross_weight": "21600",
            "bl_cargo_gross_weight_unit": "KG",
        })
        self.assertEqual(res["status"], "Passed")
        self.assertIs(type(res["status"]), str)

    def test_pending_review_bypass_prevention(self):
        """review_status='pending' cannot evaluate to Passed."""
        d = {
            "pl_cargo_gross_weight": "21600",
            "pl_cargo_gross_weight_unit": "KG",
            "bl_cargo_gross_weight": "21600",
            "bl_cargo_gross_weight_unit": "KG",
        }
        states = {
            "pl_cargo_gross_weight": {"status": "confirmed", "review_status": "pending", "reviewed_value": "21600"},
            "pl_cargo_gross_weight_unit": {"status": "confirmed", "review_status": "confirmed", "reviewed_value": "KG"},
            "bl_cargo_gross_weight": {"status": "confirmed", "review_status": "confirmed", "reviewed_value": "21600"},
            "bl_cargo_gross_weight_unit": {"status": "confirmed", "review_status": "confirmed", "reviewed_value": "KG"},
        }
        res = check_cargo_gross_weight(d, states)
        self.assertEqual(res["status"], "Insufficient data")
        self.assertIn("Packing List gross weight review: 'pending'", res["evidence"])

    def test_human_confirmed_correction_flow(self):
        """Initially missing weight field confirmed by human evaluates to Passed."""
        initial_states = {
            "pl_cargo_gross_weight": {
                "status": "missing",
                "reason": "No value returned; source absence is not established.",
                "candidates": [],
                "review_status": "pending",
            },
            "pl_cargo_gross_weight_unit": {
                "status": "missing",
                "reason": "No value returned",
                "candidates": [],
                "review_status": "pending",
            },
            "bl_cargo_gross_weight": {
                "status": "extracted",
                "reason": "Source-linked candidate",
                "candidates": [{"value": "21600", "status": "extracted"}],
                "review_status": "pending",
            },
            "bl_cargo_gross_weight_unit": {
                "status": "extracted",
                "reason": "Source-linked candidate",
                "candidates": [{"value": "KGS", "status": "extracted"}],
                "review_status": "pending",
            },
        }

        user_entered_values = {
            "pl_cargo_gross_weight": "21600",
            "pl_cargo_gross_weight_unit": "KGS",
            "bl_cargo_gross_weight": "21600",
            "bl_cargo_gross_weight_unit": "KGS",
        }
        reviewed = review_fields(user_entered_values, initial_states)

        self.assertEqual(reviewed["pl_cargo_gross_weight"]["status"], "missing")
        self.assertEqual(reviewed["pl_cargo_gross_weight"]["review_status"], "confirmed")
        self.assertEqual(reviewed["pl_cargo_gross_weight"]["reviewed_value"], "21600")

        res = check_cargo_gross_weight(user_entered_values, reviewed)
        self.assertEqual(res["status"], "Passed")
        self.assertIn("harmonized", res["evidence"].lower())

    def test_wrong_label_rejection_in_validator(self):
        """Net weight, Tare, and VGM substitute labels rejected during extraction validation."""
        # 1. Net Weight rejected
        val_nw, err_nw = validate_value("pl_cargo_gross_weight", "20000", "Cargo Net Weight: 20,000.00 KGS")
        self.assertFalse(val_nw)
        self.assertIn("Net Weight context", err_nw)

        # 2. Container Tare rejected
        val_tare, err_tare = validate_value("pl_cargo_gross_weight", "3800", "Container Tare Weight: 3,800.00 KGS")
        self.assertFalse(val_tare)
        self.assertIn("Container Tare", err_tare)

        # 3. Packaging Tare rejected
        val_pt, err_pt = validate_value("pl_cargo_gross_weight", "1600", "Packaging Tare: 1,600.00 KGS")
        self.assertFalse(val_pt)
        self.assertIn("Packaging Tare", err_pt)

        # 4. VGM rejected
        val_vgm, err_vgm = validate_value("pl_cargo_gross_weight", "25400", "Verified Gross Mass (VGM): 25,400.00 KGS")
        self.assertFalse(val_vgm)
        self.assertIn("Verified Gross Mass", err_vgm)

        # 5. Multi-field: Net Weight vs Gross Weight distinction
        multi_quote = "Net Weight: 20,000.00 KGS | Total Gross Weight: 21,600.00 KGS"
        val_bad, err_bad = validate_value("pl_cargo_gross_weight", "20000", multi_quote)
        self.assertFalse(val_bad)
        self.assertIn("Net Weight substitute", err_bad)

        val_good, err_good = validate_value("pl_cargo_gross_weight", "21600", multi_quote)
        self.assertEqual(val_good, "21600")
        self.assertEqual(err_good, "")

        # 6. Candidate preceding Gross Weight label rejected
        val_pre, err_pre = validate_value("bl_cargo_gross_weight", "21600", "21,600 KGS | Gross Weight: 20,700 KGS")
        self.assertFalse(val_pre)
        self.assertIn("appears before the Cargo Gross Weight label", err_pre)

        # 7. Candidate under Gross Weight accepted
        val_post, err_post = validate_value("bl_cargo_gross_weight", "20700", "21,600 KGS | Gross Weight: 20,700 KGS")
        self.assertEqual(val_post, "20700")
        self.assertEqual(err_post, "")

        # 8. Unit validation: supported vs unsupported
        unit_ok, u_err = validate_value("pl_cargo_gross_weight_unit", "KGS", "Cargo Gross Weight: 21,600.00 KGS")
        self.assertEqual(unit_ok, "KGS")
        self.assertEqual(u_err, "")

        unit_lbs, lbs_err = validate_value("pl_cargo_gross_weight_unit", "LBS", "Cargo Gross Weight: 47,600.00 LBS")
        self.assertFalse(unit_lbs)
        self.assertIn("Unsupported cargo weight unit: LBS", lbs_err)


class TestAuditPipelineEightChecks(unittest.TestCase):
    """Verify live audit execution pipeline runs all 8 deterministic checks."""

    def test_audit_pipeline_returns_eight_findings_on_complete_clean_data(self):
        clean_input = {
            "lc_currency": "USD",
            "invoice_currency": "USD",
            "invoice_quantity": "20000",
            "packing_quantity": "20000",
            "packing_container": "MEDU1000060",
            "bl_container": "MEDU1000060",
            "invoice_total": "25000.00",
            "lc_amount": "26250.00",
            "unit_price": "1.25",
            "on_board_date": "2026-11-10",
            "latest_shipment_date": "2026-11-15",
            "lc_port_of_discharge": "Chattogram Sea Port, Bangladesh",
            "bl_port_of_discharge": "Chattogram Sea Port, Bangladesh",
            "bl_port_of_loading": "Busan, South Korea",
            "bl_place_of_delivery": "Dhaka, Bangladesh",
            "pl_cargo_gross_weight": "21600",
            "pl_cargo_gross_weight_unit": "KGS",
            "bl_cargo_gross_weight": "21600",
            "bl_cargo_gross_weight_unit": "KGS",
        }
        findings = audit(clean_input)
        self.assertEqual(len(findings), 8, f"Audit must return exactly 8 findings, got {len(findings)}")

        checks = [f["check"] for f in findings]
        self.assertIn("Port of discharge consistency", checks)
        self.assertIn("Cargo gross weight consistency", checks)

        for finding in findings:
            self.assertEqual(finding["status"], "Passed", f"Check {finding['check']} failed: {finding['evidence']}")


if __name__ == "__main__":
    unittest.main()

