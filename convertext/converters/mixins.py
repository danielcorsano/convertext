"""Mixin classes providing common output format writers with enhanced Document support."""

from pathlib import Path
from typing import Dict, Any
from convertext.converters.base import Document
from convertext.converters.utils import escape_html


class TextWriterMixin:
    """Provides enhanced _write_txt() with formatting representation."""

    def _write_txt(self, doc: Document, path: Path, include_metadata: bool = True) -> bool:
        """Write Document to plain text with basic formatting markers."""
        with open(path, "w", encoding="utf-8") as f:
            if include_metadata and doc.metadata.get("title"):
                f.write(doc.metadata["title"] + "\n")
                f.write("=" * len(doc.metadata["title"]) + "\n\n")
            if include_metadata and doc.metadata.get("author"):
                f.write(f"By: {doc.metadata['author']}\n\n")

            for block in doc.content:
                if block["type"] in ["text", "paragraph"]:
                    f.write(block["data"] + "\n\n")

                elif block["type"] == "heading":
                    f.write("\n" + block["data"].upper() + "\n")
                    f.write("-" * len(block["data"]) + "\n\n")

                elif block["type"] == "run":
                    text = block["text"]
                    if block.get("bold"):
                        text = f"**{text}**"
                    if block.get("italic"):
                        text = f"*{text}*"
                    f.write(text)

                elif block["type"] == "table":
                    headers = block.get("headers", [])
                    rows = block["rows"]

                    if headers:
                        f.write(" | ".join(headers) + "\n")
                        f.write("-" * (len(" | ".join(headers))) + "\n")

                    for row in rows:
                        f.write(" | ".join(str(cell) for cell in row) + "\n")
                    f.write("\n")

                elif block["type"] == "list":
                    for i, item in enumerate(block["items"], 1):
                        if block.get("ordered"):
                            f.write(f"{i}. {item}\n")
                        else:
                            f.write(f"• {item}\n")
                    f.write("\n")

                elif block["type"] == "link":
                    f.write(f"{block['text']} ({block['url']})\n")

                elif block["type"] == "image":
                    f.write(f"[Image: {block['name']}]\n")

        return True


class HtmlWriterMixin:
    """Provides enhanced _write_html() with full formatting support."""

    def _write_html(self, doc: Document, path: Path) -> bool:
        """Write Document to HTML with styles, tables, images, links."""
        html_parts = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            '<meta charset="utf-8">',
        ]

        if doc.metadata.get("title"):
            html_parts.append(
                f"<title>{escape_html(doc.metadata['title'])}</title>"
            )
        else:
            html_parts.append("<title>Document</title>")

        html_parts.append("</head>")
        html_parts.append("<body>")

        if doc.metadata.get("title"):
            html_parts.append(f"<h1>{escape_html(doc.metadata['title'])}</h1>")
        if doc.metadata.get("author"):
            html_parts.append(
                f"<p><em>By {escape_html(doc.metadata['author'])}</em></p>"
            )

        for block in doc.content:
            if block["type"] == "paragraph":
                html_parts.append(f"<p>{escape_html(block['data'])}</p>")

            elif block["type"] == "heading":
                level = min(block["level"], 6)
                html_parts.append(
                    f"<h{level}>{escape_html(block['data'])}</h{level}>"
                )

            elif block["type"] == "text":
                html_parts.append(f"<p>{escape_html(block['data'])}</p>")

            elif block["type"] == "run":
                span_content = escape_html(block["text"])
                styles = []

                if block.get("bold"):
                    span_content = f"<strong>{span_content}</strong>"
                if block.get("italic"):
                    span_content = f"<em>{span_content}</em>"
                if block.get("underline"):
                    styles.append("text-decoration: underline")

                if block.get("color"):
                    styles.append(f"color: {block['color']}")
                if block.get("font"):
                    styles.append(f"font-family: {block['font']}")
                if block.get("size"):
                    styles.append(f"font-size: {block['size']}pt")

                if styles:
                    style_attr = "; ".join(styles)
                    span_content = f'<span style="{style_attr}">{span_content}</span>'

                html_parts.append(f"<p>{span_content}</p>")

            elif block["type"] == "table":
                html_parts.append('<table border="1">')

                if block.get("headers"):
                    html_parts.append("<thead><tr>")
                    for header in block["headers"]:
                        html_parts.append(f"<th>{escape_html(str(header))}</th>")
                    html_parts.append("</tr></thead>")

                html_parts.append("<tbody>")
                for row in block["rows"]:
                    html_parts.append("<tr>")
                    for cell in row:
                        html_parts.append(f"<td>{escape_html(str(cell))}</td>")
                    html_parts.append("</tr>")
                html_parts.append("</tbody>")
                html_parts.append("</table>")

            elif block["type"] == "list":
                tag = "ol" if block.get("ordered") else "ul"
                html_parts.append(f"<{tag}>")
                for item in block["items"]:
                    html_parts.append(f"<li>{escape_html(item)}</li>")
                html_parts.append(f"</{tag}>")

            elif block["type"] == "link":
                html_parts.append(
                    f'<p><a href="{escape_html(block["url"])}">'
                    f'{escape_html(block["text"])}</a></p>'
                )

            elif block["type"] == "image":
                img_name = block["name"]
                if img_name in doc.images:
                    html_parts.append(
                        f'<img src="data:image/{doc.images[img_name]["format"]};'
                        f'base64,..." alt="{escape_html(img_name)}">'
                    )

        html_parts.append("</body>")
        html_parts.append("</html>")

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(html_parts))

        return True


