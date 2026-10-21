"""pdf_viewer.py — Read-only PDF evidence viewer for PortShield AI.

This module renders PDF pages from in-memory bytes using PyMuPDF (fitz),
visually highlights full-quote candidate matches on the page image, and
exposes a pure read-only Streamlit entry-point ``render_pdf_viewer()``.

Design invariants (enforced throughout):
- PURE READ-ONLY: never writes to st.session_state outside the 'pdfv_' namespace.
- STATE ISOLATION: viewer interactions never re-trigger extraction or reset
  unconfirmed human review edits.
- NO DISK WRITES: PDF bytes are read directly from in-memory session_state;
  no temporary files are written to disk.
- NO NETWORK CALLS: all rendering, text extraction, and matching are purely local.
- SECRET-SAFE: no API keys, credentials, or confidential document text are logged.
- HONEST HIGHLIGHTING: highlights only full-quote matches on the page image.
  Partial matches are labelled explicitly; no hallucinations or implied compliance.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
import zipfile
from pathlib import Path
from typing import Optional

try:
    import streamlit as st
    _ST_AVAILABLE = True
except ImportError:
    _ST_AVAILABLE = False

# Rendering configuration
_DPI = 150
_MATRIX_SCALE = _DPI / 72.0
_CACHE_MAX = 64

_MULTI_SPACE_RE = re.compile(r'[^\S\n]{2,}')
_NBSP_RE = re.compile(r'[\u00a0\u202f\u2009\u2007]')
_HIGHLIGHT_STROKE = (1.0, 0.85, 0.0)  # Amber / Yellow highlight


def _fitz():
    """Import and return pymupdf (fitz)."""
    try:
        import pymupdf
        return pymupdf
    except ImportError:
        try:
            import fitz
            return fitz
        except ImportError as exc:
            raise ImportError(
                "PyMuPDF is required for the PDF evidence viewer. "
                "Install it with: pip install pymupdf"
            ) from exc


def normalize_ws(text: str) -> str:
    """Collapse irregular whitespace on a single line (preserves newlines)."""
    if not text:
        return ""
    text = unicodedata.normalize('NFC', text)
    text = _NBSP_RE.sub(' ', text)
    text = _MULTI_SPACE_RE.sub(' ', text)
    return text


def normalize_page_text(text: str) -> str:
    """Normalize page text for whitespace-agnostic comparison."""
    if not text:
        return ""
    lines = text.split('\n')
    return '\n'.join(normalize_ws(line) for line in lines)


def normalize_quote(quote: str) -> str:
    """Collapse all whitespace and line breaks into single ordinary spaces."""
    if not quote:
        return ""
    q = quote.replace('\n', ' ').replace('\r', ' ')
    q = _NBSP_RE.sub(' ', q)
    q = _MULTI_SPACE_RE.sub(' ', q)
    return unicodedata.normalize('NFC', q).strip()


def _pdf_hash(pdf_bytes: bytes) -> str:
    """Compute SHA-256 of the PDF bytes for cache indexing."""
    return hashlib.sha256(pdf_bytes).hexdigest()


# In-memory LRU cache dictionary: (hash, page_index, highlight_key) -> png_bytes
_page_cache: dict[tuple[str, int, Optional[str]], bytes] = {}


def clear_cache() -> None:
    """Clear the in-memory page pixmap cache."""
    _page_cache.clear()


def get_page_count(pdf_bytes: bytes) -> tuple[int, str]:
    """Return (page_count, error_msg); page_count is 0 on error."""
    if not pdf_bytes:
        return 0, "Document bytes are empty."
    fitz = _fitz()
    doc = None
    try:
        doc = fitz.open(stream=pdf_bytes, filetype='pdf')
        if doc.is_encrypted:
            return 0, "Document is encrypted."
        return len(doc), ""
    except Exception as exc:
        return 0, f"Cannot open document: {type(exc).__name__}: {exc}"
    finally:
        if doc is not None:
            try:
                doc.close()
            except Exception:
                pass


def extract_page_text(pdf_bytes: bytes, page_index: int) -> tuple[str, str]:
    """Extract plain text from a 0-based page index. Returns (text, error_msg)."""
    if not pdf_bytes:
        return "", "Document bytes are empty."
    fitz = _fitz()
    doc = None
    try:
        doc = fitz.open(stream=pdf_bytes, filetype='pdf')
        if doc.is_encrypted:
            return "", "Document is encrypted."
        if page_index < 0 or page_index >= len(doc):
            return "", f"Page {page_index + 1} is out of bounds (document has {len(doc)} pages)."
        page = doc[page_index]
        return page.get_text(), ""
    except Exception as exc:
        return "", f"Text extraction error: {type(exc).__name__}: {exc}"
    finally:
        if doc is not None:
            try:
                doc.close()
            except Exception:
                pass


def find_quote_rects(page, quote: str) -> list:
    """Locate rectangle bounding boxes for a full quote on a fitz.Page.

    Handles whitespace differences and multi-line quotations.
    Returns a list of fitz.Rect instances, or [] if no full match exists.
    """
    if not quote or not quote.strip():
        return []

    norm_quote = normalize_quote(quote)
    if not norm_quote:
        return []

    # 1. Search for normalized single-spaced quote
    rects = page.search_for(norm_quote)
    if rects:
        return rects

    # 2. Search for exact quote if different
    raw_stripped = quote.strip()
    if raw_stripped != norm_quote:
        rects = page.search_for(raw_stripped)
        if rects:
            return rects

    # 3. Search collapsing tabs and excessive spacing
    collapsed = re.sub(r'\s+', ' ', raw_stripped)
    if collapsed != norm_quote and collapsed != raw_stripped:
        rects = page.search_for(collapsed)
        if rects:
            return rects

    return []


def locate_quote_on_page(pdf_bytes: bytes, page_index: int, quote: str) -> dict:
    """Check whether candidate quote can be visually matched on the cited page.

    Returns dict with keys:
    - 'found': bool (True ONLY if full quote is located)
    - 'partial': bool (True if significant partial tokens match)
    - 'rects_count': int
    - 'error': str
    - 'label': str (honest label for human reviewer)
    """
    if not quote or not quote.strip():
        return {
            'found': False, 'partial': False, 'rects_count': 0,
            'error': '', 'label': 'No quotation provided.'
        }

    page_text, err = extract_page_text(pdf_bytes, page_index)
    if err:
        return {
            'found': False, 'partial': False, 'rects_count': 0,
            'error': err, 'label': f'Cannot inspect page: {err}'
        }

    # If page has no text, it is an image-only or scanned page
    if not page_text.strip():
        return {
            'found': False, 'partial': False, 'rects_count': 0,
            'error': '', 'label': 'Image-only page — quote not locatable visually'
        }

    # Open document to search page rects
    fitz = _fitz()
    doc = None
    try:
        doc = fitz.open(stream=pdf_bytes, filetype='pdf')
        if doc.is_encrypted:
            return {
                'found': False, 'partial': False, 'rects_count': 0,
                'error': 'Document is encrypted.', 'label': 'Document is encrypted.'
            }
        if page_index < 0 or page_index >= len(doc):
            return {
                'found': False, 'partial': False, 'rects_count': 0,
                'error': f'Page {page_index + 1} is out of bounds (document has {len(doc)} pages).',
                'label': f'Page {page_index + 1} is out of bounds.'
            }

        page = doc[page_index]
        rects = find_quote_rects(page, quote)
        if rects:
            return {
                'found': True, 'partial': False, 'rects_count': len(rects),
                'error': '', 'label': 'Quote located on page'
            }

        # Full quote not located: check if genuine multi-token partial match exists
        norm_page = normalize_page_text(page_text).lower()
        norm_q = normalize_quote(quote).lower()
        tokens = [t for t in re.split(r'\s+', norm_q) if len(t) >= 4]
        matched_tokens = [t for t in tokens if t in norm_page]
        
        # Require at least 2 tokens to avoid false positives on generic single words
        min_required = max(2, len(tokens) // 2) if len(tokens) >= 2 else 1
        if matched_tokens and len(matched_tokens) >= min_required:
            return {
                'found': False, 'partial': True, 'rects_count': 0,
                'error': '', 'label': 'Partial match only — visual verification required'
            }

        return {
            'found': False, 'partial': False, 'rects_count': 0,
            'error': '', 'label': 'Quote not located visually'
        }
    except Exception as exc:
        return {
            'found': False, 'partial': False, 'rects_count': 0,
            'error': str(exc), 'label': f'Search error: {exc}'
        }
    finally:
        if doc is not None:
            try:
                doc.close()
            except Exception:
                pass


def render_page(
    pdf_bytes: bytes,
    page_index: int,
    highlight_quote: Optional[str] = None
) -> tuple[bytes, str]:
    """Render a 0-indexed page to PNG bytes.

    Clamps resolution to 150 DPI.
    Applies visual highlight ONLY when a full quote match is located.
    Results are cached in memory capped at _CACHE_MAX entries.

    Returns:
        (png_bytes, error_message)
    """
    if not pdf_bytes:
        return b"", "Document bytes are empty."

    fitz = _fitz()
    pdf_h = _pdf_hash(pdf_bytes)

    # Determine highlight key for caching
    norm_hl = normalize_quote(highlight_quote) if highlight_quote else None
    cache_key = (pdf_h, page_index, norm_hl)

    if cache_key in _page_cache:
        return _page_cache[cache_key], ""

    doc = None
    try:
        doc = fitz.open(stream=pdf_bytes, filetype='pdf')
        if doc.is_encrypted:
            return b"", "Document is encrypted; cannot render."
        if page_index < 0 or page_index >= len(doc):
            return b"", f"Page {page_index + 1} is out of bounds (document has {len(doc)} pages)."

        page = doc[page_index]

        # Highlight full quote matches only
        if norm_hl:
            rects = find_quote_rects(page, norm_hl)
            for r in rects:
                annot = page.add_highlight_annot(r)
                if annot is not None:
                    annot.set_colors(stroke=_HIGHLIGHT_STROKE)
                    annot.update()

        mat = fitz.Matrix(_MATRIX_SCALE, _MATRIX_SCALE)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        png = pix.tobytes("png")
        pix = None  # Free pixmap immediately
    except Exception as exc:
        return b"", f"Rendering error: {type(exc).__name__}: {exc}"
    finally:
        if doc is not None:
            try:
                doc.close()
            except Exception:
                pass

    # Enforce LRU cache cap
    if len(_page_cache) >= _CACHE_MAX:
        oldest_key = next(iter(_page_cache))
        del _page_cache[oldest_key]

    _page_cache[cache_key] = png
    return png, ""


def _load_documents(uploaded_files) -> dict[str, bytes]:
    """Load documents map name -> bytes from uploaded_files or bundled samples."""
    docs: dict[str, bytes] = {}
    if uploaded_files:
        for f in uploaded_files:
            try:
                if hasattr(f, 'getvalue') and hasattr(f, 'name'):
                    data = f.getvalue()
                    name = f.name
                elif isinstance(f, tuple) and len(f) == 2:
                    name, data = f
                else:
                    continue
                if data:
                    # Handle duplicate document names gracefully
                    base_name = name
                    counter = 1
                    while name in docs and docs[name] != data:
                        name = f"{base_name} ({counter})"
                        counter += 1
                    docs[name] = data
            except Exception:
                pass

    if not docs:
        # Graceful fallback to bundled sample PDFs for demo / smoke test
        sample_zip = Path(__file__).parent / 'sample_documents.zip'
        if sample_zip.exists():
            try:
                with zipfile.ZipFile(sample_zip) as z:
                    for name in z.namelist():
                        if name.endswith('.pdf'):
                            docs[name] = z.read(name)
            except Exception:
                pass

    return docs


def render_pdf_viewer(
    uploaded_files: list,
    evidence: dict,
) -> None:
    """Render the read-only PDF evidence viewer in Streamlit.

    Strictly conforms to:
    1. Read-only: never modifies fields or review status.
    2. State isolation: all viewer session_state keys start with 'pdfv_'.
    3. Multi-candidate provenance: lists ALL candidates with validation status.
    4. Memory & Performance: in-memory rendering, DPI clamp, LRU cache.
    """
    if not _ST_AVAILABLE:
        raise RuntimeError("Streamlit is required for render_pdf_viewer().")

    st.markdown("---")
    st.subheader("📄 PDF Evidence Viewer")
    st.caption(
        "Visual verification workbench. Highlighting indicates exact text quotations. "
        "Viewer is strictly read-only and does not confirm, modify, or auto-resolve field statuses."
    )

    docs = _load_documents(uploaded_files)
    if not docs:
        st.info("Upload PDF documents in **Document intake** to inspect visual evidence.")
        return

    doc_names = list(docs.keys())

    # Safely inspect field states from evidence (read-only, never mutate)
    field_states: dict = {}
    if isinstance(evidence, dict) and isinstance(evidence.get('_field_states'), dict):
        field_states = evidence['_field_states']

    # Initialize namespaced session state keys
    if 'pdfv_doc_index' not in st.session_state:
        st.session_state['pdfv_doc_index'] = 0
    if 'pdfv_page_number' not in st.session_state:
        st.session_state['pdfv_page_number'] = 1
    if 'pdfv_selected_field' not in st.session_state:
        st.session_state['pdfv_selected_field'] = '(none — browse only)'
    if 'pdfv_selected_candidate' not in st.session_state:
        st.session_state['pdfv_selected_candidate'] = 0

    # Ensure document index is within bounds
    current_doc_idx = min(max(0, st.session_state['pdfv_doc_index']), len(doc_names) - 1)
    st.session_state['pdfv_doc_index'] = current_doc_idx
    current_doc_name = doc_names[current_doc_idx]
    current_pdf_bytes = docs[current_doc_name]

    # Two-column layout: Navigation & Provenance (Left) | Visual Page (Right)
    left_col, right_col = st.columns([1, 2])

    with left_col:
        # Document selection
        sel_doc = st.selectbox(
            "Document",
            options=doc_names,
            index=current_doc_idx,
            key='pdfv_doc_selector',
        )
        new_doc_idx = doc_names.index(sel_doc)
        if new_doc_idx != st.session_state['pdfv_doc_index']:
            st.session_state['pdfv_doc_index'] = new_doc_idx
            st.session_state['pdfv_page_number'] = 1
            st.session_state['pdfv_selected_candidate'] = 0
            current_doc_idx = new_doc_idx
            current_doc_name = sel_doc
            current_pdf_bytes = docs[sel_doc]

        # Inspect page count
        page_count, pc_err = get_page_count(current_pdf_bytes)
        if pc_err:
            st.error(f"Cannot inspect document: {pc_err}")
            return
        if page_count == 0:
            st.warning("Document has no readable pages.")
            return

        st.caption(f"Total: **{page_count}** page(s)")

        # Page navigation with bounds check
        current_page_val = min(max(1, st.session_state['pdfv_page_number']), page_count)
        page_input = st.number_input(
            "Page",
            min_value=1,
            max_value=page_count,
            value=current_page_val,
            step=1,
            key='pdfv_page_input',
        )
        st.session_state['pdfv_page_number'] = int(page_input)
        active_page_index = int(page_input) - 1

        st.divider()

        # Field provenance selector
        st.markdown("**Field Provenance & Candidates**")
        field_options = ['(none — browse only)']
        if field_states:
            field_options.extend(sorted(field_states.keys()))

        cur_field = st.session_state.get('pdfv_selected_field', '(none — browse only)')
        f_idx = field_options.index(cur_field) if cur_field in field_options else 0
        sel_field = st.selectbox(
            "Select Field",
            options=field_options,
            index=f_idx,
            key='pdfv_field_selector',
        )
        if sel_field != st.session_state['pdfv_selected_field']:
            st.session_state['pdfv_selected_field'] = sel_field
            st.session_state['pdfv_selected_candidate'] = 0

        active_quote: Optional[str] = None
        match_result: Optional[dict] = None

        if sel_field and sel_field != '(none — browse only)' and sel_field in field_states:
            field_record = field_states[sel_field]
            f_status = field_record.get('status', 'unknown')
            f_reason = field_record.get('reason', '')
            candidates = field_record.get('candidates', [])

            st.markdown(f"**Extraction State:** `{f_status}`")
            if f_reason:
                st.caption(f"State rationale: {f_reason}")

            if not candidates:
                st.info("No candidates returned for this field.")
            else:
                st.markdown(f"**Candidates ({len(candidates)}):**")
                cand_labels = []
                for idx, cand in enumerate(candidates):
                    val = cand.get('value') or '(blank)'
                    c_stat = cand.get('status', 'unknown')
                    c_doc = cand.get('document')
                    c_pg = cand.get('page')
                    doc_desc = ""
                    if isinstance(c_doc, int) and 1 <= c_doc <= len(doc_names):
                        doc_desc = f" in {doc_names[c_doc - 1]} p.{c_pg}"
                    cand_labels.append(f"[{idx + 1}] {val} — {c_stat}{doc_desc}")

                selected_cand_idx = min(
                    st.session_state['pdfv_selected_candidate'],
                    len(candidates) - 1
                )
                chosen_cand_idx = st.radio(
                    "Choose Candidate",
                    options=list(range(len(candidates))),
                    format_func=lambda i: cand_labels[i],
                    index=selected_cand_idx,
                    key='pdfv_candidate_radio',
                )
                st.session_state['pdfv_selected_candidate'] = chosen_cand_idx
                active_cand = candidates[chosen_cand_idx]

                # Detailed Candidate Card
                st.markdown("---")
                st.markdown("**Candidate Details**")
                c_status_label = active_cand.get('status', 'unknown')
                st.write(f"• **Status:** `{c_status_label}`")
                if active_cand.get('reason'):
                    st.write(f"• **Reason:** {active_cand['reason']}")
                st.write(f"• **Raw Value:** {active_cand.get('value') or '(blank)'}")
                if active_cand.get('validated_value'):
                    st.write(f"• **Validated Value:** {active_cand['validated_value']}")

                # Candidate Cited Location
                c_doc = active_cand.get('document')
                c_pg = active_cand.get('page')
                if isinstance(c_doc, int) and 1 <= c_doc <= len(doc_names):
                    target_doc_name = doc_names[c_doc - 1]
                    st.write(f"• **Cited Document:** {target_doc_name} (Page {c_pg})")
                    if target_doc_name != current_doc_name or (isinstance(c_pg, int) and c_pg != current_page_val):
                        if st.button("📍 Jump to Cited Location", key='pdfv_jump_btn'):
                            st.session_state['pdfv_doc_index'] = c_doc - 1
                            if isinstance(c_pg, int) and c_pg >= 1:
                                st.session_state['pdfv_page_number'] = c_pg
                            st.rerun()

                cand_quote = active_cand.get('quote')
                if cand_quote and str(cand_quote).strip():
                    active_quote = str(cand_quote).strip()
                    st.markdown("**Cited Quotation:**")
                    st.code(active_quote, language=None)

                    # Locate quote on current page
                    match_result = locate_quote_on_page(
                        current_pdf_bytes,
                        active_page_index,
                        active_quote
                    )

                    if match_result.get('found'):
                        st.success(f"✅ {match_result['label']}")
                    elif match_result.get('partial'):
                        st.warning(f"🔶 {match_result['label']}")
                    elif match_result.get('error'):
                        st.error(f"⚠️ {match_result['label']}")
                    else:
                        st.error(f"❌ {match_result['label']}")
                else:
                    st.caption("No text quotation cited for this candidate.")

    with right_col:
        st.markdown(f"**Viewing:** `{current_doc_name}` — Page {active_page_index + 1} of {page_count}")

        # Highlight quote on the page ONLY if it represents a full match
        highlight_for_render = active_quote if (match_result and match_result.get('found')) else None

        png_data, r_err = render_page(
            current_pdf_bytes,
            active_page_index,
            highlight_quote=highlight_for_render
        )

        if r_err:
            st.error(f"Rendering failed: {r_err}")
        elif png_data:
            st.image(
                png_data,
                use_container_width=True,
                caption=f"{current_doc_name} — Page {active_page_index + 1}"
            )
            if match_result:
                if match_result.get('found'):
                    st.caption("🟡 Yellow highlight indicates full exact quotation match on this page.")
                elif match_result.get('partial'):
                    st.caption("🔶 Partial match only: some keywords match page text. Full quote could not be located; visual human verification required.")
                elif not match_result.get('error'):
                    st.caption("❌ Quote not located visually on this page. Verify document and page citations.")
        else:
            st.warning("Page rendered as empty image.")
