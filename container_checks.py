"""ISO 6346 identifier integrity; no registry or physical-container verification."""
import re

RULE = 'Container check digit (ISO 6346)'
LETTER_VALUES = dict(zip('ABCDEFGHIJKLMNOPQRSTUVWXYZ',
    (10,12,13,14,15,16,17,18,19,20,21,23,24,25,26,27,28,29,30,31,32,34,35,36,37,38)))


def normalize_container(value):
    # Presentation normalization only; never substitute OCR characters.
    if not isinstance(value, str):
        return ''
    if not value.isascii():
        return value  # Unicode lookalikes must fail format validation.
    return re.sub(r'[\s-]', '', value.upper())


def calculate_check_digit(prefix):
    """Accept exactly owner (3), category (U/J/Z), serial (6)."""
    if not isinstance(prefix, str) or not re.fullmatch(r'[A-Z]{3}[UJZ][0-9]{6}', prefix):
        raise ValueError('Expected a canonical ten-character ISO 6346 prefix')
    total = sum((int(c) if c.isdigit() else LETTER_VALUES[c]) * (2 ** i)
                for i, c in enumerate(prefix))
    return (total % 11) % 10


def check_container_check_digits(values, field_states=None):
    from field_states import usable_values
    usable = usable_values(values, field_states)
    details, missing, invalid = [], False, False
    for key, label in (('packing_container', 'Packing List'), ('bl_container', 'Bill of Lading')):
        raw = usable.get(key)
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            missing = True
            details.append(f'{label}: missing or not confirmed at its current value.')
            continue
        normalized = normalize_container(raw)
        if not re.fullmatch(r'[A-Z]{3}[UJZ][0-9]{7}', normalized):
            invalid = True
            details.append(f'{label}: {raw!r} has invalid ISO 6346 format; verify against the shipping record.')
            continue
        stated, calculated = int(normalized[-1]), calculate_check_digit(normalized[:10])
        invalid |= stated != calculated
        details.append(f'{label}: {raw!r}; normalized {normalized}; stated digit {stated}, calculated digit {calculated}.')
    status = 'Insufficient data' if missing else 'Review required' if invalid else 'Passed'
    return {'check': RULE, 'status': status,
            'evidence': ' '.join(details) + ' Identifier integrity only; registration, existence and ownership are not verified. No automatic correction.'}
