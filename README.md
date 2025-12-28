# ConverText

[![PyPI version](https://badge.fury.io/py/convertext.svg)](https://pypi.org/project/convertext/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Downloads](https://img.shields.io/pypi/dm/convertext)](https://pypi.org/project/convertext/)

**Lightweight universal text converter** for documents and ebooks. Self-contained Python package with native format parsers.

Convert between all major document and ebook formats with a single terminal command or through a Python API. Get editable .txt, .md or HTML from PDF or ebook formats or make ebooks/PDFs/HTML/etc. from text formats. Batch convert multiple files and send them anywhere in the file system or to your ereader automatically.

## Supported Formats

**Bidirectional (Read & Write):**
PDF, DOCX, RTF, TXT, Markdown, HTML, EPUB, MOBI, FB2

**Read Only:**
DOC, ODT, AZW, AZW3

## Features

- 🚀 **Fast & Lightweight** - Self-contained Python package (~25MB)
- 📝 **Formatting Preservation** - Maintains bold, italic, tables, lists, colors across formats
- ⚙️ **Highly Configurable** - YAML config with priority merging
- 🎯 **Simple and Scriptable CLI & API** - Intuitive command-line interface and built-in Python functions
- 🔍 **Metadata Preservation** - Keeps author, title, and document properties

## Installation

```bash
pip install convertext
```

## Quick Start

### Command Line
```bash
# Convert PDF to EPUB
convertext book.pdf --format epub

# Convert Markdown to HTML and EPUB
convertext document.md --format html,epub

# Batch convert all Word docs to Markdown
convertext *.docx --format md

# Convert PDF to MOBI
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

# Markdown to HTML or PDF
convertext README.md --format html
convertext README.md --format pdf

# DOCX to Markdown
convertext report.docx --format md

# Any format to PDF
convertext story.txt --format pdf
convertext article.html --format pdf
convertext notes.md --format pdf

# Create Word documents from any format
convertext article.md --format docx
convertext notes.txt --format docx

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

ConverText supports flexible configuration through YAML files. You can set global defaults or create directory-specific configurations that automatically apply when converting files from those locations.

### How Configuration Works

When you convert a file, ConverText searches for configuration in this order (highest priority first):

1. **CLI arguments** - Flags you pass directly (e.g., `--output ~/Books/`)
2. **Directory config** - `convertext.yaml` in the file's directory or any parent directory
3. **User config** - `~/.convertext/config.yaml` (your global defaults)
4. **Built-in defaults** - Sensible defaults built into ConverText

### Directory-Based Configuration

Place a `convertext.yaml` file in any directory to configure conversions for files in that directory and its subdirectories. The configuration is automatically discovered - ConverText searches from the file's location up through parent directories.

**Example directory structure:**
```
~/Documents/books/
├── convertext.yaml          # Config for all books
├── fiction/
│   ├── convertext.yaml      # Override for fiction
│   └── novel.pdf
└── technical/
    └── manual.pdf           # Uses ~/Documents/books/convertext.yaml
```

When converting `fiction/novel.pdf`, ConverText uses `fiction/convertext.yaml`.
When converting `technical/manual.pdf`, ConverText uses `books/convertext.yaml` (inherited).

### Creating Configuration Files

**Initialize global config:**
```bash
convertext --init-config
```

**Create directory config:**
```bash
# Copy example file
cp convertext.yaml.example convertext.yaml

# Or create from scratch
cat > convertext.yaml << EOF
output:
  directory: ~/Documents/converted
  overwrite: false
documents:
  encoding: utf-8
EOF
```

### Configuration Example

See `convertext.yaml.example` for all available options. Here's a common configuration:

```yaml
# Output settings
output:
  directory: ~/Documents/converted
  filename_pattern: "{name}.{ext}"
  overwrite: false

# Document settings
documents:
  encoding: utf-8
```

### Key Configuration Options

| Section | Key | Default | Description |
|---------|-----|---------|-------------|
| `output.directory` | | `null` | Output directory (null = source dir) |
| `output.filename_pattern` | | `{name}.{ext}` | Output filename pattern |
| `output.overwrite` | | `false` | Overwrite existing files |
| `documents.encoding` | | `utf-8` | Text file encoding |

## CLI Reference

```
Usage: convertext [OPTIONS] [FILES]...

  ConverText - Lightweight universal text converter.

Options:
  -f, --format TEXT            Output format(s), comma-separated
  -o, --output PATH            Output directory
  -c, --config PATH            Custom config file
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

## Related Projects

Want to listen to your text files instead of reading them? Try [**audiobook-reader**](https://pypi.org/project/audiobook-reader/) - converts text, ebooks, and documents into natural-sounding audiobooks.

## 💝 Support This Project

If you find this tool helpful, please consider [sponsoring the project](https://github.com/sponsors/danielcorsano). I created and maintain this software alone as a public service, and donations help me improve it and develop requested features. If I get $99 of donations, I will use it to pay for the Apple developer program so I can make iOS versions of all my open source apps.

Your support makes a real difference in keeping this project active and growing. Thank you!

## Support

- 📖 [Documentation](https://github.com/danielcorsano/convertext)
- 🐛 [Issue Tracker](https://github.com/danielcorsano/convertext/issues)
- 💬 [Discussions](https://github.com/danielcorsano/convertext/discussions)

## License

MIT License - see [LICENSE](LICENSE) file for details.
