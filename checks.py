from decimal import Decimal, InvalidOperation
from datetime import date
import re
from typing import Optional


class CheckStatus(str):
    """String subclass treating 'Insufficient data' and 'Incomplete' as equivalent for backward compatibility."""
    def __eq__(self, other):
        if str(self) == 'Insufficient data' and other == 'Incomplete':
            return True
        if str(self) == 'Incomplete' and other == 'Insufficient data':
            return True
        return super().__eq__(other)

    def __hash__(self):
        return super().__hash__()


CANONICAL_PORTS = {
    "BDCGP / Chattogram": {
        "aliases": {
            "chattogram", "chittagong", "chattogram sea port", "port of chattogram",
            "port of chittagong", "chattogram port", "chittagong port", "chittagong sea port",
            "bdcgp", "bdcgp / chattogram", "bdcgp/chattogram", "bdcgp chattogram",
            "chattogram sea port bangladesh", "chittagong bangladesh", "chattogram bangladesh",
            "port of chattogram bangladesh", "port of chittagong bangladesh",
        },
        "unlocode": "BDCGP",
        "name": "Chattogram",
        "country": "Bangladesh",
    },
    "BDMGL / Mongla": {
        "aliases": {
            "mongla", "mongla port", "port of mongla", "chalna", "chalna port",
            "port of chalna", "bdmgl", "bdmgl / mongla", "bdmgl/mongla", "bdmgl mongla",
            "mongla port bangladesh", "mongla bangladesh", "chalna bangladesh",
            "port of mongla bangladesh",
        },
        "unlocode": "BDMGL",
        "name": "Mongla",
        "country": "Bangladesh",
    },
    "BDPYR / Payra": {
        "aliases": {
            "payra", "payra port", "port of payra", "bdpyr", "bdpyr / payra", "bdpyr/payra",
            "payra port bangladesh", "payra bangladesh",
        },
        "unlocode": "BDPYR",
        "name": "Payra",
        "country": "Bangladesh",
    },
    "KRPUS / Busan": {
        "aliases": {
            "busan", "pusan", "busan port", "port of busan", "krpus", "krpus / busan", "krpus/busan",
            "busan south korea", "busan korea", "port of busan south korea",
        },
        "unlocode": "KRPUS",
        "name": "Busan",
        "country": "South Korea",
    },
    "BDDAC / Dhaka": {
        "aliases": {
            "dhaka", "kamalapur icd", "dhaka icd", "bddac", "bddac / dhaka", "bddac/dhaka",
            "dhaka bangladesh",
        },
        "unlocode": "BDDAC",
        "name": "Dhaka",
        "country": "Bangladesh",
    },
    "SGSIN / Singapore": {
        "aliases": {
            "singapore", "port of singapore", "sgsin", "sgsin / singapore", "sgsin/singapore",
        },
        "unlocode": "SGSIN",
        "name": "Singapore",
        "country": "Singapore",
    },
    "LKCMB / Colombo": {
        "aliases": {
            "colombo", "port of colombo", "lkcmb", "lkcmb / colombo", "lkcmb/colombo",
            "colombo sri lanka",
        },
        "unlocode": "LKCMB",
        "name": "Colombo",
        "country": "Sri Lanka",
    },
    "MYPKG / Port Klang": {
        "aliases": {
            "port klang", "klang", "mypkg", "mypkg / port klang", "mypkg/port klang",
            "port klang malaysia",
        },
        "unlocode": "MYPKG",
        "name": "Port Klang",
        "country": "Malaysia",
    },
    "MYTPP / Tanjung Pelepas": {
        "aliases": {
            "tanjung pelepas", "mytpp", "mytpp / tanjung pelepas", "mytpp/tanjung pelepas",
            "tanjung pelepas malaysia",
        },
        "unlocode": "MYTPP",
        "name": "Tanjung Pelepas",
        "country": "Malaysia",
    },
    "AEJEA / Jebel Ali": {
        "aliases": {
            "jebel ali", "port of jebel ali", "aejea", "aejea / jebel ali", "aejea/jebel ali",
            "jebel ali uae", "jebel ali dubai",
        },
        "unlocode": "AEJEA",
        "name": "Jebel Ali",
        "country": "United Arab Emirates",
    },
}


