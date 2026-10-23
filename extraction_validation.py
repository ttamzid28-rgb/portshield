"""Conservative checks on model-proposed values; no benchmark answers or inference."""
import re
from decimal import Decimal, InvalidOperation
from datetime import date

def normalized(text):
    """Normalize prose spacing without turning numeric columns into grouped numbers."""
    def space(match):
        left = text[match.start()-1:match.start()]
        right = text[match.end():match.end()+1]
        if left.isdigit() and right.isdigit():
            if '\n' in match[0] or '\r' in match[0]:
                return '\n'
            if len(match[0]) > 1 or '\t' in match[0]:
                return '\t'
        return ' '
    return re.sub(r'\s+', space, text).strip().casefold()


# A maximal numeric run is parsed as a whole: never salvage a smaller number
# from malformed punctuation, an exponent, an identifier, or adjacent columns.
_NUMBER = re.compile(r'(?<![\w.,/+\-−])(?:[+\-−]?[0-9](?:[0-9., \u00a0\u202f]*[0-9])?)(?![\w.,/\-])')


def _source_number(token):
    token = token.replace('\u00a0', ' ').replace('\u202f', ' ')
    if len(token) > 100 or token.startswith(('-', '−')):
        return None
    token = token.removeprefix('+')
    canonical = None
    if ' ' in token:
        # One separator only; two spaces/tab/newline may delimit table cells.
        if re.fullmatch(r'[0-9]{1,3}(?: [0-9]{3})+(?:[.,][0-9]+)?', token):
            canonical = token.replace(' ', '').replace(',', '.')
    elif ',' in token and '.' in token:
        if re.fullmatch(r'[0-9]{1,3}(?:,[0-9]{3})+\.[0-9]+', token) or re.fullmatch(r'[0-9]{1,2}(?:,[0-9]{2})+,[0-9]{3}\.[0-9]+', token):
            canonical = token.replace(',', '')
        elif re.fullmatch(r'[0-9]{1,3}(?:\.[0-9]{3})+,[0-9]+', token):
            canonical = token.replace('.', '').replace(',', '.')
    elif ',' in token:
        if re.fullmatch(r'[0-9]{1,3}(?:,[0-9]{3})+', token) or re.fullmatch(r'[0-9]{1,2}(?:,[0-9]{2})+,[0-9]{3}', token):
            canonical = token.replace(',', '')
        elif re.fullmatch(r'[0-9]+,[0-9]{1,2}', token):
            canonical = token.replace(',', '.')
    elif re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', token):
        # 18.000 could be 18 or 18000. Without a locale, abstain.
        if re.fullmatch(r'[0-9]{1,3}\.[0-9]{3}', token):
            return None
        canonical = token
    if canonical is None:
        return None
    try:
        return Decimal(canonical)
    except InvalidOperation:
        return None


def _quoted_numbers(quote):
    # Prevent matching the positive interior of accounting negatives.
    for match in _NUMBER.finditer(quote):
        before = quote[:match.start()].rstrip()
        after = quote[match.end():].lstrip()
        if before.endswith('(') and after.startswith(')'):
            continue
        number = _source_number(match[0])
        if number is not None:
            yield number


_MONTHS = {name: i for i, names in enumerate([
    ('jan', 'january'), ('feb', 'february'), ('mar', 'march'),
    ('apr', 'april'), ('may',), ('jun', 'june'), ('jul', 'july'),
    ('aug', 'august'), ('sep', 'sept', 'september'), ('oct', 'october'),
    ('nov', 'november'), ('dec', 'december')], 1) for name in names}
_MONTH = '(?:' + '|'.join(sorted(_MONTHS, key=len, reverse=True)) + ')'
_DATE_NUMERIC = re.compile(r'(?<![\w/.-])([0-9]{1,4})([/.-])([0-9]{1,2})\2([0-9]{1,4})(?![\w/.-])')
_DATE_DMY = re.compile(r'\b([0-9]{1,2})[ -]+('+_MONTH+r')\.?[ ,\-]+([0-9]{4})\b', re.I)
_DATE_MDY = re.compile(r'\b('+_MONTH+r')\.?[ -]+([0-9]{1,2})(?:,)?[ -]+([0-9]{4})\b', re.I)


