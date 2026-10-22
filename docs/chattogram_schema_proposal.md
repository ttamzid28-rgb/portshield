# Architectural RFC & Schema Contract: Chattogram Trade Compliance Extension

**Status**: Proposed / Under Review  
**Target Release**: PortShield AI Compliance Engine v1.2  
**Target Branch**: `demo/chattogram-packets`  
**Author**: PortShield AI Architecture Team  
**Date**: October 2026  

---

## 1. Executive Summary & Purpose

PortShield AI currently executes six baseline documentary compliance checks (currency alignment, quantity equality, container string equality, invoice limit compliance, invoice arithmetic verification, and shipment deadline compliance). 

This RFC proposes the canonical schema contract and field lifecycle integration for **four additional compliance checks** tailored for high-volume containerized industrial import flows through **Chattogram Sea Port (CGP), Bangladesh**, governed by **ICC UCP 600** and **ISBP 745**:

1. **Port of Discharge Consistency** (Letter of Credit vs. Ocean Bill of Lading).
2. **Cargo Gross Weight Consistency** (Packing List vs. Ocean Bill of Lading), isolating cargo gross mass from packaging tare, container tare, and Verified Gross Mass (VGM).
3. **ISO 6346 Container Check Digit Verification** (Equipment identifier mathematical checksum validation).
4. **Goods Description Conformity** (Commercial Invoice vs. Letter of Credit Tag 45A under UCP 600 Article 18c).

All proposed fields and rules integrate into PortShield's existing `field_states.py` and `evidence` infrastructure **without breaking changes** to active extraction models or downstream UI components.

---

## 2. Field Definitions, Canonical Types, and Normalization Contracts

### 2.1 `port_of_discharge` (BL, LC)

| Property | Specification |
| :--- | :--- |
| **Field Name** | `port_of_discharge` |
| **Source Documents** | Ocean Bill of Lading (BL), Letter of Credit (LC Tag 44F) |
| **Canonical Type** | `STRING` (Normalized Port Identity) |
| **Extraction Format** | Contiguous substring containing the port name, country, and optional UN/LOCODE |
| **Normalization Pipeline** | Casefolded (`casefold()`), stripped of punctuation, with alias resolution table: `{"chattogram", "chittagong", "cgp", "bdcgp"} -> "CHATTOGRAM SEA PORT"` |

#### Critical Compliance Invariant:
Under maritime multimodal transport to Bangladesh, the **Port of Discharge** (sea port where the container vessel unberths, e.g., *Chattogram Sea Port*) must be strictly distinguished from the **Place of Final Delivery** (inland destination, e.g., *Dhaka Inland Container Depot*). A document confusing Place of Delivery with Port of Discharge, or designating an unauthorized discharge port (e.g., *Mongla Port* when the credit stipulates *Chattogram*), constitutes a major documentary discrepancy.

---

### 2.2 `cargo_gross_weight` & `gross_weight_unit` (PL, BL)

| Property | Specification |
| :--- | :--- |
| **Field Name** | `cargo_gross_weight`, `gross_weight_unit` |
| **Source Documents** | Packing List (PL), Ocean Bill of Lading (BL) |
| **Canonical Type** | `Decimal` string (`cargo_gross_weight`), `STRING` ISO/metric symbol (`gross_weight_unit`) |
| **Normalized Units** | Canonical unit is `KG` (or `KGS`, `MT` with 1 MT = 1,000 KG conversion factor) |
| **Validation Regex** | `^[0-9]+(?:\.[0-9]+)?$` (plain decimal, no thousand separators) |

