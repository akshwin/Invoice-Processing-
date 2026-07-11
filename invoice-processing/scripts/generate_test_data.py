"""
Generates reproducible test invoice PDFs per BRD Section 8.4.

Produces, into data/invoices/:
  - 4 happy-path invoices from different fictional vendors, each matching a PO
    in data/po_dataset.csv (one uses an explicit PO reference, one uses implicit
    vendor+amount matching, one is within tolerance but not exact, to exercise
    different matching/validation branches on the happy path).
  - 1 EC-1 invoice: amount meaningfully outside BR-4 tolerance of its matched PO.
  - 1 EC-2 invoice: missing its total (a required field per BR-2), so extraction
    must return null rather than compute/guess it.

Layouts are deliberately varied per vendor (field order, header wording, PO
reference wording) to mimic the "every vendor formats differently" premise in
the BRD, without requiring OCR (all text stays machine-readable).

Run: python scripts/generate_test_data.py
"""
import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "invoices")
os.makedirs(OUT_DIR, exist_ok=True)

styles = getSampleStyleSheet()
title_style = ParagraphStyle("title", parent=styles["Heading1"], fontSize=18, spaceAfter=4)
label_style = ParagraphStyle("label", parent=styles["Normal"], fontSize=10, textColor=colors.HexColor("#555555"))
normal = styles["Normal"]


def _money(n):
    return f"-${-n:,.2f}" if n < 0 else f"${n:,.2f}"


def build_invoice_pdf(
    filename,
    vendor_name,
    vendor_address,
    invoice_number,
    invoice_date,
    bill_to,
    line_items,
    subtotal,
    tax,
    total,
    po_reference=None,
    po_label="PO Reference",
    header_style="standard",
    show_total=True,
    notes=None,
    tax_breakdown=None,
):
    """line_items: list of (description, quantity, unit_price, amount).

    notes: optional paragraph rendered after the summary table — used to simulate a
    PO reference mentioned in running text rather than a labeled field.
    tax_breakdown: optional list of (label, amount) rendered as separate tax rows
    (e.g. state + local tax) instead of a single "Tax" row; `tax` is ignored if set.
    """
    path = os.path.join(OUT_DIR, filename)
    doc = SimpleDocTemplate(path, pagesize=letter, topMargin=0.6 * inch, bottomMargin=0.6 * inch)
    elements = []

    if header_style == "standard":
        elements.append(Paragraph(vendor_name, title_style))
        elements.append(Paragraph(vendor_address, label_style))
        elements.append(Spacer(1, 12))
        elements.append(Paragraph(f"<b>INVOICE</b> #{invoice_number}", styles["Heading2"]))
        elements.append(Paragraph(f"Date: {invoice_date}", normal))
        if po_reference:
            elements.append(Paragraph(f"{po_label}: {po_reference}", normal))
        elements.append(Spacer(1, 8))
        elements.append(Paragraph(f"Bill To: {bill_to}", normal))
    elif header_style == "compact":
        elements.append(Paragraph(f"<b>{vendor_name}</b> - {vendor_address}", normal))
        elements.append(Spacer(1, 10))
        elements.append(Paragraph(f"Invoice No: {invoice_number}    Issued: {invoice_date}", styles["Heading3"]))
        if po_reference:
            elements.append(Paragraph(f"{po_label}: {po_reference}", normal))
        elements.append(Paragraph(f"Customer: {bill_to}", normal))
    elif header_style == "minimal":
        elements.append(Paragraph(vendor_name, title_style))
        elements.append(Paragraph(f"{invoice_date}", label_style))
        elements.append(Spacer(1, 10))
        elements.append(Paragraph(f"Invoice {invoice_number}", styles["Heading2"]))
        elements.append(Paragraph(f"For: {bill_to}", normal))
        if po_reference:
            elements.append(Paragraph(f"{po_label} {po_reference}", normal))

    elements.append(Spacer(1, 16))

    table_data = [["Description", "Qty", "Unit Price", "Amount"]]
    for desc, qty, unit_price, amount in line_items:
        table_data.append([desc, str(qty), _money(unit_price), _money(amount)])

    table = Table(table_data, colWidths=[3.0 * inch, 0.7 * inch, 1.3 * inch, 1.3 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2b3a4a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f2f2")]),
            ]
        )
    )
    elements.append(table)
    elements.append(Spacer(1, 14))

    summary_rows = [["Subtotal", _money(subtotal)]]
    if tax_breakdown:
        for label, amount in tax_breakdown:
            summary_rows.append([label, _money(amount)])
    elif tax is not None:
        summary_rows.append(["Tax", _money(tax)])
    if show_total:
        summary_rows.append(["TOTAL DUE", _money(total)])

    summary_table = Table(summary_rows, colWidths=[4.3 * inch, 1.3 * inch])
    summary_style = [
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
    ]
    if show_total:
        summary_style += [
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("LINEABOVE", (0, -1), (-1, -1), 1, colors.black),
        ]
    summary_table.setStyle(TableStyle(summary_style))
    elements.append(summary_table)

    if notes:
        elements.append(Spacer(1, 18))
        elements.append(Paragraph(notes, normal))

    doc.build(elements)
    print(f"Generated {path}")


