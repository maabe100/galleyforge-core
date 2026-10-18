import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Section:
    title: str
    content: str


@dataclass
class Manuscript:
    title: str
    authors: Optional[str]
    sections: List[Section] = field(default_factory=list)


def _is_heading(line: str) -> bool:
    """Detects if a line looks like a section heading."""
    stripped = line.strip()

    if not stripped:
        return False

    # Markdown-style heading: "## Methods"
    if stripped.startswith("#"):
        return True

    # Fully upper-case headings like "INTRODUCTION"
    if stripped.isupper() and len(stripped.split()) <= 5:
        return True

    return False


def parse_manuscript_text(text: str) -> Manuscript:
    """
    Very simple manuscript parser.

    Assumptions:
    - First non-empty line: title
    - Second non-empty line: authors (optional)
    - Remaining text: sections, recognized by headings
    """
    lines = [l.rstrip("\n") for l in text.splitlines()]

    # Titel / Autoren extrahieren
    non_empty = [l for l in lines if l.strip()]
    title = non_empty[0] if non_empty else "Untitled manuscript"
    authors = non_empty[1] if len(non_empty) > 1 else None

    # Restzeilen nach den ersten beiden nicht-leeren
    # wir laufen einmal durch und merken, wann wir den Titel und die Autoren "verbraucht" haben
    used = 0
    for l in lines:
        if l.strip():
            used += 1
        if used == 2:
            break

    body_lines = lines[lines.index(non_empty[1]) + 1 :] if len(non_empty) > 1 else lines[1:]

    sections: List[Section] = []
    current_title = "Body"
    current_content: List[str] = []

    for line in body_lines:
        if _is_heading(line):
            # alte Section speichern
            if current_content:
                sections.append(
                    Section(title=current_title, content="\n".join(current_content).strip())
                )
                current_content = []

            # Heading-Zeichen entfernen, falls Markdown
            heading = line.lstrip("#").strip()
            current_title = heading or "Section"
        else:
            current_content.append(line)

    if current_content:
        sections.append(
            Section(title=current_title, content="\n".join(current_content).strip())
        )

    return Manuscript(title=title, authors=authors, sections=sections)


def parse_manuscript_file(path: str) -> Manuscript:
    """Convenience: read a .txt file and parse it."""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    return parse_manuscript_text(text)


def manuscript_to_schema_v1(manuscript: Manuscript, manuscript_id: str = "TXT001") -> dict:
    """Convert the plain-text parser result into the schema v1 dictionary.

    Section headings are mapped with the same aliases the DOCX parser uses; unknown
    headings are ignored. Reference lines such as "(1) ..." become list entries.
    """
    # imported here to keep the plain-text parser free of the python-docx dependency
    from galleyforge_core.docx_parser_v1 import SECTION_ALIASES

    def section_key(title: str):
        t = title.strip().lower()
        for key, aliases in SECTION_ALIASES.items():
            if t in aliases:
                return key
        return None

    names = [n.strip() for n in (manuscript.authors or "").split(",") if n.strip()]
    sections = {}
    references: List[str] = []
    for sec in manuscript.sections:
        key = section_key(sec.title)
        if key == "references":
            for line in sec.content.splitlines():
                line = re.sub(r"^\s*\(?\d+[\).]?\s*", "", line).strip()
                if line:
                    references.append(line)
        elif key and key != "keywords":
            sections[key] = sec.content
    sections["references"] = references

    return {
        "schema_version": "1.0",
        "template_id": None,
        "manuscript_id": manuscript_id,
        "title": manuscript.title,
        "authors": [{"name": n, "affiliation_indices": []} for n in names],
        "affiliations": [],
        "corresponding": {"author_index": 0, "email": ""},
        "keywords": [],
        "sections": sections,
    }
