import copy
import unittest
from checks import audit
from container_checks import RULE, calculate_check_digit, check_container_check_digits
from field_states import review_fields


class ContainerCheckTests(unittest.TestCase):
    def values(self, a='MEDU1000060', b=None):
        return dict(packing_container=a, bl_container=a if b is None else b)

    def test_known_vectors(self):
        for prefix, digit in [('CSQU305438', 3), ('MEDU100006', 0), ('AAAU000000', 7)]:
            self.assertEqual(calculate_check_digit(prefix), digit)

    def test_remainder_ten_maps_to_zero(self):
        # MEDU100004 weighted sum = 2430 = 220*11 + 10.
        self.assertEqual(calculate_check_digit('MEDU100004'), 0)

    def test_same_invalid_id_does_not_pass_checksum(self):
        results = {f['check']: f for f in audit(self.values('MEDU1000067'))}
        self.assertEqual(results['Container identifier']['status'], 'Passed')
        self.assertEqual(results[RULE]['status'], 'Review required')
        self.assertIn('stated digit 7, calculated digit 0', results[RULE]['evidence'])

    def test_different_valid_ids_still_fail_equality(self):
        results = {f['check']: f for f in audit(self.values(b='CSQU3054383'))}
        self.assertEqual(results['Container identifier']['status'], 'Review required')
        self.assertEqual(results[RULE]['status'], 'Passed')

    def test_presentation_normalization(self):
        self.assertEqual(check_container_check_digits(self.values('medu 100006-0'))['status'], 'Passed')

    def test_malformed_values_no_ocr_repair(self):
        for value in ['MEDU1O00060', 'ABCD1234567', 'MEDU100006', 'MEDU10000600',
                      'MEDU１００００６０', 'MEDU1000060/CSQU3054383', 123, [], {}]:
            with self.subTest(value=value):
                self.assertEqual(check_container_check_digits(self.values(value))['status'], 'Review required')

    def test_missing_precedes_other_failure(self):
        for value in [None, '', '   ']:
            self.assertEqual(check_container_check_digits(self.values('MEDU1000067', value) if value is not None
                else dict(packing_container='MEDU1000067', bl_container=None))['status'], 'Insufficient data')

    def test_pending_and_stale_confirmation(self):
        values = self.values()
        self.assertEqual(check_container_check_digits(values, {})['status'], 'Insufficient data')
        reviewed = review_fields(values, {})
        self.assertEqual(check_container_check_digits(values, reviewed)['status'], 'Passed')
        values['bl_container'] = 'CSQU3054383'
        self.assertEqual(check_container_check_digits(values, reviewed)['status'], 'Insufficient data')
        self.assertEqual(next(f for f in audit(values, reviewed) if f['check'] == RULE)['status'], 'Insufficient data')

    def test_human_correction_preserves_original_evidence(self):
        values = self.values('MEDU1000067')
        states = {k: {'status': 'extracted', 'candidates': [{'quote': 'Container MEDU1000067', 'value': v}]} for k,v in values.items()}
        original = copy.deepcopy(states)
        reviewed = review_fields(values, states)
        self.assertEqual(check_container_check_digits(values, reviewed)['status'], 'Review required')
        corrected = self.values()
        new_review = review_fields(corrected, reviewed)
        self.assertEqual(check_container_check_digits(corrected, new_review)['status'], 'Passed')
        self.assertEqual(states, original)
        for key in values:
            self.assertEqual(new_review[key]['candidates'], original[key]['candidates'])
            self.assertEqual(new_review[key]['status'], 'extracted')

    def test_prefix_rejects_invalid_input(self):
        for prefix in [None, 'MEDU1000067', 'MEDX100006', 'medu100006']:
            with self.assertRaises(ValueError):
                calculate_check_digit(prefix)


if __name__ == '__main__':
    unittest.main()
