"""
TheraTrak Pro – CMS-1500 (02/12) PDF generator using ReportLab.
Generates an 8.5 × 11 inch letter-size PDF with all CMS-1500 fields.
"""
from datetime import date
from pathlib import Path

try:
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib.utils import ImageReader
    REPORTLAB_OK = True
except ImportError:
    REPORTLAB_OK = False

try:
    from app_paths import ASSETS_DIR
except ImportError:
    ASSETS_DIR = Path(__file__).resolve().parent / "assets"


# ─── Constants ─────────────────────────────────────────────────────────────────

W, H = letter  # 612 × 792 pt

# Margins (in points)
LEFT = 0.2 * inch
RIGHT = W - 0.2 * inch

# Font settings
FONT = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
FONT_SM = 7
FONT_MD = 8
FONT_LG = 10


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _draw_box(c, x, y, w, h_box):
    c.rect(x, y, w, h_box)


def _label(c, text, x, y, size=6, bold=False):
    c.setFont(FONT_BOLD if bold else FONT, size)
    c.drawString(x, y, text)


def _value(c, text, x, y, size=FONT_MD):
    c.setFont(FONT, size)
    c.drawString(x, y, str(text) if text else "")


def _checkbox(c, x, y, checked=False, label=""):
    sz = 8
    c.rect(x, y, sz, sz)
    if checked:
        c.setFont(FONT_BOLD, 9)
        c.drawString(x + 1, y + 1, "X")
    if label:
        c.setFont(FONT, FONT_SM)
        c.drawString(x + sz + 2, y + 1, label)


# ─── Main PDF builder ──────────────────────────────────────────────────────────

def build_cms1500_pdf(output_path: str, fd: dict) -> bool:
    """
    Build a CMS-1500 form PDF.
    fd = form_data dict with all field keys listed below.
    Returns True on success.
    """
    if not REPORTLAB_OK:
        return False

    c = rl_canvas.Canvas(output_path, pagesize=letter)
    if not _draw_form_on_sample_background(c, fd):
        _draw_form(c, fd)
    c.save()
    return True


def _alignment_section_for_field(field_name: str) -> str:
    if field_name.startswith("sl"):
        return "line"
    if field_name.startswith("dx") or field_name in {"resubmission_code", "original_ref_no"}:
        return "dx"
    if field_name in {
        "illness_date", "ref_provider", "ref_npi", "illness_qual", "other_date",
        "other_date_qual", "unable_from", "unable_to", "add_info", "ref_qual",
        "auth_number", "hospital_from", "hospital_to", "outside_lab",
        "outside_lab_charge", "related_emp_yes", "related_emp_no", "related_auto_yes",
        "related_auto_no", "related_auto_state", "related_other_yes", "related_other_no",
        "reserved_local_use",
    }:
        return "mid"
    if field_name in {
        "tax_id", "tax_id_ein", "tax_id_ssn", "patient_acct", "accept_assign", "total_charge",
        "amount_paid", "provider_sig", "provider_sig_date", "billing_date",
        "facility_name", "facility_address", "facility_city_state_zip", "facility_qualifier",
        "facility_npi", "facility_other_id", "billing_name", "billing_address",
        "billing_city_state_zip", "billing_phone", "billing_qualifier", "billing_npi",
        "billing_other_id",
    }:
        return "bot"
    return "top"


def _aligned_xy(fd: dict, field_name: str, x: float, y: float):
    alignment = fd.get("alignment_offsets", {}) if isinstance(fd, dict) else {}
    section_offsets = alignment.get("section_offsets", {}) if isinstance(alignment, dict) else {}
    field_offsets = alignment.get("field_offsets", {}) if isinstance(alignment, dict) else {}
    section = _alignment_section_for_field(field_name)
    sec_x, sec_y = section_offsets.get(section, [0, 0])
    fld_x, fld_y = field_offsets.get(field_name, [0, 0])
    return x + sec_x + fld_x, y + sec_y + fld_y


