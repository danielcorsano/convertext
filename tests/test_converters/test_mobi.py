"""Tests for MOBI format converter."""

import tempfile
from pathlib import Path
import struct


def test_mobi_write_basic():
    """Test basic TXT to MOBI conversion."""
    from convertext.converters.ebooks.mobi import ToMobiConverter
    converter = ToMobiConverter()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        txt_file = tmppath / "test.txt"
        txt_file.write_text("Test Document\n\nThis is a test paragraph.\n\nAnother paragraph here.")
        mobi_file = tmppath / "test.mobi"
        result = converter.convert(txt_file, mobi_file, {})
        assert result is True
        assert mobi_file.exists()
        assert mobi_file.stat().st_size > 0


def test_mobi_palmdb_header():
    """Test MOBI file has valid PalmDB header."""
    from convertext.converters.ebooks.mobi import ToMobiConverter
    converter = ToMobiConverter()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        txt_file = tmppath / "test.txt"
        txt_file.write_text("Test Document\n\nContent here.")
        mobi_file = tmppath / "test.mobi"
        converter.convert(txt_file, mobi_file, {})

        with open(mobi_file, 'rb') as f:
            f.seek(60)
            assert f.read(4) == b'BOOK'
            assert f.read(4) == b'MOBI'
            f.seek(76)
            num_records = struct.unpack('>H', f.read(2))[0]
            assert num_records >= 3  # record0 + text + EOF


def test_mobi_mobi_header():
    """Test record 0 has valid PalmDOC + MOBI headers."""
    from convertext.converters.ebooks.mobi import ToMobiConverter
    converter = ToMobiConverter()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        txt_file = tmppath / "test.txt"
        txt_file.write_text("Test\n\nContent.")
        mobi_file = tmppath / "test.mobi"
        converter.convert(txt_file, mobi_file, {})

        with open(mobi_file, 'rb') as f:
            f.seek(78)
            record0_offset = struct.unpack('>I', f.read(4))[0]
            f.seek(record0_offset)
            compression = struct.unpack('>H', f.read(2))[0]
            assert compression == 2  # PalmDOC
            f.seek(record0_offset + 16)
            assert f.read(4) == b'MOBI'


def test_palmdoc_compress_decompress_ascii():
    """Test PalmDOC compression roundtrip with ASCII content."""
    from convertext.converters.ebooks.mobi import ToMobiConverter, MobiConverter
    writer = ToMobiConverter()
    reader = MobiConverter()

    test_cases = [
        b"Hello World",
        b"<p>Simple paragraph</p>",
        b"<html><body><h1>Title</h1><p>Content here with spaces and punctuation!</p></body></html>",
        b"Repeated text. Repeated text. Repeated text.",
        b"Short",
    ]
    for data in test_cases:
        compressed = writer._palmdoc_compress(data)
        decompressed = reader._palmdoc_decompress(compressed)
        assert decompressed == data, f"Roundtrip failed for: {data!r}\nGot: {decompressed!r}"


def test_palmdoc_compress_decompress_utf8():
    """Test PalmDOC compression handles UTF-8 multi-byte characters."""
    from convertext.converters.ebooks.mobi import ToMobiConverter, MobiConverter
    writer = ToMobiConverter()
    reader = MobiConverter()

    test_cases = [
        "Café résumé naïve".encode('utf-8'),
        "Ünîcödé text with spëcial chars".encode('utf-8'),
        "<p>Ação über straße</p>".encode('utf-8'),
    ]
    for data in test_cases:
        compressed = writer._palmdoc_compress(data)
        decompressed = reader._palmdoc_decompress(compressed)
        assert decompressed == data, f"UTF-8 roundtrip failed for: {data!r}\nGot: {decompressed!r}"


def test_mobi_roundtrip_txt():
    """Test TXT -> MOBI -> TXT roundtrip preserves content."""
    from convertext.converters.ebooks.mobi import ToMobiConverter, MobiConverter
    writer = ToMobiConverter()
    reader = MobiConverter()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        txt_file = tmppath / "test.txt"
        txt_file.write_text("My Book Title\n\nFirst paragraph of the book.\n\nSecond paragraph with more text.")
        mobi_file = tmppath / "test.mobi"
        writer.convert(txt_file, mobi_file, {})
        txt_out = tmppath / "output.txt"
        reader.convert(mobi_file, txt_out, {})
        output = txt_out.read_text()
        assert "First paragraph" in output
        assert "Second paragraph" in output


