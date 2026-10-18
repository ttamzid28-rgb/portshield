import unittest
from extraction_validation import validate_value

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

if __name__=='__main__':unittest.main()
