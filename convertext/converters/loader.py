"""Load and register all converters."""

from convertext.registry import register_converter
from convertext.converters.documents.txt import TxtConverter
from convertext.converters.documents.pdf import PDFConverter
from convertext.converters.documents.markdown import MarkdownConverter
from convertext.converters.documents.html import HtmlConverter
from convertext.converters.documents.docx import DocxConverter
from convertext.converters.documents.rtf import RtfConverter
from convertext.converters.ebooks.epub import EpubConverter, ToEpubConverter


def load_converters():
    """Load and register all available converters."""
    register_converter(TxtConverter())
    register_converter(PDFConverter())
    register_converter(MarkdownConverter())
    register_converter(HtmlConverter())
    register_converter(DocxConverter())
    register_converter(RtfConverter())
    register_converter(EpubConverter())
    register_converter(ToEpubConverter())
