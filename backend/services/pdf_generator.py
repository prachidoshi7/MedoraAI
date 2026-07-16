"""
MedoraAI — PDF Report Generator
Renders HTML report template via Jinja2 and converts to PDF with WeasyPrint.
"""

import logging
import os
from typing import Optional

from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)


class PDFGenerator:
    """
    Generates formatted PDF clinical reports.
    
    Flow: Report data dict → Jinja2 HTML template → WeasyPrint → PDF bytes
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
            findings=report_data.get("findings", ""),
            impression=report_data.get("impression", ""),
            recommendations=report_data.get("recommendations", ""),
            all_scores=report_data.get("all_scores", {}),
            llm_provider=report_data.get("llm_provider", "template"),
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
        """
        Generate a formatted PDF from report data.
        
        Args:
            report_data: Full report dictionary
            scan_id: Scan UUID
            heatmap_path: Path to heatmap image for embedding
            
        Returns:
            PDF file as bytes
        """
        try:
            from weasyprint import HTML

            html_content = self.render_html(report_data, scan_id, heatmap_path=heatmap_path)
            pdf_bytes = HTML(string=html_content).write_pdf()
            logger.info(f"PDF generated for scan {scan_id[:8]} ({len(pdf_bytes)} bytes)")
            return pdf_bytes

        except ImportError:
            logger.warning("WeasyPrint not installed. Using simple PDF fallback.")
            return self._generate_simple_pdf(report_data, scan_id)
        except Exception as e:
            logger.warning(f"WeasyPrint PDF generation failed: {e}. Using simple PDF fallback.")
            return self._generate_simple_pdf(report_data, scan_id)

    def generate_pdf_with_edits(
        self,
        report_data: dict,
        scan_id: str,
        edited_findings: Optional[str] = None,
        edited_impression: Optional[str] = None,
        edited_recommendations: Optional[str] = None,
        heatmap_path: str = "",
    ) -> bytes:
        """
        Generate PDF with optional clinician edits applied.
        Edits override the original LLM-generated text.
        """
        # Apply edits
        data = report_data.copy()
        if edited_findings:
            data["findings"] = edited_findings
        if edited_impression:
            data["impression"] = edited_impression
        if edited_recommendations:
            data["recommendations"] = edited_recommendations

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
            f"Report Source: {report_data.get('llm_provider', 'template')}",
            "",
            "Findings",
            report_data.get("findings", ""),
            "",
            "Impression",
            report_data.get("impression", ""),
            "",
            "Recommendations",
            report_data.get("recommendations", ""),
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
