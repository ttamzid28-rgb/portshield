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


def validate_value(key, value, quote):
    if not all(isinstance(v, str) for v in (key, value, quote)):
        return '', 'Value and source quotation must be text.'
    value=value.strip()
    if key.endswith('_container'):
        value=re.sub(r'[\s-]','',value.upper())
        if not re.fullmatch(r'[A-Z]{3}[UJZ][0-9]{7}',value):
            return '', 'Container must have three owner letters, U/J/Z and seven digits; packaging text is not an identifier.'
        compact=re.sub(r'[\s-]','',quote.upper())
        if value not in compact:return '', 'Container value is absent from its source quotation.'
    elif key.endswith('_currency'):
        value=value.upper()
        if not re.fullmatch(r'[A-Z]{3}',value) or not re.search(r'\b'+re.escape(value)+r'\b',quote.upper()):
            return '', 'Explicit currency code missing from quotation.'
    elif key in ('lc_amount','invoice_total','invoice_quantity','packing_quantity','unit_price'):
        if not re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', value) or len(value)>100:
            return '', 'Expected an ungrouped plain decimal value.'
        amount=Decimal(value)
        if amount<=0:return '', 'Expected a positive finite number.'
        if not any(number==amount for number in _quoted_numbers(quote)):
            return '', 'Numeric value is absent or its source formatting is ambiguous; manual review required.'
        if key.endswith('_quantity') and re.search(r'number of (bags|packages|cartons)|packaging',quote,re.I) and not re.search(r'quantity',quote,re.I):
            return '', 'Package count or packaging specification needs separate quantity/unit review.'
    elif key in ('latest_shipment_date','on_board_date'):
        if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', value):
            return '', 'Expected a full ISO date (YYYY-MM-DD).'
        try:date.fromisoformat(value)
        except ValueError:return '', 'Invalid calendar date.'
        if key=='on_board_date' and re.search(r'\b(?:latest|last|deadline|expiry|expiration)\b', quote, re.I):
            return '', 'Quotation includes a deadline or expiry; cite the actual on-board date separately.'
        label = (r'latest[ -]+(?:date[ -]+of[ -]+)?shipment(?:[ -]+date)?|last[ -]+shipment(?:[ -]+date)?|shipment[ -]+deadline|44C'
                 if key=='latest_shipment_date' else
                 r'on[ -]?board(?:[ -]+date)?|date[ -]+of[ -]+shipment|shipment[ -]+date')
        if not re.search(r'\b(?:'+label+r')\b', quote, re.I):
            return '', 'Quotation lacks the required shipment-date label; manual review required.'
        if _quoted_date(quote)!=value:
            return '', 'Date is absent, ambiguous, or conflicts with its source quotation; manual review required.'
    return value,''