#### Isolation from Container Tare and SOLAS VGM:
A common source of false discrepancies in automated audit engines is comparing container tare weight (e.g., 3,800 KG for a 40' HC) or SOLAS Verified Gross Mass (VGM, e.g., 47,000 KG) against cargo gross mass (43,200 KG). 

The schema strictly isolates:
$$\text{Cargo Net Weight} + \text{Packaging Tare (Pallets/Bags)} = \text{Cargo Gross Weight}$$
$$\text{Cargo Gross Weight} + \text{Container Tare Weight} = \text{Verified Gross Mass (VGM)}$$

The compliance check evaluates:
$$\text{PL Cargo Gross Weight} == \text{BL Cargo Gross Weight}$$
This successfully catches transposition errors (e.g., 43,200 KG on PL vs. 42,300 KG on BL, a 900 KG shortage discrepancy) while preventing false alerts from container tare.

---

### 2.3 `cargo_net_weight` & `net_weight_unit` (PL, CI)

| Property | Specification |
| :--- | :--- |
| **Field Name** | `cargo_net_weight`, `net_weight_unit` |
| **Source Documents** | Packing List (PL), Commercial Invoice (CI) |
| **Canonical Type** | `Decimal` string, normalized unit (`KG`, `MT`) |
| **Relationship** | Must equal commercial goods quantity when invoice unit of measure is weight |

---

### 2.4 `container_number` (PL, BL) & ISO 6346 Check Digit Algorithm

| Property | Specification |
| :--- | :--- |
| **Field Name** | `container_number` (or `packing_container`, `bl_container`) |
| **Source Documents** | Packing List (PL), Ocean Bill of Lading (BL) |
| **Canonical Format** | Standardized 11-character string: `[A-Z]{3}[UJZ][0-9]{7}` (e.g. `MEDU1000060`) |
| **Component Breakdown** | `Owner Code` (3 letters) + `Equipment Category` (1 letter: U/J/Z) + `Serial Number` (6 digits) + `Check Digit` (1 digit) |

#### ISO 6346 Check Digit Mathematical Formulation:
Each character in the 10-character prefix ($c_0, c_1, \dots, c_9$) is mapped to an integer value $V(c_i)$ according to the ISO 6346 lookup table (where multiples of 11 are excluded):

$$\begin{aligned}
\text{Digits } 0\text{--}9 &\to 0\text{--}9 \\
\text{Letters } A\text{--}Z &\to [A=10, B=12, C=13, D=14, E=15, F=16, G=17, H=18, I=19, \\
&\quad J=20, K=21, L=23, M=24, N=25, O=26, P=27, Q=28, \\
&\quad R=29, S=30, T=31, U=32, V=34, W=35, X=36, Y=37, Z=38]
\end{aligned}$$

Each character value is multiplied by a positional weight $2^i$:
$$S = \sum_{i=0}^{9} V(c_i) \cdot 2^i$$

The calculated check digit $CD$ is:
$$R = S \pmod{11}$$
$$CD = 0 \quad \text{if } R = 10, \quad \text{else } CD = R$$

#### Mathematical Walkthrough for Clean Container `MEDU1000060`:
- Prefix: `M`, `E`, `D`, `U`, `1`, `0`, `0`, `0`, `0`, `6`
- Values: $24, 15, 14, 32, 1, 0, 0, 0, 0, 6$
- Weights: $1, 2, 4, 8, 16, 32, 64, 128, 256, 512$
- Weighted Sum:
  $$S = (24 \cdot 1) + (15 \cdot 2) + (14 \cdot 4) + (32 \cdot 8) + (1 \cdot 16) + (0) + (0) + (0) + (0) + (6 \cdot 512)$$
  $$S = 24 + 30 + 56 + 256 + 16 + 3072 = 3454$$
- Modulus:
  $$3454 \div 11 = 314 \text{ remainder } 0$$
  $$CD = 0$$
- Result: **VALID** (`MEDU1000060`).
- Discrepancy Case: When stated as `MEDU1000067`, $CD_{\text{stated}} = 7 \neq 0 \implies$ **INVALID CHECK DIGIT**.

---

### 2.5 `goods_description` (CI, LC)

| Property | Specification |
| :--- | :--- |
| **Field Name** | `goods_description` |
| **Source Documents** | Commercial Invoice (CI), Letter of Credit (LC Tag 45A) |
| **Canonical Type** | Normalized text string |
| **Compliance Rule** | **UCP 600 Article 18(c)**: "The description of the goods, services or performance in a commercial invoice must correspond with that in the credit." |
| **Discrepancy Severity** | Critical Discrepancy. For instance, L/C specifies *High Density Polyethylene (HDPE) Resin Grade HD5010*, but Invoice lists *Linear Low Density Polyethylene (LLDPE) Film Grade*. |

---

## 3. Integration with `field_states` and Evidence Pipeline

The existing PortShield field lifecycle in `field_states.py` maintains five rigorous states:

```
[missing] ──(Candidate Returned)──> [extracted] ──(Validation Failed)──> [rejected]
                                          │
                                          ├──(Unreadable Page)─────────> [unreadable]
                                          │
                                          ├──(Multiple Values)─────────> [conflicting]
                                          │
                                          └──(Human Confirmation)──────> [confirmed]
```

### 3.1 Non-Breaking Candidate Collection
When the model extracts candidates for the new fields, `collect_fields(entries, field_names, packet, page_text)` processes them through `validate_value(key, value, quote)`.

1. **Unrecognized / Future Fields**: If `field_names` includes `cargo_gross_weight`, `port_of_discharge`, or `goods_description`, `collect_fields` instantiates their records in `states` with initial status `missing`.
2. **Quote Verification**: All candidate quotations are verified against the cited document and page via `normalized(quote) in normalized(page_text[(doc, page)])`.
3. **Evidence Storage**: Quotes and page citations are appended to `evidence[key]` and indexed in `evidence['_field_states'][key]['candidates']`.
4. **Human Confirmation Pipeline**: Downstream functions (`review_fields`, `usable_values`) consume confirmed values without modification.

### 3.2 Evidence Structure Example
```json
{
  "_field_states": {
    "cargo_gross_weight": {
      "status": "extracted",
      "reason": "Source-linked candidate; human confirmation required.",
      "review_status": "pending",
      "candidates": [
        {
          "value": "43200",
          "unit": "KGS",
          "quote": "Cargo Gross Weight: 43,200.00 KGS",
          "document": 2,
          "page": 1,
          "status": "extracted",
          "validated_value": "43200"
        }
      ]
    }
  },
  "cargo_gross_weight": "packing_list.pdf · page 1 · AI-cited text (verify): Cargo Gross Weight: 43,200.00 KGS"
}
```

---

## 4. Planned Compliance Audit Engine Rules (`checks.py`)

When the compliance rules are implemented in the next phase, they will be registered into `audit(d, field_states=None)`:

```python
# Planned Rule 7: Port of Discharge Consistency
compare('Port of discharge consistency', 'lc_port_of_discharge', 'bl_port_of_discharge')

# Planned Rule 8: Cargo Gross Weight Consistency
compare_numeric('Cargo gross weight consistency', 'packing_gross_weight', 'bl_gross_weight')

# Planned Rule 9: ISO 6346 Container Check Digit
validate_iso_6346('ISO 6346 check digit', 'bl_container')

# Planned Rule 10: Goods Description Conformity
compare_goods_description('Goods description conformity', 'lc_goods_description', 'invoice_goods_description')
```

---

## 5. Backward Compatibility & Test Guarantees

1. **Active Core Code Untouched**: No changes are made to `app.py`, `checks.py`, `field_states.py`, `ai_runtime.py`, or `benchmark_data.json`.
2. **Full Baseline Suite Passing**: All 60 existing unit tests pass without warning.
3. **Reproducibility**: All 12 demonstration PDFs can be deterministically regenerated via `py scripts/generate_chattogram_packets.py`.
4. **Answer Key Parity**: `fixtures/chattogram_answer_keys.json` serves as the single source of truth for both human audit and automated CI testing.