def make_scanned_pdf(source_filename, scanned_filename, dpi=150):
    """Rasterizes an existing text-based invoice PDF into an image-only PDF with no
    text layer, to simulate a real scanned/photographed invoice (EC-3)."""
    import fitz

    source_path = os.path.join(OUT_DIR, source_filename)
    scanned_path = os.path.join(OUT_DIR, scanned_filename)

    src_doc = fitz.open(source_path)
    out_doc = fitz.open()
    for page in src_doc:
        pix = page.get_pixmap(dpi=dpi)
        img_page = out_doc.new_page(width=page.rect.width, height=page.rect.height)
        img_page.insert_image(page.rect, pixmap=pix)
    out_doc.save(scanned_path)
    out_doc.close()
    src_doc.close()
    os.remove(source_path)
    print(f"Generated {scanned_path} (image-only, no text layer)")


def make_skewed_scan(source_filename, scanned_filename, dpi=150, angle=3.5):
    """Rasterizes a PDF into an image-only PDF, rotated slightly to simulate a real
    scanned page that wasn't perfectly aligned on the scanner bed or in the camera
    frame."""
    import io

    import fitz
    from PIL import Image

    source_path = os.path.join(OUT_DIR, source_filename)
    scanned_path = os.path.join(OUT_DIR, scanned_filename)

    src_doc = fitz.open(source_path)
    out_doc = fitz.open()
    for page in src_doc:
        pix = page.get_pixmap(dpi=dpi)
        img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
        rotated = img.rotate(angle, expand=True, fillcolor=(255, 255, 255), resample=Image.BICUBIC)
        buf = io.BytesIO()
        rotated.save(buf, format="PNG")
        img_page = out_doc.new_page(width=rotated.width * 72 / dpi, height=rotated.height * 72 / dpi)
        img_page.insert_image(img_page.rect, stream=buf.getvalue())
    out_doc.save(scanned_path)
    out_doc.close()
    src_doc.close()
    os.remove(source_path)
    print(f"Generated {scanned_path} (skewed {angle} degree scan, no text layer)")


def make_noisy_scan(source_filename, scanned_filename, dpi=100):
    """Rasterizes a PDF at low resolution with added noise, slight blur, and JPEG
    recompression artifacts, to simulate a poor-quality scanner or a phone photo
    taken in bad lighting."""
    import io

    import fitz
    import numpy as np
    from PIL import Image, ImageFilter

    rng = np.random.default_rng(42)  # deterministic noise, reproducible output
    source_path = os.path.join(OUT_DIR, source_filename)
    scanned_path = os.path.join(OUT_DIR, scanned_filename)

    src_doc = fitz.open(source_path)
    out_doc = fitz.open()
    for page in src_doc:
        pix = page.get_pixmap(dpi=dpi)
        img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
        img = img.filter(ImageFilter.GaussianBlur(radius=0.6))
        arr = np.array(img).astype(np.int16)
        noise = rng.normal(0, 10, arr.shape).astype(np.int16)
        arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
        img = Image.fromarray(arr)
        jpeg_buf = io.BytesIO()
        img.save(jpeg_buf, format="JPEG", quality=45)  # lossy recompression artifacts
        img = Image.open(jpeg_buf).convert("RGB")
        png_buf = io.BytesIO()
        img.save(png_buf, format="PNG")
        img_page = out_doc.new_page(width=img.width * 72 / dpi, height=img.height * 72 / dpi)
        img_page.insert_image(img_page.rect, stream=png_buf.getvalue())
    out_doc.save(scanned_path)
    out_doc.close()
    src_doc.close()
    os.remove(source_path)
    print(f"Generated {scanned_path} (low-quality/noisy scan, no text layer)")


