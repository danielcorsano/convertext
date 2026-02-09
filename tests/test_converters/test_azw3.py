"""Tests for AZW3/KF8 format converter."""

import tempfile
from pathlib import Path
import struct


def test_azw3_write_basic():
    """Test basic TXT to AZW3 conversion."""
    from convertext.converters.ebooks.azw3 import ToAzw3Converter
    converter = ToAzw3Converter()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        txt_file = tmppath / "test.txt"
        txt_file.write_text("Test Document\n\nThis is a test paragraph.\n\nAnother paragraph here.")
        azw3_file = tmppath / "test.azw3"
        result = converter.convert(txt_file, azw3_file, {})
        assert result is True
        assert azw3_file.exists()
        assert azw3_file.stat().st_size > 0


def test_azw3_palmdb_header():
    """Test AZW3 file has valid PalmDB header with BOOK/MOBI type/creator."""
    from convertext.converters.ebooks.azw3 import ToAzw3Converter
    converter = ToAzw3Converter()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        txt_file = tmppath / "test.txt"
        txt_file.write_text("Test Document\n\nContent here.")
        azw3_file = tmppath / "test.azw3"
        converter.convert(txt_file, azw3_file, {})

        with open(azw3_file, 'rb') as f:
            f.seek(60)
            assert f.read(4) == b'BOOK'
            assert f.read(4) == b'MOBI'
            f.seek(76)
            num_records = struct.unpack('>H', f.read(2))[0]
            # record0 + text + FDST + FLIS + FCIS + EOF
            assert num_records >= 6


def test_azw3_mobi_header_v8():
    """Test record 0 has MOBI v8 header with 264-byte length and UTF-8 encoding."""
    from convertext.converters.ebooks.azw3 import ToAzw3Converter
    converter = ToAzw3Converter()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        txt_file = tmppath / "test.txt"
        txt_file.write_text("Test\n\nContent.")
        azw3_file = tmppath / "test.azw3"
        converter.convert(txt_file, azw3_file, {})

        with open(azw3_file, 'rb') as f:
            f.seek(78)
            record0_offset = struct.unpack('>I', f.read(4))[0]
            f.seek(record0_offset)
            compression = struct.unpack('>H', f.read(2))[0]
            assert compression == 2  # PalmDOC
            f.seek(record0_offset + 16)
            assert f.read(4) == b'MOBI'
            # Header length = 264
            header_len = struct.unpack('>I', f.read(4))[0]
            assert header_len == 264
            f.seek(record0_offset + 0x1C)
            encoding = struct.unpack('>I', f.read(4))[0]
            assert encoding == 65001  # UTF-8
            f.seek(record0_offset + 0x24)
            version = struct.unpack('>I', f.read(4))[0]
            assert version == 8  # KF8
            f.seek(record0_offset + 0x68)
            min_version = struct.unpack('>I', f.read(4))[0]
            assert min_version == 8


def test_palmdoc_compress_decompress():
    """Test PalmDOC compression roundtrip with ASCII and UTF-8 content."""
    from convertext.converters.ebooks.azw3 import ToAzw3Converter, Azw3Converter
    writer = ToAzw3Converter()
    reader = Azw3Converter()

    test_cases = [
        b"Hello World",
        b"<p>Simple paragraph</p>",
        b"<html><body><h1>Title</h1><p>Content here with spaces and punctuation!</p></body></html>",
        b"Repeated text. Repeated text. Repeated text.",
        b"Short",
        "Cafe\u0301 re\u0301sume\u0301 nai\u0308ve".encode('utf-8'),
        "Acao uber strasse".encode('utf-8'),
        "<p>A\u00e7\u00e3o \u00fcber stra\u00dfe</p>".encode('utf-8'),
    ]
    for data in test_cases:
        compressed = writer._palmdoc_compress(data)
        decompressed = reader._palmdoc_decompress(compressed)
        assert decompressed == data, f"Roundtrip failed for: {data!r}\nGot: {decompressed!r}"


def test_azw3_roundtrip_txt():
    """Test TXT -> AZW3 -> TXT roundtrip preserves content."""
    from convertext.converters.ebooks.azw3 import ToAzw3Converter, Azw3Converter
    writer = ToAzw3Converter()
    reader = Azw3Converter()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        txt_file = tmppath / "test.txt"
        txt_file.write_text("My Book Title\n\nFirst paragraph of the book.\n\nSecond paragraph with more text.")
        azw3_file = tmppath / "test.azw3"
        writer.convert(txt_file, azw3_file, {})
        txt_out = tmppath / "output.txt"
        reader.convert(azw3_file, txt_out, {})
        output = txt_out.read_text()
        assert "First paragraph" in output
        assert "Second paragraph" in output


