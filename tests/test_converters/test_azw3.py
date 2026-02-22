"""Tests for AZW3/KF8 format converter."""

import tempfile
from pathlib import Path
import struct


def test_azw3_write_basic():
    """TXT to AZW3 produces non-empty file."""
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
    """PalmDB header has BOOK/MOBI type/creator."""
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
            assert num_records >= 10  # KF8 needs: rec0+text+chunk(3)+skel(2)+fdst+flis+fcis+eof


def test_azw3_kf8_header():
    """Record 0 has MOBI v8 header with 264-byte length and UTF-8 encoding."""
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
            header_len = struct.unpack('>I', f.read(4))[0]
            assert header_len == 264  # KF8
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
    """PalmDOC compression roundtrip with ASCII and UTF-8."""
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
    """TXT -> AZW3 -> TXT roundtrip preserves content."""
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
    """HTML -> AZW3 -> HTML roundtrip preserves content."""
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
    """Format support declarations."""
    from convertext.converters.ebooks.azw3 import ToAzw3Converter, Azw3Converter

    writer = ToAzw3Converter()
    assert writer.can_convert('txt', 'azw3')
    assert writer.can_convert('html', 'azw3')
    assert writer.can_convert('md', 'azw3')
    assert writer.can_convert('epub', 'azw3')
    assert writer.can_convert('txt', 'mobi')
    assert not writer.can_convert('azw3', 'txt')

    reader = Azw3Converter()
    assert reader.can_convert('azw3', 'txt')
    assert reader.can_convert('azw3', 'html')
    assert reader.can_convert('azw', 'txt')
    assert reader.can_convert('mobi', 'txt')
    assert not reader.can_convert('txt', 'azw3')


