"""Conservative checks on model-proposed values; no benchmark answers or inference."""
import re
from decimal import Decimal, InvalidOperation
from datetime import datetime

def normalized(text):
    return ' '.join(text.split()).casefold()

def validate_value(key, value, quote):
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
        try:
            amount=Decimal(value)
            if not amount.is_finite() or amount<=0:return '', 'Expected a positive finite number.'
            candidates=re.findall(r'(?<![\w.])\d+(?:,\d{3})*(?:\.\d+)?(?![\w.])',quote)
            if not any(Decimal(n.replace(',',''))==amount for n in candidates):
                return '', 'Numeric value is absent from its source quotation.'
        except InvalidOperation:return '', 'Invalid numeric value.'
        if key.endswith('_quantity') and re.search(r'number of (bags|packages|cartons)|packaging',quote,re.I) and not re.search(r'quantity',quote,re.I):
            return '', 'Package count or packaging specification needs separate quantity/unit review.'
    elif key in ('latest_shipment_date','on_board_date'):
        try:datetime.strptime(value,'%Y-%m-%d')
        except ValueError:return '', 'Invalid ISO date.'
    return value,''
