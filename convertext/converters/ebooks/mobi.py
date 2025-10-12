"""MOBI format converter."""

from pathlib import Path
from typing import Any, Dict, List
import struct

from convertext.converters.base import BaseConverter, Document


class MobiConverter(BaseConverter):
    """MOBI format converter (read-only, converts via EPUB)."""

    @property
    def input_formats(self) -> List[str]:
        return ['mobi', 'azw', 'azw3']

    @property
    def output_formats(self) -> List[str]:
        return ['txt', 'html', 'md']

    def can_convert(self, source: str, target: str) -> bool:
        return source in self.input_formats and target in self.output_formats

    def convert(self, source_path: Path, target_path: Path, config: Dict[str, Any]) -> bool:
        """Convert MOBI/AZW to target format using Calibre."""
        import shutil
        import subprocess
        import tempfile

        # Use Calibre's ebook-convert for MOBI reading
        ebook_convert = shutil.which('ebook-convert')
        if not ebook_convert:
            raise RuntimeError(
                "MOBI/AZW reading requires Calibre's 'ebook-convert'. "
                "Install Calibre: https://calibre-ebook.com/download"
            )

        # Convert MOBI → EPUB first, then read EPUB
        with tempfile.NamedTemporaryFile(suffix='.epub', delete=False) as tmp:
            tmp_epub = Path(tmp.name)

        try:
            # Convert to EPUB using Calibre
            result = subprocess.run(
                [ebook_convert, str(source_path), str(tmp_epub)],
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode != 0 or not tmp_epub.exists():
                raise RuntimeError(f"MOBI conversion failed: {result.stderr}")

            # Now read the EPUB and convert to target
            from convertext.converters.ebooks.epub import EpubConverter
            epub_converter = EpubConverter()
            success = epub_converter.convert(tmp_epub, target_path, config)

            return success

        finally:
            # Cleanup temp file
            if tmp_epub.exists():
                tmp_epub.unlink()

        doc = self._read_mobi(source_path, config)

        target_fmt = target_path.suffix.lstrip('.').lower()
        if target_fmt == 'txt':
            return self._write_txt(doc, target_path)
        elif target_fmt == 'html':
            return self._write_html(doc, target_path)
        elif target_fmt == 'md':
            return self._write_md(doc, target_path)

        return False


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


class ToMobiConverter(BaseConverter):
    """Convert various formats to MOBI via EPUB."""

    @property
    def input_formats(self) -> List[str]:
        return ['epub']

    @property
    def output_formats(self) -> List[str]:
        return ['mobi', 'azw3']

    def can_convert(self, source: str, target: str) -> bool:
        return source == 'epub' and target in self.output_formats

    def convert(self, source_path: Path, target_path: Path, config: Dict[str, Any]) -> bool:
        """Convert EPUB to MOBI/AZW3 using kindlegen or calibre."""
        import shutil
        import subprocess

        # Try kindlegen first (Amazon's official tool)
        kindlegen = shutil.which('kindlegen')
        if kindlegen:
            try:
                result = subprocess.run(
                    [kindlegen, str(source_path), '-o', target_path.name],
                    capture_output=True,
                    text=True,
                    cwd=str(source_path.parent)
                )
                if result.returncode in [0, 1]:  # kindlegen returns 1 on warnings
                    # Move the generated file to target location
                    generated = source_path.with_suffix('.mobi')
                    if generated.exists():
                        if generated != target_path:
                            shutil.move(str(generated), str(target_path))
                        return True
            except Exception as e:
                pass  # Fall through to ebook-convert

        # Try ebook-convert from Calibre
        ebook_convert = shutil.which('ebook-convert')
        if ebook_convert:
            try:
                result = subprocess.run(
                    [ebook_convert, str(source_path), str(target_path)],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                if result.returncode == 0 and target_path.exists():
                    return True
            except Exception as e:
                pass

        # No conversion tool available
        raise RuntimeError(
            "MOBI/AZW3 creation requires 'kindlegen' or 'ebook-convert' (Calibre). "
            "Install Calibre: https://calibre-ebook.com/download or "
            "Download kindlegen: https://www.amazon.com/gp/feature.html?docId=1000765211"
        )