def _draw_form_on_sample_background(c, fd):
    """Draw values over the bundled CMS sample image background."""
    sample_image = ASSETS_DIR / "cms1500_sample.png"
    if not sample_image.exists():
        return False

    try:
        bg = ImageReader(str(sample_image))
    except Exception:
        return False

    # The on-screen field map uses these pixel coordinates from the sample image.
    bg_w = 1170.0
    bg_h = 1515.0
    sx = W / bg_w
    sy = H / bg_h

    def px_to_pt_x(x):
        return x * sx

    def px_to_pt_y(y):
        # ReportLab origin is bottom-left; field map y is top-origin.
        return H - (y * sy)

    c.drawImage(bg, 0, 0, width=W, height=H, preserveAspectRatio=False, mask="auto")
    c.setFillColorRGB(0, 0, 0)

    def draw_field(name, x, y, size=12):
        val = fd.get(name, "")
        if val is None:
            return
        text = str(val).strip()
        if not text:
            return
        ax, ay = _aligned_xy(fd, name, x, y)
        c.setFont(FONT, size)
        c.drawString(px_to_pt_x(ax), px_to_pt_y(ay), text)

    field_positions = [
        ("ins_id", 760, 212),
        ("patient_name", 44, 283),
        ("patient_dob", 492, 285),
        ("patient_sex", 665, 285),
        ("patient_sex_f", 688, 285),
        ("ins_name", 760, 283),
        ("patient_address", 40, 337),
        ("ins_relation_self", 486, 337),
        ("ins_relation_spouse", 533, 337),
        ("ins_relation_child", 580, 337),
        ("ins_relation_other", 627, 337),
        ("ins_address2", 760, 337),
        ("patient_city", 40, 390),
        ("patient_state", 392, 390),
        ("patient_zip", 40, 448),
        ("patient_phone", 216, 448),
        ("ins_city2", 760, 390),
        ("ins_state2", 1088, 390),
        ("ins_zip2", 760, 448),
        ("ins_phone", 934, 448),
        ("other_ins_name", 40, 504),
        ("other_ins_policy", 40, 560),
        ("other_ins_sex", 604, 559),
        ("other_ins_sex_f", 632, 559),
        ("ins_group", 760, 503),
        ("ins_dob", 816, 559),
        ("ins_sex", 1032, 559),
        ("ins_sex_f", 1054, 559),
        ("other_claim_id", 760, 617),
        ("ins_plan", 760, 621),
        ("other_plan", 40, 676),
        ("patient_sig", 110, 742),
        ("patient_sig_date", 502, 742),
        ("ins_sig", 787, 742),
        ("illness_date", 38, 823),
        ("illness_qual", 206, 823),
        ("other_date", 432, 823),
        ("other_date_qual", 600, 823),
        ("unable_from", 816, 823),
        ("unable_to", 997, 823),
        ("ref_provider", 38, 880),
        ("ref_qual", 421, 880),
        ("ref_npi", 459, 880),
        ("hospital_from", 817, 880),
        ("hospital_to", 998, 880),
        ("add_info", 38, 939),
        ("outside_lab", 816, 939),
        ("outside_lab_charge", 972, 939),
        ("dx1", 95, 977),
        ("dx2", 286, 977),
        ("dx3", 477, 977),
        ("dx4", 669, 977),
        ("dx5", 95, 1007),
        ("dx6", 286, 1007),
        ("dx7", 477, 1007),
        ("dx8", 669, 1007),
        ("dx9", 95, 1037),
        ("dx10", 286, 1037),
        ("dx11", 477, 1037),
        ("dx12", 669, 1037),
        ("resubmission_code", 816, 974),
        ("original_ref_no", 936, 974),
        ("auth_number", 760, 994),
        ("tax_id", 38, 1365),
        ("tax_id_ein", 223, 1365),
        ("patient_acct", 381, 1365),
        ("accept_assign", 605, 1365),
        ("total_charge", 774, 1365),
        ("amount_paid", 928, 1365),
        ("provider_sig", 38, 1425),
        ("provider_sig_date", 294, 1425),
        ("billing_date", 271, 1501),
        ("facility_name", 378, 1425),
        ("facility_address", 378, 1460),
        ("facility_city_state_zip", 378, 1492),
        ("tax_id_ssn", 472, 1501),
        ("facility_npi", 496, 1501),
        ("facility_other_id", 661, 1501),
        ("billing_name", 771, 1425),
        ("billing_address", 771, 1460),
        ("billing_city_state_zip", 771, 1492),
        ("billing_phone", 1000, 1365),
        ("billing_qualifier", 756, 1501),
        ("billing_npi", 780, 1501),
        ("billing_other_id", 947, 1501),
    ]

    for name, x, y in field_positions:
        draw_field(name, x, y)

    line_y = [1048, 1105, 1162, 1219, 1276, 1333]
    service_lines = fd.get("service_lines", [])
    for i, y in enumerate(line_y):
        sl = service_lines[i] if i < len(service_lines) else {}
        if not sl:
            continue
        c.setFont(FONT, 12)
        for key, x in [
            ("from_date", 47),
            ("to_date", 162),
            ("pos", 285),
            ("cpt", 369),
            ("modifier", 468),
            ("dx_ptr", 648),
            ("charge", 769),
            ("units", 872),
            ("epsdt", 919),
            ("family_plan", 946),
            ("id_qual", 979),
            ("npi", 1000),
        ]:
            txt = str(sl.get(key, "") or "").strip()
            if txt:
                field_name = f"sl{i+1}_{key}"
                ax, ay = _aligned_xy(fd, field_name, x, y)
                c.drawString(px_to_pt_x(ax), px_to_pt_y(ay), txt)

    return True


