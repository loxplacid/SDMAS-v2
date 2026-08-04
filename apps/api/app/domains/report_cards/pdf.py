"""PDF rendering for report cards and class marksheets.

The class marksheet reuses ``report_builder.exporters.export_pdf`` (the
same reportlab pipeline used by the custom report builder). The single
student report card builds a dedicated A4 layout on top of the same
reportlab primitives so it stays consistent with the existing export
style (blue header, zebra rows, currency/percentage formatting).
"""

from __future__ import annotations

import datetime
import io
from typing import Optional
from xml.sax.saxutils import escape as _xml_escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.domains.report_builder.base import ReportColumn
from app.domains.report_builder.exporters import export_pdf
from app.domains.report_cards.schemas import (
    ClassMarksheet,
    StudentReportCard,
)

HEADER_BLUE = colors.HexColor("#2563EB")
ZEBRA = colors.HexColor("#F3F4F6")

_MONTHS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


def _esc(value: str) -> str:
    """Escape XML-significant characters for reportlab ``Paragraph``.

    ``Paragraph`` parses mini-XML, so raw ``&``/``<``/``>`` in real-world
    data (e.g. subject names like "Math & Science") would otherwise raise
    at ``doc.build`` time.
    """
    return _xml_escape(value)


def _fmt_pct(value: Optional[float]) -> str:
    return f"{value:.1f}%" if value is not None else "—"


def _fmt_num(value: Optional[float]) -> str:
    return f"{value:.2f}" if value is not None else "—"


def _fmt_date(iso: Optional[str]) -> str:
    if not iso:
        return "—"
    try:
        year, month, day = iso.split("-")[:3]
        return f"{int(day)} {_MONTHS[int(month) - 1]} {year}"
    except Exception:
        return iso


# ---------------------------------------------------------------------------
# Student report card (A4 portrait, dedicated layout)
# ---------------------------------------------------------------------------


def build_report_card_pdf(card: StudentReportCard) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=18 * mm,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"Report Card — {card.student_name}",
        author="SDMAS",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CardTitle", parent=styles["Title"], fontSize=20, textColor=HEADER_BLUE,
    )
    sub_style = ParagraphStyle(
        "CardSub", parent=styles["Normal"], fontSize=10, textColor=colors.grey,
        alignment=1,
    )
    h2_style = ParagraphStyle(
        "CardH2", parent=styles["Heading2"], fontSize=12, textColor=HEADER_BLUE,
        spaceBefore=10, spaceAfter=4,
    )
    cell_style = ParagraphStyle("Cell", parent=styles["Normal"], fontSize=8)
    small_style = ParagraphStyle(
        "Small", parent=styles["Normal"], fontSize=8, textColor=colors.grey,
    )

    elements: list = []

    # ── Header ─────────────────────────────────────────────────────
    elements.append(Paragraph("REPORT CARD", title_style))
    elements.append(Paragraph("SDMAS School Management System", sub_style))
    elements.append(Paragraph(_esc(card.academic_year_name), sub_style))
    elements.append(Spacer(1, 8 * mm))

    # ── Student identity ───────────────────────────────────────────
    identity_rows = [
        ["Student", card.student_name, "Roll No.", card.student_number],
        ["Class", card.class_name or "—", "Section", card.section_name or "—"],
        ["Academic Year", card.academic_year_name, "Term",
         card.term_filter or "All Terms"],
    ]
    identity = Table(identity_rows, colWidths=[28 * mm, 62 * mm, 28 * mm, 42 * mm])
    identity.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.grey),
                ("TEXTCOLOR", (2, 0), (2, -1), colors.grey),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F9FAFB")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    elements.append(identity)
    elements.append(Spacer(1, 6 * mm))

    # ── Terms / subjects ───────────────────────────────────────────
    for term in card.terms:
        elements.append(Paragraph(f"Term: {_esc(term.term_name)}", h2_style))
        header = ["Subject", "Marks", "Max", "Grade", "Grade Pt.", "Remarks"]
        body = [
            [
                Paragraph(_esc(s.subject_name), cell_style),
                _fmt_num(s.marks_obtained),
                str(s.max_marks),
                s.grade or "—",
                _fmt_num(s.grade_point),
                Paragraph(_esc(s.remarks or "—"), cell_style),
            ]
            for s in term.subjects
        ]
        if not body:
            body = [["—", "—", "—", "—", "—", "No grades recorded"]]
        body.append(
            [
                Paragraph("Total", cell_style),
                _fmt_num(term.total_marks),
                str(term.total_max_marks),
                "",
                "",
                Paragraph(
                    f"Percentage: {_fmt_pct(term.percentage)} · "
                    f"GPA: {_fmt_num(term.grade_point_average)}",
                    cell_style,
                ),
            ]
        )
        # Sum of column widths must stay <= usable width (178mm on A4 with
        # 16mm side margins) or reportlab raises LayoutError.
        tbl = Table([header] + body, colWidths=[50 * mm, 18 * mm, 14 * mm, 16 * mm, 16 * mm, 56 * mm])
        tbl.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), HEADER_BLUE),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E5E7EB")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, ZEBRA]),
                    ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F0F4FF")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        elements.append(tbl)
        elements.append(Spacer(1, 4 * mm))

    # ── Overall summary + attendance ───────────────────────────────
    summary_rows = [
        ["Overall Percentage", _fmt_pct(card.overall_percentage)],
        ["Overall GPA", _fmt_num(card.overall_grade_point_average)],
        ["Attendance", f"{card.attendance.present}/{card.attendance.total} "
                       f"({_fmt_pct(card.attendance.percentage)})"],
    ]
    summary = Table(summary_rows, colWidths=[55 * mm, 105 * mm])
    summary.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F9FAFB")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    elements.append(summary)

    # ── Teacher remarks ────────────────────────────────────────────
    if card.teacher_remarks:
        elements.append(Paragraph("Teacher Remarks", h2_style))
        for remark in card.teacher_remarks:
            elements.append(Paragraph(f"• {_esc(remark)}", small_style))
        elements.append(Spacer(1, 3 * mm))

    # ── Signatures ─────────────────────────────────────────────────
    elements.append(Spacer(1, 14 * mm))
    sig_rows = [
        ["Class Teacher", "Principal", "Parent / Guardian"],
        ["____________________", "____________________", "____________________"],
    ]
    sig = Table(sig_rows, colWidths=[58 * mm, 58 * mm, 58 * mm])
    sig.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.grey),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ]
        )
    )
    elements.append(sig)
    elements.append(Spacer(1, 6 * mm))
    elements.append(
        Paragraph(
            f"Generated by SDMAS on {_fmt_date(datetime.datetime.now().date().isoformat())}",
            small_style,
        )
    )

    doc.build(elements)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Class marksheet — reuses report_builder.exporters.export_pdf