def _independent_parse_kf8(path):
    """Parse KF8/AZW3 file from raw binary - validates all KF8 structures."""
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
    assert num_records >= 10, f"KF8 needs at least 10 records, got {num_records}"

    record_offsets = []
    for i in range(num_records):
        base = 78 + i * 8
        offset = struct.unpack('>I', data[base:base+4])[0]
        record_offsets.append(offset)

    for i, off in enumerate(record_offsets):
        assert off < len(data), f"Record {i} offset {off} beyond file size {len(data)}"
        if i > 0:
            assert off > record_offsets[i-1], f"Record {i} offset not ascending"

    # Record 0 - PalmDOC header
    r0 = record_offsets[0]
    compression = struct.unpack('>H', data[r0:r0+2])[0]
    assert compression in (1, 2), f"Unknown compression type {compression}"
    text_length = struct.unpack('>I', data[r0+4:r0+8])[0]
    num_text_records = struct.unpack('>H', data[r0+8:r0+10])[0]
    record_size = struct.unpack('>H', data[r0+10:r0+12])[0]
    assert record_size == 4096, f"Expected record size 4096, got {record_size}"

    # MOBI header - KF8 specific
    mobi_magic = data[r0+16:r0+20]
    assert mobi_magic == b'MOBI', "Missing MOBI magic"
    mobi_header_len = struct.unpack('>I', data[r0+20:r0+24])[0]
    assert mobi_header_len == 264, f"Expected KF8 header length 264, got {mobi_header_len}"
    encoding = struct.unpack('>I', data[r0+28:r0+32])[0]
    assert encoding == 65001, f"Expected UTF-8 (65001), got {encoding}"
    version = struct.unpack('>I', data[r0+0x24:r0+0x28])[0]
    assert version == 8, f"Expected KF8 version 8, got {version}"
    min_ver = struct.unpack('>I', data[r0+0x68:r0+0x6C])[0]
    assert min_ver == 8, f"Expected min version 8, got {min_ver}"

    # KF8-specific field validation
    fdst_idx = struct.unpack('>I', data[r0+0xC0:r0+0xC4])[0]
    fdst_count = struct.unpack('>I', data[r0+0xC4:r0+0xC8])[0]
    assert fdst_idx < num_records, f"FDST index {fdst_idx} out of range"
    assert fdst_count >= 1, "FDST count must be >= 1"

    chunk_idx = struct.unpack('>I', data[r0+0xF8:r0+0xFC])[0]
    skel_idx = struct.unpack('>I', data[r0+0xFC:r0+0x100])[0]
    assert chunk_idx < num_records, f"Chunk index {chunk_idx} out of range"
    assert skel_idx < num_records, f"Skeleton index {skel_idx} out of range"

    extra_data_flags = struct.unpack('>I', data[r0+0xF0:r0+0xF4])[0]

    # EXTH validation
    exth_flags = struct.unpack('>I', data[r0+0x80:r0+0x84])[0]
    has_exth = (exth_flags & 0x40) != 0
    if has_exth:
        exth_offset = r0 + 16 + mobi_header_len
        exth_magic = data[exth_offset:exth_offset+4]
        assert exth_magic == b'EXTH', "EXTH flag set but no EXTH header"

    # Validate FDST record
    fdst_off = record_offsets[fdst_idx]
    assert data[fdst_off:fdst_off+4] == b'FDST', "FDST record missing FDST magic"
    fdst_offset_val = struct.unpack('>I', data[fdst_off+4:fdst_off+8])[0]
    assert fdst_offset_val == 12, f"FDST offset should be 12, got {fdst_offset_val}"

    # Validate chunk INDX header record
    chunk_off = record_offsets[chunk_idx]
    assert data[chunk_off:chunk_off+4] == b'INDX', "Chunk INDX missing INDX magic"
    chunk_hdr_type = struct.unpack('>I', data[chunk_off+12:chunk_off+16])[0]
    assert chunk_hdr_type == 0, f"Chunk header type should be 0, got {chunk_hdr_type}"
    chunk_indx_type = struct.unpack('>I', data[chunk_off+16:chunk_off+20])[0]
    assert chunk_indx_type == 2, f"Chunk INDX type should be 2, got {chunk_indx_type}"

    # Validate chunk INDX data record
    chunk_data_off = record_offsets[chunk_idx + 1]
    assert data[chunk_data_off:chunk_data_off+4] == b'INDX', "Chunk data missing INDX magic"
    chunk_data_type = struct.unpack('>I', data[chunk_data_off+12:chunk_data_off+16])[0]
    assert chunk_data_type == 1, f"Chunk data type should be 1, got {chunk_data_type}"

    # Validate skeleton INDX header record
    skel_off = record_offsets[skel_idx]
    assert data[skel_off:skel_off+4] == b'INDX', "Skeleton INDX missing INDX magic"
    skel_hdr_type = struct.unpack('>I', data[skel_off+12:skel_off+16])[0]
    assert skel_hdr_type == 0, f"Skel header type should be 0, got {skel_hdr_type}"

    # Validate skeleton INDX data record
    skel_data_off = record_offsets[skel_idx + 1]
    assert data[skel_data_off:skel_data_off+4] == b'INDX', "Skel data missing INDX magic"
    skel_data_type = struct.unpack('>I', data[skel_data_off+12:skel_data_off+16])[0]
    assert skel_data_type == 1, f"Skel data type should be 1, got {skel_data_type}"

    # Validate TAGX in chunk INDX header
    tagx_offset = struct.unpack('>I', data[chunk_off+180:chunk_off+184])[0]
    tagx_pos = chunk_off + tagx_offset
    assert data[tagx_pos:tagx_pos+4] == b'TAGX', "Missing TAGX in chunk INDX header"

    # Validate TAGX in skeleton INDX header
    tagx_offset_s = struct.unpack('>I', data[skel_off+180:skel_off+184])[0]
    tagx_pos_s = skel_off + tagx_offset_s
    assert data[tagx_pos_s:tagx_pos_s+4] == b'TAGX', "Missing TAGX in skel INDX header"

    # Decompress text records
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
        if compression == 2:
            text_parts.append(palmdoc_decompress(rec_data))
        else:
            text_parts.append(rec_data)

    full_text = b''.join(text_parts)
    assert len(full_text) == text_length, f"Decompressed {len(full_text)} != declared {text_length}"

    decoded = full_text.decode('utf-8')
    assert len(errors) == 0, f"Validation errors: {errors}"
    return decoded


def test_azw3_kf8_validation():
    """Validate output with independent KF8 binary parser."""
    from convertext.converters.ebooks.azw3 import ToAzw3Converter
    converter = ToAzw3Converter()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        txt_file = tmppath / "test.txt"
        txt_file.write_text("Test Book\n\nA paragraph with some content.\n\nAnother paragraph.")
        azw3_file = tmppath / "test.azw3"
        converter.convert(txt_file, azw3_file, {})
        text = _independent_parse_kf8(azw3_file)
        assert "A paragraph with some content" in text
        assert "Another paragraph" in text