def _draw_form(c, fd):
    """Draw the entire CMS-1500 form onto canvas c."""
    # ── Page border / title ───────────────────────────────────────────────────
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(0.5)

    _label(c, "HEALTH INSURANCE CLAIM FORM", W / 2 - 80, H - 0.35 * inch,
           size=11, bold=True)
    _label(c, "APPROVED BY NATIONAL UNIFORM CLAIM COMMITTEE (NUCC) 02/12",
           W / 2 - 110, H - 0.5 * inch, size=6)

    # ── Row heights / layout (y positions from top of page) ──────────────────
    # We define row y-coords measuring from BOTTOM (ReportLab origin).
    # Row 1:  Insurance type checkboxes          y ≈ 720
    # Row 2:  Patient/Insured info               y ≈ 680-700
    # Row 3:  Patient address / insured address  y ≈ 640-660
    # Row 4:  Other coverage                     y ≈ 580-630
    # Row 5:  Condition / dates                  y ≈ 540-570
    # Row 6:  Referring provider / hospitalization y ≈ 500-530
    # Row 7:  Dx codes (Box 21)                  y ≈ 460-490
    # Row 8:  Service lines (Box 24)             y ≈ 320-450
    # Row 9:  Provider/billing info              y ≈ 130-310

    bx = 0.25 * inch
    row1_y = H - 0.75 * inch
    row_h = 0.28 * inch

    # ── BOX 1: Insurance type ─────────────────────────────────────────────────
    _draw_box(c, bx, row1_y, 6.5 * inch, row_h)
    _label(c, "1. INSURANCE TYPE:", bx + 2, row1_y + 10, bold=True)
    ins_type = fd.get("ins_type", "")
    types = [("Medicare", "Medicare"), ("Medicaid", "Medicaid"),
             ("TRICARE", "TRICARE"), ("CHAMPVA", "CHAMPVA"),
             ("Group Health Plan", "GroupHP"), ("FECA/BLK LUNG", "FECA"),
             ("Other", "Other")]
    tx = bx + 90
    for lbl, key in types:
        _checkbox(c, tx, row1_y + 4, ins_type == key, lbl)
        tx += 65

    # ── BOX 1a: Insured ID ────────────────────────────────────────────────────
    r2y = row1_y - row_h
    _draw_box(c, bx, r2y, 3.0 * inch, row_h)
    _label(c, "1a. INSURED'S I.D. NUMBER", bx + 2, r2y + 10, bold=True)
    _value(c, fd.get("ins_id", ""), bx + 2, r2y + 2)

    # ── BOX 2: Patient name ───────────────────────────────────────────────────
    _draw_box(c, bx + 3.0 * inch, r2y, 2.0 * inch, row_h)
    _label(c, "2. PATIENT'S NAME (Last, First, MI)", bx + 3.0 * inch + 2, r2y + 10, bold=True)
    _value(c, fd.get("patient_name", ""), bx + 3.0 * inch + 2, r2y + 2)

    # ── BOX 3: DOB / Sex ──────────────────────────────────────────────────────
    _draw_box(c, bx + 5.0 * inch, r2y, 1.75 * inch, row_h)
    _label(c, "3. PATIENT'S BIRTH DATE / SEX", bx + 5.0 * inch + 2, r2y + 10, bold=True)
    _value(c, f"{fd.get('patient_dob','')}  {fd.get('patient_sex','')}", bx + 5.0 * inch + 2, r2y + 2)

    # ── BOX 4: Insured's name ─────────────────────────────────────────────────
    r3y = r2y - row_h
    _draw_box(c, bx, r3y, 3.0 * inch, row_h)
    _label(c, "4. INSURED'S NAME (Last, First, MI)", bx + 2, r3y + 10, bold=True)
    _value(c, fd.get("ins_name", ""), bx + 2, r3y + 2)

    # ── BOX 5: Patient address ────────────────────────────────────────────────
    _draw_box(c, bx + 3.0 * inch, r3y, 2.0 * inch, row_h)
    _label(c, "5. PATIENT'S ADDRESS (No., Street)", bx + 3.0 * inch + 2, r3y + 10, bold=True)
    _value(c, fd.get("patient_address", ""), bx + 3.0 * inch + 2, r3y + 2)

    # ── BOX 6: Relationship ───────────────────────────────────────────────────
    _draw_box(c, bx + 5.0 * inch, r3y, 1.75 * inch, row_h)
    _label(c, "6. PATIENT REL. TO INSURED", bx + 5.0 * inch + 2, r3y + 10, bold=True)
    _value(c, fd.get("ins_relation", ""), bx + 5.0 * inch + 2, r3y + 2)

    # ── BOX 7: City/State/Zip ─────────────────────────────────────────────────
    r4y = r3y - row_h
    _draw_box(c, bx, r4y, 3.0 * inch, row_h)
    _label(c, "CITY / STATE / ZIP", bx + 2, r4y + 10, bold=True)
    csz = f"{fd.get('patient_city','')}  {fd.get('patient_state','')}  {fd.get('patient_zip','')}"
    _value(c, csz, bx + 2, r4y + 2)

    # ── BOX 7b: Insured address/city/state ────────────────────────────────────
    _draw_box(c, bx + 3.0 * inch, r4y, 3.75 * inch, row_h)
    _label(c, "7. INSURED'S ADDRESS / CITY / STATE / ZIP", bx + 3.0 * inch + 2, r4y + 10, bold=True)
    ins_addr = f"{fd.get('ins_address2','')} {fd.get('ins_city2','')} {fd.get('ins_state2','')} {fd.get('ins_zip2','')}"
    _value(c, ins_addr.strip(), bx + 3.0 * inch + 2, r4y + 2)

    # ── BOX 9-10: Other insured / conditions ──────────────────────────────────
    r5y = r4y - row_h * 3
    _draw_box(c, bx, r5y, 3.0 * inch, row_h)
    _label(c, "9. OTHER INSURED'S NAME", bx + 2, r5y + 10, bold=True)
    _value(c, fd.get("other_ins_name", ""), bx + 2, r5y + 2)

    _draw_box(c, bx + 3.0 * inch, r5y, 3.75 * inch, row_h)
    _label(c, "10. IS PATIENT'S CONDITION RELATED TO:", bx + 3.0 * inch + 2, r5y + 10, bold=True)

    # ── BOX 11: Insured's policy ──────────────────────────────────────────────
    r6y = r5y - row_h
    _draw_box(c, bx, r6y, 3.0 * inch, row_h)
    _label(c, "11. INSURED'S POLICY GROUP OR FECA NUMBER", bx + 2, r6y + 10, bold=True)
    _value(c, fd.get("ins_group", ""), bx + 2, r6y + 2)

    # ── BOX 12/13: Signatures ─────────────────────────────────────────────────
    r7y = r6y - row_h
    _draw_box(c, bx, r7y, 4.0 * inch, row_h)
    _label(c, "12. PATIENT'S OR AUTHORIZED PERSON'S SIGNATURE", bx + 2, r7y + 10, bold=True)
    _value(c, fd.get("patient_sig", "Signature on File"), bx + 2, r7y + 2)

    _draw_box(c, bx + 4.0 * inch, r7y, 2.75 * inch, row_h)
    _label(c, "13. INSURED'S OR AUTHORIZED PERSON'S SIGNATURE", bx + 4.0 * inch + 2, r7y + 10, bold=True)
    _value(c, fd.get("ins_sig", "Signature on File"), bx + 4.0 * inch + 2, r7y + 2)

    # ── BOX 14-16: Illness/injury dates ───────────────────────────────────────
    r8y = r7y - row_h
    _draw_box(c, bx, r8y, 2.0 * inch, row_h)
    _label(c, "14. DATE OF CURRENT ILLNESS/INJURY", bx + 2, r8y + 10, bold=True)
    _value(c, fd.get("illness_date", ""), bx + 2, r8y + 2)

    _draw_box(c, bx + 2.0 * inch, r8y, 2.0 * inch, row_h)
    _label(c, "15. OTHER DATE", bx + 2.0 * inch + 2, r8y + 10, bold=True)

    _draw_box(c, bx + 4.0 * inch, r8y, 2.75 * inch, row_h)
    _label(c, "16. DATES PATIENT UNABLE TO WORK", bx + 4.0 * inch + 2, r8y + 10, bold=True)

    # ── BOX 17: Referring provider ────────────────────────────────────────────
    r9y = r8y - row_h
    _draw_box(c, bx, r9y, 3.5 * inch, row_h)
    _label(c, "17. NAME OF REFERRING PROVIDER", bx + 2, r9y + 10, bold=True)
    _value(c, fd.get("ref_provider", ""), bx + 2, r9y + 2)

    _draw_box(c, bx + 3.5 * inch, r9y, 1.25 * inch, row_h)
    _label(c, "17b. NPI", bx + 3.5 * inch + 2, r9y + 10, bold=True)
    _value(c, fd.get("ref_npi", ""), bx + 3.5 * inch + 2, r9y + 2)

    _draw_box(c, bx + 4.75 * inch, r9y, 2.0 * inch, row_h)
    _label(c, "18. HOSPITALIZATION DATES", bx + 4.75 * inch + 2, r9y + 10, bold=True)

    # ── BOX 19-23: Auth/Codes ─────────────────────────────────────────────────
    r10y = r9y - row_h
    _draw_box(c, bx, r10y, 4.0 * inch, row_h)
    _label(c, "19. ADDITIONAL CLAIM INFORMATION", bx + 2, r10y + 10, bold=True)
    _value(c, fd.get("add_info", ""), bx + 2, r10y + 2)

    _draw_box(c, bx + 4.0 * inch, r10y, 2.75 * inch, row_h)
    _label(c, "23. PRIOR AUTHORIZATION NUMBER", bx + 4.0 * inch + 2, r10y + 10, bold=True)
    _value(c, fd.get("auth_number", ""), bx + 4.0 * inch + 2, r10y + 2)

    # ── BOX 21: Diagnosis codes ───────────────────────────────────────────────
    r11y = r10y - row_h * 1.8
    _draw_box(c, bx, r11y, 6.75 * inch, row_h * 1.8)
    _label(c, "21. DIAGNOSIS OR NATURE OF ILLNESS OR INJURY – ICD-10-CM", bx + 2, r11y + row_h * 1.8 - 8, bold=True)

    dx_codes = [fd.get(f"dx{i}", "") for i in range(1, 13)]
    dx_positions = [
        (bx + 5,        r11y + 14), (bx + 110,      r11y + 14),
        (bx + 210,      r11y + 14), (bx + 310,       r11y + 14),
        (bx + 5,        r11y + 3),  (bx + 110,       r11y + 3),
        (bx + 210,      r11y + 3),  (bx + 310,       r11y + 3),
    ]
    labels_21 = ["A.", "B.", "C.", "D.", "E.", "F.", "G.", "H."]
    for i, ((x, y), lbl) in enumerate(zip(dx_positions, labels_21)):
        _label(c, lbl, x, y, size=7, bold=True)
        _value(c, dx_codes[i] if i < len(dx_codes) else "", x + 10, y, size=FONT_MD)

    # ── BOX 24: Service lines ─────────────────────────────────────────────────
    r12y = r11y - 0.2 * inch
    line_h = 0.28 * inch
    # Header
    _draw_box(c, bx, r12y - 0.18 * inch, 6.75 * inch, 0.18 * inch)
    headers = ["24A. DATE(S) OF SERVICE", "B.POS", "C.EMG", "D.PROCEDURES/SERVICES",
               "E.DX PTR", "F.CHARGES", "G.DAYS", "H.", "I.", "J.RENDERING NPI"]
    hx = [bx + 2, bx + 1.1 * inch, bx + 1.45 * inch, bx + 1.65 * inch,
          bx + 3.3 * inch, bx + 3.7 * inch, bx + 4.6 * inch,
          bx + 4.9 * inch, bx + 5.1 * inch, bx + 5.3 * inch]
    for h_txt, hxx in zip(headers, hx):
        _label(c, h_txt, hxx, r12y - 0.14 * inch, size=5, bold=True)

    service_lines = fd.get("service_lines", [])
    for i in range(6):
        ly = r12y - (i + 1) * line_h - 0.18 * inch
        _draw_box(c, bx, ly, 6.75 * inch, line_h)
        if i < len(service_lines):
            sl = service_lines[i]
            _value(c, sl.get("from_date", ""),   bx + 2,           ly + 10)
            _value(c, sl.get("to_date", ""),     bx + 60,          ly + 10)
            _value(c, sl.get("pos", "11"),       bx + 1.15 * inch, ly + 10)
            _value(c, sl.get("cpt", ""),         bx + 1.65 * inch, ly + 10)
            _value(c, sl.get("modifier", ""),    bx + 2.45 * inch, ly + 10)
            _value(c, sl.get("dx_ptr", ""),      bx + 3.35 * inch, ly + 10)
            chg = sl.get("charge", 0)
            _value(c, f"${float(chg):.2f}" if chg else "",
                   bx + 3.75 * inch, ly + 10)
            _value(c, sl.get("units", "1"),      bx + 4.65 * inch, ly + 10)
            _value(c, sl.get("npi", ""),         bx + 5.35 * inch, ly + 10)

    # ── BOX 25-33: Billing / Provider ─────────────────────────────────────────
    bot_y = r12y - 7 * line_h - 0.18 * inch
    row_bot_h = 0.3 * inch

    _draw_box(c, bx, bot_y - row_bot_h, 1.7 * inch, row_bot_h)
    _label(c, "25. FEDERAL TAX I.D. NUMBER", bx + 2, bot_y - 8, bold=True)
    _value(c, fd.get("tax_id", ""), bx + 2, bot_y - row_bot_h + 4)

    _draw_box(c, bx + 1.7 * inch, bot_y - row_bot_h, 1.0 * inch, row_bot_h)
    _label(c, "26. PATIENT ACCT. #", bx + 1.7 * inch + 2, bot_y - 8, bold=True)
    _value(c, fd.get("patient_acct", ""), bx + 1.7 * inch + 2, bot_y - row_bot_h + 4)

    _draw_box(c, bx + 2.7 * inch, bot_y - row_bot_h, 0.7 * inch, row_bot_h)
    _label(c, "27. ACCEPT\nASSIGN?", bx + 2.7 * inch + 2, bot_y - 8, bold=True)
    _value(c, "YES" if fd.get("accept_assign") else "NO",
           bx + 2.7 * inch + 2, bot_y - row_bot_h + 4)

    _draw_box(c, bx + 3.4 * inch, bot_y - row_bot_h, 1.0 * inch, row_bot_h)
    _label(c, "28. TOTAL CHARGE", bx + 3.4 * inch + 2, bot_y - 8, bold=True)
    tc = fd.get("total_charge", 0)
    _value(c, f"${float(tc):.2f}" if tc else "", bx + 3.4 * inch + 2, bot_y - row_bot_h + 4)

    _draw_box(c, bx + 4.4 * inch, bot_y - row_bot_h, 1.0 * inch, row_bot_h)
    _label(c, "29. AMOUNT PAID", bx + 4.4 * inch + 2, bot_y - 8, bold=True)
    paid = fd.get("amount_paid", 0)
    _value(c, f"${float(paid):.2f}" if paid else "", bx + 4.4 * inch + 2, bot_y - row_bot_h + 4)

    _draw_box(c, bx + 5.4 * inch, bot_y - row_bot_h, 1.35 * inch, row_bot_h)
    _label(c, "30. RESERVED FOR NUCC", bx + 5.4 * inch + 2, bot_y - 8, bold=True)

    # BOX 31: Signature
    bot2_y = bot_y - row_bot_h
    _draw_box(c, bx, bot2_y - row_bot_h, 2.7 * inch, row_bot_h)
    _label(c, "31. SIGNATURE OF PHYSICIAN OR SUPPLIER", bx + 2, bot2_y - 8, bold=True)
    _value(c, fd.get("provider_sig", "Signature on File"), bx + 2, bot2_y - row_bot_h + 4)
    _value(c, f"DATE: {fd.get('billing_date', date.today().strftime('%m/%d/%Y'))}",
           bx + 2, bot2_y - row_bot_h + 4 - 10)

    # BOX 32: Service facility
    _draw_box(c, bx + 2.7 * inch, bot2_y - row_bot_h, 2.0 * inch, row_bot_h)
    _label(c, "32. SERVICE FACILITY LOCATION", bx + 2.7 * inch + 2, bot2_y - 8, bold=True)
    _value(c, fd.get("facility_name", ""), bx + 2.7 * inch + 2, bot2_y - row_bot_h + 14)
    fac_addr = f"{fd.get('facility_address','')}, {fd.get('facility_city','')} {fd.get('facility_state','')} {fd.get('facility_zip','')}"
    _value(c, fac_addr.strip(", "), bx + 2.7 * inch + 2, bot2_y - row_bot_h + 4)

    # BOX 33: Billing provider
    _draw_box(c, bx + 4.7 * inch, bot2_y - row_bot_h, 2.05 * inch, row_bot_h)
    _label(c, "33. BILLING PROVIDER INFO & PH #", bx + 4.7 * inch + 2, bot2_y - 8, bold=True)
    _value(c, fd.get("billing_name", ""), bx + 4.7 * inch + 2, bot2_y - row_bot_h + 20)
    _value(c, fd.get("billing_address", ""), bx + 4.7 * inch + 2, bot2_y - row_bot_h + 11)
    _value(c, f"NPI: {fd.get('billing_npi','')}", bx + 4.7 * inch + 2, bot2_y - row_bot_h + 4)


