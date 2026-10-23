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
                finding = audit(values, reviewed)[-1]
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
                self.assertEqual(audit(values, reviewed)[-1]['status'],
                                 'Passed' if value.startswith('Chattogram') else 'Review required')


if __name__ == '__main__':
    unittest.main()
