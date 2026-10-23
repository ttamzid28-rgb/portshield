from decimal import Decimal, InvalidOperation
from datetime import date
import re
from typing import Optional


CANONICAL_PORTS = {
    "BDCGP / Chattogram": {
        "base_aliases": {
            "chattogram", "chittagong", "chattogram sea port", "port of chattogram",
            "port of chittagong", "chattogram port", "chittagong port", "chittagong sea port",
            "bdcgp", "bdcgp / chattogram", "bdcgp/chattogram", "bdcgp chattogram",
        },
        "permitted_countries": {"bangladesh", "bd"},
        "unlocode": "BDCGP",
        "name": "Chattogram",
        "country": "Bangladesh",
    },
    "BDMGL / Mongla": {
        "base_aliases": {
            "mongla", "mongla port", "port of mongla", "chalna", "chalna port",
            "port of chalna", "bdmgl", "bdmgl / mongla", "bdmgl/mongla", "bdmgl mongla",
        },
        "permitted_countries": {"bangladesh", "bd"},
        "unlocode": "BDMGL",
        "name": "Mongla",
        "country": "Bangladesh",
    },
    "BDPYR / Payra": {
        "base_aliases": {
            "payra", "payra port", "port of payra", "bdpyr", "bdpyr / payra", "bdpyr/payra",
        },
        "permitted_countries": {"bangladesh", "bd"},
        "unlocode": "BDPYR",
        "name": "Payra",
        "country": "Bangladesh",
    },
    "KRPUS / Busan": {
        "base_aliases": {
            "busan", "pusan", "busan port", "port of busan", "krpus", "krpus / busan", "krpus/busan",
        },
        "permitted_countries": {"south korea", "korea", "kr", "republic of korea"},
        "unlocode": "KRPUS",
        "name": "Busan",
        "country": "South Korea",
    },
    "BDDAC / Dhaka": {
        "base_aliases": {
            "dhaka", "kamalapur icd", "dhaka icd", "bddac", "bddac / dhaka", "bddac/dhaka",
        },
        "permitted_countries": {"bangladesh", "bd"},
        "unlocode": "BDDAC",
        "name": "Dhaka",
        "country": "Bangladesh",
    },
    "SGSIN / Singapore": {
        "base_aliases": {
            "singapore", "port of singapore", "sgsin", "sgsin / singapore", "sgsin/singapore",
        },
        "permitted_countries": {"singapore", "sg"},
        "unlocode": "SGSIN",
        "name": "Singapore",
        "country": "Singapore",
    },
    "LKCMB / Colombo": {
        "base_aliases": {
            "colombo", "port of colombo", "lkcmb", "lkcmb / colombo", "lkcmb/colombo",
        },
        "permitted_countries": {"sri lanka", "lk"},
        "unlocode": "LKCMB",
        "name": "Colombo",
        "country": "Sri Lanka",
    },
    "MYPKG / Port Klang": {
        "base_aliases": {
            "port klang", "klang", "mypkg", "mypkg / port klang", "mypkg/port klang",
        },
        "permitted_countries": {"malaysia", "my"},
        "unlocode": "MYPKG",
        "name": "Port Klang",
        "country": "Malaysia",
    },
    "MYTPP / Tanjung Pelepas": {
        "base_aliases": {
            "tanjung pelepas", "mytpp", "mytpp / tanjung pelepas", "mytpp/tanjung pelepas",
        },
        "permitted_countries": {"malaysia", "my"},
        "unlocode": "MYTPP",
        "name": "Tanjung Pelepas",
        "country": "Malaysia",
    },
    "AEJEA / Jebel Ali": {
        "base_aliases": {
            "jebel ali", "port of jebel ali", "aejea", "aejea / jebel ali", "aejea/jebel ali",
        },
        "permitted_countries": {"united arab emirates", "uae", "dubai"},
        "unlocode": "AEJEA",
        "name": "Jebel Ali",
        "country": "United Arab Emirates",
    },
}

KNOWN_COUNTRIES = (
    "united arab emirates", "republic of korea", "south korea", "united states",
    "united kingdom", "sri lanka", "singapore", "bangladesh", "malaysia",
    "indonesia", "pakistan", "thailand", "vietnam", "myanmar", "germany",
    "korea", "china", "japan", "india", "dubai", "burma", "usa", "uae",
    "bd", "kr", "sg", "lk", "my", "in", "cn", "jp", "th", "vn", "id", "pk", "mm", "uk", "us", "de"
)


