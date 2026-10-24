"""Field lifecycle: retain extraction state separately from human confirmation."""
from extraction_validation import normalized, validate_value
from decimal import Decimal


def collect_fields(entries, field_names, packet, page_text):
    states = {k: {'status': 'missing', 'reason': 'No value returned; source absence is not established.',
                  'candidates': [], 'review_status': 'pending'} for k in field_names}
    evidence = {}
    for item in entries:
        if not isinstance(item, dict) or not isinstance(item.get('field'), str) or item['field'] not in states:
            evidence['_rejected'] = evidence.get('_rejected', '') + ' Unrecognized or malformed field entry omitted.'
            continue
        key = item['field']; record = states[key]
        value, quote = item.get('value'), item.get('quote')
        doc, page = item.get('document'), item.get('page')
        if isinstance(doc, str) and doc.isdigit(): doc = int(doc)
        if isinstance(page, str) and page.isdigit(): page = int(page)
        if type(value) is int: value = str(value)
        reason = ''; status = 'extracted'
        if not isinstance(value, str) or not isinstance(quote, str) or not value.strip() or not quote.strip():
            reason = 'Missing or malformed candidate value/quotation.'
        elif type(doc) is not int or type(page) is not int or (doc, page) not in page_text:
            reason = 'Invalid source document/page.'
        elif not page_text[(doc, page)].strip():
            status = 'unreadable'; reason = 'Cited page has no independently readable text; visual confirmation required.'
        elif type(doc) is int and 1 <= doc <= len(packet) and packet[doc-1][1].startswith(b'%PDF'):
            from extraction_validation import verify_quote_in_pdf_page
            if not verify_quote_in_pdf_page(packet[doc-1][1], page, quote):
                reason = 'Quotation not found on cited page.'
            else:
                value, reason = validate_value(key, value, quote)
        elif normalized(quote) not in normalized(page_text[(doc, page)]):
            reason = 'Quotation not found on cited page.'
        else:
            value, reason = validate_value(key, value, quote)
        if reason and status != 'unreadable': status = 'rejected'
        cand = {
            'value': item.get('value'),
            'quote': quote,
            'document': doc,
            'page': page,
            'document_type': item.get('document_type', ''),
            'char_offsets': item.get('char_offsets'),
            'status': status,
            'reason': reason,
            'validated_value': value if status == 'extracted' else ''
        }
        record['candidates'].append(cand)
        if reason:evidence['_rejected'] = evidence.get('_rejected', '') + f' {key}: {reason}'
        if type(doc) is int and 1 <= doc <= len(packet):
            evidence[key] = evidence.get(key, '') + f'\n{packet[doc-1][0]} · page {page} · AI-cited text (verify): {str(quote)[:1000]}'
    # Bind paired fields to the same validated source entry, never just matching numbers.
    from extraction_validation import gross_weight_pair
    for prefix in ('pl', 'bl'):
        amount_key = prefix + '_cargo_gross_weight'
        unit_key = amount_key + '_unit'
        if amount_key not in states or unit_key not in states:
            continue
        groups = []
        for key in (amount_key, unit_key):
            candidates = states[key]['candidates']
            for candidate in candidates:
                if candidate['status'] == 'extracted':
                    pair = gross_weight_pair(candidate['quote'])
                    candidate['weight_source'] = {
                        **pair, 'document': candidate['document'], 'page': candidate['page']}
            groups.append(candidates)
        for candidates, partners in (groups, groups[::-1]):
            for candidate in candidates:
                if candidate['status'] != 'extracted':
                    continue
                if not any(p.get('weight_source') == candidate['weight_source']
                           and p['status'] == 'extracted' for p in partners):
                    candidate.update(status='rejected', validated_value='',
                                     reason='Weight amount and unit do not share a verified source entry.')
                    evidence['_rejected'] = evidence.get('_rejected', '') + ' ' + candidate['reason']
    values = {}
    for key, record in states.items():
        candidates = record['candidates']
        valid = {c['validated_value'] for c in candidates if c['status'] == 'extracted'}
        comparable = {Decimal(v) for v in valid} if key in {'invoice_total','lc_amount','invoice_quantity','packing_quantity','unit_price','pl_cargo_gross_weight','bl_cargo_gross_weight'} else valid
        if len(comparable) > 1:record.update(status='conflicting', reason='Multiple validated values; source review required.')
        elif any(c['status'] == 'rejected' for c in candidates):record.update(status='rejected', reason='At least one candidate failed validation; inspect candidate reasons.')
        elif any(c['status'] == 'unreadable' for c in candidates):record.update(status='unreadable', reason='Source text cannot independently verify a candidate.')
        elif valid:record.update(status='extracted', reason='Source-linked candidate; human confirmation required.')
        values[key] = next(c['validated_value'] for c in candidates if c['status'] == 'extracted') if record['status'] == 'extracted' else ''
    evidence['_field_states'] = states
    return values, evidence


def review_fields(values, states):
    return {k: {**states.get(k, {'status': 'manual', 'reason': 'Manual entry', 'candidates': []}),
                'review_status': 'confirmed' if str(v or '').strip() else 'unresolved',
                'reviewed_value': str(v or '').strip()} for k, v in values.items()}


def usable_values(values, states):
    if states is None:return values
    return {k: v if states.get(k, {}).get('review_status') == 'confirmed'
            and states[k].get('reviewed_value') == str(v or '').strip() else '' for k, v in values.items()}

