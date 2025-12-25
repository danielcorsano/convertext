"""PDF format output converter using ReportLab."""

from pathlib import Path
from typing import Any, Dict, List
from io import BytesIO

from reportlab.lib.pagesizes import A4, letter, legal
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
    PageBreak,
    ListFlowable,
    ListItem,
)
from reportlab.lib import colors

from convertext.converters.base import BaseConverter, Document
from convertext.converters.utils import escape_html, hex_to_rgb


class ToPdfConverter(BaseConverter):
    """Convert various formats to PDF using ReportLab."""

    @property
    def input_formats(self) -> List[str]:
        return ['txt', 'html', 'md', 'docx', 'odt', 'epub', 'mobi', 'fb2', 'rtf']

    @property
    def output_formats(self) -> List[str]:
        return ['pdf']

    def can_convert(self, source: str, target: str) -> bool:
        return source in self.input_formats and target == 'pdf'

    def convert(self, source_path: Path, target_path: Path, config: Dict[str, Any]) -> bool:
        """Convert to PDF."""
        source_fmt = source_path.suffix.lstrip('.').lower()

        # If source is already HTML or TXT, read directly
        if source_fmt in ['html', 'htm']:
            doc = self._read_html(source_path, config)
            return self._create_pdf(doc, target_path, config)
        elif source_fmt == 'txt':
            doc = self._read_txt(source_path, config)
            return self._create_pdf(doc, target_path, config)

        # Otherwise, convert to intermediate format first
        from convertext.registry import get_registry
        registry = get_registry()

        converter = registry.get_converter(source_fmt, 'html')
        if not converter:
            converter = registry.get_converter(source_fmt, 'txt')
        if not converter:
            return False

        from tempfile import NamedTemporaryFile
        with NamedTemporaryFile(mode='w', suffix='.html', delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            if not converter.convert(source_path, tmp_path, config):
                return False

            if tmp_path.suffix == '.html':
                doc = self._read_html(tmp_path, config)
            else:
                doc = self._read_txt(tmp_path, config)

            return self._create_pdf(doc, target_path, config)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def _read_txt(self, path: Path, config: Dict[str, Any]) -> Document:
        """Read plain text into Document."""
        doc = Document()
        encoding = config.get('documents', {}).get('encoding', 'utf-8')

        with open(path, 'r', encoding=encoding) as f:
            content = f.read()
            for para in content.split('\n\n'):
                if para.strip():
                    doc.add_paragraph(para.strip())

        return doc

    def _read_html(self, path: Path, config: Dict[str, Any]) -> Document:
        """Read HTML into Document."""
        doc = Document()
        encoding = config.get('documents', {}).get('encoding', 'utf-8')

        with open(path, 'r', encoding=encoding) as f:
            content = f.read()

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(content, 'html.parser')

        title_tag = soup.find('title')
        if title_tag:
            doc.metadata['title'] = title_tag.get_text()

        for element in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'table', 'ul', 'ol']):
            if element.name.startswith('h'):
                level = int(element.name[1])
                doc.add_heading(element.get_text().strip(), level)

            elif element.name == 'p':
                text = element.get_text().strip()
                if text:
                    doc.add_paragraph(text)

            elif element.name == 'table':
                rows = []
                headers = []
                thead = element.find('thead')
                if thead:
                    header_row = thead.find('tr')
                    if header_row:
                        headers = [th.get_text().strip() for th in header_row.find_all(['th', 'td'])]

                tbody = element.find('tbody') or element
                for row in tbody.find_all('tr'):
                    cells = [cell.get_text().strip() for cell in row.find_all(['td', 'th'])]
                    if cells:
                        rows.append(cells)

                if rows:
                    doc.add_table(rows=rows, headers=headers if headers else None)

            elif element.name in ['ul', 'ol']:
                items = [li.get_text().strip() for li in element.find_all('li')]
                if items:
                    doc.add_list(items=items, ordered=(element.name == 'ol'))

        return doc

    def _create_pdf(self, doc: Document, path: Path, config: Dict[str, Any]) -> bool:
        """Create PDF using ReportLab."""
        page_size_name = config.get('documents', {}).get('pdf', {}).get('page_size', 'A4')
        page_sizes = {'A4': A4, 'letter': letter, 'legal': legal}
        page_size = page_sizes.get(page_size_name, A4)

        pdf_doc = SimpleDocTemplate(
            str(path),
            pagesize=page_size,
            title=doc.metadata.get('title', ''),
            author=doc.metadata.get('author', ''),
            subject=doc.metadata.get('subject', ''),
        )

        styles = getSampleStyleSheet()

        heading_styles = {}
        for i in range(1, 7):
            heading_styles[i] = ParagraphStyle(
                name=f'Heading{i}',
                parent=styles['Heading1'],
                fontSize=20 - (i * 2),
                spaceAfter=12,
                spaceBefore=12,
                textColor=colors.black,
            )

        story = []

        if doc.metadata.get('title'):
            title_style = ParagraphStyle(
                name='Title',
                parent=styles['Title'],
                fontSize=24,
                textColor=colors.black,
                spaceAfter=12,
            )
            story.append(Paragraph(doc.metadata['title'], title_style))

        if doc.metadata.get('author'):
            author_style = ParagraphStyle(
                name='Author',
                parent=styles['Normal'],
                fontSize=12,
                textColor=colors.grey,
                spaceAfter=20,
                alignment=TA_CENTER,
            )
            story.append(Paragraph(f"By {doc.metadata['author']}", author_style))

        for block in doc.content:
            if block['type'] == 'heading':
                level = min(block['level'], 6)
                story.append(Paragraph(block['data'], heading_styles[level]))

            elif block['type'] in ['paragraph', 'text']:
                story.append(Paragraph(block['data'], styles['Normal']))
                story.append(Spacer(1, 0.2 * inch))

            elif block['type'] == 'run':
                formatted_text = self._format_run_for_pdf(block)
                story.append(Paragraph(formatted_text, styles['Normal']))

            elif block['type'] == 'table':
                headers = block.get('headers', [])
                rows = block['rows']

                table_data = []
                if headers:
                    table_data.append(headers)
                table_data.extend(rows)

                table = Table(table_data)
                table_style = [
                    ('BACKGROUND', (0, 0), (-1, 0 if headers else -1), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0 if headers else -1), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0 if headers else -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                    ('TOPPADDING', (0, 0), (-1, -1), 6),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ]
                table.setStyle(TableStyle(table_style))
                story.append(table)
                story.append(Spacer(1, 0.2 * inch))

            elif block['type'] == 'list':
                items = []
                for item in block['items']:
                    items.append(ListItem(Paragraph(item, styles['Normal'])))

                list_style = 'decimal' if block.get('ordered') else 'bullet'
                story.append(ListFlowable(items, bulletType=list_style))
                story.append(Spacer(1, 0.2 * inch))

            elif block['type'] == 'image':
                if block['name'] in doc.images:
                    img_data = doc.images[block['name']]['data']
                    try:
                        img = Image(BytesIO(img_data), width=4 * inch)
                        story.append(img)
                        story.append(Spacer(1, 0.2 * inch))
                    except Exception:
                        pass

            elif block['type'] == 'link':
                link_text = f'<a href="{block["url"]}" color="blue">{block["text"]}</a>'
                story.append(Paragraph(link_text, styles['Normal']))

        pdf_doc.build(story)
        return True

    def _format_run_for_pdf(self, block: Dict[str, Any]) -> str:
        """Format a run block for ReportLab Paragraph markup."""
        text = escape_html(block['text'])

        if block.get('bold'):
            text = f'<b>{text}</b>'
        if block.get('italic'):
            text = f'<i>{text}</i>'
        if block.get('underline'):
            text = f'<u>{text}</u>'

        if block.get('color'):
            text = f'<font color="{block["color"]}">{text}</font>'

        if block.get('size'):
            text = f'<font size="{block["size"]}">{text}</font>'

        return text
