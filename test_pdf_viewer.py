import copy
import pickle
import unittest
import pymupdf

from pdf_viewer import (
    render_page,
    get_page_count,
    extract_page_text,
    locate_quote_on_page,
    normalize_quote,
    normalize_ws,
    normalize_page_text,
    clear_cache,
    _load_documents,
    render_pdf_viewer,
    _CACHE_MAX,
)


def make_text_pdf(text: str) -> bytes:
    """Generate an in-memory PDF with the provided text on page 1."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 72), text, fontsize=12)
    data = doc.tobytes()
    doc.close()
    return data


def make_image_only_pdf() -> bytes:
    """Generate an in-memory PDF containing an image only (no text)."""
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=400)
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 100, 100), 1)
    pix.clear_with(255)
    page.insert_image(pymupdf.Rect(50, 50, 150, 150), pixmap=pix)
    data = doc.tobytes()
    doc.close()
    return data


def make_encrypted_pdf(text: str = "Confidential L/C details") -> bytes:
    """Generate an in-memory AES-256 encrypted PDF."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 72), text, fontsize=12)
    data = doc.tobytes(
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        owner_pw="owner123",
        user_pw="user123"
    )
    doc.close()
    return data


class PdfViewerUnitTests(unittest.TestCase):
    def setUp(self):
        clear_cache()

    def tearDown(self):
        clear_cache()

    def test_exact_quote_match(self):
        quote = "Invoice Total USD 25,000"
        pdf_bytes = make_text_pdf(f"Commercial Invoice\n{quote}\nChattogram Port")

        # 1. Page count & text
        count, err = get_page_count(pdf_bytes)
        self.assertEqual(count, 1)
        self.assertEqual(err, "")

        text, err = extract_page_text(pdf_bytes, 0)
        self.assertIn("Invoice Total USD 25,000", text)
        self.assertEqual(err, "")

        # 2. Locate quote
        result = locate_quote_on_page(pdf_bytes, 0, quote)
        self.assertTrue(result['found'])
        self.assertFalse(result['partial'])
        self.assertEqual(result['label'], "Quote located on page")

        # 3. Render page with highlight
        png, r_err = render_page(pdf_bytes, 0, highlight_quote=quote)
        self.assertEqual(r_err, "")
        self.assertTrue(len(png) > 100)
        self.assertEqual(png[:8], b'\x89PNG\r\n\x1a\n')

    def test_whitespace_broken_quote_match(self):
        # Text with multiple spaces, tabs, and newline between words
        page_content = "Latest shipment  date:\n    2026-11-10\nExpiry: 2026-12-01"
        pdf_bytes = make_text_pdf(page_content)

        quote = "Latest shipment date: 2026-11-10"
        result = locate_quote_on_page(pdf_bytes, 0, quote)
        self.assertTrue(result['found'])
        self.assertFalse(result['partial'])
        self.assertEqual(result['label'], "Quote located on page")

        # Verify rendering with whitespace-broken quote works without errors
        png, r_err = render_page(pdf_bytes, 0, highlight_quote=quote)
        self.assertEqual(r_err, "")
        self.assertTrue(len(png) > 100)

    def test_no_match_fallback(self):
        pdf_bytes = make_text_pdf("Packing List\nQuantity: 720 cartons\nTotal gross 18,000 KG")
        quote = "Invoice Total USD 999,999"

        result = locate_quote_on_page(pdf_bytes, 0, quote)
        self.assertFalse(result['found'])
        self.assertFalse(result['partial'])
        self.assertEqual(result['label'], "Quote not located visually")

        # Page rendering with unmatched quote must succeed without hallucinating highlights
        png, r_err = render_page(pdf_bytes, 0, highlight_quote=quote)
        self.assertEqual(r_err, "")
        self.assertTrue(len(png) > 100)

    def test_partial_match_label(self):
        pdf_bytes = make_text_pdf("Commercial Invoice\nTotal quantity 18000 KG\nUnit price USD 1.50")
        quote = "Total quantity 25000 Metric Tons"

        result = locate_quote_on_page(pdf_bytes, 0, quote)
        self.assertFalse(result['found'])
        self.assertTrue(result['partial'])
        self.assertEqual(result['label'], "Partial match only — visual verification required")

    def test_out_of_bounds_page(self):
        pdf_bytes = make_text_pdf("Single page doc")

        # Page index 5 on a 1-page document
        png, r_err = render_page(pdf_bytes, 5)
        self.assertEqual(png, b"")
        self.assertIn("out of bounds", r_err)

        # Negative page index
        png, r_err = render_page(pdf_bytes, -1)
        self.assertEqual(png, b"")
        self.assertIn("out of bounds", r_err)

        # Extract text out of bounds
        text, err = extract_page_text(pdf_bytes, 10)
        self.assertEqual(text, "")
        self.assertIn("out of bounds", err)

        # Locate quote out of bounds
        result = locate_quote_on_page(pdf_bytes, 10, "anything")
        self.assertFalse(result['found'])
        self.assertIn("out of bounds", result['error'])

    def test_encrypted_doc(self):
        enc_bytes = make_encrypted_pdf()

        # Page count
        count, err = get_page_count(enc_bytes)
        self.assertEqual(count, 0)
        self.assertIn("encrypted", err.lower())

        # Extract text
        text, err = extract_page_text(enc_bytes, 0)
        self.assertEqual(text, "")
        self.assertIn("encrypted", err.lower())

        # Render page
        png, err = render_page(enc_bytes, 0)
        self.assertEqual(png, b"")
        self.assertIn("encrypted", err.lower())

        # Locate quote
        res = locate_quote_on_page(enc_bytes, 0, "Confidential")
        self.assertFalse(res['found'])
        self.assertIn("encrypted", res['error'].lower())

    def test_image_only_scanned_page(self):
        scan_bytes = make_image_only_pdf()

        # Count is 1
        count, err = get_page_count(scan_bytes)
        self.assertEqual(count, 1)
        self.assertEqual(err, "")

        # Text is empty
        text, err = extract_page_text(scan_bytes, 0)
        self.assertEqual(text, "")
        self.assertEqual(err, "")

        # Locate quote on image-only page
        res = locate_quote_on_page(scan_bytes, 0, "Any quote text")
        self.assertFalse(res['found'])
        self.assertFalse(res['partial'])
        self.assertEqual(res['label'], "Image-only page — quote not locatable visually")

        # Renders successfully as an image
        png, err = render_page(scan_bytes, 0)
        self.assertEqual(err, "")
        self.assertTrue(len(png) > 100)

    def test_deepcopy_evidence_unmodified(self):
        """Prove that evidence and evidence['_field_states'] are byte-for-byte unmodified."""
        pdf_bytes = make_text_pdf("Invoice Total USD 25,000\nLatest shipment date 2026-11-10")

        evidence = {
            'invoice_total': 'Invoice total = 25000',
            'latest_shipment_date': 'Latest shipment date = 2026-11-10',
            '_field_states': {
                'invoice_total': {
                    'status': 'conflicting',
                    'reason': 'Multiple validated values; source review required.',
                    'candidates': [
                        {
                            'value': '25000',
                            'quote': 'Invoice Total USD 25,000',
                            'document': 1,
                            'page': 1,
                            'status': 'extracted',
                            'reason': '',
                            'validated_value': '25000',
                        },
                        {
                            'value': '27000',
                            'quote': 'Invoice Total USD 27,000',
                            'document': 1,
                            'page': 1,
                            'status': 'rejected',
                            'reason': 'Quotation not found on cited page.',
                            'validated_value': '',
                        },
                    ],
                    'review_status': 'pending',
                },
                'latest_shipment_date': {
                    'status': 'extracted',
                    'reason': 'Source-linked candidate; human confirmation required.',
                    'candidates': [
                        {
                            'value': '2026-11-10',
                            'quote': 'Latest shipment date 2026-11-10',
                            'document': 1,
                            'page': 1,
                            'status': 'extracted',
                            'reason': '',
                            'validated_value': '2026-11-10',
                        }
                    ],
                    'review_status': 'pending',
                },
                'unreadable_field': {
                    'status': 'unreadable',
                    'reason': 'Cited page has no independently readable text; visual confirmation required.',
                    'candidates': [
                        {
                            'value': '100',
                            'quote': 'Scanned text',
                            'document': 1,
                            'page': 1,
                            'status': 'unreadable',
                            'reason': 'Cited page has no independently readable text; visual confirmation required.',
                            'validated_value': '',
                        }
                    ],
                    'review_status': 'pending',
                }
            }
        }

        # Take independent deepcopy and binary pickle snapshot
        evidence_copy = copy.deepcopy(evidence)
        original_pickle = pickle.dumps(evidence)

        # Call inspect and rendering operations as viewer would
        doc_map = _load_documents([('invoice.pdf', pdf_bytes)])
        self.assertIn('invoice.pdf', doc_map)

        for field_name, fstate in evidence['_field_states'].items():
            for cand in fstate['candidates']:
                q = cand.get('quote')
                if q:
                    res = locate_quote_on_page(pdf_bytes, 0, q)
                    _ = render_page(pdf_bytes, 0, highlight_quote=q if res.get('found') else None)

        # Assert evidence structure and contents are byte-for-byte unmodified
        self.assertEqual(evidence, evidence_copy)
        self.assertEqual(pickle.dumps(evidence), original_pickle)
        self.assertEqual(evidence['_field_states'], evidence_copy['_field_states'])

    def test_cache_cap_and_eviction(self):
        clear_cache()
        doc = pymupdf.open()
        # Create a document with 70 pages to test cache cap of 64
        for i in range(70):
            p = doc.new_page(width=300, height=300)
            p.insert_text((50, 50), f"Page number {i + 1}")
        pdf_bytes = doc.tobytes()
        doc.close()

        # Render 70 distinct pages
        for i in range(70):
            png, err = render_page(pdf_bytes, i)
            self.assertEqual(err, "")
            self.assertTrue(len(png) > 0)

        # Cache size must not exceed _CACHE_MAX
        from pdf_viewer import _page_cache
        self.assertLessEqual(len(_page_cache), _CACHE_MAX)

    def test_duplicate_document_names_handled(self):
        pdf1 = make_text_pdf("Document Version A")
        pdf2 = make_text_pdf("Document Version B")

        # Two documents with the identical filename 'invoice.pdf' but different bytes
        docs = _load_documents([('invoice.pdf', pdf1), ('invoice.pdf', pdf2)])
        self.assertEqual(len(docs), 2)
        self.assertIn('invoice.pdf', docs)
        self.assertIn('invoice.pdf (1)', docs)

    def test_smoke_sample_documents(self):
        """Smoke-test the viewer against bundled sample_documents.zip."""
        import zipfile
        from pathlib import Path
        sample_path = Path(__file__).parent / 'sample_documents.zip'
        self.assertTrue(sample_path.exists())

        with zipfile.ZipFile(sample_path) as z:
            pdf_names = [n for n in z.namelist() if n.endswith('.pdf')]
            self.assertGreaterEqual(len(pdf_names), 4)

            for name in pdf_names:
                data = z.read(name)
                count, err = get_page_count(data)
                self.assertEqual(err, "")
                self.assertGreaterEqual(count, 1)

                text, t_err = extract_page_text(data, 0)
                self.assertEqual(t_err, "")
                self.assertTrue(len(text) > 0)

                png, r_err = render_page(data, 0)
                self.assertEqual(r_err, "")
                self.assertTrue(len(png) > 100)
                self.assertEqual(png[:8], b'\x89PNG\r\n\x1a\n')

            # Test finding known quotes from sample documents
            lc_bytes = z.read('lc.pdf')
            res = locate_quote_on_page(lc_bytes, 0, 'Lc Amount: 25000')
            self.assertTrue(res['found'])
            self.assertFalse(res['partial'])
            self.assertEqual(res['label'], 'Quote located on page')

            png_hl, hl_err = render_page(lc_bytes, 0, highlight_quote='Lc Amount: 25000')
            self.assertEqual(hl_err, "")
            self.assertTrue(len(png_hl) > 100)


if __name__ == '__main__':
    unittest.main()
