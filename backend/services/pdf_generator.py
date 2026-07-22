"""MedoraAI professional clinical PDF generation."""

import io
import logging
import os
from typing import Optional
from xml.sax.saxutils import escape

from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)


class PDFGenerator:
    """
    Generates formatted PDF clinical reports.
    
    Generates a native, multi-page ReportLab document on every supported OS.
    The HTML renderer is retained only for preview/testing compatibility.
    """

    def __init__(self, template_dir: Optional[str] = None):
        """
        Initialize with the report template directory.
        
        Args:
            template_dir: Path to templates directory. Defaults to backend/templates/
        """
        if template_dir is None:
            template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")

        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=True,
        )
        self.report_template = self.env.get_template("report.html")
        logger.info(f"PDFGenerator initialized with template dir: {template_dir}")

    def render_html(self, report_data: dict, scan_id: str, heatmap_path: str = "") -> str:
        """
        Render report data into an HTML string.
        
        Args:
            report_data: Full report dictionary from LLMReportEngine
            scan_id: Scan UUID for the report header
            heatmap_path: Absolute path to heatmap image for base64 embedding
            
        Returns:
            Rendered HTML string
        """
        # Base64-encode the heatmap for embedding in HTML/PDF
        heatmap_b64 = ""
        if heatmap_path and os.path.exists(heatmap_path):
            try:
                import base64
                with open(heatmap_path, "rb") as f:
                    heatmap_b64 = base64.b64encode(f.read()).decode("utf-8")
            except Exception as e:
                logger.warning(f"Could not encode heatmap for PDF: {e}")

        # Build secondary findings list for template
        secondary_findings = report_data.get("secondary_findings", [])

        return self.report_template.render(
            report_id=scan_id[:8].upper(),
            scan_id=scan_id,
            generated_at=report_data.get("generated_at", ""),
            patient_id=report_data.get("patient_id", "DEMO-001"),
            scan_date=report_data.get("scan_date", ""),
            scan_type=report_data.get("scan_type", ""),
            modality=report_data.get("modality", ""),
            top_label=report_data.get("top_label", ""),
            confidence=report_data.get("confidence", 0),
            severity=report_data.get("severity", ""),
            clinical_history=report_data.get("clinical_history", "Not provided."),
            technique=report_data.get("technique", ""),
            comparison=report_data.get("comparison", ""),
            image_quality=report_data.get("image_quality", ""),
            findings=report_data.get("findings", ""),
            impression=report_data.get("impression", ""),
            differential_diagnosis=report_data.get("differential_diagnosis", ""),
            recommendations=report_data.get("recommendations", ""),
            critical_communication=report_data.get("critical_communication", ""),
            all_scores=report_data.get("all_scores", {}),
            disclaimer=report_data.get("disclaimer", ""),
            # New fields
            heatmap_b64=heatmap_b64,
            heatmap_target_label=report_data.get("heatmap_target_label", ""),
            is_low_confidence=report_data.get("is_low_confidence", False),
            secondary_findings=secondary_findings,
            methodology=report_data.get("methodology", ""),
            limitations=report_data.get("limitations", ""),
        )

    def generate_pdf(self, report_data: dict, scan_id: str, heatmap_path: str = "") -> bytes:
        """Generate the professional PDF without native GTK/Pango dependencies."""
        try:
            pdf_bytes = self._generate_professional_pdf(report_data, scan_id, heatmap_path)
            logger.info("Professional PDF generated for scan %s (%s bytes)", scan_id[:8], len(pdf_bytes))
            return pdf_bytes
        except Exception as exc:
            logger.error("Professional PDF generation failed: %s", exc, exc_info=True)
            return self._generate_simple_pdf(report_data, scan_id)

    def _generate_professional_pdf(
        self, report_data: dict, scan_id: str, heatmap_path: str = "",
    ) -> bytes:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            HRFlowable,
            Image as ReportImage,
            KeepTogether,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )

        buffer = io.BytesIO()
        report_id = scan_id[:8].upper()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=17 * mm,
            leftMargin=17 * mm,
            topMargin=25 * mm,
            bottomMargin=19 * mm,
            title=f"MedoraAI Clinical Imaging Report {report_id}",
            author="MedoraAI",
            subject="Preliminary clinical imaging report",
        )

        ink = colors.HexColor("#172126")
        muted = colors.HexColor("#667177")
        teal = colors.HexColor("#17676E")
        teal_soft = colors.HexColor("#EAF4F3")
        line = colors.HexColor("#D9DFDF")
        paper = colors.HexColor("#F7F7F4")
        warning = colors.HexColor("#FFF4D8")

        base = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "ReportTitle", parent=base["Title"], fontName="Helvetica-Bold",
            fontSize=20, leading=23, textColor=ink, alignment=TA_LEFT, spaceAfter=3,
        )
        subtitle_style = ParagraphStyle(
            "ReportSubtitle", parent=base["Normal"], fontName="Helvetica",
            fontSize=8, leading=11, textColor=teal, spaceAfter=12,
        )
        section_style = ParagraphStyle(
            "SectionTitle", parent=base["Heading2"], fontName="Helvetica-Bold",
            fontSize=8.5, leading=11, textColor=teal, spaceBefore=8, spaceAfter=5,
            uppercase=True,
        )
        body_style = ParagraphStyle(
            "ClinicalBody", parent=base["BodyText"], fontName="Helvetica",
            fontSize=9.2, leading=13.4, textColor=ink, spaceAfter=5,
        )
        impression_style = ParagraphStyle(
            "ImpressionBody", parent=body_style, fontName="Helvetica-Bold",
            fontSize=9.5, leading=14, textColor=ink,
        )
        small_style = ParagraphStyle(
            "Small", parent=body_style, fontSize=7.5, leading=10.5, textColor=muted,
        )
        meta_label = ParagraphStyle(
            "MetaLabel", parent=small_style, fontName="Helvetica-Bold",
            fontSize=6.6, leading=8, textColor=muted,
        )
        meta_value = ParagraphStyle(
            "MetaValue", parent=body_style, fontName="Helvetica-Bold",
            fontSize=8.5, leading=10.5, textColor=ink,
        )

        def markup(value) -> str:
            return escape(str(value or "Not provided.")).replace("\n", "<br/>")

        def meta_cell(label: str, value) -> list:
            return [
                Paragraph(label.upper(), meta_label),
                Paragraph(markup(value), meta_value),
            ]

        def draw_page(canvas, document):
            canvas.saveState()
            canvas.setStrokeColor(line)
            canvas.setLineWidth(0.5)
            canvas.line(17 * mm, A4[1] - 16 * mm, A4[0] - 17 * mm, A4[1] - 16 * mm)
            canvas.setFont("Helvetica-Bold", 7.5)
            canvas.setFillColor(teal)
            canvas.drawString(17 * mm, A4[1] - 12 * mm, "MEDORAAI  /  CLINICAL IMAGING")
            canvas.setFont("Helvetica", 7)
            canvas.setFillColor(muted)
            canvas.drawRightString(A4[0] - 17 * mm, A4[1] - 12 * mm, f"REPORT {report_id}")
            canvas.line(17 * mm, 13 * mm, A4[0] - 17 * mm, 13 * mm)
            canvas.drawString(17 * mm, 8.5 * mm, "Preliminary report — clinician verification required")
            canvas.drawRightString(A4[0] - 17 * mm, 8.5 * mm, f"Page {document.page}")
            canvas.restoreState()

        story = [
            Paragraph("Clinical Imaging Report", title_style),
            Paragraph("STRUCTURED PRELIMINARY INTERPRETATION FOR CLINICIAN REVIEW", subtitle_style),
        ]

        scan_label = "Brain MRI" if report_data.get("scan_type") == "brain_mri" else "Chest radiograph"
        metadata = Table(
            [[
                meta_cell("Patient ID", report_data.get("patient_id", "DEMO-001")),
                meta_cell("Study date", report_data.get("scan_date", "")),
                meta_cell("Examination", scan_label),
                meta_cell("Modality", report_data.get("modality", "")),
            ]],
            colWidths=[doc.width / 4] * 4,
            hAlign="LEFT",
        )
        metadata.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), paper),
            ("BOX", (0, 0), (-1, -1), 0.6, line),
            ("INNERGRID", (0, 0), (-1, -1), 0.4, line),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        story.extend([metadata, Spacer(1, 8)])

        confidence = float(report_data.get("confidence", 0) or 0)
        summary = Table(
            [[
                Paragraph("PRIMARY MODEL SIGNAL", meta_label),
                Paragraph("CONFIDENCE", meta_label),
                Paragraph("MODEL PRIORITY", meta_label),
            ], [
                Paragraph(markup(report_data.get("top_label", "Not available")), meta_value),
                Paragraph(f"{confidence * 100:.1f}%", meta_value),
                Paragraph(markup(report_data.get("severity", "Not available")), meta_value),
            ]],
            colWidths=[doc.width * 0.5, doc.width * 0.22, doc.width * 0.28],
        )
        summary.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), teal),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("BACKGROUND", (0, 1), (-1, 1), teal_soft),
            ("BOX", (0, 0), (-1, -1), 0.6, teal),
            ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B7D2D1")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.extend([summary, Spacer(1, 6)])

        def add_section(title: str, value, emphasized: bool = False):
            paragraph_style = impression_style if emphasized else body_style
            block = [
                Paragraph(title.upper(), section_style),
                HRFlowable(width="100%", thickness=0.5, color=line, spaceAfter=5),
                Paragraph(markup(value), paragraph_style),
            ]
            story.append(KeepTogether(block))

        add_section("Clinical history", report_data.get("clinical_history", "Not provided."))
        add_section("Technique", report_data.get("technique", "Not provided."))
        add_section("Comparison", report_data.get("comparison", "No prior imaging supplied."))
        add_section("Image quality / study limitations", report_data.get("image_quality", "Not provided."))
        add_section("Findings", report_data.get("findings", "Not available."))
        add_section("Impression", report_data.get("impression", "Not available."), emphasized=True)
        add_section("Differential diagnosis", report_data.get("differential_diagnosis", "None stated."))
        add_section("Recommendations", report_data.get("recommendations", "Clinical correlation recommended."))
        add_section("Critical communication", report_data.get("critical_communication", "No critical communication generated."))

        if heatmap_path and os.path.exists(heatmap_path):
            from PIL import Image as PILImage

            with PILImage.open(heatmap_path) as heatmap:
                width, height = heatmap.size
            image_width = min(doc.width, 132 * mm)
            image_height = image_width * height / max(width, 1)
            image_height = min(image_height, 92 * mm)
            story.extend([
                Paragraph("GRAD-CAM HEATMAP", section_style),
                HRFlowable(width="100%", thickness=0.5, color=line, spaceAfter=7),
                ReportImage(heatmap_path, width=image_width, height=image_height, hAlign="CENTER"),
                Spacer(1, 4),
                Paragraph(
                    "Gradient-weighted class activation map for target: "
                    f"<b>{markup(report_data.get('heatmap_target_label', 'primary model signal'))}</b>. "
                    "Warmer regions indicate greater influence on the model output; this is not lesion segmentation.",
                    small_style,
                ),
            ])

        scores = report_data.get("all_scores") or {}
        if scores:
            score_rows = [[
                Paragraph("CLASSIFICATION LABEL", meta_label),
                Paragraph("SCORE", meta_label),
            ]]
            for label, score in sorted(scores.items(), key=lambda item: -float(item[1])):
                score_rows.append([
                    Paragraph(markup(label), body_style),
                    Paragraph(f"{float(score) * 100:.1f}%", body_style),
                ])
            score_table = Table(score_rows, colWidths=[doc.width * 0.78, doc.width * 0.22], repeatRows=1)
            score_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), teal),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, paper]),
                ("BOX", (0, 0), (-1, -1), 0.5, line),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, line),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.extend([
                Paragraph("DETAILED CLASSIFICATION SCORES", section_style),
                HRFlowable(width="100%", thickness=0.5, color=line, spaceAfter=6),
                score_table,
            ])

        add_section("Method", report_data.get("methodology", "Automated image classification with Grad-CAM explainability."))
        add_section("Known limitations", report_data.get("limitations", "Performance depends on image quality and trained categories."))

        disclaimer_table = Table(
            [[Paragraph(
                f"<b>CLINICAL VERIFICATION NOTICE</b><br/>{markup(report_data.get('disclaimer', 'Clinician verification is required.'))}",
                small_style,
            )]],
            colWidths=[doc.width],
        )
        disclaimer_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), warning),
            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#D8B85E")),
            ("LEFTPADDING", (0, 0), (-1, -1), 9),
            ("RIGHTPADDING", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.extend([Spacer(1, 10), disclaimer_table])

        doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
        return buffer.getvalue()

    def generate_pdf_with_edits(
        self,
        report_data: dict,
        scan_id: str,
        edited_clinical_history: Optional[str] = None,
        edited_technique: Optional[str] = None,
        edited_comparison: Optional[str] = None,
        edited_image_quality: Optional[str] = None,
        edited_findings: Optional[str] = None,
        edited_impression: Optional[str] = None,
        edited_differential_diagnosis: Optional[str] = None,
        edited_recommendations: Optional[str] = None,
        edited_critical_communication: Optional[str] = None,
        heatmap_path: str = "",
    ) -> bytes:
        """
        Generate PDF with optional clinician edits applied.
        Edits override the original LLM-generated text.
        """
        # Apply edits
        data = report_data.copy()
        if edited_clinical_history:
            data["clinical_history"] = edited_clinical_history
        if edited_technique:
            data["technique"] = edited_technique
        if edited_comparison:
            data["comparison"] = edited_comparison
        if edited_image_quality:
            data["image_quality"] = edited_image_quality
        if edited_findings:
            data["findings"] = edited_findings
        if edited_impression:
            data["impression"] = edited_impression
        if edited_differential_diagnosis:
            data["differential_diagnosis"] = edited_differential_diagnosis
        if edited_recommendations:
            data["recommendations"] = edited_recommendations
        if edited_critical_communication:
            data["critical_communication"] = edited_critical_communication

        return self.generate_pdf(data, scan_id, heatmap_path=heatmap_path)

    def _generate_simple_pdf(self, report_data: dict, scan_id: str) -> bytes:
        """
        Generate a minimal text-only PDF without native rendering dependencies.
        This keeps local Windows demos working when WeasyPrint/Pango is unavailable.
        """
        lines = [
            "MedoraAI Clinical Decision-Support Report",
            f"Report ID: {scan_id[:8].upper()}",
            f"Patient ID: {report_data.get('patient_id', 'DEMO-001')}",
            f"Scan Date: {report_data.get('scan_date', '')}",
            f"Scan Type: {report_data.get('scan_type', '')}",
            f"Modality: {report_data.get('modality', '')}",
            f"Primary Finding: {report_data.get('top_label', '')}",
            f"Confidence: {float(report_data.get('confidence', 0)) * 100:.1f}%",
            f"Severity: {report_data.get('severity', '')}",
            "",
            "Clinical History",
            report_data.get("clinical_history", "Not provided."),
            "",
            "Technique",
            report_data.get("technique", ""),
            "",
            "Comparison",
            report_data.get("comparison", ""),
            "",
            "Image Quality",
            report_data.get("image_quality", ""),
            "",
            "Findings",
            report_data.get("findings", ""),
            "",
            "Impression",
            report_data.get("impression", ""),
            "",
            "Differential Diagnosis",
            report_data.get("differential_diagnosis", ""),
            "",
            "Recommendations",
            report_data.get("recommendations", ""),
            "",
            "Critical Communication",
            report_data.get("critical_communication", ""),
            "",
            "Disclaimer",
            report_data.get("disclaimer", ""),
        ]
        return _build_text_pdf(lines)


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _wrap_pdf_line(text: str, max_chars: int = 88) -> list[str]:
    words = str(text).replace("\r", "").split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        if len(current) + 1 + len(word) > max_chars:
            lines.append(current)
            current = word
        else:
            current += " " + word
    lines.append(current)
    return lines


def _build_text_pdf(lines: list[str]) -> bytes:
    content_lines = ["BT", "/F1 11 Tf", "50 780 Td", "14 TL"]
    first = True
    for raw_line in lines:
        wrapped = _wrap_pdf_line(raw_line)
        for line in wrapped:
            if not first:
                content_lines.append("T*")
            content_lines.append(f"({_pdf_escape(line)}) Tj")
            first = False
        if raw_line == "":
            content_lines.append("T*")
    content_lines.append("ET")
    stream = "\n".join(content_lines).encode("latin-1", errors="replace")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for idx, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{idx} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")

    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(pdf)