def test_azw3_roundtrip_html():
    """Test HTML -> AZW3 -> HTML roundtrip preserves content."""
    from convertext.converters.ebooks.azw3 import ToAzw3Converter, Azw3Converter
    writer = ToAzw3Converter()
    reader = Azw3Converter()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        html_file = tmppath / "test.html"
        html_file.write_text("<html><head><title>Test Book</title></head><body><h1>Test Book</h1><p>A paragraph.</p></body></html>")
        azw3_file = tmppath / "test.azw3"
        writer.convert(html_file, azw3_file, {})
        html_out = tmppath / "output.html"
        reader.convert(azw3_file, html_out, {})
        output = html_out.read_text()
        assert "A paragraph" in output


def test_azw3_can_convert():
    """Test format support declarations."""
    from convertext.converters.ebooks.azw3 import ToAzw3Converter, Azw3Converter

    writer = ToAzw3Converter()
    assert writer.can_convert('txt', 'azw3')
    assert writer.can_convert('html', 'azw3')
    assert writer.can_convert('md', 'azw3')
    assert not writer.can_convert('azw3', 'txt')

    reader = Azw3Converter()
    assert reader.can_convert('azw3', 'txt')
    assert reader.can_convert('azw3', 'html')
    assert reader.can_convert('azw', 'txt')
    assert not reader.can_convert('txt', 'azw3')


def _independent_parse_azw3(path):
    """Parse AZW3 file from raw binary - independent of our reader code.

    Validates PalmDB header, record list, PalmDOC header, MOBI v8 header,
    EXTH header, FDST record, and decompresses text. Returns extracted text.
    """
    with open(path, 'rb') as f:
        data = f.read()

    errors = []

    # PalmDB header
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

    # Record 0: PalmDOC header + MOBI v8 header
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
    assert mobi_header_len == 264, f"Expected KF8 header length 264, got {mobi_header_len}"
    encoding = struct.unpack('>I', data[r0+28:r0+32])[0]
    assert encoding == 65001, f"Expected UTF-8 encoding (65001), got {encoding}"
    version = struct.unpack('>I', data[r0+0x24:r0+0x28])[0]
    assert version == 8, f"Expected MOBI version 8, got {version}"

    # EXTH flags
    exth_flags = struct.unpack('>I', data[r0+16+112:r0+16+116])[0]
    has_exth = (exth_flags & 0x40) != 0

    # Extra data flags at offset 0xF0 (240) in record 0
    extra_data_flags = struct.unpack('>I', data[r0+240:r0+244])[0]

    # EXTH header validation
    if has_exth:
        exth_offset = r0 + 16 + mobi_header_len
        exth_magic = data[exth_offset:exth_offset+4]
        assert exth_magic == b'EXTH', f"EXTH flag set but no EXTH header at offset {exth_offset}"

    # FDST record validation
    fdst_index = struct.unpack('>I', data[r0+0xF8:r0+0xFC])[0]
    if fdst_index < num_records:
        fdst_offset = record_offsets[fdst_index]
        fdst_magic = data[fdst_offset:fdst_offset+4]
        assert fdst_magic == b'FDST', f"Expected FDST magic, got {fdst_magic}"
        fdst_entry_count = struct.unpack('>I', data[fdst_offset+8:fdst_offset+12])[0]
        assert fdst_entry_count == num_text_records, f"FDST count {fdst_entry_count} != text records {num_text_records}"

    # Decompress text records independently
    def palmdoc_decompress(compressed):
        result = []
        j = 0
        while j < len(compressed):
            c = compressed[j]
            j += 1
            if c == 0:
                result.append(0)
            elif 1 <= c <= 8:
                result.extend(compressed[j:j+c])
                j += c
            elif 0x09 <= c <= 0x7F:
                result.append(c)
            elif 0xC0 <= c:
                result.append(0x20)
                result.append(c ^ 0x80)
            else:
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
        return bytes(result)

    text_parts = []
    for i in range(1, num_text_records + 1):
        if i >= len(record_offsets):
            break
        rec_start = record_offsets[i]
        rec_end = record_offsets[i+1] if i+1 < len(record_offsets) else len(data)
        rec_data = data[rec_start:rec_end]
        if extra_data_flags & 1:
            trail_size = (rec_data[-1] & 0b11) + 1
            rec_data = rec_data[:-trail_size]
        if compression == 2:
            text_parts.append(palmdoc_decompress(rec_data))
        else:
            text_parts.append(rec_data)

    full_text = b''.join(text_parts)
    assert len(full_text) == text_length, f"Decompressed length {len(full_text)} != declared {text_length}"

    decoded = full_text.decode('utf-8')

    assert len(errors) == 0, f"Validation errors: {errors}"
    return decoded


