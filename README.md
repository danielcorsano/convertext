# ConvertExt

**Lightweight universal text converter** for documents and ebooks with zero external dependencies for core formats.

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Convert between document and ebook formats with a single command. No Calibre, no heavy dependencies—just pure Python conversion.

## Features

- 🚀 **Fast & Lightweight** - Core package < 15MB, no system dependencies
- 📚 **Multiple Formats** - Documents (PDF, DOCX, HTML, MD, TXT, RTF) and Ebooks (EPUB)
- 🔄 **Batch Processing** - Convert multiple files at once with glob patterns
- ⚙️ **Highly Configurable** - YAML config with priority merging
- 🎯 **Simple CLI** - Intuitive command-line interface
- 🔍 **Metadata Preservation** - Keeps author, title, and document properties
- 📦 **Optional Extras** - Install only what you need

## Installation

### Basic Installation
```bash
pip install convertext
```

### With Optional Format Support
```bash
# RTF support
pip install convertext[rtf]

# All optional formats
pip install convertext[all]
```

### From Source
```bash
git clone https://github.com/danielcorsano/convertext.git
cd convertext
poetry install
```

## Quick Start

```bash
# Convert a PDF to EPUB
convertext book.pdf --format epub

# Convert Markdown to HTML and PDF
convertext document.md --format html,pdf

# Batch convert all Word docs to Markdown
convertext *.docx --format md

# See all supported formats
convertext --list-formats
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

### Working with EPUBs

```bash
# Create EPUB from Markdown (with chapters)
convertext book.md --format epub

# Convert EPUB to text for reading
convertext ebook.epub --format txt

# Extract EPUB to HTML
convertext ebook.epub --format html
```

## Supported Formats

### Input → Output Conversions

| Input Format | Output Formats | Notes |
|-------------|----------------|-------|
| **PDF** | TXT, HTML, MD | Extracts text and metadata |
| **DOCX/DOC** | TXT, HTML, MD | Preserves headings and structure |
| **RTF** | TXT, HTML, MD | Requires `striprtf` extra |
| **TXT** | HTML, MD, EPUB | Plain text with paragraph detection |
| **Markdown** | HTML, TXT, EPUB | Full markdown support |
| **HTML** | TXT, MD, EPUB | Extracts content from web pages |
| **EPUB** | TXT, HTML, MD | Extracts ebook content |

### Format Matrix

```
convertext --list-formats
```
Output:
```
Supported format conversions:

  DOC → HTML, MD, TXT
  DOCX → HTML, MD, TXT
  EPUB → HTML, MD, TXT
  HTM → EPUB, MD, TXT
  HTML → EPUB, MD, TXT
  MARKDOWN → HTML, TXT
  MD → EPUB, HTML, TXT
  PDF → HTML, MD, TXT
  RTF → HTML, MD, TXT
  TXT → EPUB, HTML, MD
```

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

  ConvertExt - Lightweight universal text converter.

Options:
  -f, --format TEXT            Output format(s), comma-separated
  -o, --output PATH            Output directory
  -c, --config PATH            Custom config file
  --quality [low|medium|high]  Conversion quality preset
  --overwrite                  Overwrite existing files
  --list-formats               List all supported formats
  --init-config                Initialize user config file
  --version                    Show version
  -v, --verbose                Verbose output
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

ConvertExt uses an intermediate `Document` format for conversions:

```
Input Format → Document (internal) → Output Format
```

This allows any-to-any conversions without N² converter implementations.

### Key Components

- **BaseConverter**: Abstract base for all format converters
- **Document**: Intermediate representation (metadata, content blocks, images)
- **ConverterRegistry**: Routes source→target format conversions
- **ConversionEngine**: Orchestrates the conversion process
- **Config**: Manages configuration with priority merging

## Development

### Setup
```bash
git clone https://github.com/danielcorsano/convertext.git
cd convertext
poetry install
```

### Run Tests
```bash
poetry run pytest
poetry run pytest -v                    # Verbose
poetry run pytest --cov                 # With coverage
```

### Code Quality
```bash
poetry run black .                      # Format code
poetry run ruff check convertext/       # Lint
poetry run mypy convertext/             # Type check
```

### Manual Testing
```bash
poetry run convertext --help
poetry run convertext test.md --format html --verbose
```

## Troubleshooting

### "No converter found for X → Y"
The requested conversion is not supported. Check supported formats with:
```bash
convertext --list-formats
```

### "RTF support requires striprtf package"
Install the RTF extra:
```bash
pip install convertext[rtf]
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

- [ ] ODT (OpenDocument) support
- [ ] MOBI/AZW3 ebook formats
- [ ] Comic book formats (CBZ, CBR)
- [ ] Apple Pages format
- [ ] Multi-hop conversions (e.g., PDF → HTML → EPUB)
- [ ] Custom CSS for HTML/EPUB output
- [ ] Image optimization options
- [ ] OCR support for scanned PDFs

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Submit a pull request

See [CLAUDE.md](CLAUDE.md) for development guidelines.

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Credits

Created by [danielcorsano](https://github.com/danielcorsano)

Built with:
- [Click](https://click.palletsprojects.com/) - CLI framework
- [pypdf](https://pypdf.readthedocs.io/) - PDF handling
- [python-docx](https://python-docx.readthedocs.io/) - DOCX support
- [ebooklib](https://github.com/aerkalov/ebooklib) - EPUB handling
- [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/) - HTML parsing
- [markdown](https://python-markdown.github.io/) - Markdown processing

## Support

- 📖 [Documentation](https://github.com/danielcorsano/convertext)
- 🐛 [Issue Tracker](https://github.com/danielcorsano/convertext/issues)
- 💬 [Discussions](https://github.com/danielcorsano/convertext/discussions)
