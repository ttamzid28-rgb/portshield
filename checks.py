from decimal import Decimal, InvalidOperation
from datetime import date

def audit(d, field_states=None):
    from field_states import usable_values
    d = usable_values(d, field_states)
    findings=[]
    def add(rule, status, evidence):
        findings.append({'check':rule,'status':status,'evidence':evidence})
    def compare(rule,a,b):
        x,y=d.get(a),d.get(b)
        if x in (None,'') or y in (None,''): add(rule,'Incomplete',f'{a}={x}; {b}={y}')
        else: add(rule,'Passed' if str(x).strip().upper()==str(y).strip().upper() else 'Review required',f'{a}={x}; {b}={y}')
    compare('Currency','lc_currency','invoice_currency')
    compare('Quantity (same unit required)','invoice_quantity','packing_quantity')
    compare('Container identifier','packing_container','bl_container')
    for rule, keys in [('Invoice amount within configured limit',['invoice_total','lc_amount']),('Invoice arithmetic',['invoice_total','invoice_quantity','unit_price'])]:
        try:
            v=[Decimal(str(d[k])) for k in keys]
            ok=v[0]<=v[1] if len(v)==2 else v[0]==v[1]*v[2]
            add(rule,'Passed' if ok else 'Review required','; '.join(f'{k}={d[k]}' for k in keys))
        except (KeyError,InvalidOperation,ValueError): add(rule,'Incomplete','Required numeric field missing or unreadable')
    try:
        ship=date.fromisoformat(d['on_board_date']); latest=date.fromisoformat(d['latest_shipment_date'])
        add('Shipment deadline','Passed' if ship<=latest else 'Review required',f'On board: {ship}; latest: {latest}')
    except (KeyError,ValueError,TypeError): add('Shipment deadline','Incomplete','Dates must be present in YYYY-MM-DD format')
    return findings
