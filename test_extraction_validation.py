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