def test_mobi_roundtrip_html():
    """Test HTML -> MOBI -> HTML roundtrip preserves content."""
    from convertext.converters.ebooks.mobi import ToMobiConverter, MobiConverter
    writer = ToMobiConverter()
    reader = MobiConverter()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        html_file = tmppath / "test.html"
        html_file.write_text("<html><head><title>Test Book</title></head><body><h1>Test Book</h1><p>A paragraph.</p></body></html>")
        mobi_file = tmppath / "test.mobi"
        writer.convert(html_file, mobi_file, {})
        html_out = tmppath / "output.html"
        reader.convert(mobi_file, html_out, {})
        output = html_out.read_text()
        assert "A paragraph" in output


def test_mobi_can_convert():
    """Test format support declarations."""
    from convertext.converters.ebooks.mobi import ToMobiConverter, MobiConverter

    writer = ToMobiConverter()
    assert writer.can_convert('txt', 'mobi')
    assert writer.can_convert('html', 'mobi')
    assert writer.can_convert('md', 'mobi')
    assert not writer.can_convert('mobi', 'txt')

    reader = MobiConverter()
    assert reader.can_convert('mobi', 'txt')
    assert reader.can_convert('mobi', 'html')
    assert reader.can_convert('azw', 'txt')
    assert not reader.can_convert('txt', 'mobi')


def _independent_parse_mobi(path):
    """Parse MOBI file from raw binary — independent of our reader code.

    Validates PalmDB header, record list, PalmDOC header, MOBI header,
    EXTH header, and decompresses text records. Returns extracted text.
    """
    with open(path, 'rb') as f:
        data = f.read()

    errors = []

    # PalmDB header (78 bytes + record list)
    name = data[0:32].rstrip(b'\x00')
    assert len(name) > 0, "Empty PalmDB name"

    type_code = data[60:64]
    creator = data[64:68]
    if type_code != b'BOOK':
        errors.append(f"Type should be BOOK, got {type_code}")
    if creator != b'MOBI':
        errors.append(f"Creator should be MOBI, got {creator}")

    num_records = struct.unpack('>H', data[76:78])[0]
    assert num_records >= 3, f"Need at least 3 records, got {num_records}"

    # Parse record list
    record_offsets = []
    for i in range(num_records):
        base = 78 + i * 8
        offset = struct.unpack('>I', data[base:base+4])[0]
        record_offsets.append(offset)

    # Validate offsets are within file and ascending
    for i, off in enumerate(record_offsets):
        assert off < len(data), f"Record {i} offset {off} beyond file size {len(data)}"
        if i > 0:
            assert off > record_offsets[i-1], f"Record {i} offset not ascending"

    # Record 0: PalmDOC header (16 bytes) + MOBI header
    r0 = record_offsets[0]
    compression = struct.unpack('>H', data[r0:r0+2])[0]
    assert compression in (1, 2), f"Unknown compression type {compression}"
    text_length = struct.unpack('>I', data[r0+4:r0+8])[0]
    num_text_records = struct.unpack('>H', data[r0+8:r0+10])[0]
    record_size = struct.unpack('>H', data[r0+10:r0+12])[0]
    assert record_size == 4096, f"Expected record size 4096, got {record_size}"

    # MOBI header at r0 + 16
    mobi_magic = data[r0+16:r0+20]
    assert mobi_magic == b'MOBI', f"Missing MOBI magic at record 0 + 16"
    mobi_header_len = struct.unpack('>I', data[r0+20:r0+24])[0]
    mobi_type = struct.unpack('>I', data[r0+24:r0+28])[0]
    encoding = struct.unpack('>I', data[r0+28:r0+32])[0]
    assert encoding == 65001, f"Expected UTF-8 encoding (65001), got {encoding}"

    # EXTH flags
    exth_flags = struct.unpack('>I', data[r0+16+112:r0+16+116])[0]
    has_exth = (exth_flags & 0x40) != 0

    # Find and validate EXTH header
    if has_exth:
        exth_offset = r0 + 16 + mobi_header_len
        exth_magic = data[exth_offset:exth_offset+4]
        assert exth_magic == b'EXTH', f"EXTH flag set but no EXTH header at offset {exth_offset}"

    # Decompress text records independently
    def palmdoc_decompress(compressed):
        result = []
        j = 0
        while j < len(compressed):
            c = compressed[j]
            j += 1
            if c == 0:
                continue
            elif 1 <= c <= 8:
                result.extend(compressed[j:j+c])
                j += c
            elif 0x80 <= c <= 0xBF:
                result.append(0x20)
                result.append(c ^ 0x80)
            elif c >= 0xC0:
                if j < len(compressed):
                    c2 = compressed[j]
                    j += 1
                    pair = ((c << 8) | c2) & 0x3FFF
                    length = (pair & 7) + 3
                    dist = (pair >> 3) + 1
                    start = len(result) - dist
                    if start >= 0:
                        for _ in range(length):
                            if start < len(result):
                                result.append(result[start])
                                start += 1
            else:
                result.append(c)
        return bytes(result)

    text_parts = []
    for i in range(1, num_text_records + 1):
        if i >= len(record_offsets):
            break
        rec_start = record_offsets[i]
        rec_end = record_offsets[i+1] if i+1 < len(record_offsets) else len(data)
        rec_data = data[rec_start:rec_end]
        if compression == 2:
            text_parts.append(palmdoc_decompress(rec_data))
        else:
            text_parts.append(rec_data)

    full_text = b''.join(text_parts)
    assert len(full_text) == text_length, f"Decompressed length {len(full_text)} != declared {text_length}"

    # Verify it's valid UTF-8
    decoded = full_text.decode('utf-8')

    assert len(errors) == 0, f"Validation errors: {errors}"
    return decoded