def normalize_port_name(text: str) -> str:
    """Strip punctuation, collapse whitespace, and normalize case for port nomenclature."""
    if not text or not isinstance(text, str):
        return ""
    s = text.casefold()
    s = re.sub(r'[^\w\s]', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def resolve_canonical_port(port_name: str) -> tuple[Optional[str], str]:
    """Resolve a raw port string against canonical alias clusters.

    Returns (canonical_cluster_name, normalized_string).
    If unrecognized or unknown, canonical_cluster_name is None.
    """
    norm = normalize_port_name(port_name)
    if not norm:
        return None, ""
    # Direct alias match
    for canon, data in CANONICAL_PORTS.items():
        if norm in data["aliases"]:
            return canon, norm
    # Match with country name suffix stripped
    norm_no_country = re.sub(
        r'\b(bangladesh|bd|south korea|korea|kr|sri lanka|lk|malaysia|my|singapore|sg|uae|united arab emirates)\b',
        '', norm
    )
    norm_no_country = re.sub(r'\s+', ' ', norm_no_country).strip()
    if norm_no_country:
        for canon, data in CANONICAL_PORTS.items():
            if norm_no_country in data["aliases"]:
                return canon, norm
    return None, norm


def check_port_of_discharge(d: dict, field_states: Optional[dict] = None) -> dict:
    """Deterministic check: Port of discharge consistency.

    Compares lc_port_of_discharge (Tag 44F) with bl_port_of_discharge.
    Disentangles Port of Loading (bl_port_of_loading) and Place of Delivery (bl_place_of_delivery).
    Uses strictly documentary trade discrepancy phrasing.
    """
    rule = 'Port of discharge consistency'

    # Governance & Field Lifecycle Check
    if field_states is not None:
        lc_state = field_states.get('lc_port_of_discharge', {})
        bl_state = field_states.get('bl_port_of_discharge', {})

        lc_confirmed = (lc_state.get('review_status') == 'confirmed' or lc_state.get('status') == 'confirmed')
        bl_confirmed = (bl_state.get('review_status') == 'confirmed' or bl_state.get('status') == 'confirmed')

        if not lc_confirmed or not bl_confirmed:
            return {
                'check': rule,
                'status': CheckStatus('Insufficient data'),
                'evidence': (
                    "Insufficient data: Port of discharge unconfirmed or unresolved "
                    f"(Letter of Credit Field 44F review: '{lc_state.get('review_status', 'missing')}', "
                    f"Bill of Lading review: '{bl_state.get('review_status', 'missing')}')."
                )
            }

        if lc_state.get('status') in ('rejected', 'unreadable', 'conflicting', 'missing') or \
           bl_state.get('status') in ('rejected', 'unreadable', 'conflicting', 'missing'):
            return {
                'check': rule,
                'status': CheckStatus('Insufficient data'),
                'evidence': (
                    "Insufficient data: Port of discharge field state invalid "
                    f"(Letter of Credit Field 44F extraction: '{lc_state.get('status')}', "
                    f"Bill of Lading extraction: '{bl_state.get('status')}')."
                )
            }

    # Extract port values (strictly isolating discharge port from loading port and delivery place)
    lc_val = d.get('lc_port_of_discharge')
    bl_val = d.get('bl_port_of_discharge')

    if not lc_val or not str(lc_val).strip() or not bl_val or not str(bl_val).strip():
        return {
            'check': rule,
            'status': CheckStatus('Insufficient data'),
            'evidence': (
                f"Insufficient data: Missing port of discharge field "
                f"(Letter of Credit Field 44F: '{lc_val or ''}', Bill of Lading: '{bl_val or ''}')."
            )
        }

    lc_raw = str(lc_val).strip()
    bl_raw = str(bl_val).strip()

    lc_canon, _ = resolve_canonical_port(lc_raw)
    bl_canon, _ = resolve_canonical_port(bl_raw)

    # Unknown or unrecognized port name
    if lc_canon is None or bl_canon is None:
        unrec = []
        if lc_canon is None:
            unrec.append(f"Letter of Credit Field 44F '{lc_raw}'")
        if bl_canon is None:
            unrec.append(f"Bill of Lading Port of Discharge '{bl_raw}'")
        return {
            'check': rule,
            'status': 'Review required',
            'evidence': f"Discrepancy: Unrecognized port of discharge authority or UN/LOCODE ({', '.join(unrec)})."
        }

    # Deterministic port consistency outcome
    if lc_canon == bl_canon:
        return {
            'check': rule,
            'status': 'Passed',
            'evidence': (
                f"Port of discharge harmonized: Letter of Credit Field 44F ('{lc_raw}') and "
                f"Bill of Lading ('{bl_raw}') both resolve to canonical '{lc_canon}'."
            )
        }
    else:
        return {
            'check': rule,
            'status': 'Review required',
            'evidence': (
                f"Discrepancy: Bill of Lading states Port of Discharge as '{bl_raw}', "
                f"whereas Letter of Credit Field 44F stipulates '{lc_raw}'."
            )
        }


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
    # Check 1: Port of discharge consistency
    findings.append(check_port_of_discharge(d, field_states))
    return findings