# ─── Convenience wrapper ───────────────────────────────────────────────────────

def cms_form_data_from_patient(patient, sessions, provider):
    """
    Build a form_data dict from patient row, list of sessions, and provider dict.
    patient, provider  = sqlite3.Row / dict
    sessions           = list of sqlite3.Row / dict
    """
    def g(row, key, default=""):
        try:
            return row[key] or default
        except (KeyError, IndexError, TypeError):
            return default

    service_lines = []
    total_charge = 0.0
    for s in sessions[:6]:
        fee = float(g(s, "fee", 0) or 0)
        total_charge += fee
        service_lines.append({
            "from_date": g(s, "session_date"),
            "to_date":   g(s, "session_date"),
            "pos":       g(s, "place_of_service", "11"),
            "cpt":       g(s, "cpt_code", "90834"),
            "modifier":  g(s, "cpt_modifier"),
            "dx_ptr":    "A",
            "charge":    fee,
            "units":     "1",
            "npi":       g(provider, "npi"),
        })

    pt_name = f"{g(patient,'last_name')}, {g(patient,'first_name')}"
    ins_holder = g(patient, "ins_holder") or pt_name
    patient_phone = g(patient, "phone_home") or g(patient, "phone_cell") or g(patient, "phone_work")
    facility_city_state_zip = f"{g(provider,'city')} {g(provider,'state')} {g(provider,'zip')}".strip()
    billing_city_state_zip = facility_city_state_zip
    provider_id_qualifier = g(provider, "id_qualifier", "ZZ")

    fd = {
        "ins_type":       "",
        "ins_id":         g(patient, "ins_id"),
        "patient_name":   pt_name,
        "patient_dob":    g(patient, "dob"),
        "patient_sex":    g(patient, "sex"),
        "ins_name":       ins_holder,
        "patient_address":g(patient, "address"),
        "patient_city":   g(patient, "city"),
        "patient_state":  g(patient, "state"),
        "patient_zip":    g(patient, "zip"),
        "patient_phone":  patient_phone,
        "ins_relation":   g(patient, "ins_relation", "Self"),
        "ins_relation_self": "",
        "ins_relation_spouse": "",
        "ins_relation_child": "",
        "ins_relation_other": "",
        "ins_address2":   g(patient, "ins_address"),
        "ins_city2":      g(patient, "ins_city"),
        "ins_state2":     g(patient, "ins_state"),
        "ins_zip2":       g(patient, "ins_zip"),
        "ins_phone":      g(patient, "ins_phone"),
        "ins_group":      g(patient, "ins_group"),
        "other_ins_name": g(patient, "other_ins_name"),
        "other_ins_policy": g(patient, "other_ins_policy"),
        "ins_dob":        g(patient, "ins_dob"),
        "ins_sex":        g(patient, "ins_sex"),
        "other_claim_id": g(patient, "other_claim_id"),
        "other_plan":     g(patient, "other_plan"),
        "patient_sig":    "Signature on File",
        "patient_sig_date": date.today().strftime("%m %d %y"),
        "ins_sig":        "Signature on File",
        "ref_provider":   g(patient, "referring_name"),
        "ref_qual":       "",
        "ref_npi":        g(patient, "referring_npi"),
        "dx1":            g(patient, "dx1"),
        "dx2":            g(patient, "dx2"),
        "dx3":            g(patient, "dx3"),
        "dx4":            g(patient, "dx4"),
        "service_lines":  service_lines,
        "tax_id":         g(provider, "tax_id"),
        "tax_id_ein":     "X" if g(provider, "tax_id_type", "EIN") == "EIN" else "",
        "tax_id_ssn":     "X" if g(provider, "tax_id_type", "EIN") == "SSN" else "",
        "patient_acct":   str(g(patient, "id")),
        "accept_assign":  g(provider, "accept_assign", 1),
        "total_charge":   total_charge,
        "amount_paid":    0.0,
        "provider_sig":   "Signature on File",
        "billing_date":   date.today().strftime("%m/%d/%Y"),
        "facility_name":  g(provider, "practice_name") or f"{g(provider,'provider_first')} {g(provider,'provider_last')}".strip(),
        "facility_address": g(provider, "address"),
        "facility_city_state_zip": facility_city_state_zip,
        "facility_qualifier": provider_id_qualifier,
        "facility_npi":   g(provider, "npi"),
        "facility_other_id": g(provider, "license_num"),
        "billing_name":   f"{g(provider,'practice_name') or g(provider,'provider_last')+', '+g(provider,'provider_first')}",
        "billing_address":g(provider, "address"),
        "billing_city_state_zip": billing_city_state_zip,
        "billing_phone":  g(provider, "phone"),
        "billing_qualifier": provider_id_qualifier,
        "billing_npi":    g(provider, "npi"),
        "billing_other_id": g(provider, "license_num"),
    }

    relation = str(fd.get("ins_relation", "") or "").strip().lower()
    if relation == "self":
        fd["ins_relation_self"] = "X"
    elif relation == "spouse":
        fd["ins_relation_spouse"] = "X"
    elif relation == "child":
        fd["ins_relation_child"] = "X"
    elif relation == "other":
        fd["ins_relation_other"] = "X"

    return fd
