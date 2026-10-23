"""test_checks.py — Unit test verification for checks.py including Check 1 (Port of Discharge Consistency).

Verifies:
  1. Equivalent aliases: Chattogram cluster (Chattogram, Chittagong, BDCGP) and Mongla cluster (Mongla, Chalna, BDMGL) -> Passed.
  2. Discrepancy detection: Chattogram vs Mongla -> Review required, strictly documentary phrasing.
  3. Unknown port authority / UN/LOCODE: e.g., 'Atlantis Port' -> Review required.
  4. Missing, unreadable, conflicting, or unconfirmed field states -> Insufficient data.
  5. Field disentanglement: Place of Delivery (Dhaka) and Port of Loading (Busan) never cross-match or confound the discharge port check.
  6. Source quotation mismatch rejection in validator.
  7. Audit pipeline integration: All 7 deterministic checks executed.
"""

from __future__ import annotations

import unittest
from checks import (
    audit,
    check_port_of_discharge,
    resolve_canonical_port,
    normalize_port_name,
    CheckStatus,
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

    def test_unknown_port_evaluates_to_review_required(self):
        res = check_port_of_discharge({
            "lc_port_of_discharge": "Chattogram Sea Port",
            "bl_port_of_discharge": "Atlantis Port",
        })
        self.assertEqual(res["status"], "Review required")
        self.assertIn("Unrecognized port of discharge", res["evidence"])
        self.assertIn("Atlantis Port", res["evidence"])

    def test_missing_fields_evaluate_to_insufficient_data(self):
        # Missing B/L port
        res1 = check_port_of_discharge({"lc_port_of_discharge": "Chattogram Sea Port"})
        self.assertEqual(res1["status"], "Insufficient data")
        self.assertEqual(res1["status"], "Incomplete")  # Backward compatibility

        # Missing L/C port
        res2 = check_port_of_discharge({"bl_port_of_discharge": "Chattogram Sea Port"})
        self.assertEqual(res2["status"], "Insufficient data")

        # Empty strings
        res3 = check_port_of_discharge({"lc_port_of_discharge": "", "bl_port_of_discharge": "   "})
        self.assertEqual(res3["status"], "Insufficient data")

    def test_unconfirmed_and_invalid_field_states_evaluate_to_insufficient_data(self):
        d = {
            "lc_port_of_discharge": "Chattogram Sea Port",
            "bl_port_of_discharge": "Chattogram Sea Port",
        }

        # 1. review_status == 'pending'
        states_pending = {
            "lc_port_of_discharge": {"status": "extracted", "review_status": "pending"},
            "bl_port_of_discharge": {"status": "extracted", "review_status": "confirmed"},
        }
        res = check_port_of_discharge(d, states_pending)
        self.assertEqual(res["status"], "Insufficient data")

        # 2. extraction state == 'unreadable'
        states_unreadable = {
            "lc_port_of_discharge": {"status": "unreadable", "review_status": "confirmed"},
            "bl_port_of_discharge": {"status": "extracted", "review_status": "confirmed"},
        }
        res = check_port_of_discharge(d, states_unreadable)
        self.assertEqual(res["status"], "Insufficient data")

        # 3. extraction state == 'conflicting'
        states_conflict = {
            "lc_port_of_discharge": {"status": "extracted", "review_status": "confirmed"},
            "bl_port_of_discharge": {"status": "conflicting", "review_status": "confirmed"},
        }
        res = check_port_of_discharge(d, states_conflict)
        self.assertEqual(res["status"], "Insufficient data")

        # 4. extraction state == 'rejected'
        states_rejected = {
            "lc_port_of_discharge": {"status": "rejected", "review_status": "confirmed"},
            "bl_port_of_discharge": {"status": "extracted", "review_status": "confirmed"},
        }
        res = check_port_of_discharge(d, states_rejected)
        self.assertEqual(res["status"], "Insufficient data")

        # 5. review_status == 'confirmed' on both passes
        states_confirmed = {
            "lc_port_of_discharge": {"status": "extracted", "review_status": "confirmed"},
            "bl_port_of_discharge": {"status": "extracted", "review_status": "confirmed"},
        }
        res = check_port_of_discharge(d, states_confirmed)
        self.assertEqual(res["status"], "Passed")

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


class TestAuditPipelineSevenChecks(unittest.TestCase):
    """Verify live audit execution pipeline runs all 7 deterministic checks."""

    def test_audit_pipeline_returns_seven_findings_on_complete_clean_data(self):
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
        }
        findings = audit(clean_input)
        self.assertEqual(len(findings), 7, f"Audit must return exactly 7 findings, got {len(findings)}")

        checks = [f["check"] for f in findings]
        self.assertIn("Port of discharge consistency", checks)

        for finding in findings:
            self.assertEqual(finding["status"], "Passed", f"Check {finding['check']} failed: {finding['evidence']}")


if __name__ == "__main__":
    unittest.main()
