import unittest
from decimal import Decimal
import pymupdf
from checks import audit, check_cargo_gross_weight
from field_states import collect_fields, review_fields


class WeightPairingTests(unittest.TestCase):
    def extract(self, amount, unit, quote, unit_quote=None):
        unit_quote = quote if unit_quote is None else unit_quote
        with pymupdf.open() as doc:
            page = doc.new_page()
            page.insert_text((30, 50), quote + '\n' + unit_quote, fontsize=8)
            text = page.get_text()
            data = doc.tobytes()
        keys = ['pl_cargo_gross_weight', 'pl_cargo_gross_weight_unit']
        entries = [dict(field=k, value=v, quote=q, document=1, page=1)
                   for k, v, q in zip(keys, [amount, unit], [quote, unit_quote])]
        return collect_fields(entries, keys, [('packing_list.pdf', data)], {(1, 1): text})

    def test_cross_entry_pair_rejected(self):
        for q, uq in [
            ('Gross Weight: 21600 KG | Gross Weight: 21.6 MT', None),
            ('Gross Weight: 21600 KG', 'Gross Weight: 21.6 MT'),
        ]:
            values, evidence = self.extract('21600', 'MT', q, uq)
            self.assertFalse(values['pl_cargo_gross_weight'])
            self.assertFalse(values['pl_cargo_gross_weight_unit'])
            self.assertEqual(evidence['_field_states']['pl_cargo_gross_weight']['status'], 'rejected')

    def test_numeric_boundaries_and_container_gross_rejected(self):
        for q, amount in [
            ('Gross Weight: 21\n600 KG | Net Weight: 21600 KG', '21600'),
            ('Gross Weight: 21\t600 KG | Net Weight: 21600 KG', '21600'),
            ('Container Gross Weight: 25400 KGS', '25400'),
            ('Verified Gross Mass: 25400 KG', '25400'),
        ]:
            with self.subTest(q=q):
                values, evidence = self.extract(amount, 'KG', q)
                self.assertFalse(values['pl_cargo_gross_weight'])
                values.update(bl_cargo_gross_weight='21600', bl_cargo_gross_weight_unit='KG')
                reviewed = review_fields(values, evidence['_field_states'])
                self.assertEqual(audit(values, reviewed)[-1]['status'], 'Insufficient data')

    def test_valid_pair_provenance_and_conversion(self):
        for quote, amount, unit in [
            ('Cargo Gross Weight:\n21,600.00 KGS', '21600', 'KGS'),
            ('Gross Weight: 21.6 MT', '21.6', 'MT'),
            ('Gross Weight: 21 600 KG', '21600', 'KG'),
        ]:
            values, evidence = self.extract(amount, unit, quote)
            self.assertEqual(values['pl_cargo_gross_weight'], amount)
            states = evidence['_field_states']
            self.assertEqual(states['pl_cargo_gross_weight']['candidates'][0]['weight_source'],
                             states['pl_cargo_gross_weight_unit']['candidates'][0]['weight_source'])
            values.update(bl_cargo_gross_weight='21600', bl_cargo_gross_weight_unit='KG')
            reviewed = review_fields(values, states)
            self.assertEqual(audit(values, reviewed)[-1]['status'], 'Passed')

    def test_bad_manual_numbers_do_not_crash_or_change_meaning(self):
        for value in ['Infinity', '-Infinity', 'NaN', 'sNaN', '1e100', '21,6', '9' * 100, '-1', '0']:
            with self.subTest(value=value):
                values = dict(pl_cargo_gross_weight=value, pl_cargo_gross_weight_unit='KG',
                              bl_cargo_gross_weight='216', bl_cargo_gross_weight_unit='KG')
                self.assertEqual(audit(values, review_fields(values, {}))[-1]['status'], 'Insufficient data')

    def test_invalid_tolerances_are_bounded(self):
        values = dict(pl_cargo_gross_weight='21600', pl_cargo_gross_weight_unit='KG',
                      bl_cargo_gross_weight='21600', bl_cargo_gross_weight_unit='KG')
        for tolerance in [Decimal('Infinity'), Decimal('NaN'), -1, '1e100']:
            self.assertEqual(check_cargo_gross_weight(values, max_weight_delta_kg=tolerance)['status'],
                             'Insufficient data')
        self.assertEqual(check_cargo_gross_weight(values, max_weight_delta_kg=0)['status'], 'Passed')


if __name__ == '__main__':
    unittest.main()