def build_freeform_invoice_pdf(filename, po_number_for_notes):
    """A deliberately unfamiliar invoice layout to stress-test format generalization:
    no line-item table (bullet-style text lines instead), different field vocabulary
    ("Invoice Ref" / "Client" / "Issued" / "Related PO" / "Amount Due"), a DD/MM/YYYY
    date, and "USD 123.45" currency notation instead of "$123.45". Built from raw
    flowables rather than build_invoice_pdf, since the whole point is that it does
    not share that function's table-based structure."""
    path = os.path.join(OUT_DIR, filename)
    doc = SimpleDocTemplate(path, pagesize=letter, topMargin=0.75 * inch, bottomMargin=0.75 * inch)
    elements = []

    right_style = ParagraphStyle("right", parent=normal, alignment=2)  # 2 = TA_RIGHT

    elements.append(Paragraph("<b>ZENITH CLOUD SERVICES</b>", title_style))
    elements.append(Paragraph("A division of Zenith Digital Holdings", label_style))
    elements.append(Spacer(1, 20))

    elements.append(Paragraph("Invoice Ref: ZCS-2026-0442", normal))
    elements.append(Paragraph("Issued: 22/05/2026", normal))
    elements.append(Paragraph(f"Related PO: {po_number_for_notes}", normal))
    elements.append(Paragraph("Client: Zamp Operations", normal))
    elements.append(Spacer(1, 24))

    elements.append(Paragraph("<b>Services rendered this cycle:</b>", normal))
    elements.append(Spacer(1, 8))
    elements.append(Paragraph("3 x Cloud Compute Instance (m5.large) @ USD 85.00 each = USD 255.00", normal))
    elements.append(Paragraph("1 x Managed Database Add-on @ USD 120.00 each = USD 120.00", normal))
    elements.append(Paragraph("12 x Support Hours @ USD 45.00 each = USD 540.00", normal))
    elements.append(Spacer(1, 24))

    elements.append(Paragraph("<b>Amount Due: USD 915.00</b>", ParagraphStyle("amt", parent=normal, fontSize=13)))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph("Payment due within 30 days. Thank you for your business.", label_style))

    doc.build(elements)
    print(f"Generated {path}")


