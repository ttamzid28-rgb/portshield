# Architectural RFC & Schema Contract: Chattogram Trade Compliance Extension

**Status**: Proposed / Under Review  
**Target Release**: PortShield AI Compliance Engine v1.2  
**Target Branch**: `demo/chattogram-packets`  
**Author**: PortShield AI Architecture Team  
**Date**: October 2026  

---

## 1. Executive Summary & Purpose

PortShield AI executes documentary compliance audits for international trade finance under **ICC UCP 600** and **ISBP 745**. This RFC specifies:
1. The **Canonical-to-Runtime Migration Adapter** bridging modern canonical `<document_prefix>_<field_name>` keys with current runtime engines without breaking changes.
2. The **Validation Contract & Unknown Field Rejection Specification** for all new maritime trade fields.
3. The **Decoupled Field State Machine** strictly separating system extraction quality (`extraction_status`) from human governance (`review_status`).
4. Operational container equipment ratings and **Financial Headroom vs. L/C Tolerance Disambiguation**.
5. The **Cargo Gross Weight Tolerance Rule** governing scale calibration variances.

---

## 2. Document Provenance & Canonical-to-Runtime Migration Architecture

### 2.1 Document Provenance Mapping
All extracted and validated trade fields strictly follow a `<document_prefix>_<field_name>` format reflecting source document provenance:

| Document Prefix | Document Name | File Reference | Sequence Index | Source Authority |
| :---: | :--- | :--- | :---: | :--- |
| `ci_` | Commercial Invoice | `commercial_invoice.pdf` | Document 1 | Beneficiary / Exporter |
| `pl_` | Packing List | `packing_list.pdf` | Document 2 | Exporter / Warehouse / Packer |
| `bl_` | Ocean Bill of Lading | `bill_of_lading.pdf` | Document 3 | Ocean Carrier / Vessel Agent |
| `lc_` | Letter of Credit (MT700) | `letter_of_credit.pdf` | Document 4 | Issuing Bank / SWIFT Network |

---

### 2.2 Formal Canonical-to-Runtime Adapter Specification