def _quoted_date(quote):
    dates = set()
    def add(year, month, day):
        try:
            dates.add(date(year, month, day).isoformat())
            return True
        except ValueError:
            return False
    for match in _DATE_NUMERIC.finditer(quote):
        first, _, middle, last = match.groups()
        a, b, c = int(first), int(middle), int(last)
        if len(first) == 4:
            if not add(a, b, c):return None
        elif len(last) == 4:
            if a <= 12 and b <= 12 and a != b:
                return None  # 10/11/2026 has two possible interpretations.
            if a > 12:
                if not add(c, b, a):return None
            else:
                if not add(c, a, b):return None
        else:
            return None  # Two-digit years require review.
    for match in _DATE_DMY.finditer(quote):
        day, month, year = match.groups()
        if not add(int(year), _MONTHS[month.lower()], int(day)):return None
    for match in _DATE_MDY.finditer(quote):
        month, day, year = match.groups()
        if not add(int(year), _MONTHS[month.lower()], int(day)):return None
    return next(iter(dates)) if len(dates) == 1 else None


PORT_FIELDS = {
    'lc_port_of_discharge',
    'bl_port_of_discharge',
    'bl_port_of_loading',
    'bl_place_of_delivery',
}

REGISTERED_CONTAINER_KEYS = {'packing_container', 'bl_container', 'pl_container_number', 'bl_container_number'}
REGISTERED_CURRENCY_KEYS = {'lc_currency', 'invoice_currency', 'ci_currency'}
REGISTERED_NUMERIC_KEYS = {
    'lc_amount', 'invoice_total', 'ci_invoice_total', 'invoice_quantity',
    'ci_quantity', 'packing_quantity', 'pl_quantity', 'pl_cargo_net_weight',
    'unit_price', 'ci_unit_price', 'pl_cargo_gross_weight', 'bl_cargo_gross_weight',
    'ci_cargo_net_weight',
}
REGISTERED_DATE_KEYS = {'latest_shipment_date', 'lc_latest_shipment_date', 'on_board_date', 'bl_on_board_date'}


def verify_quote_in_page_text(quote: str, page_text: str) -> bool:
    """Verify quote text is contained in page text layer (verbatim or normalized)."""
    if not quote or not page_text:
        return False
    return (
        quote.strip() in page_text
        or normalized(quote) in normalized(page_text)
    )


def verify_quote_in_pdf_page(pdf_bytes: bytes, page_number: int, quote: str) -> bool:
    """Verify quote text is an exact/normalized substring of the cited PDF page text layer via pymupdf."""
    if not pdf_bytes or not quote or page_number < 1:
        return False
    try:
        import pymupdf
        doc = pymupdf.open(stream=pdf_bytes, filetype='pdf')
        if page_number > len(doc):
            doc.close()
            return False
        page_text = doc[page_number - 1].get_text()
        doc.close()
        return verify_quote_in_page_text(quote, page_text)
    except Exception:
        return False


def collapse_whitespace(text: str) -> str:
    """Collapse all consecutive whitespace, newlines, and tabs into single spaces, and strip."""
    if not text:
        return ''
    return re.sub(r'\s+', ' ', text).strip()


DISCHARGE_ROLE_PATTERNS = (
    r'\bport\s+of\s+discharge\b',
    r'\bdischarge\s+port\b',
    r'\bdischarging\s+port\b',
    r'\bport\s+of\s+dest(?:ination)?\b',
    r'\bpod\b',
    r'(?<!\w)(?::\s*)?(?:tag\s*|field\s*)?44f(?::|\b)(?!\w)',
)
DISCHARGE_ROLE_LABELS = DISCHARGE_ROLE_PATTERNS

LOADING_ROLE_PATTERNS = (
    r'\bport\s+of\s+loading\b',
    r'\bloading\s+port\b',
    r'\bport\s+of\s+receipt\b',
    r'\bplace\s+of\s+receipt\b',
    r'\btaking\s+in\s+charge\b',
    r'\bpol\b',
    r'(?<!\w)(?::\s*)?(?:tag\s*|field\s*)?44e(?::|\b)(?!\w)',
    r'(?<!\w)(?::\s*)?(?:tag\s*|field\s*)?44a(?::|\b)(?!\w)',
)
LOADING_ROLE_LABELS = LOADING_ROLE_PATTERNS

DELIVERY_ROLE_PATTERNS = (
    r'\bplace\s+of\s+delivery\b',
    r'\bfinal\s+destination\b',
    r'\bdelivery\s+place\b',
    r'(?<!\w)(?::\s*)?(?:tag\s*|field\s*)?44b(?::|\b)(?!\w)',
)
DELIVERY_ROLE_LABELS = DELIVERY_ROLE_PATTERNS

FIELD_DELIMITER_RE = re.compile(r'\|+|;|/{2,}|\t')
OTHER_FIELD_HEADER_RE = re.compile(
    r'\b(?:notify\s+party|consignee|shipper|also\s+notify|vessel|voyage|'
    r'booking\s+(?:number|no)|bill\s+of\s+lading\s+(?:number|no)|'
    r'container\s+(?:number|no)|seal\s+(?:number|no)|'
    r'gross\s+weight|net\s+weight|description\s+of\s+goods)\s*:', re.I)