# ---------------------------------------------------------------------------


def build_class_marksheet_pdf(marksheet: ClassMarksheet) -> bytes:
    """Render a class marksheet as a landscape PDF via ``export_pdf``.

    Columns are derived from the marksheet subject set so the PDF always
    matches the JSON payload: one (marks / grade) pair per subject plus
    totals, percentage, GPA and attendance columns.
    """
    columns: list[ReportColumn] = [
        ReportColumn(key="student_number", header="Roll No."),
        ReportColumn(key="student_name", header="Student"),
    ]
    for subj in marksheet.subjects:
        short = _esc(subj.code or subj.name or str(subj.id))
        columns.append(ReportColumn(key=f"m_{subj.id}", header=f"{short} Marks", type="number", format="0.00"))
        columns.append(ReportColumn(key=f"g_{subj.id}", header=f"{short} Grade"))

    columns += [
        ReportColumn(key="total_marks", header="Total", type="number", format="0.00"),
        ReportColumn(key="max_marks", header="Max"),
        ReportColumn(key="percentage", header="%", type="percentage"),
        ReportColumn(key="gpa", header="GPA", type="number", format="0.00"),
        ReportColumn(key="attendance", header="Att. %", type="percentage"),
    ]

    rows: list[dict] = []
    for row in marksheet.rows:
        item: dict = {
            "student_number": row.student_number,
            "student_name": row.student_name,
        }
        for cell in row.subjects:
            item[f"m_{cell.subject_id}"] = cell.marks_obtained
            item[f"g_{cell.subject_id}"] = cell.grade or ""
        item["total_marks"] = row.total_marks
        item["max_marks"] = row.max_marks
        item["percentage"] = row.percentage
        item["gpa"] = row.grade_point_average
        item["attendance"] = row.attendance_percentage
        rows.append(item)

    title = f"{_esc(marksheet.class_name)} — Marksheet ({_esc(marksheet.academic_year_name)})"
    if marksheet.term_filter:
        title += f" — {_esc(marksheet.term_filter)}"

    # Reuse the report-builder PDF pipeline (landscape when > 6 columns).
    return export_pdf(columns, rows, title=title)