def normalize_port_name(text: str) -> str:
    """Strip punctuation, collapse whitespace, and normalize case for port nomenclature."""
    if not text or not isinstance(text, str):
        return ""
    s = text.casefold()
    s = re.sub(r'[^\w\s]', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def resolve_canonical_port(port_name: str) -> tuple[Optional[str], str]:
    """Resolve a raw port string against canonical alias clusters with country constraints.

    Returns (canonical_cluster_name, normalized_string).
    If unrecognized, contradictory country, or conflicting multi-location, canonical_cluster_name is None.
    """
    norm = normalize_port_name(port_name)
    if not norm:
        return None, ""

    # Check multi-location slashes (e.g. "Chattogram / Singapore")
    if '/' in port_name:
        parts = [p.strip() for p in port_name.split('/') if p.strip()]
        if len(parts) > 1:
            resolved_parts = set()
            for p in parts:
                p_canon, _ = resolve_canonical_port(p)
                if p_canon:
                    resolved_parts.add(p_canon)
                else:
                    p_norm = normalize_port_name(p)
                    if any(re.search(r'\b' + re.escape(c) + r'\b', p_norm) for c in KNOWN_COUNTRIES):
                        resolved_parts.add(f"country:{p_norm}")
            if len(resolved_parts) > 1:
                return None, norm

    # Find any known countries present in the normalized string
    found_countries = set()
    for c in KNOWN_COUNTRIES:
        if re.search(r'\b' + re.escape(c) + r'\b', norm):
            found_countries.add(c)

    for canon, data in CANONICAL_PORTS.items():
        base_aliases = data["base_aliases"]
        permitted = data["permitted_countries"]

        # Direct match with base aliases
        if norm in base_aliases:
            if not found_countries or found_countries.issubset(permitted):
                return canon, norm
            # Contradictory country in string (e.g. "Chattogram, Malaysia")
            return None, norm

        # Match with permitted country suffix stripped
        matching_permitted = found_countries.intersection(permitted)
        if matching_permitted:
            stripped = norm
            for c in matching_permitted:
                stripped = re.sub(r'\b' + re.escape(c) + r'\b', '', stripped)
            stripped = re.sub(r'\s+', ' ', stripped).strip()
            if stripped in base_aliases:
                contradictory = found_countries - permitted
                if contradictory:
                    return None, norm
                return canon, norm

    return None, norm


def check_port_of_discharge(d: dict, field_states: Optional[dict] = None) -> dict:
    """Deterministic check: Port of discharge consistency.

    Compares lc_port_of_discharge (Tag 44F) with bl_port_of_discharge.
    Disentangles Port of Loading (bl_port_of_loading) and Place of Delivery (bl_place_of_delivery).
    Uses strictly documentary trade discrepancy phrasing. Plain string status.
    """
    rule = 'Port of discharge consistency'

    # Strict Governance & Human Review Contract
    if field_states is not None:
        lc_state = field_states.get('lc_port_of_discharge', {})
        bl_state = field_states.get('bl_port_of_discharge', {})

        # A field is confirmed IF AND ONLY IF review_status == "confirmed"
        lc_confirmed = (lc_state.get('review_status') == 'confirmed')
        bl_confirmed = (bl_state.get('review_status') == 'confirmed')

        if not lc_confirmed or not bl_confirmed:
            return {
                'check': rule,
                'status': 'Insufficient data',
                'evidence': (
                    "Insufficient data: Port of discharge unconfirmed or unresolved "
                    f"(Letter of Credit Field 44F review: '{lc_state.get('review_status', 'missing')}', "
                    f"Bill of Lading review: '{bl_state.get('review_status', 'missing')}')."
                )
            }

    # Extract port values (strictly isolating discharge port from loading port and delivery place)
    lc_val = d.get('lc_port_of_discharge')
    bl_val = d.get('bl_port_of_discharge')

    if not lc_val or not str(lc_val).strip() or not bl_val or not str(bl_val).strip():
        return {
            'check': rule,
            'status': 'Insufficient data',
            'evidence': (
                f"Insufficient data: Missing port of discharge field "
                f"(Letter of Credit Field 44F: '{lc_val or ''}', Bill of Lading: '{bl_val or ''}')."
            )
        }

    lc_raw = str(lc_val).strip()
    bl_raw = str(bl_val).strip()

    lc_canon, _ = resolve_canonical_port(lc_raw)
    bl_canon, _ = resolve_canonical_port(bl_raw)

    # Unknown, contradictory, or multi-location port string
    if lc_canon is None or bl_canon is None:
        return {
            'check': rule,
            'status': 'Review required',
            'evidence': (
                f"Discrepancy: Bill of Lading states Port of Discharge as '{bl_raw}', "
                f"whereas Letter of Credit Field 44F stipulates '{lc_raw}'."
            )
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

