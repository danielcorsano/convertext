# ConverText

**Lightweight universal text converter** for documents and ebooks. Self-contained Python package with native format parsers.

[![PyPI version](https://badge.fury.io/py/convertext.svg)](https://pypi.org/project/convertext/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Convert between all major document and ebook formats with a single terminal command. Get editable .txt or .md from PDF or ebook formats or make ebooks/PDFs from editable text formats. Work on multiple files at the same time and send them anywhere in the file system instantly.

## Supported Formats

### Read (Input)
**Documents**: PDF, DOCX, DOC, ODT, RTF, TXT, Markdown, HTML
**Ebooks**: EPUB, MOBI, AZW (non-DRM), FB2

### Write (Output)
**Documents**: TXT, Markdown, HTML
**Ebooks**: EPUB, MOBI, FB2

**Native Python Implementations**:
- EPUB reader/writer
- MOBI reader/writer
- ODT reader
- FB2 reader/writer

## Features

- 🚀 **Fast & Lightweight** - Self-contained Python package < 15MB
- 🔄 **Batch Processing** - Convert multiple files at once with glob patterns
- 🔗 **Multi-Hop Conversion** - Automatically chains conversions (e.g., PDF → HTML → EPUB)
- ⚙️ **Highly Configurable** - YAML config with priority merging
- 🎯 **Simple CLI** - Intuitive command-line interface
- 🔍 **Metadata Preservation** - Keeps author, title, and document properties

## Installation

### Basic Installation
```bash
pip install convertext
```

### With Optional Format Support
```bash
# Comic book formats (CBZ, CBR, CB7)
pip install convertext[comics]

# All optional formats
pip install convertext[all]
```

**Note**: Core package includes native Python EPUB and MOBI readers/writers.


## Quick Start

### Command Line
```bash
# Convert a PDF to EPUB (multi-hop: PDF → TXT → EPUB)
convertext book.pdf --format epub

# Convert Markdown to HTML and EPUB
convertext document.md --format html,epub

# Batch convert all Word docs to Markdown
convertext *.docx --format md

# Convert PDF to Kindle format (multi-hop: PDF → TXT → MOBI)
convertext book.pdf --format mobi

# See all supported formats
convertext --list-formats
```

### Python / Jupyter
```python
import convertext

# Simple conversion
convertext.convert('book.pdf', 'epub')

# With options
convertext.convert('document.md', 'html', output='./out/', overwrite=True)

# Keep intermediate files (for debugging multi-hop)
convertext.convert('book.pdf', 'mobi', keep_intermediate=True)
```

## Usage Examples

### Single File Conversion

```bash
# PDF to text
convertext document.pdf --format txt

# Markdown to HTML
convertext README.md --format html

# DOCX to Markdown
convertext report.docx --format md

# Text to EPUB (creates an ebook)
convertext story.txt --format epub
```

### Multiple Output Formats

```bash
# Convert to multiple formats at once
convertext book.md --format html,epub,txt

# Output to specific directory
convertext document.pdf --format txt --output ~/Documents/converted/
```

### Batch Conversion

```bash
# Convert all Markdown files to HTML
convertext *.md --format html

# Convert multiple specific files
convertext chapter1.md chapter2.md chapter3.md --format epub

# Use with find for recursive conversion
find . -name "*.pdf" -exec convertext {} --format txt \;
```

### Advanced Options

```bash
# Overwrite existing files
convertext document.pdf --format txt --overwrite

# Verbose output with progress
convertext *.md --format html --verbose

# Use custom config file
convertext book.md --format epub --config my-config.yaml

# Set quality preset
convertext document.pdf --format epub --quality high
```

### Working with Ebooks

```bash
# Create EPUB from Markdown (with chapters)
convertext book.md --format epub

# Convert EPUB to Kindle format
convertext ebook.epub --format mobi

# Convert any document to multiple ebook formats
convertext document.pdf --format epub,mobi,fb2 --verbose

# Convert EPUB to text for reading
convertext ebook.epub --format txt

# Extract EPUB to HTML
convertext ebook.epub --format html
```

## Multi-Hop Conversion

ConverText automatically finds conversion paths for unsupported direct conversions:

```bash
# PDF → EPUB: Automatically converts via PDF → TXT → EPUB (2 hops)
convertext book.pdf --format epub --verbose
# Output: ✓ book.pdf → book.epub (PDF → TXT → EPUB, 2 hops)

# PDF → MOBI: Automatically converts via PDF → TXT → MOBI (2 hops)
convertext book.pdf --format mobi --verbose
# Output: ✓ book.pdf → book.mobi (PDF → TXT → MOBI, 2 hops)

# Keep intermediate files for debugging
convertext book.pdf --format epub --keep-intermediate
# Creates: book_intermediate.txt, book.epub
```

**How it works**: Uses BFS pathfinding to find the shortest conversion chain (max 3 hops). Intermediate files are automatically cleaned up unless `--keep-intermediate` is specified.

### Format Matrix

Run `convertext --list-formats` to see all direct conversions. Multi-hop enables any-to-any conversion between compatible formats.

## Configuration

### Create Config File

```bash
# Initialize user config (creates ~/.convertext/config.yaml)
convertext --init-config
```

### Configuration Locations (Priority Order)

1. **CLI arguments** (highest priority)
2. `./convertext.yaml` (project-level)
3. `~/.convertext/config.yaml` (user-level)
4. Built-in defaults (lowest priority)

### Example Configuration

**~/.convertext/config.yaml**:
```yaml
# Output settings
output:
  directory: ~/Documents/converted  # Where to save files
  filename_pattern: "{name}.{ext}"  # Output naming pattern
  overwrite: false                  # Protect existing files
  preserve_structure: true          # Keep folder hierarchy in batch mode

# Conversion quality
conversion:
  quality: high                     # low/medium/high
  preserve_metadata: true           # Keep author, title, etc.
  preserve_formatting: true         # Keep bold, italic, etc.
  preserve_images: true             # Include images in output

# Document-specific settings
documents:
  encoding: utf-8
  embed_fonts: true
  image_quality: 85                 # JPEG quality 1-100
  dpi: 300                          # For image extraction

  pdf:
    compression: true
    optimize: true

  docx:
    style_preservation: true
    embed_images: true

# Ebook settings
ebooks:
  epub:
    version: 3                      # EPUB 2 or 3
    split_chapters: true            # Auto-detect chapters
    toc_depth: 3                    # Table of contents depth
    cover_auto_detect: true         # Find cover image

# Performance
processing:
  parallel: true                    # Process multiple files in parallel
  max_workers: 4                    # CPU cores to use

# Logging
logging:
  level: INFO                       # DEBUG/INFO/WARNING/ERROR
  verbose: false
  show_progress: true               # Progress bars
```

### Config Key Reference

| Section | Key | Default | Description |
|---------|-----|---------|-------------|
| `output` | `directory` | `null` | Output directory (null = source dir) |
| `output` | `overwrite` | `false` | Overwrite existing files |
| `conversion` | `quality` | `medium` | Conversion quality preset |
| `conversion` | `preserve_metadata` | `true` | Keep document metadata |
| `documents` | `encoding` | `utf-8` | Text file encoding |
| `documents` | `dpi` | `300` | Image extraction DPI |
| `ebooks.epub` | `version` | `3` | EPUB version (2 or 3) |
| `processing` | `parallel` | `true` | Parallel processing |

## CLI Reference

```
Usage: convertext [OPTIONS] [FILES]...

  ConverText - Lightweight universal text converter.

Options:
  -f, --format TEXT            Output format(s), comma-separated
  -o, --output PATH            Output directory
  -c, --config PATH            Custom config file
  --quality [low|medium|high]  Conversion quality preset
  --overwrite                  Overwrite existing files
  --list-formats               List all supported formats
  --init-config                Initialize user config file
  --version                    Show version
  -v, --verbose                Verbose output (shows conversion hops)
  --keep-intermediate          Keep intermediate files in multi-hop conversions
  --help                       Show help message
```

## Use Cases

### 1. Documentation Workflow
```bash
# Write docs in Markdown, publish as HTML and PDF
convertext docs/*.md --format html
convertext docs/*.md --format pdf

# Generate EPUB documentation
convertext manual.md --format epub
```

### 2. Ebook Management
```bash
# Convert ebooks to text for reading on e-readers
convertext library/*.epub --format txt --output ~/ereader/

# Create EPUB from your writing
convertext novel.md --format epub
```

### 3. Archive Conversion
```bash
# Convert old Word documents to Markdown for version control
convertext archive/*.docx --format md --output ./converted/

# Extract text from PDFs
convertext reports/*.pdf --format txt
```

### 4. Blog Publishing
```bash
# Convert Markdown posts to HTML
convertext posts/*.md --format html --output ./public/

# Create downloadable EPUB versions
convertext posts/*.md --format epub --output ./public/downloads/
```

### 5. Research & Note-Taking
```bash
# Convert research PDFs to Markdown for notes
convertext papers/*.pdf --format md

# Create EPUB from notes for mobile reading
convertext notes/*.md --format epub
```

## Architecture

ConverText uses an intermediate `Document` format for conversions:

```
Input Format → Document (internal) → Output Format
```

This allows any-to-any conversions without N² converter implementations.

### Key Components

- **BaseConverter**: Abstract base for all format converters
- **Document**: Intermediate representation (metadata, content blocks, images)
- **ConverterRegistry**: Routes source→target format conversions with BFS pathfinding
- **ConversionEngine**: Orchestrates conversions and multi-hop chaining
- **Config**: Manages configuration with priority merging

### Native Implementations

ConverText implements lightweight native Python parsers for ebook formats:

- **EPUB**: Native Python reader/writer using zipfile + lxml
  - Reads: Parses OPF metadata and spine order
  - Writes: Generates EPUB 3 structure (container.xml, OPF, NCX, XHTML)

- **MOBI**: Native Python reader/writer using PalmDB format
  - Reads: PalmDB parser with PalmDOC decompression
  - Writes: PalmDB structure with optimized PalmDOC compression

- **ODT**: Native Python reader using zipfile + lxml

- **FB2**: Native Python reader/writer using lxml XML parser

## Development

### Setup
```bash
git clone https://github.com/danielcorsano/convertext.git
cd convertext
poetry install
```

### Run Tests
```bash
pytest
pytest -v                    # Verbose
pytest --cov                 # With coverage
```

### Code Quality
```bash
black .                      # Format code
ruff check convertext/       # Lint
mypy convertext/             # Type check
```

### Manual Testing
```bash
convertext --help
convertext test.md --format html --verbose
```

## Troubleshooting

### "No converter found for X → Y"
The requested conversion is not supported. Check supported formats with:
```bash
convertext --list-formats
```

### RTF Files Not Converting
RTF is now included in the core package. If you have issues, ensure striprtf is installed:
```bash
pip install --upgrade convertext
```

### "Target file already exists"
Use the `--overwrite` flag:
```bash
convertext file.pdf --format txt --overwrite
```

### Encoding Issues
Specify encoding in config:
```yaml
documents:
  encoding: utf-8  # or latin-1, cp1252, etc.
```

## Roadmap

**Completed (v0.1.0):**
- [x] Multi-hop conversions with BFS pathfinding
- [x] Native Python EPUB reader/writer
- [x] Native Python MOBI reader/writer
- [x] ODT (OpenDocument) support
- [x] FB2 (FictionBook) format
- [x] RTF format support

**Future Features:**
- [ ] Comic book formats (CBZ, CBR, CB7)
- [ ] Apple Pages format
- [ ] Custom CSS for HTML/EPUB output
- [ ] Image optimization options
- [ ] OCR support for scanned PDFs
- [ ] Parallel processing for batch conversions

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Submit a pull request

For development setup, see the Development section above.

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Credits

Created by [danielcorsano](https://github.com/danielcorsano)

Built with:
- [Click](https://click.palletsprojects.com/) - CLI framework
- [pypdf](https://pypdf.readthedocs.io/) - PDF handling
- [python-docx](https://python-docx.readthedocs.io/) - DOCX support
- [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/) - HTML parsing
- [markdown](https://python-markdown.github.io/) - Markdown processing

## Related Projects

Want to listen to your text files instead of reading them? Try [**audiobook-reader**](https://pypi.org/project/audiobook-reader/) - converts text, ebooks, and documents into natural-sounding audiobooks.

## Support

- 📖 [Documentation](https://github.com/danielcorsano/convertext)
- 🐛 [Issue Tracker](https://github.com/danielcorsano/convertext/issues)
- 💬 [Discussions](https://github.com/danielcorsano/convertext/discussions)
