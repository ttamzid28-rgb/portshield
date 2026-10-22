#!/usr/bin/env python3
"""generate_chattogram_packets.py — Reproducible trade demonstration packet generator.

Generates 12 synthetic trade PDFs across 3 packet directories using PyMuPDF:
  - fixtures/packets/chattogram_clean/
  - fixtures/packets/chattogram_discrepancy/
  - fixtures/packets/chattogram_corrected/

Each packet contains:
  1. commercial_invoice.pdf
  2. packing_list.pdf
  3. bill_of_lading.pdf
  4. letter_of_credit.pdf

All generated PDFs display the mandatory synthetic watermarking banner:
  "FICTIONAL DEMONSTRATION DOCUMENT - FOR TESTING ONLY - NO COMMERCIAL OR BANKING VALUE"
"""

from __future__ import annotations

import os
from pathlib import Path
import pymupdf

# Target root directory
ROOT_DIR = Path(__file__).resolve().parent.parent
FIXTURES_DIR = ROOT_DIR / "fixtures" / "packets"

BANNER_TEXT = "FICTIONAL DEMONSTRATION DOCUMENT - FOR TESTING ONLY - NO COMMERCIAL OR BANKING VALUE"

# Shared Shipment Constants
LC_NUMBER = "26DC01EBL789012"
INVOICE_NUMBER = "BPC-INV-2026-9042"
PACKING_LIST_NUMBER = "BPC-PL-2026-9042"
BL_NUMBER = "EHCL-CGP-2026-8841"
VESSEL_VOYAGE = "M/V STAR HORIZON V.2618W"
SEAL_NUMBER = "KRS-982144"

SELLER_NAME = "BUSAN PETROCHEMICAL CORPORATION"
SELLER_ADDR = "124 Centum Jungang-ro, Haeundae-gu, Busan 48058, Republic of Korea"

BUYER_NAME = "Bengal Polymer Industries Ltd."
BUYER_ADDR = "Plot 14, Tejgaon I/A, Dhaka-1208, Bangladesh"

ISSUING_BANK = "Eastern Bank PLC, Principal Branch, Dhaka, Bangladesh"
ADVISING_BANK = "KEB Hana Bank, Busan Branch, South Korea"

PORT_OF_LOADING = "Busan, South Korea"
PLACE_OF_DELIVERY = "Dhaka, Bangladesh"

# Quantities & Weights
QUANTITY_KG = "40000"
QUANTITY_DISPLAY = "40,000 KGS"
UNIT_PRICE = "1.25"
UNIT_PRICE_DISPLAY = "USD 1.25 / KG"
INVOICE_TOTAL = "50000.00"
INVOICE_TOTAL_DISPLAY = "USD 50,000.00"
LC_AMOUNT = "52500.00"
LC_AMOUNT_DISPLAY = "USD 52,500.00"
CURRENCY = "USD"

NET_WEIGHT_KG = "40,000.00 KGS"
GROSS_WEIGHT_CLEAN_KG = "43,200.00 KGS"
GROSS_WEIGHT_DISCREPANCY_KG = "42,300.00 KGS"  # 900 kg transposition
CONTAINER_TARE_KG = "3,800.00 KGS"
VGM_CLEAN_KG = "47,000.00 KGS"
VGM_DISCREPANCY_KG = "46,100.00 KGS"

CONTAINER_VALID = "MEDU1000060"    # ISO 6346 check digit 0 (valid)
CONTAINER_INVALID = "MEDU1000067"  # ISO 6346 check digit 7 (invalid, expected 0)

GOODS_DESC_CLEAN = "Prime Virgin High Density Polyethylene (HDPE) Resin Grade HD5010"
GOODS_DESC_DISCREPANCY = "Linear Low Density Polyethylene (LLDPE) Film Grade"

DATE_LC_ISSUE = "2026-10-25"
DATE_INVOICE = "2026-11-02"
DATE_PACKING = "2026-11-02"
DATE_ON_BOARD = "2026-11-10"
DATE_LATEST_SHIPMENT = "2026-11-15"
DATE_LC_EXPIRY = "2026-12-05"


def draw_watermark_banner(page: pymupdf.Page, width: float = 612.0) -> None:
    """Render prominent synthetic demonstration banner across page top."""
    rect = pymupdf.Rect(20, 14, width - 20, 36)
    # Background fill: light warning amber
    page.draw_rect(rect, color=(0.85, 0.45, 0.1), fill=(1.0, 0.96, 0.88), width=1.0)
    page.insert_text(
        pymupdf.Point(26, 28),
        BANNER_TEXT,
        fontsize=8.5,
        fontname="helv",
        fontfile=None,
        color=(0.75, 0.15, 0.1),
    )


def draw_box(page: pymupdf.Page, rect: pymupdf.Rect, fill=None, stroke=(0.7, 0.7, 0.7), width=0.8) -> None:
    """Draw a bordered rectangle with optional background."""
    page.draw_rect(rect, color=stroke, fill=fill, width=width)


