"""Professional PDF report generator using WeasyPrint"""

import os
from datetime import datetime
from typing import Optional
from weasyprint import HTML, CSS
from markdown import markdown

from app.core.logging import get_logger

logger = get_logger(__name__)


class PDFGenerator:
    """Generate professional PDF reports from markdown content"""

    def __init__(self):
        self.css_template = """
        @page {
            size: A4;
            margin: 2cm;
            @top-right {
                content: "Helios Observability Platform";
                font-size: 9pt;
                color: #666;
            }
            @bottom-left {
                content: "Helios Incident Report";
                font-size: 8pt;
                color: #999;
            }
            @bottom-right {
                content: "Page " counter(page) " of " counter(pages);
                font-size: 8pt;
                color: #999;
            }
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            font-size: 11pt;
            line-height: 1.6;
            color: #333;
        }

        h1 {
            color: #1a1a1a;
            font-size: 24pt;
            font-weight: 600;
            margin-top: 0;
            margin-bottom: 20pt;
            padding-bottom: 10pt;
            border-bottom: 3px solid #e74c3c;
        }

        h2 {
            color: #2c3e50;
            font-size: 18pt;
            font-weight: 600;
            margin-top: 24pt;
            margin-bottom: 12pt;
            page-break-after: avoid;
        }

        h3 {
            color: #34495e;
            font-size: 14pt;
            font-weight: 600;
            margin-top: 16pt;
            margin-bottom: 8pt;
        }

        p {
            margin-bottom: 10pt;
            text-align: justify;
        }

        strong {
            color: #2c3e50;
            font-weight: 600;
        }

        code {
            background-color: #f4f4f4;
            padding: 2pt 6pt;
            border-radius: 3pt;
            font-family: "Courier New", monospace;
            font-size: 10pt;
            color: #e74c3c;
        }

        pre {
            background-color: #f8f8f8;
            padding: 12pt;
            border-left: 4pt solid #3498db;
            border-radius: 4pt;
            overflow-x: auto;
            margin: 12pt 0;
        }

        ul, ol {
            margin: 10pt 0;
            padding-left: 24pt;
        }

        li {
            margin-bottom: 6pt;
        }

        hr {
            border: none;
            border-top: 2px solid #ecf0f1;
            margin: 20pt 0;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            margin: 12pt 0;
        }

        th {
            background-color: #3498db;
            color: white;
            padding: 8pt;
            text-align: left;
            font-weight: 600;
        }

        td {
            padding: 8pt;
            border-bottom: 1px solid #ecf0f1;
        }

        .severity-critical {
            color: #e74c3c;
            font-weight: bold;
        }

        .severity-high {
            color: #e67e22;
            font-weight: bold;
        }

        .severity-medium {
            color: #f39c12;
            font-weight: bold;
        }

        .severity-low {
            color: #3498db;
            font-weight: bold;
        }

        .highlight-box {
            background-color: #fff3cd;
            border-left: 4pt solid #ffc107;
            padding: 12pt;
            margin: 12pt 0;
        }

        .header-logo {
            text-align: right;
            color: #3498db;
            font-size: 14pt;
            font-weight: 600;
            margin-bottom: 20pt;
        }

        .metadata {
            background-color: #ecf0f1;
            padding: 12pt;
            border-radius: 4pt;
            margin-bottom: 20pt;
        }

        .metadata p {
            margin: 4pt 0;
            font-size: 10pt;
        }

        blockquote {
            border-left: 4pt solid #95a5a6;
            padding-left: 12pt;
            margin: 12pt 0;
            color: #7f8c8d;
            font-style: italic;
        }

        .checklist input[type="checkbox"] {
            margin-right: 6pt;
        }

        .page-break {
            page-break-before: always;
        }
        """

    def markdown_to_pdf(
        self,
        markdown_content: str,
        output_path: str,
        title: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        """
        Convert markdown content to professional PDF

        Args:
            markdown_content: Markdown formatted report content
            output_path: Path where PDF should be saved
            title: Optional report title
            metadata: Optional metadata to include in header

        Returns:
            Path to generated PDF file
        """
        try:
            # Convert markdown to HTML
            html_content = markdown(
                markdown_content,
                extensions=[
                    'tables',
                    'fenced_code',
                    'nl2br',
                    'sane_lists',
                    'codehilite',
                ]
            )

            # Build full HTML document
            html_doc = self._build_html_document(html_content, title, metadata)

            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Generate PDF
            HTML(string=html_doc).write_pdf(
                target=output_path,
                stylesheets=[CSS(string=self.css_template)]
            )

            logger.info(
                "pdf_generated",
                output_path=output_path,
                size_kb=os.path.getsize(output_path) / 1024
            )

            return output_path

        except Exception as e:
            logger.error("pdf_generation_failed", error=str(e), output_path=output_path)
            raise

    def _build_html_document(
        self,
        body_html: str,
        title: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> str:
        """Build complete HTML document with header and styling"""

        title = title or "Incident Report"
        generated_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

        metadata_html = ""
        if metadata:
            metadata_html = '<div class="metadata">'
            if metadata.get("service"):
                metadata_html += f'<p><strong>Service:</strong> {metadata["service"]}</p>'
            if metadata.get("severity"):
                severity_class = f"severity-{metadata['severity'].lower()}"
                metadata_html += f'<p><strong>Severity:</strong> <span class="{severity_class}">{metadata["severity"]}</span></p>'
            if metadata.get("anomaly_score"):
                metadata_html += f'<p><strong>Anomaly Score:</strong> {metadata["anomaly_score"]}</p>'
            if metadata.get("generated_at"):
                metadata_html += f'<p><strong>Generated:</strong> {metadata["generated_at"]}</p>'
            metadata_html += '</div>'

        html_doc = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>{title}</title>
        </head>
        <body data-generated="{generated_date}">
            <div class="header-logo">
                🔭 HELIOS OBSERVABILITY PLATFORM
            </div>
            {metadata_html}
            {body_html}
            <hr style="margin-top: 40pt;">
            <p style="text-align: center; font-size: 9pt; color: #999;">
                This is an automated incident report generated by Helios Observability Platform<br>
                For questions or concerns, contact your DevOps team
            </p>
        </body>
        </html>
        """

        return html_doc
