"""EPUB format converter."""

from pathlib import Path
from typing import Any, Dict, List

from ebooklib import epub
from bs4 import BeautifulSoup

from convertext.converters.base import BaseConverter, Document


class EpubConverter(BaseConverter):
    """EPUB format converter."""

    @property
    def input_formats(self) -> List[str]:
        return ['epub']

    @property
    def output_formats(self) -> List[str]:
        return ['txt', 'html', 'md']

    def can_convert(self, source: str, target: str) -> bool:
        return source == 'epub' and target in self.output_formats

    def convert(self, source_path: Path, target_path: Path, config: Dict[str, Any]) -> bool:
        """Convert EPUB to target format."""
        doc = self._read_epub(source_path, config)

        target_fmt = target_path.suffix.lstrip('.').lower()
        if target_fmt == 'txt':
            return self._write_txt(doc, target_path)
        elif target_fmt == 'html':
            return self._write_html(doc, target_path)
        elif target_fmt == 'md':
            return self._write_md(doc, target_path)

        return False

    def _read_epub(self, path: Path, config: Dict[str, Any]) -> Document:
        """Read EPUB into intermediate Document."""
        doc = Document()
        book = epub.read_epub(str(path))

        if book.get_metadata('DC', 'title'):
            doc.metadata['title'] = book.get_metadata('DC', 'title')[0][0]
        if book.get_metadata('DC', 'creator'):
            doc.metadata['author'] = book.get_metadata('DC', 'creator')[0][0]
        if book.get_metadata('DC', 'language'):
            doc.metadata['language'] = book.get_metadata('DC', 'language')[0][0]

        for item in book.get_items():
            if item.get_type() == 9:  # ITEM_DOCUMENT
                soup = BeautifulSoup(item.get_content(), 'html.parser')

                for element in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                    if element.name.startswith('h'):
                        level = int(element.name[1])
                        text = element.get_text().strip()
                        if text:
                            doc.add_heading(text, level)
                    elif element.name == 'p':
                        text = element.get_text().strip()
                        if text:
                            doc.add_paragraph(text)

        return doc

    def _write_txt(self, doc: Document, path: Path) -> bool:
        """Write Document to plain text."""
        with open(path, 'w', encoding='utf-8') as f:
            if doc.metadata.get('title'):
                f.write(doc.metadata['title'] + '\n')
                f.write('=' * len(doc.metadata['title']) + '\n\n')
            if doc.metadata.get('author'):
                f.write(f"By: {doc.metadata['author']}\n\n")

            for block in doc.content:
                if block['type'] in ['text', 'paragraph']:
                    f.write(block['data'] + '\n\n')
                elif block['type'] == 'heading':
                    f.write('\n' + block['data'].upper() + '\n')
                    f.write('-' * len(block['data']) + '\n\n')
        return True

    def _write_html(self, doc: Document, path: Path) -> bool:
        """Write Document to HTML."""
        html_parts = [
            '<!DOCTYPE html>',
            '<html>',
            '<head>',
            '<meta charset="utf-8">',
        ]

        if doc.metadata.get('title'):
            html_parts.append(f"<title>{self._escape_html(doc.metadata['title'])}</title>")
        else:
            html_parts.append('<title>Document</title>')

        html_parts.append('</head>')
        html_parts.append('<body>')

        if doc.metadata.get('title'):
            html_parts.append(f"<h1>{self._escape_html(doc.metadata['title'])}</h1>")
        if doc.metadata.get('author'):
            html_parts.append(f"<p><em>By {self._escape_html(doc.metadata['author'])}</em></p>")

        for block in doc.content:
            if block['type'] == 'paragraph':
                html_parts.append(f"<p>{self._escape_html(block['data'])}</p>")
            elif block['type'] == 'heading':
                level = block['level']
                html_parts.append(f"<h{level}>{self._escape_html(block['data'])}</h{level}>")

        html_parts.append('</body>')
        html_parts.append('</html>')

        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(html_parts))

        return True

    def _write_md(self, doc: Document, path: Path) -> bool:
        """Write Document to Markdown."""
        with open(path, 'w', encoding='utf-8') as f:
            if doc.metadata.get('title'):
                f.write(f"# {doc.metadata['title']}\n\n")
            if doc.metadata.get('author'):
                f.write(f"**Author:** {doc.metadata['author']}\n\n")

            for block in doc.content:
                if block['type'] == 'paragraph':
                    f.write(block['data'] + '\n\n')
                elif block['type'] == 'heading':
                    f.write('#' * (block['level'] + 1) + ' ' + block['data'] + '\n\n')
        return True

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&#39;'))