def test_azw3_independent_validation():
    """Validate AZW3 output with an independent binary parser."""
    from convertext.converters.ebooks.azw3 import ToAzw3Converter
    converter = ToAzw3Converter()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        txt_file = tmppath / "test.txt"
        txt_file.write_text("Test Book\n\nA paragraph with some content.\n\nAnother paragraph.")
        azw3_file = tmppath / "test.azw3"
        converter.convert(txt_file, azw3_file, {})
        text = _independent_parse_azw3(azw3_file)
        assert "A paragraph with some content" in text
        assert "Another paragraph" in text


def test_azw3_header_field_offsets():
    """Validate critical AZW3/KF8 header fields are at correct byte offsets."""
    from convertext.converters.ebooks.azw3 import ToAzw3Converter
    converter = ToAzw3Converter()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        txt_file = tmppath / "test.txt"
        txt_file.write_text("Test\n\nContent.")
        azw3_file = tmppath / "test.azw3"
        converter.convert(txt_file, azw3_file, {})

        with open(azw3_file, 'rb') as f:
            f.seek(78)
            r0 = struct.unpack('>I', f.read(4))[0]
            f.seek(r0)
            data = f.read(280)

        # MOBI header length at 0x14 = 264
        assert struct.unpack('>I', data[0x14:0x18])[0] == 264
        # Version at 0x24 = 8
        assert struct.unpack('>I', data[0x24:0x28])[0] == 8
        # Min version at 0x68 = 8
        assert struct.unpack('>I', data[0x68:0x6C])[0] == 8
        # EXTH flags at 0x80 = 0x50
        assert struct.unpack('>I', data[0x80:0x84])[0] == 0x50
        # DRM offset at 0xA4 = no DRM
        assert struct.unpack('>I', data[0xA4:0xA8])[0] == 0xffffffff
        # DRM count at 0xA8 = no DRM
        assert struct.unpack('>I', data[0xA8:0xAC])[0] == 0xffffffff
        # First content record at 0xC0 = 1
        assert struct.unpack('>H', data[0xC0:0xC2])[0] == 1
        # Extra data flags at 0xF0 = 1
        assert struct.unpack('>I', data[0xF0:0xF4])[0] == 1
        # INDX at 0xF4 = none
        assert struct.unpack('>I', data[0xF4:0xF8])[0] == 0xffffffff
        # KF8 FDST index at 0xF8
        fdst_idx = struct.unpack('>I', data[0xF8:0xFC])[0]
        assert fdst_idx != 0xffffffff  # should point to FDST record
        # SKEL index at 0x100 = not used
        assert struct.unpack('>I', data[0x100:0x104])[0] == 0xffffffff
        # FLIS/FCIS counts at 0xCC and 0xD4 = 1
        assert struct.unpack('>I', data[0xCC:0xD0])[0] == 1
        assert struct.unpack('>I', data[0xD4:0xD8])[0] == 1


def test_azw3_large_content():
    """Validate AZW3 with content spanning multiple 4096-byte records."""
    from convertext.converters.ebooks.azw3 import ToAzw3Converter
    converter = ToAzw3Converter()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        txt_file = tmppath / "test.txt"
        paragraphs = [f"Paragraph number {i}. " + "Lorem ipsum dolor sit amet. " * 20 for i in range(30)]
        txt_file.write_text("Large Book\n\n" + "\n\n".join(paragraphs))
        azw3_file = tmppath / "test.azw3"
        converter.convert(txt_file, azw3_file, {})
        text = _independent_parse_azw3(azw3_file)
        assert "Paragraph number 0" in text
        assert "Paragraph number 29" in text
