# Architectural RFC & Schema Contract: Chattogram Trade Compliance Extension

**Status**: Proposed / Under Review  
**Target Release**: PortShield AI Compliance Engine v1.2  
**Target Branch**: `demo/chattogram-packets`  
**Author**: PortShield AI Architecture Team  
**Date**: October 2026  

---

## 1. Executive Summary & Purpose

PortShield AI executes documentary compliance audits for international trade finance under **ICC UCP 600** and **ISBP 745**. This RFC specifies the canonical schema contract, field lifecycle integration, and realistic operational parameters for containerized industrial import flows through **Chattogram Sea Port (CGP), Bangladesh**.

The architecture enforces a strict **canonical naming convention** (`<doc_prefix>_<field_name>`), establishes realistic operational weights within ISO/CSC container ratings, isolates cargo mass from container tare and SOLAS Verified Gross Mass (VGM), and specifies non-breaking integration with [`field_states.py`](file:///D:/Projects/portshield-1/field_states.py) and [`checks.py`](file:///D:/Projects/portshield-1/checks.py).

---

## 2. Document Provenance & Canonical Naming Contract

All extracted and validated trade fields strictly follow a `<document_prefix>_<field_name>` format reflecting source document provenance:

| Document Prefix | Document Name | File Reference | Sequence Index | Typical Source Authority |
| :--- | :--- | :--- | :---: | :--- |
| `ci_` | Commercial Invoice | `commercial_invoice.pdf` | Document 1 | Beneficiary / Exporter |
| `pl_` | Packing List | `packing_list.pdf` | Document 2 | Exporter / Warehouse / Packer |
| `bl_` | Ocean Bill of Lading | `bill_of_lading.pdf` | Document 3 | Ocean Carrier / Vessel Agent |
| `lc_` | Letter of Credit (MT700) | `letter_of_credit.pdf` | Document 4 | Issuing Bank / SWIFT Network |

### 2.1 Complete Canonical Field Registry

```
+-- Ports
|   +-- lc_port_of_discharge         (LC Tag 44F)
|   +-- bl_port_of_discharge         (BL Port of Discharge)
|   +-- bl_place_of_delivery         (BL Place of Final Delivery)
|   +-- bl_port_of_loading           (BL Port of Loading)
|
+-- Weights & Units
|   +-- pl_cargo_gross_weight        (PL Total Cargo Gross Weight)
|   +-- pl_cargo_gross_weight_unit   (PL Weight Unit: KGS)
|   +-- bl_cargo_gross_weight        (BL Total Cargo Gross Weight)
|   +-- bl_cargo_gross_weight_unit   (BL Weight Unit: KGS)
|   +-- ci_cargo_net_weight          (CI Stated Net Weight)
|   +-- ci_cargo_net_weight_unit     (CI Weight Unit: KGS)
|   +-- pl_cargo_net_weight          (PL Stated Net Weight)
|   +-- pl_cargo_net_weight_unit     (PL Weight Unit: KGS)
|
+-- Goods Description
|   +-- ci_goods_description         (CI Description of Goods)
|   +-- lc_goods_description         (LC Tag 45A Goods Description)
|
+-- Identifiers
|   +-- pl_container_number          (PL Container Identification)
|   +-- bl_container_number          (BL Container Identification)
|
+-- Financials
|   +-- ci_invoice_total             (CI Total Payable Amount)
|   +-- ci_currency                  (CI Currency Code: ISO 4217)
|   +-- ci_unit_price                (CI Unit Price)
|   +-- ci_quantity                  (CI Commercial Quantity)
|   +-- lc_amount                    (LC Tag 32B Face Amount)
|   +-- lc_currency                  (LC Tag 32B Currency Code)
|
+-- Shipment Dates
    +-- lc_latest_shipment_date      (LC Tag 44C Shipment Deadline)
    +-- bl_on_board_date             (BL Shipped on Board Date)
```

---

## 3. Operational Equipment Specifications & Weight Feasibility

### 3.1 40-foot High-Cube (40' HC) Container Rating Limits
Standard ISO 668 / CSC (Convention for Safe Containers) ratings establish maximum container gross ratings:
- **Maximum Gross Mass (Rating)**: $32,500\text{ KG}$ (or $30,480\text{ KG}$ for standard ISO containers).
- **Empty Container Box Tare**: $3,800\text{ KG}$ (for steel 40' HC).
- **Maximum Payload Capacity**: $\approx 28,700\text{ KG}$.

### 3.2 Harmonized Demonstration Baseline
To reflect realistic operations without exceeding safe transport limits, the demonstration fixtures adopt a **20.00 Metric Ton (20,000 KG)** net resin shipment:

$$\begin{aligned}
\text{Cargo Net Weight} &= 20,000.00\text{ KGS} \quad (800\text{ bags } @\ 25.00\text{ KG}) \\
\text{Packaging Tare} &= 1,600.00\text{ KGS} \quad (20\text{ pallets } @\ 75\text{ KG} + \text{bags/shrinkwrap}) \\
\mathbf{\text{Cargo Gross Weight}} &= \mathbf{21,600.00\text{ KGS}} \quad (\text{Clean Baseline \& PL}) \\
\text{Container Box Tare} &= 3,800.00\text{ KGS} \quad (40\text{' HC empty}) \\
\mathbf{\text{Verified Gross Mass (VGM)}} &= \mathbf{25,400.00\text{ KGS}} \quad (25.4\text{ MT} \le 32.5\text{ MT rating})
\end{aligned}$$

### 3.3 Financial Alignment & 5% LC Tolerance
$$\begin{aligned}
\text{Invoice Commercial Quantity} &= 20,000\text{ KGS} \\
\text{Unit Price} &= \text{USD } 1.25\text{ / KG} \\
\mathbf{\text{Invoice Total}} &= \mathbf{\text{USD } 25,000.00} \\
\text{LC Tolerance (Tag 39A)} &= +5\% / -5\% \\
\mathbf{\text{LC Face Amount (Tag 32B)}} &= \mathbf{\text{USD } 26,250.00} \quad (\text{USD } 25,000 \times 1.05)
\end{aligned}$$

### 3.4 Discrepancy Modeling (900 KG Transposition)
In the discrepancy packet:
- `pl_cargo_gross_weight`: **21,600.00 KGS**
- `bl_cargo_gross_weight`: **20,700.00 KGS**
- **Discrepancy**: $21,600 - 20,700 = 900.00\text{ KGS}$ transposition/typo shortage.
- **VGM on Discrepant BL**: $20,700 + 3,800 = 24,500.00\text{ KGS}$.
- **Isolation Guarantee**: Isolating cargo gross mass from container tare ($3,800\text{ KG}$) and VGM ($25,400\text{ KG}$) ensures the 900 KG transposition is flagged accurately without conflating tare components.

---

## 4. Compliance Check Rules Specification

### 4.1 Existing Baseline Checks (Mapped to Engine Format)
| Engine Rule | Evaluated Canonical Fields | Clean Evaluation | Discrepancy Evaluation |
| :--- | :--- | :--- | :--- |
| `Currency` | `lc_currency` vs. `ci_currency` | `USD == USD` (Passed) | `USD == USD` (Passed) |
| `Quantity (same unit required)` | `ci_quantity` vs. `pl_cargo_net_weight` | `20000 == 20000` (Passed) | `20000 == 20000` (Passed) |
| `Container identifier` | `pl_container_number` vs. `bl_container_number` | `MEDU1000060 == MEDU1000060` (Passed) | `MEDU1000067 == MEDU1000067` (Passed) |
| `Invoice amount limit` | `ci_invoice_total` vs. `lc_amount` | `25000.00 <= 26250.00` (Passed) | `25000.00 <= 26250.00` (Passed) |
| `Invoice arithmetic` | `ci_invoice_total` vs. `ci_quantity * ci_unit_price` | `25000 == 20000 * 1.25` (Passed) | `25000 == 20000 * 1.25` (Passed) |
| `Shipment deadline` | `bl_on_board_date` vs. `lc_latest_shipment_date` | `2026-11-10 <= 2026-11-15` (Passed) | `2026-11-10 <= 2026-11-15` (Passed) |

### 4.2 Future Compliance Checks
1. **Port of Discharge Consistency**:
   - Compares `bl_port_of_discharge` against `lc_port_of_discharge`.
   - Clean: `Chattogram Sea Port, Bangladesh == Chattogram Sea Port, Bangladesh` -> **Passed**.
   - Discrepancy: `Mongla Port, Bangladesh != Chattogram Sea Port, Bangladesh` -> **Review required**.
   - Distinct from `bl_place_of_delivery` (`Dhaka, Bangladesh`).
2. **Cargo Gross Weight Consistency**:
   - Compares `pl_cargo_gross_weight` against `bl_cargo_gross_weight`.
   - Clean: `21600 == 21600` -> **Passed**.
   - Discrepancy: `21600 != 20700` ($\Delta = 900\text{ KG}$) -> **Review required**.
3. **ISO 6346 Container Check Digit Verification**:
   - Evaluates modulus 11 checksum on `bl_container_number` and `pl_container_number`.
   - Clean: `MEDU1000060`: computed check digit $0 == 0$ -> **Passed**.
   - Discrepancy: `MEDU1000067`: computed check digit $0 \neq 7$ -> **Review required**.
4. **Goods Description Conformity (UCP 600 Art. 18c)**:
   - Compares `ci_goods_description` against `lc_goods_description`.
   - Clean: Both specify *Prime Virgin High Density Polyethylene (HDPE) Resin Grade HD5010* -> **Passed**.
   - Discrepancy: Invoice lists *Linear Low Density Polyethylene (LLDPE) Film Grade* -> **Review required**.

---

## 5. Field Lifecycle & Reviewer Confirmation Pipeline

The PortShield field lifecycle in [`field_states.py`](file:///D:/Projects/portshield-1/field_states.py) preserves original model extraction state while maintaining human confirmation state separately:

```
[missing] ──(Candidate Returned)──> [extracted] ──(Validation Failed)──> [rejected]
                                          │
                                          ├──(Unreadable Page)─────────> [unreadable]
                                          │
                                          ├──(Multiple Values)─────────> [conflicting]
                                          │
                                          └──(Human Confirmation)──────> [confirmed]
```

### Reviewer Confirmation Invariant
1. **Separation of Extraction State and Review State**:
   - `status`: Preserves the immutable extraction state (`extracted`, `rejected`, `unreadable`, `conflicting`, `missing`).
   - `review_status`: Records human review disposition (`pending`, `confirmed`, `unresolved`).
   - `reviewed_value`: Contains the human-audited value if modified or confirmed.
2. **Provenance & Candidate Audit Trail**:
   - The original AI candidate quote, document index, and page number remain stored in `evidence['_field_states'][field]['candidates']`.
   - Human review edits never overwrite or erase original candidate quotes or provenance manifests.
   - Usable values consumed by [`checks.py:audit()`](file:///D:/Projects/portshield-1/checks.py#L4-L28) require `review_status == 'confirmed'` when field states are active.

---

## 6. Verification & Test Guarantees

1. **Deterministic Regeneration**: All 12 demonstration PDFs compile deterministically via `py scripts/generate_chattogram_packets.py`.
2. **Multi-Page SWIFT MT700**: Letter of Credit paginates dynamically into 2 pages, rendering all tags through Tag 49 (`WITHOUT`) with watermark banners on every page.
3. **Behavioral Engine Execution**: Unit tests in [`test_chattogram_fixtures.py`](file:///D:/Projects/portshield-1/test_chattogram_fixtures.py) execute [`checks.py:audit()`](file:///D:/Projects/portshield-1/checks.py#L4-L28) on parsed answer-key values, asserting live `"Passed"` statuses.
4. **Direct Weight Calculation**: Unit tests directly evaluate `float(pl_gross) - float(bl_gross) == 900.0`.
5. **Exact Verbatim Citations**: 100% of answer-key quotations are verified verbatim in PDF page text layers via `pdf_viewer.locate_quote_on_page`.
