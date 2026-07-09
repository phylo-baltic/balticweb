#!/usr/bin/env python3
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

BIB_FILE = PROJECT_ROOT / "source" / "baltic-uses" / "baltic-uses.bib"
USES_DOCS = PROJECT_ROOT / "source" / "uses"

DETAIL_FIELDS = (
    "volume",
    "issue",
    "number",
    "pages",
)

PREPRINT_SOURCES = {
    "biorxiv",
    "medrxiv",
}


@dataclass
class BibRecord:
    key: str
    fields: dict[str, str]
    source_index: int

    @property
    def year(self) -> int:
        value = self.fields.get("year", "")
        match = re.search(r"\d{4}", value)
        return int(match.group(0)) if match else 0


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def clean_value(value: str) -> str:
    value = value.strip().strip(",")
    if len(value) >= 2 and value[0] == "{" and value[-1] == "}":
        value = value[1:-1]
    elif len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        value = value[1:-1]

    value = re.sub(r"\\(?:textit|textbf|emph)\s*\{+\s*([^{}]+?)\s*\}+", r"\1", value)

    replacements = {
        r"{\textgreater}": ">",
        r"{\textless}": "<",
        r"{\textasciitilde}": "~",
        r"{\textbackslash}": "\\",
        r"\&": "&",
        r"\%": "%",
        r"\$": "$",
        r"\#": "#",
        r"\_": "_",
        r"--": "-",
        r"~": " ",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)

    value = re.sub(r"[{}]", "", value)
    value = re.sub(r"\\(?:textit|textbf|emph)\s*([A-Za-z0-9_-]+)", r"\1", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" ,")


def split_records(text: str) -> list[str]:
    records: list[str] = []
    start: int | None = None
    brace_depth = 0

    for index, char in enumerate(text):
        if char == "@" and start is None:
            start = index
            brace_depth = 0
            continue

        if start is None:
            continue

        if char == "{":
            brace_depth += 1
        elif char == "}":
            brace_depth -= 1
            if brace_depth == 0:
                records.append(text[start:index + 1])
                start = None

    return records


def split_fields(body: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    index = 0

    while index < len(body):
        while index < len(body) and body[index] in " \n\t,":
            index += 1

        name_start = index
        while index < len(body) and re.match(r"[\w-]", body[index]):
            index += 1

        field_name = body[name_start:index].lower()
        if not field_name:
            break

        while index < len(body) and body[index].isspace():
            index += 1
        if index >= len(body) or body[index] != "=":
            break
        index += 1

        while index < len(body) and body[index].isspace():
            index += 1

        value_start = index
        if index < len(body) and body[index] in '{"':
            opener = body[index]
            closer = "}" if opener == "{" else '"'
            index += 1
            depth = 1 if opener == "{" else 0
            escaped = False

            while index < len(body):
                char = body[index]
                if opener == '"' and char == "\\" and not escaped:
                    escaped = True
                    index += 1
                    continue
                if opener == "{" and char == "{":
                    depth += 1
                elif opener == "{" and char == "}":
                    depth -= 1
                    if depth == 0:
                        index += 1
                        break
                elif opener == '"' and char == closer and not escaped:
                    index += 1
                    break
                escaped = False
                index += 1
        else:
            while index < len(body) and body[index] not in ",\n":
                index += 1

        fields[field_name] = clean_value(body[value_start:index])

        while index < len(body) and body[index] != ",":
            index += 1
        if index < len(body) and body[index] == ",":
            index += 1

    return fields


def parse_bibtex(path: Path) -> list[BibRecord]:
    text = path.read_text(encoding="utf-8")
    parsed: list[BibRecord] = []

    for source_index, raw_record in enumerate(split_records(text)):
        match = re.match(r"@\w+\s*\{\s*([^,]+),", raw_record, flags=re.S)
        if not match:
            continue

        key = match.group(1).strip()
        body = raw_record[match.end():].rstrip().rstrip("}")
        parsed.append(BibRecord(key=key, fields=split_fields(body), source_index=source_index))

    return parsed


def format_authors(value: str) -> str:
    authors = [author.strip() for author in value.split(" and ") if author.strip()]
    formatted: list[str] = []

    for author in authors:
        if "," in author:
            family, given = [part.strip() for part in author.split(",", 1)]
            formatted.append(f"{family} {format_initials(given)}".strip())
        else:
            formatted.append(author)

    return ", ".join(formatted)


def format_initials(given_names: str) -> str:
    initials = []
    for token in re.split(r"[\s.-]+", given_names):
        token = token.strip()
        if token:
            initials.append(token[0].upper())
    return "".join(initials)


def normalized_doi(record: BibRecord) -> str:
    doi = record.fields.get("doi", "")
    return re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi, flags=re.I)