# ----------------------------------------------------------------------
# 1. Commercial Invoice
# ----------------------------------------------------------------------
def generate_commercial_invoice(packet_type: str, out_path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    draw_watermark_banner(page)

    is_revised = (packet_type == "corrected")
    is_discrepancy = (packet_type == "discrepancy")

    title = "COMMERCIAL INVOICE REV-1" if is_revised else "COMMERCIAL INVOICE"
    goods_desc = GOODS_DESC_DISCREPANCY if is_discrepancy else GOODS_DESC_CLEAN
    container_no = CONTAINER_INVALID if is_discrepancy else CONTAINER_VALID

    # Header section
    page.insert_text(pymupdf.Point(40, 60), SELLER_NAME, fontsize=14, fontname="hebo", color=(0.1, 0.2, 0.4))
    page.insert_text(pymupdf.Point(40, 75), SELLER_ADDR, fontsize=8.5, fontname="helv", color=(0.3, 0.3, 0.3))
    page.insert_text(pymupdf.Point(40, 88), "Tel: +82-51-749-8000 | Fax: +82-51-749-8009 | Email: export@busanpetrochem.co.kr", fontsize=8, fontname="helv", color=(0.4, 0.4, 0.4))

    # Title box
    title_rect = pymupdf.Rect(360, 50, 572, 85)
    draw_box(page, title_rect, fill=(0.94, 0.96, 0.98), stroke=(0.2, 0.4, 0.6), width=1.2)
    page.insert_text(pymupdf.Point(372, 72), title, fontsize=12, fontname="hebo", color=(0.1, 0.2, 0.5))

    if is_revised:
        rev_stamp = pymupdf.Rect(40, 96, 572, 116)
        draw_box(page, rev_stamp, fill=(0.93, 0.98, 0.93), stroke=(0.2, 0.6, 0.2), width=1.0)
        page.insert_text(pymupdf.Point(48, 110), "REVISION STAMP: AMENDED GOODS DESCRIPTION PER L/C CLAUSE 45A - REPLACES ORIGINAL INVOICE", fontsize=8.5, fontname="hebo", color=(0.1, 0.5, 0.1))

    # Metadata Grid
    top_y = 125 if is_revised else 105
    meta_rect = pymupdf.Rect(40, top_y, 572, top_y + 115)
    draw_box(page, meta_rect, fill=(0.99, 0.99, 0.99), stroke=(0.75, 0.75, 0.75))

    # Column 1
    page.insert_text(pymupdf.Point(48, top_y + 18), f"Invoice Number: {INVOICE_NUMBER}", fontsize=9.5, fontname="hebo")
    page.insert_text(pymupdf.Point(48, top_y + 35), f"Invoice Date: {DATE_INVOICE}", fontsize=9, fontname="helv")
    page.insert_text(pymupdf.Point(48, top_y + 52), f"Documentary Credit Number: {LC_NUMBER}", fontsize=9.5, fontname="hebo")
    page.insert_text(pymupdf.Point(48, top_y + 69), f"Issuing Bank: {ISSUING_BANK}", fontsize=8.5, fontname="helv")
    page.insert_text(pymupdf.Point(48, top_y + 86), f"Port of Loading: {PORT_OF_LOADING}", fontsize=9, fontname="helv")
    page.insert_text(pymupdf.Point(48, top_y + 103), f"Port of Discharge: Chattogram Sea Port, Bangladesh", fontsize=9, fontname="helv")

    # Column 2
    page.insert_text(pymupdf.Point(320, top_y + 18), "Buyer / Consignee:", fontsize=9.5, fontname="hebo")
    page.insert_text(pymupdf.Point(320, top_y + 33), BUYER_NAME, fontsize=9, fontname="hebo")
    page.insert_text(pymupdf.Point(320, top_y + 48), BUYER_ADDR, fontsize=8.5, fontname="helv")
    page.insert_text(pymupdf.Point(320, top_y + 69), f"Vessel / Voyage: {VESSEL_VOYAGE}", fontsize=9, fontname="helv")
    page.insert_text(pymupdf.Point(320, top_y + 86), f"Place of Final Destination: {PLACE_OF_DELIVERY}", fontsize=9, fontname="helv")
    page.insert_text(pymupdf.Point(320, top_y + 103), f"Terms of Delivery: CFR Chattogram Sea Port (Incoterms 2020)", fontsize=8.5, fontname="helv")

    # Table of Goods
    tbl_top = top_y + 130
    tbl_hdr = pymupdf.Rect(40, tbl_top, 572, tbl_top + 22)
    draw_box(page, tbl_hdr, fill=(0.9, 0.93, 0.96), stroke=(0.3, 0.4, 0.5), width=1.0)
    page.insert_text(pymupdf.Point(48, tbl_top + 15), "Item", fontsize=9, fontname="hebo")
    page.insert_text(pymupdf.Point(82, tbl_top + 15), "Description of Goods and Specifications", fontsize=9, fontname="hebo")
    page.insert_text(pymupdf.Point(340, tbl_top + 15), "Quantity", fontsize=9, fontname="hebo")
    page.insert_text(pymupdf.Point(425, tbl_top + 15), "Unit Price", fontsize=9, fontname="hebo")
    page.insert_text(pymupdf.Point(500, tbl_top + 15), "Total Amount", fontsize=9, fontname="hebo")

    tbl_row = pymupdf.Rect(40, tbl_top + 22, 572, tbl_top + 122)
    draw_box(page, tbl_row, fill=None, stroke=(0.7, 0.7, 0.7), width=0.8)

    page.insert_text(pymupdf.Point(50, tbl_top + 40), "01", fontsize=9.5, fontname="helv")
    page.insert_text(pymupdf.Point(82, tbl_top + 40), f"Description of Goods: {goods_desc}", fontsize=8.5, fontname="hebo")
    page.insert_text(pymupdf.Point(82, tbl_top + 56), f"Invoiced Quantity: {QUANTITY_DISPLAY} (1,600 Bags @ 25 KG net)", fontsize=8.5, fontname="hebo")
    page.insert_text(pymupdf.Point(82, tbl_top + 72), f"Unit Price: {UNIT_PRICE_DISPLAY}", fontsize=8.5, fontname="hebo")
    page.insert_text(pymupdf.Point(82, tbl_top + 88), f"Container Number: {container_no} | Seal Number: {SEAL_NUMBER}", fontsize=8.5, fontname="helv")
    page.insert_text(pymupdf.Point(82, tbl_top + 104), f"HS Code: 3901.20.90 | Country of Origin: Republic of Korea", fontsize=8.5, fontname="helv")

    page.insert_text(pymupdf.Point(340, tbl_top + 40), QUANTITY_DISPLAY, fontsize=9, fontname="hebo")
    page.insert_text(pymupdf.Point(425, tbl_top + 40), UNIT_PRICE_DISPLAY, fontsize=9, fontname="hebo")
    page.insert_text(pymupdf.Point(500, tbl_top + 40), f"USD {INVOICE_TOTAL}", fontsize=9, fontname="hebo")

    # Totals Box
    tot_top = tbl_top + 130
    tot_rect = pymupdf.Rect(40, tot_top, 572, tot_top + 110)
    draw_box(page, tot_rect, fill=(0.98, 0.98, 0.98), stroke=(0.7, 0.7, 0.7))

    page.insert_text(pymupdf.Point(48, tot_top + 22), f"Currency: {CURRENCY}", fontsize=10, fontname="hebo")
    page.insert_text(pymupdf.Point(48, tot_top + 42), f"Total Invoice Amount: {INVOICE_TOTAL_DISPLAY}", fontsize=10.5, fontname="hebo")
    page.insert_text(pymupdf.Point(48, tot_top + 60), f"Amount in Words: United States Dollars Fifty Thousand Only", fontsize=8.5, fontname="helv")
    page.insert_text(pymupdf.Point(48, tot_top + 80), f"Cargo Net Weight: {NET_WEIGHT_KG}", fontsize=9.5, fontname="hebo")
    page.insert_text(pymupdf.Point(48, tot_top + 98), f"Cargo Gross Weight: {GROSS_WEIGHT_CLEAN_KG}", fontsize=9.5, fontname="hebo")

    page.insert_text(pymupdf.Point(340, tot_top + 22), "Banking Details for Settlement:", fontsize=8.5, fontname="hebo")
    page.insert_text(pymupdf.Point(340, tot_top + 38), f"Bank: {ADVISING_BANK}", fontsize=8, fontname="helv")
    page.insert_text(pymupdf.Point(340, tot_top + 52), "SWIFT: KOEXKRSE | Account: 082-910024-8841", fontsize=8, fontname="helv")
    page.insert_text(pymupdf.Point(340, tot_top + 68), "Beneficiary: Busan Petrochemical Corporation", fontsize=8, fontname="helv")

    # Signature
    sig_top = tot_top + 125
    page.insert_text(pymupdf.Point(40, sig_top + 20), "We hereby certify that this invoice is true and correct and that the goods are of South Korean origin.", fontsize=8, fontname="helv", color=(0.3, 0.3, 0.3))
    page.insert_text(pymupdf.Point(380, sig_top + 45), "For and on behalf of", fontsize=8.5, fontname="helv")
    page.insert_text(pymupdf.Point(380, sig_top + 60), SELLER_NAME, fontsize=9.5, fontname="hebo")
    page.insert_text(pymupdf.Point(380, sig_top + 90), "Authorized Signatory: K. H. Park (Export Director)", fontsize=8.5, fontname="helv")

    doc.save(str(out_path))
    doc.close()


# ----------------------------------------------------------------------
# 2. Packing List
# ----------------------------------------------------------------------
def generate_packing_list(packet_type: str, out_path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    draw_watermark_banner(page)

    is_revised = (packet_type == "corrected")
    is_discrepancy = (packet_type == "discrepancy")

    title = "PACKING LIST"
    container_no = CONTAINER_INVALID if is_discrepancy else CONTAINER_VALID

    # Header section
    page.insert_text(pymupdf.Point(40, 60), SELLER_NAME, fontsize=14, fontname="hebo", color=(0.1, 0.2, 0.4))
    page.insert_text(pymupdf.Point(40, 75), SELLER_ADDR, fontsize=8.5, fontname="helv", color=(0.3, 0.3, 0.3))

    # Title box
    title_rect = pymupdf.Rect(380, 50, 572, 85)
    draw_box(page, title_rect, fill=(0.94, 0.96, 0.98), stroke=(0.2, 0.4, 0.6), width=1.2)
    page.insert_text(pymupdf.Point(420, 72), title, fontsize=13, fontname="hebo", color=(0.1, 0.2, 0.5))

    # Metadata Grid
    top_y = 98
    meta_rect = pymupdf.Rect(40, top_y, 572, top_y + 115)
    draw_box(page, meta_rect, fill=(0.99, 0.99, 0.99), stroke=(0.75, 0.75, 0.75))

    page.insert_text(pymupdf.Point(48, top_y + 18), f"Packing List Number: {PACKING_LIST_NUMBER}", fontsize=9.5, fontname="hebo")
    page.insert_text(pymupdf.Point(48, top_y + 35), f"Packing List Date: {DATE_PACKING}", fontsize=9, fontname="helv")
    page.insert_text(pymupdf.Point(48, top_y + 52), f"Invoice Reference: {INVOICE_NUMBER}", fontsize=9, fontname="hebo")
    page.insert_text(pymupdf.Point(48, top_y + 69), f"Documentary Credit Number: {LC_NUMBER}", fontsize=9.5, fontname="hebo")
    page.insert_text(pymupdf.Point(48, top_y + 86), f"Port of Loading: {PORT_OF_LOADING}", fontsize=9, fontname="helv")
    page.insert_text(pymupdf.Point(48, top_y + 103), f"Port of Discharge: Chattogram Sea Port, Bangladesh", fontsize=9, fontname="helv")

    page.insert_text(pymupdf.Point(320, top_y + 18), "Buyer / Consignee:", fontsize=9.5, fontname="hebo")
    page.insert_text(pymupdf.Point(320, top_y + 33), BUYER_NAME, fontsize=9, fontname="hebo")
    page.insert_text(pymupdf.Point(320, top_y + 48), BUYER_ADDR, fontsize=8.5, fontname="helv")
    page.insert_text(pymupdf.Point(320, top_y + 69), f"Vessel / Voyage: {VESSEL_VOYAGE}", fontsize=9, fontname="helv")
    page.insert_text(pymupdf.Point(320, top_y + 86), f"Place of Final Destination: {PLACE_OF_DELIVERY}", fontsize=9, fontname="helv")
    page.insert_text(pymupdf.Point(320, top_y + 103), f"Shipping Marks: BPI / DHAKA / CHATTOGRAM", fontsize=8.5, fontname="helv")

    # Equipment & Container Specifications Box
    eq_top = top_y + 125
    eq_rect = pymupdf.Rect(40, eq_top, 572, eq_top + 95)
    draw_box(page, eq_rect, fill=(0.96, 0.97, 0.99), stroke=(0.3, 0.45, 0.65), width=1.0)

    page.insert_text(pymupdf.Point(48, eq_top + 18), "EQUIPMENT & CONTAINER SPECIFICATIONS", fontsize=10, fontname="hebo", color=(0.1, 0.25, 0.5))
    page.insert_text(pymupdf.Point(48, eq_top + 38), f"Container Number: {container_no}", fontsize=10, fontname="hebo")
    page.insert_text(pymupdf.Point(48, eq_top + 55), f"Seal Number: {SEAL_NUMBER}", fontsize=9, fontname="helv")
    page.insert_text(pymupdf.Point(48, eq_top + 72), f"Equipment Size / Type: 1 x 40ft High Cube Ocean Container (40' HC)", fontsize=9, fontname="helv")
    page.insert_text(pymupdf.Point(48, eq_top + 88), f"Total Packaging Units: 1,600 Bags on 40 Industrial Wooden Pallets", fontsize=9, fontname="helv")

    page.insert_text(pymupdf.Point(320, eq_top + 38), f"Quantity: {QUANTITY_DISPLAY}", fontsize=10, fontname="hebo")
    page.insert_text(pymupdf.Point(320, eq_top + 55), f"Unit Net Mass per Bag: 25.00 KGS", fontsize=9, fontname="helv")
    page.insert_text(pymupdf.Point(320, eq_top + 72), f"Pallet Configuration: 40 Bags per Pallet (1,000 KG net/pallet)", fontsize=8.5, fontname="helv")
    page.insert_text(pymupdf.Point(320, eq_top + 88), f"Packaging Material: Heavy-Duty Multi-Wall Polyethylene Bags", fontsize=8.5, fontname="helv")

    # Harmonized Weight Breakdown Table
    wt_top = eq_top + 108
    wt_hdr = pymupdf.Rect(40, wt_top, 572, wt_top + 22)
    draw_box(page, wt_hdr, fill=(0.9, 0.93, 0.96), stroke=(0.3, 0.4, 0.5), width=1.0)
    page.insert_text(pymupdf.Point(48, wt_top + 15), "Weight Category & Specification", fontsize=9, fontname="hebo")
    page.insert_text(pymupdf.Point(340, wt_top + 15), "Components Included", fontsize=9, fontname="hebo")
    page.insert_text(pymupdf.Point(480, wt_top + 15), "Weight", fontsize=9, fontname="hebo")

    wt_box = pymupdf.Rect(40, wt_top + 22, 572, wt_top + 140)
    draw_box(page, wt_box, fill=None, stroke=(0.7, 0.7, 0.7))

    page.insert_text(pymupdf.Point(48, wt_top + 42), f"Cargo Net Weight: {NET_WEIGHT_KG}", fontsize=9.5, fontname="hebo")
    page.insert_text(pymupdf.Point(340, wt_top + 42), "1,600 PE bags @ 25 KG net", fontsize=8.5, fontname="helv")
    page.insert_text(pymupdf.Point(480, wt_top + 42), NET_WEIGHT_KG, fontsize=9, fontname="hebo")

    page.insert_text(pymupdf.Point(48, wt_top + 65), "Tare Weight (Packaging & Pallets): 3,200.00 KGS", fontsize=9, fontname="helv")
    page.insert_text(pymupdf.Point(340, wt_top + 65), "40 Pallets + 1,600 PE Bags", fontsize=8.5, fontname="helv")
    page.insert_text(pymupdf.Point(480, wt_top + 65), "3,200.00 KGS", fontsize=9, fontname="helv")

    page.insert_text(pymupdf.Point(48, wt_top + 88), f"Cargo Gross Weight: {GROSS_WEIGHT_CLEAN_KG}", fontsize=10, fontname="hebo", color=(0.1, 0.2, 0.5))
    page.insert_text(pymupdf.Point(340, wt_top + 88), "Net Cargo + Pallets & Bags", fontsize=8.5, fontname="helv")
    page.insert_text(pymupdf.Point(480, wt_top + 88), GROSS_WEIGHT_CLEAN_KG, fontsize=10, fontname="hebo", color=(0.1, 0.2, 0.5))

    page.insert_text(pymupdf.Point(48, wt_top + 112), f"Container Tare Weight: {CONTAINER_TARE_KG}", fontsize=9, fontname="helv")
    page.insert_text(pymupdf.Point(340, wt_top + 112), "Empty 40' HC Container Tare", fontsize=8.5, fontname="helv")
    page.insert_text(pymupdf.Point(480, wt_top + 112), CONTAINER_TARE_KG, fontsize=9, fontname="helv")

    page.insert_text(pymupdf.Point(48, wt_top + 135), f"Verified Gross Mass (VGM): {VGM_CLEAN_KG}", fontsize=9.5, fontname="hebo")
    page.insert_text(pymupdf.Point(340, wt_top + 135), "SOLAS Method 1 Verified Total", fontsize=8.5, fontname="helv")
    page.insert_text(pymupdf.Point(480, wt_top + 135), VGM_CLEAN_KG, fontsize=9.5, fontname="hebo")

    # Goods Description confirmation
    desc_top = wt_top + 165
    desc_rect = pymupdf.Rect(40, desc_top, 572, desc_top + 45)
    draw_box(page, desc_rect, fill=(0.98, 0.98, 0.98), stroke=(0.75, 0.75, 0.75))
    page.insert_text(pymupdf.Point(48, desc_top + 18), "Description of Goods: Prime Virgin High Density Polyethylene (HDPE) Resin Grade HD5010", fontsize=9, fontname="hebo")
    page.insert_text(pymupdf.Point(48, desc_top + 34), "Lot Numbers: 2610-HD5010-01 through 2610-HD5010-40 | 100% Prime Virgin Quality", fontsize=8.5, fontname="helv")

    # Signatures
    sig_top = desc_top + 55
    page.insert_text(pymupdf.Point(40, sig_top + 15), "Certified true and correct packing details.", fontsize=8, fontname="helv", color=(0.4, 0.4, 0.4))
    page.insert_text(pymupdf.Point(380, sig_top + 25), "For BUSAN PETROCHEMICAL CORPORATION", fontsize=9, fontname="hebo")
    page.insert_text(pymupdf.Point(380, sig_top + 55), "Logistics Manager: S. W. Choi", fontsize=8.5, fontname="helv")

    doc.save(str(out_path))
    doc.close()


# ----------------------------------------------------------------------
# 3. Bill of Lading
# ----------------------------------------------------------------------
def generate_bill_of_lading(packet_type: str, out_path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    draw_watermark_banner(page)

    is_revised = (packet_type == "corrected")
    is_discrepancy = (packet_type == "discrepancy")

    title = "REVISED BILL OF LADING" if is_revised else "BILL OF LADING FOR OCEAN TRANSPORT"
    pod = "Mongla Port, Bangladesh" if is_discrepancy else "Chattogram Sea Port, Bangladesh"
    container_no = CONTAINER_INVALID if is_discrepancy else CONTAINER_VALID
    gross_weight = GROSS_WEIGHT_DISCREPANCY_KG if is_discrepancy else GROSS_WEIGHT_CLEAN_KG
    vgm = VGM_DISCREPANCY_KG if is_discrepancy else VGM_CLEAN_KG

    # Carrier header
    page.insert_text(pymupdf.Point(40, 58), "EASTERN HORIZON CONTAINER LINES INC.", fontsize=13, fontname="hebo", color=(0.05, 0.15, 0.35))
    page.insert_text(pymupdf.Point(40, 72), "Global Multimodal Transport & Ocean Bill of Lading", fontsize=8, fontname="helv", color=(0.35, 0.35, 0.35))

    title_rect = pymupdf.Rect(350, 48, 572, 80)
    draw_box(page, title_rect, fill=(0.94, 0.96, 0.99), stroke=(0.2, 0.35, 0.55), width=1.1)
    page.insert_text(pymupdf.Point(362, 68), title, fontsize=11, fontname="hebo", color=(0.05, 0.15, 0.4))

    if is_revised:
        rev_box = pymupdf.Rect(40, 88, 572, 108)
        draw_box(page, rev_box, fill=(0.93, 0.98, 0.93), stroke=(0.2, 0.6, 0.2), width=1.0)
        page.insert_text(pymupdf.Point(46, 102), "REVISION 1: CORRECTED DISCHARGE PORT TO CHATTOGRAM, GROSS WEIGHT TO 43,200 KGS, CONTAINER TO MEDU1000060", fontsize=8, fontname="hebo", color=(0.1, 0.5, 0.1))

    # Transport Parties Box
    box1_top = 114 if is_revised else 92
    box1 = pymupdf.Rect(40, box1_top, 572, box1_top + 130)
    draw_box(page, box1, fill=None, stroke=(0.7, 0.7, 0.7))

    # Left half: Shipper, Consignee, Notify
    page.insert_text(pymupdf.Point(46, box1_top + 15), "Shipper / Exporter:", fontsize=8.5, fontname="hebo")
    page.insert_text(pymupdf.Point(46, box1_top + 28), SELLER_NAME, fontsize=8.5, fontname="helv")
    page.insert_text(pymupdf.Point(46, box1_top + 40), SELLER_ADDR, fontsize=7.5, fontname="helv")

    page.insert_text(pymupdf.Point(46, box1_top + 58), "Consignee:", fontsize=8.5, fontname="hebo")
    page.insert_text(pymupdf.Point(46, box1_top + 71), "TO ORDER OF EASTERN BANK PLC, DHAKA, BANGLADESH", fontsize=8.5, fontname="hebo")

    page.insert_text(pymupdf.Point(46, box1_top + 90), "Notify Party:", fontsize=8.5, fontname="hebo")
    page.insert_text(pymupdf.Point(46, box1_top + 103), BUYER_NAME, fontsize=8.5, fontname="helv")
    page.insert_text(pymupdf.Point(46, box1_top + 115), BUYER_ADDR, fontsize=7.5, fontname="helv")

    # Right half: BL Number, Booking Ref, Export Ref
    page.insert_text(pymupdf.Point(340, box1_top + 15), f"B/L Number: {BL_NUMBER}", fontsize=10, fontname="hebo")
    page.insert_text(pymupdf.Point(340, box1_top + 32), f"Booking Reference: BKG-2026-BUS-9912", fontsize=8.5, fontname="helv")
    page.insert_text(pymupdf.Point(340, box1_top + 48), f"Export Reference: EXP-2026-BD-8841", fontsize=8.5, fontname="helv")
    page.insert_text(pymupdf.Point(340, box1_top + 65), f"Documentary Credit Number: {LC_NUMBER}", fontsize=9, fontname="hebo")
    page.insert_text(pymupdf.Point(340, box1_top + 82), "Commercial Invoice Ref: BPC-INV-2026-9042", fontsize=8.5, fontname="helv")
    page.insert_text(pymupdf.Point(340, box1_top + 100), "Freight Status: FREIGHT PREPAID", fontsize=9, fontname="hebo")

    # Voyage & Port Routing Box
    box2_top = box1_top + 136
    box2 = pymupdf.Rect(40, box2_top, 572, box2_top + 58)
    draw_box(page, box2, fill=(0.98, 0.98, 0.98), stroke=(0.7, 0.7, 0.7))

    page.insert_text(pymupdf.Point(46, box2_top + 16), f"Ocean Vessel / Voyage: {VESSEL_VOYAGE}", fontsize=9, fontname="hebo")
    page.insert_text(pymupdf.Point(46, box2_top + 34), f"Port of Loading: {PORT_OF_LOADING}", fontsize=9, fontname="helv")
    page.insert_text(pymupdf.Point(46, box2_top + 50), f"Port of Discharge: {pod}", fontsize=9.5, fontname="hebo", color=(0.1, 0.15, 0.5) if not is_discrepancy else (0.8, 0.1, 0.1))

    page.insert_text(pymupdf.Point(340, box2_top + 16), "Place of Receipt: Busan Container Terminal", fontsize=8.5, fontname="helv")
    page.insert_text(pymupdf.Point(340, box2_top + 34), f"Place of Delivery: {PLACE_OF_DELIVERY}", fontsize=9.5, fontname="hebo")
    page.insert_text(pymupdf.Point(340, box2_top + 50), "Final Destination: Dhaka Inland Depot", fontsize=8.5, fontname="helv")

    # Cargo Particulars Table
    tbl_top = box2_top + 66
    tbl_hdr = pymupdf.Rect(40, tbl_top, 572, tbl_top + 22)
    draw_box(page, tbl_hdr, fill=(0.9, 0.93, 0.96), stroke=(0.3, 0.4, 0.5), width=1.0)

    page.insert_text(pymupdf.Point(46, tbl_top + 15), "Container Identification", fontsize=8.5, fontname="hebo")
    page.insert_text(pymupdf.Point(210, tbl_top + 15), "Description of Goods and Packaging", fontsize=8.5, fontname="hebo")
    page.insert_text(pymupdf.Point(460, tbl_top + 15), "Weight & Volume", fontsize=8.5, fontname="hebo")

    tbl_body = pymupdf.Rect(40, tbl_top + 22, 572, tbl_top + 130)
    draw_box(page, tbl_body, fill=None, stroke=(0.7, 0.7, 0.7))

    page.insert_text(pymupdf.Point(46, tbl_top + 40), f"Container Number: {container_no}", fontsize=9.5, fontname="hebo")
    page.insert_text(pymupdf.Point(46, tbl_top + 56), f"Seal Number: {SEAL_NUMBER}", fontsize=8.5, fontname="helv")
    page.insert_text(pymupdf.Point(46, tbl_top + 72), "1 x 40' High Cube FCL/FCL", fontsize=8.5, fontname="helv")
    page.insert_text(pymupdf.Point(46, tbl_top + 88), "Marks: BPI/CGP/2026", fontsize=8.5, fontname="helv")

    page.insert_text(pymupdf.Point(210, tbl_top + 40), "1x40FT HC CONTAINER S.T.C. 1,600 BAGS", fontsize=9, fontname="hebo")
    page.insert_text(pymupdf.Point(210, tbl_top + 54), "HIGH DENSITY POLYETHYLENE RESIN HD5010", fontsize=8.5, fontname="helv")
    page.insert_text(pymupdf.Point(210, tbl_top + 68), "PACKED ON 40 INDUSTRIAL PALLETS", fontsize=8.5, fontname="helv")
    page.insert_text(pymupdf.Point(210, tbl_top + 84), "CLEAN ON BOARD OCEAN VESSEL", fontsize=8.5, fontname="hebo")
    page.insert_text(pymupdf.Point(210, tbl_top + 98), f"L/C NUMBER: {LC_NUMBER}", fontsize=8.5, fontname="helv")
    page.insert_text(pymupdf.Point(210, tbl_top + 114), f"Cargo Gross Weight: {gross_weight}", fontsize=9.5, fontname="hebo", color=(0.1, 0.15, 0.5) if not is_discrepancy else (0.8, 0.1, 0.1))

    page.insert_text(pymupdf.Point(460, tbl_top + 40), f"Gross: {gross_weight}", fontsize=8.5, fontname="helv")
    page.insert_text(pymupdf.Point(460, tbl_top + 56), f"Tare: {CONTAINER_TARE_KG}", fontsize=8.5, fontname="helv")
    page.insert_text(pymupdf.Point(460, tbl_top + 72), f"VGM: {vgm}", fontsize=8.5, fontname="hebo")
    page.insert_text(pymupdf.Point(460, tbl_top + 88), "Volume: 68.40 CBM", fontsize=8.5, fontname="helv")

    # Shipped on board box
    sob_top = tbl_top + 138
    sob_rect = pymupdf.Rect(40, sob_top, 572, sob_top + 45)
    draw_box(page, sob_rect, fill=(0.95, 0.98, 0.95), stroke=(0.2, 0.55, 0.2), width=1.0)

    page.insert_text(pymupdf.Point(48, sob_top + 18), "SHIPPED ON BOARD NOTATION / CONFIRMATION:", fontsize=9, fontname="hebo", color=(0.1, 0.45, 0.1))
    page.insert_text(pymupdf.Point(48, sob_top + 34), f"Shipped on Board Date: {DATE_ON_BOARD}", fontsize=10, fontname="hebo", color=(0.05, 0.4, 0.05))
    page.insert_text(pymupdf.Point(340, sob_top + 34), f"Vessel: {VESSEL_VOYAGE} at Busan Port", fontsize=8.5, fontname="helv")

    # Carrier signature & issue box
    bot_top = sob_top + 52
    page.insert_text(pymupdf.Point(40, bot_top + 15), "RECEIVED in apparent good order and condition unless otherwise stated.", fontsize=7.5, fontname="helv", color=(0.4, 0.4, 0.4))
    page.insert_text(pymupdf.Point(40, bot_top + 30), f"Place and Date of Issue: Busan, Republic of Korea, {DATE_ON_BOARD}", fontsize=8.5, fontname="helv")
    page.insert_text(pymupdf.Point(380, bot_top + 30), "For EASTERN HORIZON CONTAINER LINES INC.", fontsize=8.5, fontname="hebo")
    page.insert_text(pymupdf.Point(380, bot_top + 58), "As Master / Authorized Carrier Agent", fontsize=8, fontname="helv")

    doc.save(str(out_path))
    doc.close()


# ----------------------------------------------------------------------
# 4. Letter of Credit (SWIFT MT700 format)
# ----------------------------------------------------------------------
def generate_letter_of_credit(packet_type: str, out_path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    draw_watermark_banner(page)

    # SWIFT MT700 Header
    page.insert_text(pymupdf.Point(40, 56), "SWIFT FINANCIAL MESSAGING SERVICE - INCOMING MESSAGE", fontsize=11, fontname="hebo", color=(0.1, 0.2, 0.4))
    page.insert_text(pymupdf.Point(40, 70), "SWIFT MT700: ISSUE OF A DOCUMENTARY CREDIT", fontsize=10, fontname="hebo", color=(0.2, 0.3, 0.5))

    # Sender / Receiver Box
    hdr_box = pymupdf.Rect(40, 78, 572, 130)
    draw_box(page, hdr_box, fill=(0.97, 0.98, 0.99), stroke=(0.6, 0.7, 0.8))

    page.insert_text(pymupdf.Point(48, 93), "Sender:", fontsize=8.5, fontname="hebo")
    page.insert_text(pymupdf.Point(100, 93), "EASTERN BANK PLC, PRINCIPAL BRANCH, DHAKA, BANGLADESH", fontsize=8.5, fontname="helv")
    page.insert_text(pymupdf.Point(100, 105), "SWIFT BIC: EBLDBDDHXXX", fontsize=8.5, fontname="hebo")

    page.insert_text(pymupdf.Point(340, 93), "Receiver:", fontsize=8.5, fontname="hebo")
    page.insert_text(pymupdf.Point(395, 93), "KEB HANA BANK, BUSAN BRANCH, KOREA", fontsize=8.5, fontname="helv")
    page.insert_text(pymupdf.Point(395, 105), "SWIFT BIC: KOEXKRSEXXX", fontsize=8.5, fontname="hebo")

    page.insert_text(pymupdf.Point(48, 122), f"Message Priority: NORMAL | Mur Ref: 20261025-EBLD-789012 | Session: 0412 Sequence: 009841", fontsize=7.5, fontname="helv", color=(0.3, 0.3, 0.3))

    # SWIFT Tags Table
    tbl_top = 138
    tbl_box = pymupdf.Rect(40, tbl_top, 572, 755)
    draw_box(page, tbl_box, fill=None, stroke=(0.7, 0.7, 0.7))

    tags = [
        ("27", "Sequence of Total", "1/1"),
        ("40A", "Form of Documentary Credit", "IRREVOCABLE"),
        ("20", "Documentary Credit Number", LC_NUMBER),
        ("31C", "Date of Issue", DATE_LC_ISSUE),
        ("31D", "Date and Place of Expiry", f"{DATE_LC_EXPIRY} IN SOUTH KOREA"),
        ("50", "Applicant", f"{BUYER_NAME.upper()}\n{BUYER_ADDR.upper()}"),
        ("59", "Beneficiary", f"{SELLER_NAME}\n{SELLER_ADDR.upper()}"),
        ("32B", "Currency Code, Amount", f"Currency: {CURRENCY} Amount: {LC_AMOUNT_DISPLAY}"),
        ("39A", "Percentage Credit Amount Tolerance", "5/5"),
        ("41D", "Available With... By...", "ANY BANK BY NEGOTIATION"),
        ("42C", "Drafts at...", "AT SIGHT FOR 100 PCT OF INVOICE VALUE"),
        ("43P", "Partial Shipments", "NOT ALLOWED"),
        ("43T", "Transhipment", "NOT ALLOWED"),
        ("44E", "Port of Loading / Airport", f"44E: Port of Loading: {PORT_OF_LOADING}"),
        ("44F", "Port of Discharge / Destination", "44F: Port of Discharge: Chattogram Sea Port, Bangladesh"),
        ("44B", "Place of Final Destination", f"Place of Final Destination: {PLACE_OF_DELIVERY}"),
        ("44C", "Latest Date of Shipment", f"44C: Latest Date of Shipment: {DATE_LATEST_SHIPMENT}"),
        ("45A", "Description of Goods and/or Services",
         f"45A: Description of Goods: {GOODS_DESC_CLEAN}\n"
         f"QUANTITY: 40,000 KGS (+/- 5 PCT)\n"
         f"UNIT PRICE: USD 1.25 PER KG CFR CHATTOGRAM SEA PORT, BANGLADESH"),
        ("46A", "Documents Required",
         "+ SIGNED COMMERCIAL INVOICE IN 3 ORIGINALS AND 3 COPIES.\n"
         "+ FULL SET CLEAN ON BOARD OCEAN BILLS OF LADING CONSIGNED TO ORDER OF EASTERN BANK PLC.\n"
         "+ PACKING LIST IN 3 ORIGINALS SHOWING GROSS WEIGHT, NET WEIGHT AND CONTAINER NUMBER."),
        ("47A", "Additional Conditions",
         "+ ALL DOCUMENTS MUST STATE L/C NUMBER 26DC01EBL789012.\n"
         "+ SHIPMENT MUST BE EFFECTED IN 1 X 40FT CONTAINER WITH VALID ISO 6346 IDENTIFIER.\n"
         "+ THIRD PARTY BILLS OF LADING ARE ACCEPTABLE."),
        ("71D", "Charges", "ALL BANKING CHARGES OUTSIDE BANGLADESH ARE FOR BENEFICIARY ACCOUNT."),
        ("48", "Period for Presentation", "21 DAYS AFTER SHIPMENT DATE BUT WITHIN CREDIT VALIDITY."),
        ("49", "Confirmation Instructions", "WITHOUT"),
    ]

    curr_y = tbl_top + 16
    for tag, name, content in tags:
        # Tag label
        page.insert_text(pymupdf.Point(48, curr_y), f":{tag}:", fontsize=8.5, fontname="hebo", color=(0.1, 0.25, 0.55))
        # Tag name
        page.insert_text(pymupdf.Point(82, curr_y), name, fontsize=8, fontname="hebo", color=(0.25, 0.25, 0.25))

        # Content lines
        lines = content.split("\n")
        line_y = curr_y + 12
        for line in lines:
            page.insert_text(pymupdf.Point(82, line_y), line, fontsize=8, fontname="helv", color=(0.0, 0.0, 0.0))
            line_y += 11

        curr_y = line_y + 3
        if curr_y > 750:
            break

    doc.save(str(out_path))
    doc.close()


def generate_all_packets() -> None:
    """Generate all 12 PDF files across clean, discrepancy, and corrected folders."""
    packets = ["chattogram_clean", "chattogram_discrepancy", "chattogram_corrected"]
    packet_types = {
        "chattogram_clean": "clean",
        "chattogram_discrepancy": "discrepancy",
        "chattogram_corrected": "corrected",
    }

    for folder in packets:
        folder_path = FIXTURES_DIR / folder
        os.makedirs(folder_path, exist_ok=True)
        ptype = packet_types[folder]

        ci_path = folder_path / "commercial_invoice.pdf"
        pl_path = folder_path / "packing_list.pdf"
        bl_path = folder_path / "bill_of_lading.pdf"
        lc_path = folder_path / "letter_of_credit.pdf"

        print(f"Generating packet: {folder} ({ptype})...")
        generate_commercial_invoice(ptype, ci_path)
        generate_packing_list(ptype, pl_path)
        generate_bill_of_lading(ptype, bl_path)
        generate_letter_of_credit(ptype, lc_path)

    print("\nAll 12 demonstration PDFs successfully generated.")


if __name__ == "__main__":
    generate_all_packets()