class MarkdownWriterMixin:
    """Provides enhanced _write_md() with tables and formatting."""

    def _write_md(self, doc: Document, path: Path) -> bool:
        """Write Document to Markdown with tables, lists, images."""
        with open(path, "w", encoding="utf-8") as f:
            if doc.metadata.get("title"):
                f.write(f"# {doc.metadata['title']}\n\n")
            if doc.metadata.get("author"):
                f.write(f"**Author:** {doc.metadata['author']}\n\n")

            for block in doc.content:
                if block["type"] == "paragraph":
                    f.write(block["data"] + "\n\n")

                elif block["type"] == "text":
                    f.write(block["data"] + "\n\n")

                elif block["type"] == "heading":
                    f.write("#" * block["level"] + " " + block["data"] + "\n\n")

                elif block["type"] == "run":
                    text = block["text"]
                    if block.get("bold"):
                        text = f"**{text}**"
                    if block.get("italic"):
                        text = f"*{text}*"
                    if block.get("underline"):
                        text = f"<u>{text}</u>"
                    f.write(text)

                elif block["type"] == "table":
                    headers = block.get("headers", [])
                    rows = block["rows"]

                    if headers:
                        f.write("| " + " | ".join(headers) + " |\n")
                        f.write("|" + "|".join([" --- "] * len(headers)) + "|\n")
                    elif rows:
                        first_row = rows[0]
                        f.write("| " + " | ".join(str(cell) for cell in first_row) + " |\n")
                        f.write("|" + "|".join([" --- "] * len(first_row)) + "|\n")
                        rows = rows[1:]

                    for row in rows:
                        f.write("| " + " | ".join(str(cell) for cell in row) + " |\n")
                    f.write("\n")

                elif block["type"] == "list":
                    for i, item in enumerate(block["items"], 1):
                        if block.get("ordered"):
                            f.write(f"{i}. {item}\n")
                        else:
                            f.write(f"- {item}\n")
                    f.write("\n")

                elif block["type"] == "link":
                    f.write(f"[{block['text']}]({block['url']})\n\n")

                elif block["type"] == "image":
                    f.write(f"![{block['name']}]({block['name']})\n\n")

        return True