def parse_field_headers(text: str) -> list[dict]:
    """Identify the start and end offsets of all port role headers in normalized text."""
    raw_matches = []
    for pat in DISCHARGE_ROLE_PATTERNS:
        for m in re.finditer(pat, text, re.IGNORECASE):
            raw_matches.append({'role': 'discharge', 'start': m.start(), 'end': m.end()})
    for pat in LOADING_ROLE_PATTERNS:
        for m in re.finditer(pat, text, re.IGNORECASE):
            raw_matches.append({'role': 'loading', 'start': m.start(), 'end': m.end()})
    for pat in DELIVERY_ROLE_PATTERNS:
        for m in re.finditer(pat, text, re.IGNORECASE):
            raw_matches.append({'role': 'delivery', 'start': m.start(), 'end': m.end()})

    raw_matches.sort(key=lambda x: (x['start'], -(x['end'] - x['start'])))
    filtered = []
    for m in raw_matches:
        if not filtered:
            filtered.append(m)
            continue
        if m['start'] < filtered[-1]['end']:
            continue
        filtered.append(m)
    return filtered


def compute_field_spans(text: str) -> list[dict]:
    """Calculate explicit value spans bounded by subsequent headers or delimiters."""
    headers = parse_field_headers(text)
    spans = []
    for i, h in enumerate(headers):
        m_sep = re.match(r'[\s:\-=]+', text[h['end']:])
        span_start = h['end'] + (m_sep.end() if m_sep else 0)
        span_end = len(text)
        if i + 1 < len(headers):
            span_end = min(span_end, headers[i + 1]['start'])
        m_delim = FIELD_DELIMITER_RE.search(text, span_start, span_end)
        if m_delim:
            span_end = min(span_end, m_delim.start())

        other_header = OTHER_FIELD_HEADER_RE.search(text, span_start, span_end)
        if other_header:
            span_end = other_header.start()
        # An unrecognized labelled field makes the remaining span ambiguous.
        # Do not guess its boundary or borrow its value as the port.
        if ':' in text[span_start:span_end]:
            span_end = span_start

        # Trim whitespace from span boundaries
        while span_start < span_end and text[span_start].isspace():
            span_start += 1
        while span_end > span_start and text[span_end - 1].isspace():
            span_end -= 1

        spans.append({
            'role': h['role'],
            'header_start': h['start'],
            'header_end': h['end'],
            'span_start': span_start,
            'span_end': span_end,
            'span_text': text[span_start:span_end],
        })
    return spans


def check_port_quote_role(key: str, value: str, quote: str) -> tuple[bool, str]:
    """Verify that candidate value appears in the legitimate field context and within its explicit value span."""
    if not isinstance(value, str) or not isinstance(quote, str):
        return False, 'Value and source quotation must be text.'

    norm_val = collapse_whitespace(value)
    norm_quote = collapse_whitespace(quote)

    if not norm_val or not norm_quote:
        return False, 'Candidate value or quotation is empty.'

    if key in ('lc_port_of_discharge', 'bl_port_of_discharge'):
        target_role = 'discharge'
        target_label = 'Port of Discharge'
        conflicting_desc = 'Port of Loading / Place of Delivery'
    elif key == 'bl_port_of_loading':
        target_role = 'loading'
        target_label = 'Port of Loading'
        conflicting_desc = 'Port of Discharge / Place of Delivery'
    elif key == 'bl_place_of_delivery':
        target_role = 'delivery'
        target_label = 'Place of Delivery'
        conflicting_desc = 'Port of Loading / Port of Discharge'
    else:
        return False, f'Unregistered or unknown field: {key}'

    headers = parse_field_headers(norm_quote)
    has_target = any(h['role'] == target_role for h in headers)

    if not has_target:
        conflicting = [h['role'] for h in headers if h['role'] != target_role]
        if 'loading' in conflicting and target_role in ('discharge', 'delivery'):
            return False, f'Quotation belongs to Port of Loading context, not {target_label}.'
        if 'delivery' in conflicting and target_role in ('discharge', 'loading'):
            return False, f'Quotation belongs to Place of Delivery context, not {target_label}.'
        if 'discharge' in conflicting and target_role in ('loading', 'delivery'):
            return False, f'Quotation belongs to Port of Discharge context, not {target_label}.'
        if target_role == 'discharge':
            return False, 'Quotation lacks the required Port of Discharge label (e.g., Port of Discharge or Tag 44F).'
        elif target_role == 'loading':
            return False, 'Quotation lacks the required Port of Loading label.'
        elif target_role == 'delivery':
            return False, 'Quotation lacks the required Place of Delivery label.'

    val_lower = norm_val.casefold()
    quote_lower = norm_quote.casefold()

    val_pat = r'(?<!\w)' + re.escape(val_lower) + r'(?!\w)'
    val_matches = [(m.start(), m.end()) for m in re.finditer(val_pat, quote_lower)]

    if not val_matches:
        return False, 'Port value is absent from or not contained in source quotation.'

    spans = compute_field_spans(norm_quote)

    # 1. Check if any occurrence falls strictly within a target role span
    for m_start, m_end in val_matches:
        for sp in spans:
            if sp['role'] == target_role and sp['span_start'] == m_start and m_end <= sp['span_end']:
                return True, ''

    # 2. Check if any occurrence falls within a conflicting role span
    for m_start, m_end in val_matches:
        for sp in spans:
            if sp['role'] != target_role and sp['span_start'] <= m_start and m_end <= sp['span_end']:
                return False, f'Candidate value in quotation is qualified by a conflicting role label ({conflicting_desc}).'

    # 3. Check if candidate appears strictly before the target header
    first_target = min((h['start'] for h in headers if h['role'] == target_role), default=-1)
    if any(m_end <= first_target for m_start, m_end in val_matches):
        return False, f'Candidate value in quotation appears before the {target_label} label and belongs to preceding field context.'

    # 4. Outside target span or ambiguous
    return False, f'Candidate value in quotation is outside the {target_label} value span.'


