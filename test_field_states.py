import unittest
from field_states import collect_fields, review_fields
from checks import audit

class FieldStateTests(unittest.TestCase):
    def collect(self, entries, text='Invoice total 18000\nInvoice total 19000'):
        return collect_fields(entries, ['invoice_total','lc_amount'], [('invoice.pdf',b'')], {(1,1):text})
    def entry(self, value='18000', quote='Invoice total 18000'):
        return dict(field='invoice_total',value=value,quote=quote,document=1,page=1)
    def test_equivalent_decimals_do_not_conflict(self):
        values,evidence=self.collect([self.entry(),self.entry('18000.00')])
        self.assertEqual(evidence['_field_states']['invoice_total']['status'],'extracted')
        self.assertEqual(values['invoice_total'],'18000')

    def test_missing_is_not_confirmed(self):
        values,evidence=self.collect([])
        states=review_fields(values,evidence['_field_states'])
        self.assertEqual(states['invoice_total']['status'],'missing')
        self.assertEqual(states['invoice_total']['review_status'],'unresolved')
        self.assertTrue(all(r['status']=='Incomplete' for r in audit(values,states)))
    def test_conflict_stays_conflict_after_repeated_value(self):
        values,evidence=self.collect([self.entry(),self.entry('19000','Invoice total 19000'),self.entry()])
        self.assertEqual(values['invoice_total'],'')
        self.assertEqual(evidence['_field_states']['invoice_total']['status'],'conflicting')
        self.assertEqual(len(evidence['_field_states']['invoice_total']['candidates']),3)
    def test_rejected_candidate_not_hidden(self):
        for entries in [[self.entry('17000'),self.entry()],[self.entry(),self.entry('17000')]]:
            values,evidence=self.collect(entries)
            self.assertEqual(values['invoice_total'],'')
            self.assertEqual(evidence['_field_states']['invoice_total']['status'],'rejected')
    def test_scan_candidate_requires_visual_review(self):
        values,evidence=self.collect([self.entry()],text='')
        self.assertEqual(values['invoice_total'],'')
        self.assertEqual(evidence['_field_states']['invoice_total']['status'],'unreadable')
    def test_pending_cannot_pass_even_with_values(self):
        values,evidence=self.collect([self.entry()])
        values['lc_amount']='20000'
        self.assertTrue(all(r['status']=='Incomplete' for r in audit(values,evidence['_field_states'])))
        reviewed=review_fields(values,evidence['_field_states'])
        self.assertEqual(audit(values,reviewed)[3]['status'],'Passed')
        values['invoice_total']='17000'
        self.assertEqual(audit(values,reviewed)[3]['status'],'Incomplete')
    def test_manual_resolution_preserves_original_candidates(self):
        values,evidence=self.collect([self.entry('17000')])
        values['invoice_total']='18000'
        reviewed=review_fields(values,evidence['_field_states'])
        self.assertEqual(reviewed['invoice_total']['status'],'rejected')
        self.assertEqual(reviewed['invoice_total']['review_status'],'confirmed')
        self.assertEqual(reviewed['invoice_total']['candidates'][0]['value'],'17000')
    def test_null_malformed_and_invalid_page(self):
        for item in [self.entry(None),{**self.entry(),'page':True},{**self.entry(),'page':99}]:
            values,evidence=self.collect([item])
            self.assertEqual(evidence['_field_states']['invoice_total']['status'],'rejected')
        values,evidence=self.collect([None,{'field':[]}])
        self.assertEqual(evidence['_field_states']['invoice_total']['status'],'missing')

if __name__=='__main__':unittest.main()