def test_azw3_kf8_header_offsets():
    """Validate critical KF8 header fields at correct byte offsets."""
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
            data = f.read(300)

        # MOBI header length at 0x14 = 264
        assert struct.unpack('>I', data[0x14:0x18])[0] == 264
        # Version at 0x24 = 8
        assert struct.unpack('>I', data[0x24:0x28])[0] == 8
        # Min version at 0x68 = 8
        assert struct.unpack('>I', data[0x68:0x6C])[0] == 8
        # EXTH flags at 0x80 = 0x50
        assert struct.unpack('>I', data[0x80:0x84])[0] == 0x50
        # DRM offset at 0xA8 = no DRM
        assert struct.unpack('>I', data[0xA8:0xAC])[0] == 0xFFFFFFFF
        # FDST at 0xC0 (should be valid record index)
        fdst_idx = struct.unpack('>I', data[0xC0:0xC4])[0]
        assert fdst_idx != 0xFFFFFFFF, "FDST index should be set for KF8"
        # FDST count at 0xC4
        assert struct.unpack('>I', data[0xC4:0xC8])[0] == 1
        # Extra data flags at 0xF0 = 0 (no trailing bytes)
        assert struct.unpack('>I', data[0xF0:0xF4])[0] == 0
        # Chunk index at 0xF8 (should be valid)
        chunk_idx = struct.unpack('>I', data[0xF8:0xFC])[0]
        assert chunk_idx != 0xFFFFFFFF, "Chunk index should be set for KF8"
        # Skel index at 0xFC (should be valid)
        skel_idx = struct.unpack('>I', data[0xFC:0x100])[0]
        assert skel_idx != 0xFFFFFFFF, "Skeleton index should be set for KF8"
        # EXTH header follows MOBI header at offset 16 + 264 = 280
        assert data[280:284] == b'EXTH'


def test_azw3_large_content():
    """Content spanning multiple 4096-byte records."""
    from convertext.converters.ebooks.azw3 import ToAzw3Converter
    converter = ToAzw3Converter()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        txt_file = tmppath / "test.txt"
        paragraphs = [f"Paragraph number {i}. " + "Lorem ipsum dolor sit amet. " * 20 for i in range(30)]
        txt_file.write_text("Large Book\n\n" + "\n\n".join(paragraphs))
        azw3_file = tmppath / "test.azw3"
        converter.convert(txt_file, azw3_file, {})
        text = _independent_parse_kf8(azw3_file)
        assert "Paragraph number 0" in text
        assert "Paragraph number 29" in text


def test_mobi_output_format():
    """Can also output .mobi files."""
    from convertext.converters.ebooks.azw3 import ToAzw3Converter
    converter = ToAzw3Converter()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        txt_file = tmppath / "test.txt"
        txt_file.write_text("Test\n\nContent paragraph.")
        mobi_file = tmppath / "test.mobi"
        result = converter.convert(txt_file, mobi_file, {})
        assert result is True
        text = _independent_parse_kf8(mobi_file)
        assert "Content paragraph" in text


def test_utf8_boundary_splitting():
    """Text records split at UTF-8 character boundaries."""
    from convertext.converters.ebooks.azw3 import _split_text_records

    text = b'A' * 4094 + '\u00e9'.encode('utf-8')  # e-acute = 2 bytes, total 4096
    text += b'B' * 100
    records = _split_text_records(text)
    assert len(records) == 2
    assert len(records[0]) == 4096
    for rec in records:
        rec.decode('utf-8')

    text2 = b'A' * 4095 + '\u2603'.encode('utf-8')  # snowman = 3 bytes
    records2 = _split_text_records(text2)
    for rec in records2:
        rec.decode('utf-8')


def test_kf8_skeleton_content():
    """KF8 text stream contains XHTML skeleton with aid attributes."""
    from convertext.converters.ebooks.azw3 import ToAzw3Converter
    converter = ToAzw3Converter()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        txt_file = tmppath / "test.txt"
        txt_file.write_text("Test Book\n\nSome content here.")
        azw3_file = tmppath / "test.azw3"
        converter.convert(txt_file, azw3_file, {})
        text = _independent_parse_kf8(azw3_file)
        assert 'aid="0000"' in text
        assert '<body' in text
        assert 'Some content here' in text
        assert '<?xml version="1.0"' in text
        assert 'xmlns="http://www.w3.org/1999/xhtml"' in text


