import unittest
from extraction_validation import validate_value, normalized

class SourceValidationTests(unittest.TestCase):
    def test_packaging_is_not_container(self):
        self.assertFalse(validate_value('packing_container','25 KG bags','Packaging 25 KG bags')[0])
    def test_package_count_needs_review(self):
        self.assertFalse(validate_value('packing_quantity','720','Number of bags 720')[0])
    def test_explicit_quantity(self):
        self.assertEqual(validate_value('packing_quantity','18000','Total quantity (KG) 18,000')[0],'18000')
    def test_numeric_value_must_be_cited(self):
        self.assertFalse(validate_value('invoice_total','18000','Invoice total 18500')[0])
    def test_nonfinite_value_rejected(self):
        self.assertFalse(validate_value('lc_amount','NaN','Credit amount NaN')[0])
    def test_container_normalization(self):
        self.assertEqual(validate_value('bl_container','TSTU 1234560','Container number TSTU 1234560')[0],'TSTU1234560')
    def test_currency_must_be_explicit(self):
        self.assertFalse(validate_value('invoice_currency','USD','Currency $')[0])
    def test_invalid_date_rejected(self):
        self.assertFalse(validate_value('on_board_date','2026-02-30','On board 2026-02-30')[0])

class DateAndNumberTests(unittest.TestCase):
    def test_matching_dates(self):
        for source, expected in [
            ('2026-11-10','2026-11-10'), ('2026/11/10','2026-11-10'),
            ('10 November 2026','2026-11-10'), ('Nov 10, 2026','2026-11-10'),
            ('10-NOV-2026','2026-11-10'), ('13/11/2026','2026-11-13'),
            ('11/13/2026','2026-11-13'), ('11/11/2026','2026-11-11'),
            ('29 February 2028','2028-02-29')]:
            with self.subTest(source=source):
                self.assertEqual(validate_value('latest_shipment_date',expected,'Latest shipment date '+source)[0], expected)

    def test_absent_wrong_ambiguous_conflicting_dates(self):
        for source in ['No date supplied', '2026-11-09', '10/11/2026', '10/11/26',
                       '2026-11-10; expiry 2026-12-10', '31 November 2026',
                       '2026-11-10; alternate date 10/11/2026']:
            with self.subTest(source=source):
                self.assertFalse(validate_value('on_board_date','2026-11-10','On board '+source)[0])

    def test_date_role_and_strict_iso(self):
        self.assertFalse(validate_value('latest_shipment_date','2026-11-10','Credit expiry 2026-11-10')[0])
        self.assertFalse(validate_value('on_board_date','2026-11-10','Latest shipment date 2026-11-10')[0])
        self.assertFalse(validate_value('on_board_date','2026-1-1','On board 2026-01-01')[0])
        self.assertFalse(validate_value('on_board_date','2026-02-29','On board 2026-02-29')[0])

    def test_grouped_and_decimal_numbers(self):
        for source, expected in [('18,000','18000'),('18 000','18000'),
                                 ('18\u00a0000','18000'),('18\u202f000','18000'),
                                 ('18 000.00','18000'),('18 000,00','18000'),
                                 ('18,000.00','18000'),('18.000,00','18000'),
                                 ('1,80,000.00','180000'),('18,00,000','1800000'),('1,234,567.89','1234567.89'),
                                 ('18000.000','18000'),('1.50','1.5'),('1,50','1.5')]:
            with self.subTest(source=source):
                self.assertEqual(validate_value('invoice_total',expected,'Invoice total '+source)[0],expected)

    def test_malformed_numbers_cannot_supply_fragments(self):
        for source, expected in [('18.000','18000'),('18.000','18'),('18 00','1800'),
                                 ('18  000','18000'),('18\t000','18000'),('18\n000','18000'),
                                 ('18,0000','180000'),('18,00,00','18'),
                                 ('18,000.00','18'),('1e3','3'),('-18,000','18000'),
                                 ('(18,000)','18000'),('INV-18000','18000')]:
            with self.subTest(source=source,expected=expected):
                self.assertFalse(validate_value('invoice_total',expected,'Invoice total '+source)[0])

    def test_model_value_must_be_plain_decimal(self):
        for value in ['18,000','18 000','NaN','Infinity','1e3','-18000','1_000']:
            self.assertFalse(validate_value('invoice_total',value,'Invoice total 18000')[0])
        self.assertEqual(validate_value('invoice_total','18000.00','Invoice total 18,000')[0],'18000.00')

    def test_null_inputs_abstain(self):
        for args in [(None,'1','1'),('invoice_total',None,'Total 1'),('invoice_total','1',None)]:
            self.assertFalse(validate_value(*args)[0])

    def test_quote_matching_preserves_numeric_boundaries(self):
        self.assertEqual(normalized('Total       18 000'), normalized('Total 18 000'))
        self.assertNotEqual(normalized('Total 18 000'), normalized('Total 18    000'))
        self.assertNotEqual(normalized('Total 18 000'), normalized('Total 18\n000'))
        self.assertEqual(normalized('Total 18\u00a0000'), normalized('Total 18 000'))