def main():
    # --- Happy path 1: exact match, explicit PO reference, standard layout ---
    build_invoice_pdf(
        filename="INV-1001_bluebird.pdf",
        vendor_name="Bluebird Supplies Inc.",
        vendor_address="14 Harbor Lane, Portland, OR 97201",
        invoice_number="INV-1001",
        invoice_date="2026-05-12",
        bill_to="Zamp Operations, 500 Market St, San Francisco, CA",
        line_items=[
            ("Office chairs (ergonomic)", 10, 350.00, 3500.00),
            ("Standing desks", 2, 500.00, 1000.00),
        ],
        subtotal=4500.00,
        tax=0.00,
        total=4500.00,
        po_reference="PO-10234",
        header_style="standard",
    )

    # --- Happy path 2: exact match, explicit PO, compact layout ---
    build_invoice_pdf(
        filename="INV-2044_meridian.pdf",
        vendor_name="Meridian Office Solutions",
        vendor_address="88 Kettering Ave, Austin, TX 78701",
        invoice_number="INV-2044",
        invoice_date="2026-05-14",
        bill_to="Zamp Operations",
        line_items=[
            ("Printer paper (case)", 20, 45.00, 900.00),
            ("Toner cartridges", 8, 125.00, 1000.00),
            ("Filing cabinets", 1, 400.50, 400.50),
        ],
        subtotal=2300.50,
        tax=0.00,
        total=2300.50,
        po_reference="PO-10235",
        po_label="Purchase Order #",
        header_style="compact",
    )

    # --- Happy path 3: within tolerance but not exact (delta $20 < $50), explicit PO ---
    build_invoice_pdf(
        filename="INV-3390_crestview.pdf",
        vendor_name="Crestview Logistics LLC",
        vendor_address="900 Dock Rd, Newark, NJ 07102",
        invoice_number="INV-3390",
        invoice_date="2026-05-15",
        bill_to="Zamp Operations",
        line_items=[
            ("Freight - regional route", 4, 1990.00, 7960.00),
            ("Fuel surcharge", 1, 810.00, 810.00),
        ],
        subtotal=8770.00,
        tax=0.00,
        total=8770.00,  # PO-10236 is 8750.00 -> delta $20, within $50 tolerance
        po_reference="PO-10236",
        header_style="standard",
    )

    # --- Happy path 4: implicit matching, no PO reference printed, minimal layout ---
    build_invoice_pdf(
        filename="INV-4502_northgate.pdf",
        vendor_name="Northgate Industrial Parts",
        vendor_address="221 Foundry St, Cleveland, OH 44113",
        invoice_number="INV-4502",
        invoice_date="2026-05-16",
        bill_to="Zamp Operations",
        line_items=[
            ("Steel brackets (box of 50)", 6, 150.00, 900.00),
            ("Bolt assortment kit", 5, 60.00, 300.00),
        ],
        subtotal=1200.00,
        tax=0.00,
        total=1200.00,
        po_reference=None,  # no PO number on this invoice -> match by vendor + amount
        header_style="minimal",
    )

    # --- EC-1: amount mismatch outside tolerance, explicit PO ---
    build_invoice_pdf(
        filename="INV-5810_alderwood_EC1_amount_mismatch.pdf",
        vendor_name="Alderwood Consulting Group",
        vendor_address="77 Summit Blvd, Denver, CO 80202",
        invoice_number="INV-5810",
        invoice_date="2026-05-18",
        bill_to="Zamp Operations",
        line_items=[
            ("Process advisory - May engagement", 1, 5600.00, 5600.00),
            ("Additional workshop session (out of scope)", 1, 600.00, 600.00),
        ],
        subtotal=6200.00,
        tax=0.00,
        total=6200.00,  # PO-10238 is 5600.00 -> delta $600, well outside 2%/$50 tolerance
        po_reference="PO-10238",
        header_style="standard",
    )

    # --- EC-2: missing total (no total printed anywhere), explicit PO ---
    build_invoice_pdf(
        filename="INV-6021_fairview_EC2_missing_total.pdf",
        vendor_name="Fairview Business Services",
        vendor_address="12 Elm Court, Raleigh, NC 27601",
        invoice_number="INV-6021",
        invoice_date="2026-05-19",
        bill_to="Zamp Operations",
        line_items=[
            ("Payroll processing - May", 1, 1800.00, 1800.00),
            ("HR compliance review", 1, 1400.00, 1400.00),
        ],
        subtotal=3200.00,
        tax=None,
        total=None,
        po_reference="PO-10239",
        header_style="compact",
        show_total=False,  # deliberately no total line anywhere on the invoice
    )

    # --- EC-3: scanned/image-based invoice (no text layer at all) ---
    # Built as a normal text PDF first, then rasterized to an image-only PDF so
    # pdfplumber finds zero extractable text and the pipeline must fall back to the
    # vision-based extraction path (BR-1 matching still applies normally afterward).
    build_invoice_pdf(
        filename="_scan_source_temp.pdf",
        vendor_name="Summit Hardware Co.",
        vendor_address="450 Foundry Row, Pittsburgh, PA 15222",
        invoice_number="INV-7188",
        invoice_date="2026-05-21",
        bill_to="Zamp Operations",
        line_items=[
            ("Hand tools assortment", 4, 140.00, 560.00),
            ("Tool chest (steel)", 1, 400.00, 400.00),
        ],
        subtotal=960.00,
        tax=0.00,
        total=960.00,  # PO-10240 is 960.00 -> exact match, happy path via scanned input
        po_reference="PO-10240",
        header_style="standard",
    )
    make_scanned_pdf("_scan_source_temp.pdf", "INV-7188_summit_EC3_scanned.pdf")

    # --- Scanned variant 2: skewed scan (imperfect scanner/camera alignment) ---
    build_invoice_pdf(
        filename="_scan_source_temp2.pdf",
        vendor_name="Cascade Parts & Supply",
        vendor_address="1180 Millrace Ave, Spokane, WA 99201",
        invoice_number="INV-9110",
        invoice_date="2026-05-22",
        bill_to="Zamp Operations",
        line_items=[
            ("Ball bearings (box of 100)", 6, 175.00, 1050.00),
            ("Drive belts", 20, 30.00, 600.00),
            ("Lubricant (5gal drum)", 10, 50.00, 500.00),
        ],
        subtotal=2150.00,
        tax=0.00,
        total=2150.00,  # PO-10244 is 2150.00 -> exact match, happy path via skewed scan
        po_reference="PO-10244",
        header_style="standard",
    )
    make_skewed_scan("_scan_source_temp2.pdf", "INV-9110_cascade_scanned_skewed.pdf")

    # --- Scanned variant 3: low-quality/noisy scan (poor scanner or phone photo) ---
    build_invoice_pdf(
        filename="_scan_source_temp3.pdf",
        vendor_name="Ironclad Freight Co.",
        vendor_address="77 Dockside Blvd, Norfolk, VA 23510",
        invoice_number="INV-9225",
        invoice_date="2026-05-23",
        bill_to="Zamp Operations",
        line_items=[
            ("Freight - long haul route", 3, 1160.00, 3480.00),
            ("Fuel surcharge", 1, 300.00, 300.00),
        ],
        subtotal=3780.00,
        tax=0.00,
        total=3780.00,  # PO-10245 is 3780.00 -> exact match, happy path via noisy scan
        po_reference="PO-10245",
        header_style="compact",
    )
    make_noisy_scan("_scan_source_temp3.pdf", "INV-9225_ironclad_scanned_lowquality.pdf")

    # --- Scanned variant 4: multi-page scan (no text layer, spans 2 pages) ---
    pinnacle_items = [
        ("Excavator rental (weekly)", 2, 1200.00, 2400.00),
        ("Bulldozer rental (weekly)", 1, 1800.00, 1800.00),
        ("Concrete mixer rental", 3, 150.00, 450.00),
        ("Scaffolding sections", 20, 45.00, 900.00),
        ("Generator rental (5kW)", 4, 200.00, 800.00),
        ("Air compressor rental", 2, 175.00, 350.00),
        ("Forklift rental (weekly)", 1, 950.00, 950.00),
        ("Traffic cones (set of 50)", 3, 60.00, 180.00),
        ("Safety barriers", 10, 35.00, 350.00),
        ("Portable lighting towers", 4, 220.00, 880.00),
        ("Pressure washer rental", 2, 90.00, 180.00),
        ("Trench box rental", 1, 600.00, 600.00),
        ("Skid steer rental (weekly)", 1, 1100.00, 1100.00),
        ("Water pump rental", 3, 120.00, 360.00),
        ("Welding machine rental", 2, 210.00, 420.00),
        ("Site office trailer (monthly)", 1, 850.00, 850.00),
        ("Portable toilets (weekly)", 4, 95.00, 380.00),
        ("Dumpster rental (20yd)", 2, 400.00, 800.00),
        ("Crane rental (daily)", 1, 1500.00, 1500.00),
        ("Survey equipment rental", 1, 300.00, 300.00),
    ]
    # Duplicated as a second batch (distinct descriptions) to push the table past a
    # single page — reportlab's Table flowable splits across pages on its own.
    pinnacle_items = pinnacle_items + [
        (f"{desc} (Batch 2)", qty, price, amount) for desc, qty, price, amount in pinnacle_items
    ]
    pinnacle_total = sum(amount for _, _, _, amount in pinnacle_items)
    build_invoice_pdf(
        filename="_scan_source_temp4.pdf",
        vendor_name="Pinnacle Equipment Rentals",
        vendor_address="2200 Yard Rd, Fresno, CA 93706",
        invoice_number="INV-9340",
        invoice_date="2026-05-24",
        bill_to="Zamp Operations",
        line_items=pinnacle_items,
        subtotal=pinnacle_total,
        tax=0.00,
        total=pinnacle_total,  # PO-10246 matches exactly
        po_reference="PO-10246",
        header_style="standard",
    )
    make_scanned_pdf("_scan_source_temp4.pdf", "INV-9340_pinnacle_scanned_multipage.pdf")

    # --- Wildly different format: no table, different field vocabulary, DD/MM/YYYY
    # date, "USD 123.45" currency notation instead of "$123.45" ---
    build_freeform_invoice_pdf("INV-ZCS-0442_zenith_freeform_format.pdf", "PO-10247")

    # --- Complex 1: many line items forcing a multi-page invoice ---
    riverside_items = [
        ("Steel rods (10ft)", 50, 22.00, 1100.00),
        ("Aluminum sheets", 30, 45.50, 1365.00),
        ("Copper wiring (100ft spool)", 20, 60.00, 1200.00),
        ("Industrial bolts (box)", 40, 15.25, 610.00),
        ("Safety helmets", 25, 18.00, 450.00),
        ("Work gloves (pair)", 60, 8.50, 510.00),
        ("Welding rods (box)", 15, 35.00, 525.00),
        ("Hydraulic hose (10ft)", 12, 40.00, 480.00),
        ("Pressure gauges", 10, 65.00, 650.00),
        ("Steel brackets", 80, 6.25, 500.00),
        ("Conveyor belt sections", 5, 220.00, 1100.00),
        ("Industrial fasteners", 100, 3.10, 310.00),
        ("Protective coating (gal)", 20, 28.00, 560.00),
        ("Machine oil (5gal)", 15, 32.00, 480.00),
        ("Packaging crates", 40, 21.25, 850.00),
    ]
    # Duplicated as a second batch (distinct descriptions) purely to push the table
    # past a single page — reportlab's Table flowable splits across pages on its own.
    riverside_items = riverside_items + [
        (f"{desc} (Batch 2)", qty, price, amount) for desc, qty, price, amount in riverside_items
    ]
    riverside_total = sum(amount for _, _, _, amount in riverside_items)
    build_invoice_pdf(
        filename="INV-7742_riverside_complex_multipage.pdf",
        vendor_name="Riverside Manufacturing Co.",
        vendor_address="88 Industrial Pkwy, Toledo, OH 43604",
        invoice_number="INV-7742",
        invoice_date="2026-05-20",
        bill_to="Zamp Operations",
        line_items=riverside_items,
        subtotal=riverside_total,
        tax=0.00,
        total=riverside_total,  # PO-10242 matches exactly
        po_reference="PO-10242",
        header_style="standard",
    )

    # --- Complex 2: discount line item, split tax lines, embedded PO reference in
    # running text, and a non-ISO date format ---
    harbor_subtotal = 6000.00 + 2500.00 - 500.00
    harbor_tax_breakdown = [("State tax (6%)", 480.00), ("Local tax (1.5%)", 120.00)]
    harbor_total = harbor_subtotal + sum(amount for _, amount in harbor_tax_breakdown)
    build_invoice_pdf(
        filename="INV-8850_harborpoint_complex_discount_tax.pdf",
        vendor_name="Harbor Point Consulting",
        vendor_address="9 Wharf Street, Baltimore, MD 21201",
        invoice_number="INV-8850",
        invoice_date="June 3, 2026",  # non-ISO date format on purpose
        bill_to="Zamp Operations",
        line_items=[
            ("Strategic advisory - Q2 engagement", 1, 6000.00, 6000.00),
            ("On-site workshop facilitation", 2, 1250.00, 2500.00),
            ("Volume discount", 1, -500.00, -500.00),
        ],
        subtotal=harbor_subtotal,
        tax=None,
        tax_breakdown=harbor_tax_breakdown,
        total=harbor_total,  # PO-10243 matches exactly
        po_reference=None,  # no labeled PO field — reference is embedded in notes below
        header_style="compact",
        notes="Please reference our purchase order (PO-10243) dated May 2026 when processing this payment.",
    )


if __name__ == "__main__":
    main()