def is_preprint_source(source: str) -> bool:
    normalized = source.strip().lower()
    return normalized in PREPRINT_SOURCES or normalized.endswith("rxiv")


def doi_paper_id(record: BibRecord) -> str:
    doi = normalized_doi(record)
    return doi.rstrip("/").split("/")[-1] if doi else ""


def title_link(record: BibRecord) -> str:
    title = record.fields.get("title", "Untitled")
    doi = normalized_doi(record)
    url = record.fields.get("url", "")

    href = f"https://doi.org/{doi}" if doi else url
    if href:
        return f'<a href="{html.escape(href, quote=True)}">{html.escape(title)}</a>'
    return html.escape(title)


def sentence_separator(value: str) -> str:
    return " " if value.rstrip().endswith((".", "?", "!")) else ". "


def citation_html(record: BibRecord) -> str:
    fields = record.fields
    parts: list[str] = []

    authors = fields.get("author", "")
    if authors:
        parts.append(html.escape(format_authors(authors)))

    year = fields.get("year", "")
    if year:
        parts.append(html.escape(year))

    citation = ", ".join(parts)
    if citation:
        citation += ". "

    title = fields.get("title", "Untitled")
    citation += title_link(record)

    journal = fields.get("journal", "")
    publisher = fields.get("publisher", "")
    source = journal
    if not source and is_preprint_source(publisher):
        source = publisher
    if source:
        citation += f"{sentence_separator(title)}<em>{html.escape(source)}</em>"

    details = []
    for field in DETAIL_FIELDS:
        value = fields.get(field, "").strip(" ,")
        if value:
            details.append(html.escape(value))
    if is_preprint_source(source):
        paper_id = doi_paper_id(record)
        if paper_id:
            details.append(html.escape(paper_id))
    if details:
        citation += "," + ",".join(details)

    citation = citation.rstrip()
    if not citation.endswith("."):
        citation += "."

    return citation


def write_uses_page(records: list[BibRecord]) -> None:
    ensure_dir(USES_DOCS)

    ordered = sorted(records, key=lambda record: (record.year, record.source_index))
    newest_first = list(reversed(ordered))
    total = len(newest_first)

    items = "\n".join(
        f'<li value="{total - index}">{citation_html(record)}</li>'
        for index, record in enumerate(newest_first)
    )

    rst = f"""\
As seen in
==========

.. raw:: html

   <ol class="uses-list">
{indent_html(items, 6)}
   </ol>
"""
    (USES_DOCS / "index.rst").write_text(rst, encoding="utf-8")


def indent_html(text: str, spaces: int) -> str:
    pad = " " * spaces
    return "\n".join(pad + line if line.strip() else line for line in text.splitlines())


def main() -> None:
    if not BIB_FILE.exists():
        raise SystemExit(f"Missing bibliography file: {BIB_FILE}")

    records = parse_bibtex(BIB_FILE)
    write_uses_page(records)
    print(f"Generated {len(records)} use records.")
    print(f"- Landing: {USES_DOCS / 'index.rst'}")


if __name__ == "__main__":
    main()