class PortFieldValidationTests(unittest.TestCase):
    def test_valid_ports_contained_in_quote(self):
        self.assertEqual(
            validate_value('lc_port_of_discharge', 'Chattogram Sea Port', '44F: Port of Discharge: Chattogram Sea Port, Bangladesh')[0],
            'Chattogram Sea Port'
        )
        self.assertEqual(
            validate_value('bl_port_of_discharge', 'BDCGP', 'Port of Discharge: BDCGP')[0],
            'BDCGP'
        )
        self.assertEqual(
            validate_value('bl_port_of_loading', 'Busan, South Korea', 'Port of Loading: Busan, South Korea')[0],
            'Busan, South Korea'
        )
        self.assertEqual(
            validate_value('bl_place_of_delivery', 'Dhaka, Bangladesh', 'Place of Delivery: Dhaka, Bangladesh')[0],
            'Dhaka, Bangladesh'
        )

    def test_quotation_containment_rejection(self):
        val, err = validate_value('lc_port_of_discharge', 'Mongla Port', '44F: Port of Discharge: Chattogram Sea Port, Bangladesh')
        self.assertFalse(val)
        self.assertIn('absent from or not contained', err)

    def test_length_boundaries_rejected(self):
        # Too short (< 3 chars)
        self.assertFalse(validate_value('lc_port_of_discharge', 'GP', 'Port GP')[0])
        # Too long (> 120 chars)
        long_port = 'A' * 121
        self.assertFalse(validate_value('lc_port_of_discharge', long_port, long_port)[0])

    def test_unregistered_unknown_field_rejected(self):
        val, err = validate_value('unregistered_unknown_field', 'Some Value', 'Quote Some Value')
        self.assertFalse(val)
        self.assertIn('Unregistered or unknown field', err)

    def test_wrong_role_quotation_rejected(self):
        """B/L with Loading: Chattogram, Discharge: Mongla. Reject Chattogram as discharge port evidence."""
        # Port of Loading quote rejected for bl_port_of_discharge
        val_load, err_load = validate_value(
            'bl_port_of_discharge',
            'Chattogram',
            'Port of Loading: Chattogram Sea Port, Bangladesh'
        )
        self.assertFalse(val_load)
        self.assertIn('Port of Loading context', err_load)

        # Multi-role quote where Chattogram is under Port of Loading
        multi_quote = 'Port of Loading: Chattogram Sea Port | Port of Discharge: Mongla Port'
        val_cgp, err_cgp = validate_value('bl_port_of_discharge', 'Chattogram Sea Port', multi_quote)
        self.assertFalse(val_cgp)
        self.assertIn('conflicting role label', err_cgp)

        # Mongla is under Port of Discharge in same multi_quote -> accepted
        val_mgl, err_mgl = validate_value('bl_port_of_discharge', 'Mongla Port', multi_quote)
        self.assertEqual(val_mgl, 'Mongla Port')
        self.assertEqual(err_mgl, '')

        # Tag 44E quote rejected for lc_port_of_discharge
        val_lc, err_lc = validate_value(
            'lc_port_of_discharge',
            'Busan',
            ':44E: Port of Loading: Busan, South Korea'
        )
        self.assertFalse(val_lc)
        self.assertIn('Port of Loading context', err_lc)

        # Place of Delivery quote rejected for bl_port_of_discharge
        val_del, err_del = validate_value(
            'bl_port_of_discharge',
            'Dhaka',
            'Place of Delivery: Dhaka, Bangladesh'
        )
        self.assertFalse(val_del)
        self.assertIn('Place of Delivery context', err_del)

    def test_wrapped_discharge_port_role_validation(self):
        """Wrapped candidate text (e.g. Port of Discharge: Chattogram\\nSea Port) matches properly and returns valid extracted status."""
        import pymupdf
        from field_states import collect_fields

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
        import pymupdf
        from field_states import collect_fields

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
        import pymupdf
        from field_states import collect_fields

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
        import pymupdf
        from field_states import collect_fields

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


class ExtractionIntegrationTests(unittest.TestCase):
    def test_wrong_date_is_omitted_while_valid_amount_survives(self):
        import base64, io, json, zipfile
        from pathlib import Path
        from unittest.mock import patch
        from pypdf import PdfReader
        from extraction import extract_ai
        from ai_runtime import Context, DEFAULT_MODELS
        bundle=json.loads(Path(__file__).with_name('benchmark_data.json').read_text())
        with zipfile.ZipFile(io.BytesIO(base64.b64decode(bundle['zip_base64']))) as z:
            packet=[(Path(n).name,z.read(n)) for n in z.namelist() if '/PSB-01/' in n and n.endswith('.pdf')]
        doc=next(i for i,(name,_) in enumerate(packet,1) if name=='lc.pdf')
        text=PdfReader(io.BytesIO(packet[doc-1][1])).pages[0].extract_text(extraction_mode='layout')
        date_quote=next(line.strip() for line in text.splitlines() if 'Latest shipment date' in line)
        amount_quote=next(line.strip() for line in text.splitlines() if 'Credit amount' in line)
        fields=[{'field':'latest_shipment_date','value':'2026-11-09','quote':date_quote,'document':doc,'page':1},
                {'field':'lc_amount','value':'20000','quote':amount_quote,'document':doc,'page':1}]
        raw={'model':DEFAULT_MODELS['OpenRouter'],'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'fields':fields})}}]}
        with patch('extraction.capability_check',return_value={'output_mode':'json_schema'}), patch('extraction.request_json',return_value=raw):
            values,evidence=extract_ai(packet,'mock',['latest_shipment_date','lc_amount'],'OpenRouter',DEFAULT_MODELS['OpenRouter'],Context({'http_requests':0}))
        self.assertEqual(values,{'latest_shipment_date':'','lc_amount':'20000'})
        self.assertIn('latest_shipment_date',evidence['_rejected'])

if __name__=='__main__':unittest.main()

