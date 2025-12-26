"""Load and register all converters."""

from convertext.registry import register_converter
from convertext.converters.documents.txt import TxtConverter
from convertext.converters.documents.pdf import PDFConverter
from convertext.converters.documents.markdown import MarkdownConverter
from convertext.converters.documents.html import HtmlConverter
from convertext.converters.documents.docx import DocxConverter
from convertext.converters.documents.rtf import RtfConverter
from convertext.converters.ebooks.epub import EpubConverter, ToEpubConverter
from convertext.converters.documents.pdf_to_epub import PdfToEpubConverter


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
    register_converter(PdfToEpubConverter())

    # Optional converters (gracefully skip if dependencies missing)
    try:
        from convertext.converters.ebooks.mobi import MobiConverter, ToMobiConverter
        register_converter(MobiConverter())
        register_converter(ToMobiConverter())
    except ImportError:
        pass  # MOBI support not installed

    try:
        from convertext.converters.ebooks.fb2 import FB2Converter, ToFB2Converter
        register_converter(FB2Converter())
        register_converter(ToFB2Converter())
    except ImportError:
        pass  # FB2 support requires lxml

    try:
        from convertext.converters.documents.odt import OdtConverter
        register_converter(OdtConverter())
    except ImportError:
        pass  # ODT support requires odfpy

    # New output converters
    from convertext.converters.documents.to_pdf import ToPdfConverter
    from convertext.converters.documents.to_docx import ToDocxConverter
    from convertext.converters.documents.to_rtf import ToRtfConverter

    register_converter(ToPdfConverter())
    register_converter(ToDocxConverter())
    register_converter(ToRtfConverter())