def test_kf8_xhtml_skeleton():
    """First text record decompresses to valid XHTML with XML declaration and xmlns."""
    from convertext.converters.ebooks.azw3 import ToAzw3Converter, _palmdoc_compress
    import struct as _struct

    converter = ToAzw3Converter()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        txt_file = tmppath / "test.txt"
        txt_file.write_text("My Book\n\nContent paragraph.")
        azw3_file = tmppath / "test.azw3"
        converter.convert(txt_file, azw3_file, {})

        with open(azw3_file, 'rb') as f:
            data = f.read()

        num_records = _struct.unpack('>H', data[76:78])[0]
        rec_offsets = [_struct.unpack('>I', data[78 + i*8: 82 + i*8])[0] for i in range(num_records)]

        # Read first text record (record index 1)
        rec_start = rec_offsets[1]
        rec_end = rec_offsets[2]
        rec_data = data[rec_start:rec_end]

        # Decompress PalmDOC
        from convertext.converters.ebooks.azw3 import Azw3Converter
        decompressed = Azw3Converter()._palmdoc_decompress(rec_data).decode('utf-8')

        assert decompressed.startswith('<?xml version="1.0"')
        assert 'xmlns="http://www.w3.org/1999/xhtml"' in decompressed


def test_kf8_xhtml_renders():
    """Decompressed skeleton contains body element with correct aid attribute."""
    from convertext.converters.ebooks.azw3 import ToAzw3Converter, Azw3Converter
    import struct as _struct

    converter = ToAzw3Converter()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        txt_file = tmppath / "test.txt"
        txt_file.write_text("Title\n\nBody text.")
        azw3_file = tmppath / "test.azw3"
        converter.convert(txt_file, azw3_file, {})

        with open(azw3_file, 'rb') as f:
            data = f.read()

        num_records = _struct.unpack('>H', data[76:78])[0]
        rec_offsets = [_struct.unpack('>I', data[78 + i*8: 82 + i*8])[0] for i in range(num_records)]

        rec_data = data[rec_offsets[1]:rec_offsets[2]]
        decompressed = Azw3Converter()._palmdoc_decompress(rec_data).decode('utf-8')

        # Extract just the skeleton (up to and including </html>)
        html_end = decompressed.index('</html>') + len('</html>')
        skeleton_xml = decompressed[:html_end]

        from xml.etree import ElementTree as ET
        root = ET.fromstring(skeleton_xml)
        ns = {'x': 'http://www.w3.org/1999/xhtml'}
        body = root.find('x:body', ns)
        assert body is not None, "body element not found in XHTML skeleton"
        assert body.get('aid') == '0000', f"Expected aid='0000', got {body.get('aid')}"


def test_kf8_vwi_encoding():
    """VWI forward encoding produces correct bytes."""
    from convertext.converters.ebooks.azw3 import _encint

    assert _encint(0) == b'\x80'
    assert _encint(1) == b'\x81'
    assert _encint(127) == b'\xFF'
    assert _encint(128) == b'\x01\x80'
    assert _encint(300) == b'\x02\xAC'


def test_kf8_base32():
    """Base-32 encoding for aid attributes."""
    from convertext.converters.ebooks.azw3 import _to_base32

    assert _to_base32(0) == '0000'
    assert _to_base32(1) == '0001'
    assert _to_base32(31) == '000V'
    assert _to_base32(32) == '0010'


def test_kf8_indx_structure():
    """INDX records have correct internal structure."""
    from convertext.converters.ebooks.azw3 import _build_skel_indx, _build_chunk_indx, ChunkInfo

    chunks = [ChunkInfo(0, 100, 100, 50), ChunkInfo(150, 100, 250, 60)]

    skel_recs = _build_skel_indx(chunks)
    assert len(skel_recs) == 2  # header + data

    # Skeleton header record
    assert skel_recs[0][:4] == b'INDX'
    hdr_type = struct.unpack('>I', skel_recs[0][12:16])[0]
    assert hdr_type == 0  # header record

    # Skeleton data record
    assert skel_recs[1][:4] == b'INDX'
    data_type = struct.unpack('>I', skel_recs[1][12:16])[0]
    assert data_type == 1  # data record

    chunk_recs = _build_chunk_indx(chunks, 310)
    assert len(chunk_recs) == 3  # header + data + cncx

    # Chunk header
    assert chunk_recs[0][:4] == b'INDX'
    # Chunk data
    assert chunk_recs[1][:4] == b'INDX'
    # CNCX should contain selector strings
    cncx_data = chunk_recs[2]
    assert b"P-//*[@aid='0000']" in cncx_data


def test_kf8_fdst_record():
    """FDST record has correct structure."""
    from convertext.converters.ebooks.azw3 import _build_fdst

    fdst = _build_fdst(5000)
    assert fdst[:4] == b'FDST'
    offset = struct.unpack('>I', fdst[4:8])[0]
    assert offset == 12
    count = struct.unpack('>I', fdst[8:12])[0]
    assert count == 1
    start = struct.unpack('>I', fdst[12:16])[0]
    end = struct.unpack('>I', fdst[16:20])[0]
    assert start == 0
    assert end == 5000
