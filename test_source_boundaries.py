"""Regression tests for source boundaries through PDF ingestion and audit."""
import unittest
import pymupdf

from checks import audit
from field_states import collect_fields, review_fields


class SourceBoundaryTests(unittest.TestCase):
    def collect(self, field, value, quote, source=None, pdf=True):
        source = quote if source is None else source
        if pdf:
            with pymupdf.open() as doc:
                page = doc.new_page()
                page.insert_text((40, 60), source, fontsize=9)
                page_text = page.get_text()
                content = doc.tobytes()
        else:
            content, page_text = b'text fixture', source
        return collect_fields(
            [{'field': field, 'value': value, 'quote': quote, 'document': 1, 'page': 1}],
            [field], [('source.pdf', content)], {(1, 1): page_text})

    def test_numeric_columns_cannot_be_rewritten_as_grouped_amount(self):
        for pdf in (True, False):
            for separator in ('\n', '\t', '  '):
                with self.subTest(pdf=pdf, separator=repr(separator)):
                    values, evidence = self.collect(
                        'invoice_total', '18000', 'Invoice total 18 000',
                        'Invoice total 18' + separator + '000', pdf)
                    self.assertEqual(values['invoice_total'], '')
                    self.assertEqual(evidence['_field_states']['invoice_total']['status'], 'rejected')

    def test_real_grouped_amount_still_extracts(self):
        values, _ = self.collect('invoice_total', '18000', 'Invoice total 18 000')
        self.assertEqual(values['invoice_total'], '18000')

    def test_false_port_candidates_cannot_reach_audit(self):
        cases = [
            ('Chattogram', 'Port of Discharge: ChattogramX'),
            ('Chattogram', 'Port of Discharge: XChattogram'),
            ('Chattogram', 'Port of Discharge: Mongla\nNotify party: Chattogram'),
            ('Chattogram', 'Port of Discharge: Mongla\nCustom reference: Chattogram'),
            ('Chattogram Sea Port', 'Port of Loading: Chattogram\nSea Port | Port of Discharge: Mongla Port'),
            ('Chattogram', 'Chattogram | Port of Discharge: Mongla'),
        ]
        for value, quote in cases:
            with self.subTest(quote=quote):
                values, evidence = self.collect('bl_port_of_discharge', value, quote)
                self.assertEqual(values['bl_port_of_discharge'], '')
                self.assertEqual(evidence['_field_states']['bl_port_of_discharge']['status'], 'rejected')
                values['lc_port_of_discharge'] = 'Chattogram'
                reviewed = review_fields(values, evidence['_field_states'])
                finding = next(f for f in audit(values, reviewed) if f['check'] == 'Port of discharge consistency')
                self.assertEqual(finding['status'], 'Insufficient data')

    def test_wrapped_and_bounded_real_ports_remain_usable(self):
        for value, quote in [
            ('Chattogram Sea Port', 'Port of Discharge: Chattogram\nSea Port'),
            ('Mongla', 'Port of Discharge: Mongla\nNotify party: Chattogram'),
            ('Mongla Port', 'Port of Loading: Chattogram\nSea Port | Port of Discharge: Mongla Port'),
        ]:
            with self.subTest(quote=quote):
                values, evidence = self.collect('bl_port_of_discharge', value, quote)
                self.assertEqual(values['bl_port_of_discharge'], value)
                values['lc_port_of_discharge'] = 'Chattogram'
                reviewed = review_fields(values, evidence['_field_states'])
                finding = next(f for f in audit(values, reviewed) if f['check'] == 'Port of discharge consistency')
                self.assertEqual(finding['status'],
                                 'Passed' if value.startswith('Chattogram') else 'Review required')

    def test_false_gross_weight_substitutes_cannot_reach_audit(self):
        cases = [
            ('pl_cargo_gross_weight', '20000', 'Cargo Net Weight: 20,000 KGS'),
            ('pl_cargo_gross_weight', '20000', 'Total Net Weight: 20,000 KGS'),
            ('pl_cargo_gross_weight', '20000', 'Net Weight: 20,000 KGS'),
            ('pl_cargo_gross_weight', '20000', 'Net Wt: 20,000 KGS'),
            ('pl_cargo_gross_weight', '20000', 'N.W.: 20,000 KGS'),
            ('pl_cargo_gross_weight', '3800', 'Container Tare Weight: 3,800 KGS'),
            ('pl_cargo_gross_weight', '3800', 'Tare Weight: 3,800 KGS'),
            ('pl_cargo_gross_weight', '3800', 'Tare Wt: 3,800 KGS'),
            ('pl_cargo_gross_weight', '3800', 'Tare: 3,800 KGS'),
            ('pl_cargo_gross_weight', '1600', 'Packaging Tare: 1,600 KGS'),
            ('pl_cargo_gross_weight', '1600', 'Cargo Packaging Tare: 1,600 KGS'),
            ('pl_cargo_gross_weight', '25400', 'Verified Gross Mass: 25,400 KGS'),
            ('pl_cargo_gross_weight', '25400', 'VGM: 25,400 KGS'),
            ('pl_cargo_gross_weight', '20000', 'Net Weight: 20,000 KGS | Gross Weight: 21,600 KGS'),
            ('bl_cargo_gross_weight', '21600', '21,600 KGS | Gross Weight: 20,700 KGS'),
        ]
        for field, value, quote in cases:
            with self.subTest(field=field, quote=quote):
                values, evidence = self.collect(field, value, quote)
                self.assertEqual(values[field], '')
                self.assertEqual(evidence['_field_states'][field]['status'], 'rejected')
                values['pl_cargo_gross_weight_unit'] = 'KG'
                values['bl_cargo_gross_weight_unit'] = 'KG'
                other_field = 'bl_cargo_gross_weight' if field == 'pl_cargo_gross_weight' else 'pl_cargo_gross_weight'
                values[other_field] = '21600'
                values[field] = ''
                reviewed = review_fields(values, evidence['_field_states'])
                finding = next(f for f in audit(values, reviewed) if f['check'] == 'Cargo gross weight consistency')
                self.assertEqual(finding['status'], 'Insufficient data')

    def test_wrapped_and_bounded_gross_weight_remains_usable(self):
        cases = [
            ('pl_cargo_gross_weight', '21600', 'Cargo Gross Weight: 21,600.00 KGS'),
            ('pl_cargo_gross_weight', '21600', 'Total Gross Weight:\n21,600 KGS'),
            ('pl_cargo_gross_weight', '21600', 'Gross Weight: 21,600 KGS'),
            ('pl_cargo_gross_weight', '21600', 'GR.WT.: 21,600 KGS'),
            ('pl_cargo_gross_weight', '21600', 'G.W.: 21,600 KGS'),
            ('bl_cargo_gross_weight', '21600', 'Net Weight: 20,000 KGS | Gross Weight: 21,600 KGS'),
            ('bl_cargo_gross_weight', '20700', '21,600 KGS | Gross Weight: 20,700 KGS'),
        ]
        for field, value, quote in cases:
            with self.subTest(field=field, quote=quote):
                values, evidence = self.collect(field, value, quote)
                self.assertEqual(values[field], value)
                self.assertEqual(evidence['_field_states'][field]['status'], 'extracted')
                values['pl_cargo_gross_weight'] = '21600'
                values['pl_cargo_gross_weight_unit'] = 'KG'
                values['bl_cargo_gross_weight'] = value if field == 'bl_cargo_gross_weight' else '21600'
                values['bl_cargo_gross_weight_unit'] = 'KG'
                reviewed = review_fields(values, evidence['_field_states'])
                finding = next(f for f in audit(values, reviewed) if f['check'] == 'Cargo gross weight consistency')
                self.assertEqual(finding['status'],
                                 'Passed' if values['bl_cargo_gross_weight'] == '21600' else 'Review required')


if __name__ == '__main__':
    unittest.main()