def test_mobi_independent_structural_validation():
    """Validate MOBI output with an independent binary parser."""
    from convertext.converters.ebooks.mobi import ToMobiConverter
    converter = ToMobiConverter()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        txt_file = tmppath / "test.txt"
        txt_file.write_text("Test Book\n\nA paragraph with some content.\n\nAnother paragraph.")
        mobi_file = tmppath / "test.mobi"
        converter.convert(txt_file, mobi_file, {})
        text = _independent_parse_mobi(mobi_file)
        assert "A paragraph with some content" in text
        assert "Another paragraph" in text


def test_mobi_independent_validation_utf8():
    """Validate MOBI with UTF-8 content using independent parser."""
    from convertext.converters.ebooks.mobi import ToMobiConverter
    converter = ToMobiConverter()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        html_file = tmppath / "test.html"
        html_file.write_text(
            "<html><head><title>Café</title></head><body>"
            "<h1>Café résumé</h1>"
            "<p>Ação über straße naïve</p>"
            "</body></html>"
        )
        mobi_file = tmppath / "test.mobi"
        converter.convert(html_file, mobi_file, {})
        text = _independent_parse_mobi(mobi_file)
        assert "Café" in text or "Caf&eacute;" in text or "Caf&#233;" in text
        assert "ber" in text  # über may be escaped


def test_mobi_independent_validation_large():
    """Validate MOBI with content spanning multiple records."""
    from convertext.converters.ebooks.mobi import ToMobiConverter
    converter = ToMobiConverter()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        txt_file = tmppath / "test.txt"
        # Create content that spans multiple 4096-byte records
        paragraphs = [f"Paragraph number {i}. " + "Lorem ipsum dolor sit amet. " * 20 for i in range(30)]
        txt_file.write_text("Large Book\n\n" + "\n\n".join(paragraphs))
        mobi_file = tmppath / "test.mobi"
        converter.convert(txt_file, mobi_file, {})
        text = _independent_parse_mobi(mobi_file)
        assert "Paragraph number 0" in text
        assert "Paragraph number 29" in text