def validate_value(key, value, quote):
    if not all(isinstance(v, str) for v in (key, value, quote)):
        return '', 'Value and source quotation must be text.'
    value=value.strip()
    if key.endswith('_container') or key.endswith('_container_number') or key in REGISTERED_CONTAINER_KEYS:
        value=re.sub(r'[\s-]','',value.upper())
        if not re.fullmatch(r'[A-Z]{3}[UJZ][0-9]{7}',value):
            return '', 'Container must have three owner letters, U/J/Z and seven digits; packaging text is not an identifier.'
        compact=re.sub(r'[\s-]','',quote.upper())
        if value not in compact:return '', 'Container value is absent from its source quotation.'
    elif key.endswith('_currency') or key in REGISTERED_CURRENCY_KEYS:
        value=value.upper()
        if not re.fullmatch(r'[A-Z]{3}',value) or not re.search(r'\b'+re.escape(value)+r'\b',quote.upper()):
            return '', 'Explicit currency code missing from quotation.'
    elif key in REGISTERED_NUMERIC_KEYS:
        if not re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', value) or len(value)>100:
            return '', 'Expected an ungrouped plain decimal value.'
        amount=Decimal(value)
        if amount<=0:return '', 'Expected a positive finite number.'
        if not any(number==amount for number in _quoted_numbers(quote)):
            return '', 'Numeric value is absent or its source formatting is ambiguous; manual review required.'
        if key.endswith('_quantity') and re.search(r'number of (bags|packages|cartons)|packaging',quote,re.I) and not re.search(r'quantity',quote,re.I):
            return '', 'Package count or packaging specification needs separate quantity/unit review.'
    elif key in REGISTERED_DATE_KEYS:
        if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', value):
            return '', 'Expected a full ISO date (YYYY-MM-DD).'
        try:date.fromisoformat(value)
        except ValueError:return '', 'Invalid calendar date.'
        if key in ('on_board_date', 'bl_on_board_date') and re.search(r'\b(?:latest|last|deadline|expiry|expiration)\b', quote, re.I):
            return '', 'Quotation includes a deadline or expiry; cite the actual on-board date separately.'
        label = (r'latest[ -]+(?:date[ -]+of[ -]+)?shipment(?:[ -]+date)?|last[ -]+shipment(?:[ -]+date)?|shipment[ -]+deadline|44C'
                 if key in ('latest_shipment_date', 'lc_latest_shipment_date') else
                 r'on[ -]?board(?:[ -]+date)?|date[ -]+of[ -]+shipment|shipment[ -]+date')
        if not re.search(r'\b(?:'+label+r')\b', quote, re.I):
            return '', 'Quotation lacks the required shipment-date label; manual review required.'
        if _quoted_date(quote)!=value:
            return '', 'Date is absent, ambiguous, or conflicts with its source quotation; manual review required.'
    elif key in PORT_FIELDS:
        val_clean = collapse_whitespace(value)
        quote_clean = collapse_whitespace(quote)
        if len(val_clean) < 3 or len(val_clean) > 120:
            return '', 'Port name must be between 3 and 120 characters.'
        if val_clean.casefold() not in quote_clean.casefold():
            return '', 'Port value is absent from or not contained in source quotation.'
        ok, role_err = check_port_quote_role(key, val_clean, quote_clean)
        if not ok:
            return '', role_err
        return val_clean, ''
    else:
        return '', f'Unregistered or unknown field: {key}'
    return value,''