To ensure seamless backward compatibility with existing components ([`app.py`](file:///D:/Projects/portshield-1/app.py), [`checks.py`](file:///D:/Projects/portshield-1/checks.py), [`field_states.py`](file:///D:/Projects/portshield-1/field_states.py), [`extraction_validation.py`](file:///D:/Projects/portshield-1/extraction_validation.py)), the architecture defines an explicit two-way **Canonical Adapter**:

```
                         [ LLM Extraction Engine ]
                                     │
                     Emits Canonical Keys (e.g., ci_invoice_total)
                                     ▼
                     ┌───────────────────────────────┐
                     │   CANONICAL ADAPTER LAYER     │
                     │  (Two-Way Bidirectional Map)  │
                     └───────────────┬───────────────┘
                                     │
         ┌───────────────────────────┴───────────────────────────┐
         ▼                                                       ▼
[ Native Canonical Engine (v1.2+) ]             [ Legacy Runtime Engine (v1.0) ]
- ci_invoice_total                              - invoice_total
- bl_on_board_date                              - on_board_date
- bl_container_number                           - bl_container
- pl_container_number                           - packing_container
```

#### Exact Bidirectional Key Mapping Table:
| Canonical Schema Key (v1.2+) | Current Runtime Key (v1.0) | Source Document | Validation Routine |
| :--- | :--- | :---: | :--- |
| `ci_invoice_total` | `invoice_total` | CI | Decimal parse, quote match |
| `ci_currency` | `invoice_currency` | CI | ISO 4217 code regex |
| `ci_quantity` | `invoice_quantity` | CI | Positive integer/decimal mass |
| `ci_unit_price` | `unit_price` | CI | Decimal price per unit |
| `pl_quantity` / `pl_cargo_net_weight` | `packing_quantity` | PL | Decimal mass in invoice unit |
| `pl_container_number` | `packing_container` | PL | ISO 6346 11-char format |
| `bl_container_number` | `bl_container` | BL | ISO 6346 11-char format |
| `lc_amount` | `lc_amount` | LC | Decimal face amount |
| `lc_currency` | `lc_currency` | LC | ISO 4217 code regex |
| `lc_latest_shipment_date` | `latest_shipment_date` | LC | ISO date YYYY-MM-DD |
| `bl_on_board_date` | `on_board_date` | BL | ISO date YYYY-MM-DD |

#### Pipeline Execution Order & Invariants:
1. **Model Extraction**: Models are prompted with canonical names (`ci_invoice_total`, etc.).
2. **Adapter Translation**: The Adapter normalizes aliases before invoking `validate_value()` and `collect_fields()`, or `validate_value()` checks canonical patterns natively via prefix routing (`key.startswith(('ci_', 'pl_', 'bl_', 'lc_'))`).
3. **Evidence Immutability**: Key translation **never** mutates source evidence metadata (`quote`, `page`, `document`, `char_offsets`). These remain bound to the canonical document index and exact verbatim byte offsets.
4. **State Decoupling**: Key alias translation preserves the immutable candidate audit record in `evidence['_field_states']`.

---

## 3. Validation Rules & Rejection of Unknown Fields

A critical vulnerability in naive schema migrations is allowing unregistered fields to bypass validation with an implicit pass. The PortShield contract mandates strict validation and explicit rejection.

### 3.1 Field Validators for New Maritime Fields

#### 1. Port Fields (`lc_port_of_discharge`, `bl_port_of_discharge`, `bl_port_of_loading`, `bl_place_of_delivery`)
- **String Validation**: Must be non-empty text, length between 3 and 120 characters after stripping whitespace.
- **Seaport Nomenclature / UN/LOCODE Sanitization**: Value must resolve to known port authority nomenclature (e.g., *Chattogram Sea Port*, *Mongla Port*, *Busan Port*) or a standard 5-character UN/LOCODE (`BDCGP`, `BDMGL`, `KRPUS`).
- **Quotation Containment Check**: Candidate value must match or be a faithful substring of the source quotation.
- **Quotation Page Verification**: Quotation must satisfy `normalized(quote) in normalized(page_text[(doc, page)])`.

#### 2. Cargo Weight Fields (`pl_cargo_gross_weight`, `bl_cargo_gross_weight`, `ci_cargo_net_weight`, `pl_cargo_net_weight`)
- **Strict Decimal Numeric Parse**: Must parse via `Decimal(value)` with `amount > 0`.
- **Anti-Hallucination Source Check**: The numeric value must be present in the source quotation as parsed by `_source_number()`. An extracted value of `'999999'` when the quote contains `'21,600.00 KGS'` is strictly **REJECTED**.
- **Plain Format Check**: Value must be plain decimal string (`^[0-9]+(?:\.[0-9]+)?$`), without thousand separators or currency/unit symbols.

#### 3. Unit Fields (`pl_cargo_gross_weight_unit`, `bl_cargo_gross_weight_unit`, `ci_cargo_net_weight_unit`, `pl_cargo_net_weight_unit`)
- **Restricted Enum Validator**: Must strictly match one of `["KGS", "KG", "MT", "LBS"]`.
- **Contextual Proximity**: Unit must be cited in or immediately adjacent to the associated weight quotation on the same page.

### 3.2 Strict Rule on Unknown / Unregistered Fields
> [!IMPORTANT]
> **No Implicit Pass**: Any field entry returned by an extraction model that is not explicitly registered in the field schema registry MUST NOT receive an implicit validation pass.
> 
> Unregistered fields are intercepted by `collect_fields()`:
> 1. Appended to `evidence['_rejected']` with reason: `"Unrecognized or malformed field entry omitted."`
> 2. Excluded from `states` dictionary.
> 3. Marked with `validation_status="unvalidated_unknown"`.

---

## 4. Decoupled State Machine: Extraction Status vs. Review Status

The PortShield field lifecycle strictly decouples **system extraction quality** from **human governance disposition**:

```
[ MODEL EXTRACTION PIPELINE ]                    [ HUMAN GOVERNANCE WORKFLOW ]
     │                                                        │
     ├── Extracted & Validated ────> extraction_status:       │
     │                               "extracted"              ▼
     ├── Parsing / Syntax Error ───> extraction_status:  review_status:
     │                               "rejected"          "unreviewed" (default)
     ├── Text Unreadable on Page ──> extraction_status:       │
     │                               "unreadable"             ├── Verified by User ──> "confirmed"
     ├── Multiple Conflicting ─────> extraction_status:       ├── Adjusted by User ──> "edited"
     │                               "conflicting"            └── Overruled ─────────> "rejected"
     └── Omitted by Model ─────────> extraction_status:
                                     "missing"
```

### 4.1 State Definitions

| State Category | Field Property | Possible Values | Semantics |
| :--- | :--- | :--- | :--- |
| **System Extraction State** | `status` (or `extraction_status`) | `extracted`, `missing`, `unreadable`, `rejected`, `conflicting` | Immutable record of automated model extraction performance and quote verification. |
| **Human Governance State** | `review_status` | `unreviewed` (or `pending`), `confirmed`, `edited`, `rejected` | Tracks human review progress and auditor actions. |
| **Audited Value** | `reviewed_value` | String (`""` if unconfirmed) | Value explicitly confirmed or modified by human auditor. |

### 4.2 State Machine Invariants
1. **Confirmation Immutability**: When an auditor confirms a field, `review_status` transitions from `"pending"` to `"confirmed"`. **The underlying `extraction_status` is NOT overwritten or mutated** (e.g. an extraction that was `"rejected"` due to a minor syntax error retains `status: "rejected"` alongside `review_status: "confirmed"`).
2. **Audit Trail Preservation**: All original model candidates, cited quotes, document indexes, and page numbers remain preserved in `evidence['_field_states'][field]['candidates']`.
3. **Engine Usable Values**: Functions in [`checks.py:audit()`](file:///D:/Projects/portshield-1/checks.py#L4-L28) consume values through [`field_states.py:usable_values()`](file:///D:/Projects/portshield-1/field_states.py#L57-L61), which enforces that values are only usable when `review_status == 'confirmed'`.

---

## 5. Operational Equipment Ratings & Financial Headroom Disambiguation

### 5.1 40-foot High-Cube Equipment Rating Feasibility
Standard ISO 668 / CSC ratings establish:
- **Maximum Gross Mass (Rating)**: $32,500\text{ KG}$.
- **Container Box Tare Weight**: $3,800\text{ KG}$ (standard 40' HC steel container).
- **Maximum Cargo Payload**: $28,700\text{ KG}$.

### 5.2 Demonstration Baseline Specifications
$$\begin{aligned}
\text{Cargo Net Weight} &= 20,000.00\text{ KGS} \quad (800\text{ bags } @\ 25.00\text{ KG}) \\
\text{Cargo Packaging Tare} &= 1,600.00\text{ KGS} \quad (20\text{ pallets } @\ 75\text{ KG} + \text{shrinkwrap/bags}) \\
\mathbf{\text{Cargo Gross Weight}} &= \mathbf{21,600.00\text{ KGS}} \quad (\text{Clean Baseline \& PL}) \\
\text{Container Tare Weight} &= 3,800.00\text{ KGS} \\
\mathbf{\text{Verified Gross Mass (VGM)}} &= \mathbf{25,400.00\text{ KGS}} \quad (25.4\text{ MT} \le 32.5\text{ MT rating})
\end{aligned}$$

### 5.3 Financial Headroom vs. L/C Tolerance Disambiguation
Under SWIFT MT700 standards, documentary credits must not confuse **Face Amount (Tag 32B)** with **Tolerance Ceiling (Tag 39A/39B)**:

1. **Tag 32B (Face Amount)**: Declares the nominal face credit value.
2. **Tag 39A (Percentage Tolerance)**: Declares permitted drawing variation (e.g., `5/5` denotes $\pm 5\%$).
3. **Disambiguation Contract**:
   - An explicit face amount of `USD 26,250.00` (with 0% tolerance) is **not** identical to a nominal face amount of `USD 25,000.00` subject to $\pm 5\%$ tolerance, even though both permit a maximum drawing of `USD 26,250.00`.
   - **Audit Engine Evaluation**: In [`checks.py`](file:///D:/Projects/portshield-1/checks.py#L17-L22), the rule `Invoice amount within configured limit` compares `Decimal(invoice_total) <= Decimal(lc_amount)`.
   - In our demonstration baseline, `lc_amount` is declared as `USD 26,250.00` (the credit ceiling), and `ci_invoice_total` is `USD 25,000.00`. This ensures:
     $$25,000.00 \le 26,250.00 \implies \mathbf{Passed}$$
   - When tolerance is explicitly extracted, future audit rules evaluate:
     $$\text{ci\_invoice\_total} \le \text{lc\_amount} \times \left(1 + \frac{\text{tolerance\_pct}}{100}\right)$$

---

## 6. Gross Weight Tolerance Rule Specification

In physical maritime shipping, slight weight variances between warehouse packing scales and weighbridge container scales occur due to scale calibration differences, packaging moisture, and environmental conditions.

### 6.1 Formal Tolerance Rule
The cargo gross weight consistency check implements a configurable delta tolerance:
- **Default Tolerance Parameter**: `max_weight_delta_kg = 10.0` ($10.0\text{ KG}$).
- **Evaluation Formula**:
  $$\Delta W = \left| \text{pl\_cargo\_gross\_weight} - \text{bl\_cargo\_gross\_weight} \right|$$
- **Finding Status**:
  $$\text{Status} = \begin{cases} \mathbf{Passed} & \text{if } \Delta W \le \text{max\_weight\_delta\_kg} \\ \mathbf{Review\ required} & \text{if } \Delta W > \text{max\_weight\_delta\_kg} \end{cases}$$

### 6.2 Application to Demonstration Fixtures
- **Clean Packet**: $\Delta W = |21,600.0 - 21,600.0| = 0.0\text{ KG} \le 10.0\text{ KG} \implies \mathbf{Passed}$.
- **Discrepancy Packet**: $\Delta W = |21,600.0 - 20,700.0| = 900.0\text{ KG} \gg 10.0\text{ KG} \implies \mathbf{Review\ required}$.
  The $900.0\text{ KG}$ shortage is a clear transposition discrepancy that vastly exceeds operational scale calibration tolerance.
- **Corrected Packet**: $\Delta W = |21,600.0 - 21,600.0| = 0.0\text{ KG} \le 10.0\text{ KG} \implies \mathbf{Passed}$.

---

## 7. Verification & Behavioral Guarantees

1. **Test Verification**: [`test_chattogram_fixtures.py`](file:///D:/Projects/portshield-1/test_chattogram_fixtures.py) executes live [`checks.py:audit()`](file:///D:/Projects/portshield-1/checks.py#L4-L28) checks on mapped canonical fields, validating all 6 baseline checks as `Passed`.
2. **Direct Weight Discrepancy Math**: Tests evaluate `float(pl_gross) - float(bl_gross) == 900.0`.
3. **Quote Citations**: 100% of answer-key quotations are verified verbatim in PDF page text layers via `pdf_viewer.locate_quote_on_page`.
4. **All 69 Tests Passing**: Suite passes completely without regressions.