class ToEpubConverter(BaseConverter):
    """Convert various formats to EPUB."""

    @property
    def input_formats(self) -> List[str]:
        return ['txt', 'html', 'md']

    @property
    def output_formats(self) -> List[str]:
        return ['epub']

    def can_convert(self, source: str, target: str) -> bool:
        return source in self.input_formats and target == 'epub'

    def convert(self, source_path: Path, target_path: Path, config: Dict[str, Any]) -> bool:
        """Convert to EPUB."""
        source_fmt = source_path.suffix.lstrip('.').lower()

        if source_fmt == 'txt':
            doc = self._read_txt(source_path, config)
        elif source_fmt in ['html', 'htm']:
            doc = self._read_html(source_path, config)
        elif source_fmt in ['md', 'markdown']:
            doc = self._read_markdown(source_path, config)
        else:
            return False

        return self._create_epub(doc, target_path, config, source_path.stem)

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

        soup = BeautifulSoup(content, 'html.parser')

        title_tag = soup.find('title')
        if title_tag:
            doc.metadata['title'] = title_tag.get_text()

        for element in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            if element.name.startswith('h'):
                level = int(element.name[1])
                doc.add_heading(element.get_text().strip(), level)
            elif element.name == 'p':
                text = element.get_text().strip()
                if text:
                    doc.add_paragraph(text)

        return doc

    def _read_markdown(self, path: Path, config: Dict[str, Any]) -> Document:
        """Read Markdown into Document."""
        doc = Document()
        encoding = config.get('documents', {}).get('encoding', 'utf-8')

        with open(path, 'r', encoding=encoding) as f:
            content = f.read()

        import markdown
        html_content = markdown.markdown(content)
        soup = BeautifulSoup(html_content, 'html.parser')

        for element in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            if element.name.startswith('h'):
                level = int(element.name[1])
                doc.add_heading(element.get_text(), level)
            elif element.name == 'p':
                doc.add_paragraph(element.get_text())

        return doc

    def _create_epub(self, doc: Document, path: Path, config: Dict[str, Any], default_title: str) -> bool:
        """Create EPUB from Document."""
        book = epub.EpubBook()

        title = doc.metadata.get('title', default_title)
        book.set_title(title)
        book.set_language(doc.metadata.get('language', 'en'))

        if doc.metadata.get('author'):
            book.add_author(doc.metadata['author'])

        chapters = []
        current_chapter_content = []
        chapter_num = 1

        for block in doc.content:
            if block['type'] == 'heading' and block['level'] == 1:
                if current_chapter_content:
                    chapter = epub.EpubHtml(
                        title=f"Chapter {chapter_num}",
                        file_name=f'chap_{chapter_num:02d}.xhtml',
                        lang='en'
                    )
                    chapter.content = ''.join(current_chapter_content)
                    chapters.append(chapter)
                    chapter_num += 1
                    current_chapter_content = []

                current_chapter_content.append(f'<h1>{self._escape_html(block["data"])}</h1>')

            elif block['type'] == 'paragraph':
                current_chapter_content.append(f'<p>{self._escape_html(block["data"])}</p>')
            elif block['type'] == 'heading':
                level = block['level']
                current_chapter_content.append(f'<h{level}>{self._escape_html(block["data"])}</h{level}>')

        if current_chapter_content:
            chapter = epub.EpubHtml(
                title=f"Chapter {chapter_num}",
                file_name=f'chap_{chapter_num:02d}.xhtml',
                lang='en'
            )
            chapter.content = ''.join(current_chapter_content)
            chapters.append(chapter)

        if not chapters:
            chapter = epub.EpubHtml(title='Content', file_name='content.xhtml', lang='en')
            chapter.content = '<h1>Content</h1><p>No content</p>'
            chapters.append(chapter)

        for chapter in chapters:
            book.add_item(chapter)

        book.toc = tuple(chapters)
        book.spine = ['nav'] + chapters
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())

        epub.write_epub(str(path), book)
        return True

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&#39;'))
