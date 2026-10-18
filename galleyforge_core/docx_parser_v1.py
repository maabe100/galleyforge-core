# galleyforge_core/docx_parser_v1.py

from pathlib import Path
from typing import List, Dict, Any, Tuple
import re

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph


SECTION_ALIASES = {
    "abstract": ["abstract"],
    "introduction": ["introduction", "background"],
    "methods": ["materials and methods", "material and methods", "methods", "patients and methods"],
    "results": ["results"],
    "discussion": ["discussion"],
    "abbreviations": ["abbreviations", "abbr.", "abbreviations and acronyms"],
    "acknowledgements": ["acknowledgements", "acknowledgments"],
    "funding": ["funding"],
    "author_contributions": ["author contributions", "contributions"],
    "ai_disclosure": ["ai disclosure", "ai statement"],
    "disclosure_statement": ["conflict of interest", "disclosure", "disclosure statement"],
    "references": ["references", "reference list"],
    "keywords": ["keywords", "key words"],
    "conclusion": ["conclusion", "conclusions"],
    "declarations": ["declarations"],
}

# "Label: text" lines inside a Declarations section -> schema section keys
DECLARATION_LABELS = {
    "ethics approval": "ethics",
    "ethics": "ethics",
    "funding": "funding",
    "conflicts of interest": "disclosure_statement",
    "conflict of interest": "disclosure_statement",
    "competing interests": "disclosure_statement",
    "data availability": "data_availability",
    "author contributions": "author_contributions",
    "acknowledgements": "acknowledgements",
    "acknowledgments": "acknowledgements",
}

SUPERSCRIPTS = "⁰¹²³⁴⁵⁶⁷⁸⁹"
_SUP_TO_DIGIT = str.maketrans(SUPERSCRIPTS, "0123456789")
SUP_GROUP_RE = re.compile(rf"[{SUPERSCRIPTS}]+(?:\s*,\s*[{SUPERSCRIPTS}]+)*")
TABLE_CAPTION_RE = re.compile(r"^\s*Table\s*(\d+)\s*[.:]\s*(.*)$", re.IGNORECASE | re.DOTALL)
FIGURE_CAPTION_RE = re.compile(r"^\s*(?:Figure|Fig\.?)\s*(\d+)\s*[.:]\s*(.*)$", re.IGNORECASE | re.DOTALL)


def _unsuperscript(text: str) -> str:
    return text.translate(_SUP_TO_DIGIT)

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _normalize(text: str) -> str:
    return text.strip().lower()


def _match_section_heading(text: str) -> str | None:
    t = _normalize(text)
    for key, aliases in SECTION_ALIASES.items():
        if t in aliases:
            return key
    return None


_DIGIT_TO_SUP = str.maketrans("0123456789", SUPERSCRIPTS)


def _paragraph_text(para: Paragraph) -> str:
    """Paragraph text; digits in runs formatted as superscript become Unicode superscript digits.

    That keeps author/affiliation labels ("Name" + superscript 1,2) recognisable after flattening.
    Falls back to the plain text if the runs do not add up to it (for example hyperlinks).
    """
    text = para.text
    if not any(run.font.superscript for run in para.runs):
        return text
    rebuilt = "".join(
        run.text.translate(_DIGIT_TO_SUP) if run.font.superscript else run.text for run in para.runs
    )
    return rebuilt if len(rebuilt) == len(text) else text


def _iter_blocks(doc: Document):
    """Yield ("p", text, style_name) and ("tbl", rows, "") in document order."""
    for child in doc.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            para = Paragraph(child, doc)
            yield ("p", _paragraph_text(para), para.style.name if para.style is not None else "")
        elif tag == "tbl":
            table = Table(child, doc)
            yield ("tbl", [[c.text.strip() for c in row.cells] for row in table.rows], "")


def _extract_blocks(doc: Document):
    """Split the body into plain paragraphs, tables and figure captions.

    A "Table N." paragraph directly before (or, failing that, after) a table becomes its caption;
    "Figure N." / "Fig. N." paragraphs become figure entries without an image file.
    Returns (paragraphs, styles, tables, figures).
    """
    items = [b for b in _iter_blocks(doc) if b[0] == "tbl" or b[1].strip()]
    table_caption = {}  # item index of the table -> (label, caption text)
    caption_items = set()
    for i, b in enumerate(items):
        if b[0] != "p":
            continue
        m = TABLE_CAPTION_RE.match(b[1])
        if not m:
            continue
        target = None
        if i + 1 < len(items) and items[i + 1][0] == "tbl" and (i + 1) not in table_caption:
            target = i + 1
        elif i > 0 and items[i - 1][0] == "tbl" and (i - 1) not in table_caption:
            target = i - 1
        if target is not None:
            table_caption[target] = (f"Table {m.group(1)}", m.group(2).strip())
            caption_items.add(i)

    paragraphs: List[str] = []
    styles: List[str] = []
    tables: List[Dict[str, Any]] = []
    figures: List[Dict[str, Any]] = []
    for i, b in enumerate(items):
        if b[0] == "tbl":
            label, caption = table_caption.get(i, (f"Table {len(tables) + 1}", ""))
            tables.append({"label": label, "caption": caption, "rows": b[1]})
            continue
        if i in caption_items:
            continue
        text = b[1].strip()
        fm = FIGURE_CAPTION_RE.match(text)
        if fm:
            figures.append({"label": f"Figure {fm.group(1)}", "caption": fm.group(2).strip(), "file": ""})
            continue
        paragraphs.append(text)
        styles.append(b[2])
    return paragraphs, styles, tables, figures


def _split_into_sections(paragraphs: List[str]) -> Dict[str, List[str]]:
    sections: Dict[str, List[str]] = {"_preamble": []}
    current = "_preamble"
    for para in paragraphs:
        heading_key = _match_section_heading(para)
        if heading_key:
            current = heading_key
            sections.setdefault(current, [])
        else:
            sections.setdefault(current, []).append(para)
    return sections


def _looks_like_affiliation_line(text: str) -> bool:
    if not text:
        return False
    t = text.strip()
    if "@" in t:
        return False
    if re.match(r"^\s*[a-zA-Z0-9][\)\.\]:]?\s+[A-Z]", t):
        return True
    if re.match(r"^\s*[a-zA-Z0-9](?=[A-Z])", t):
        lower = t.lower()
        if any(w in lower for w in ["department", "university", "institute", "faculty", "school", "center", "centre", "hospital", "clinic", "laboratory"]):
            return True
    if re.match(r"^(department|university|institute|faculty|school|center|centre|hospital|clinic|laboratory)\b", t, re.IGNORECASE):
        return True
    return False


def _parse_preamble(preamble_paras: List[str]) -> Dict[str, Any]:
    result = {
        "title": "",
        "author_lines": [],
        "affiliation_lines": [],
        "keywords_line": "",
        "corresponding_line": "",
    }
    nonempty = [p for p in preamble_paras if p.strip()]
    if not nonempty:
        return result

    result["title"] = nonempty[0].strip()

    for p in nonempty[1:]:
        ps = p.strip()
        pl = ps.lower()

        if pl.startswith("key words") or pl.startswith("keywords"):
            result["keywords_line"] = ps
            continue

        # A correspondence line (contains an e-mail address or starts with
        # "correspondence"/"corresponding") is not an author or affiliation line.
        if "@" in ps or pl.startswith(("correspondence", "corresponding")):
            if not result["corresponding_line"]:
                result["corresponding_line"] = ps
            continue

        if _looks_like_affiliation_line(_unsuperscript(ps)):
            result["affiliation_lines"].append(ps)
        else:
            result["author_lines"].append(ps)

    return result


def _extract_keywords_payload(sections: Dict[str, List[str]]) -> str:
    if sections.get("keywords"):
        return sections["keywords"][0].strip()

    pre = sections.get("_preamble", [])
    nonempty = [p for p in pre if p.strip()]
    for i, p in enumerate(nonempty):
        pl = p.strip().lower()
        if pl.startswith("key words") or pl.startswith("keywords"):
            # "Keywords: a; b; c" on a single line carries its own payload
            if re.search(r"[:\-]\s*\S", p):
                return p.strip()
            for q in nonempty[i + 1:]:
                if q.strip():
                    return q.strip()
    return ""


def _parse_keywords(payload: str) -> List[str]:
    if not payload:
        return []
    parts = re.split(r"[:\-]", payload, maxsplit=1)
    text = parts[1] if len(parts) == 2 else payload
    return [x.strip() for x in re.split(r"[;,•]", text) if x.strip()]


_LABELLED_AFFILIATION_RE = re.compile(r"^\s*(\d+|[a-zA-Z])(?:\s*[\).:]\s*|\s+)(?=[A-Z])(.+)$")


def _parse_labelled_affiliation_lines(lines: List[str]):
    """One affiliation per line, each starting with its label ("1 Department ...", "a) ...")."""
    parsed = []
    for line in lines:
        m = _LABELLED_AFFILIATION_RE.match(_unsuperscript(line.strip()))
        if not m:
            return None
        parsed.append((m.group(1).lower(), m.group(2).strip()))
    if not parsed or len({lab for lab, _ in parsed}) != len(parsed):
        return None
    affiliations = [{"index": i, "text": text} for i, (_, text) in enumerate(parsed, start=1)]
    label_map = {lab: i for i, (lab, _) in enumerate(parsed, start=1)}
    return affiliations, label_map


def _parse_affiliations(affiliation_lines: List[str], preamble_text: str) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    labelled = _parse_labelled_affiliation_lines([l for l in affiliation_lines if l.strip()])
    if labelled:
        return labelled
    text = " ".join([l.strip() for l in affiliation_lines if l.strip()]).strip()
    if not text:
        text = preamble_text.strip()

    m = EMAIL_RE.search(text)
    if m:
        pos = m.start()
        prev_comma = text.rfind(",", 0, pos)
        text = text[:prev_comma] if prev_comma != -1 else text[:pos]
        text = text.rstrip(" ,;#")

    affiliations: List[Dict[str, Any]] = []
    label_map: Dict[str, int] = {}

    matches = list(re.finditer(r"(?:(?<=^)|(?<=[,\s]))([a-zA-Z0-9])(?=[A-Z])", text))
    if not matches:
        idx = 1
        for line in affiliation_lines:
            t = line.strip()
            if not t:
                continue
            affiliations.append({"index": idx, "text": t})
            idx += 1
        return affiliations, label_map

    idx = 1
    for i, mm in enumerate(matches):
        lab = mm.group(1).lower()
        start = mm.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        seg = text[start:end].strip(" ,;")
        if not seg:
            continue
        if len(seg) < 5:
            continue
        affiliations.append({"index": idx, "text": seg})
        label_map[lab] = idx
        idx += 1

    return affiliations, label_map


def _clean_author_name(name: str) -> str:
    if not name:
        return ""
    n = name.strip()
    n = re.sub(r"[,#*†\s]+$", "", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n


def _parse_authors_with_superscripts(line: str, label_map: Dict[str, int]) -> List[Dict[str, Any]]:
    """"Name¹, Name²,³ and Name¹" -> authors with affiliation indices."""
    def mark(m):
        parts = [x.translate(_SUP_TO_DIGIT) for x in re.split(r"\s*,\s*", m.group(0))]
        return "\x00" + ";".join(parts) + "\x00"

    marked = SUP_GROUP_RE.sub(mark, line)
    marked = re.sub(r"\s+(?:and|&)\s+", ", ", marked)
    authors: List[Dict[str, Any]] = []
    for part in marked.split(","):
        m = re.match(r"^(?P<name>[^\x00]*?)\s*(?:\x00(?P<labels>[\d;]+)\x00)?\s*[*#†]?\s*$", part.strip())
        name = _clean_author_name(m.group("name") if m else part)
        if not name:
            continue
        indices: List[int] = []
        for lab in (m.group("labels") or "").split(";") if m else []:
            if lab in label_map and label_map[lab] not in indices:
                indices.append(label_map[lab])
        authors.append({"name": name, "affiliation_indices": indices, "is_corresponding": False})
    return authors


def _parse_authors(author_lines: List[str], label_map: Dict[str, int]) -> List[Dict[str, Any]]:
    authors: List[Dict[str, Any]] = []
    for line in author_lines:
        if SUP_GROUP_RE.search(line):
            authors.extend(_parse_authors_with_superscripts(line, label_map))
            continue
        tokens = re.split(r"\s{2,}", line)
        for tok in tokens:
            tok = tok.strip()
            if not tok:
                continue

            m = re.match(
                r"""^(?P<name>.+?)
                    (?:[,\s]+(?P<labels>[a-zA-Z0-9#*†](?:\s*,\s*[a-zA-Z0-9#*†])*))?
                    \s*$""",
                tok,
                flags=re.VERBOSE,
            )
            raw_name = tok if not m else (m.group("name") or "")
            labels_str = "" if not m else (m.group("labels") or "").strip()

            name = _clean_author_name(raw_name)
            if not name:
                continue

            corr = False
            aff_indices: List[int] = []
            if labels_str:
                labels = re.split(r"[,\s]+", labels_str)
                for lab in labels:
                    if not lab:
                        continue
                    if lab in ("#", "*", "†"):
                        corr = True
                        continue
                    labn = lab.lower()
                    if labn in label_map:
                        idx = label_map[labn]
                        if idx not in aff_indices:
                            aff_indices.append(idx)

            authors.append({"name": name, "affiliation_indices": aff_indices, "is_corresponding": corr})
    return authors


def _join_section(paras: List[str]) -> str:
    return "\n\n".join(paras) if paras else ""


def _parse_references(ref_paras: List[str]) -> List[str]:
    if not ref_paras:
        return []
    if not any(re.match(r"^\s*\d+\s", line) for para in ref_paras for line in para.splitlines()):
        # no numbering: every paragraph is one entry
        return [p.strip() for p in ref_paras if p.strip()]
    text = "\n".join(ref_paras)
    lines = text.splitlines()
    refs: List[str] = []
    current = ""
    for line in lines:
        if re.match(r"^\s*\d+\s", line):
            if current.strip():
                refs.append(current.strip())
            current = line.strip()
        else:
            current += " " + line.strip()
    if current.strip():
        refs.append(current.strip())
    return refs


def _parse_declarations(paras: List[str]) -> Dict[str, str]:
    """Split "Label: text" lines of a Declarations section into schema section keys."""
    out: Dict[str, List[str]] = {}
    for para in paras:
        for line in para.splitlines():
            line = line.strip()
            if not line:
                continue
            label, sep, rest = line.partition(":")
            key = DECLARATION_LABELS.get(label.strip().lower()) if sep else None
            out.setdefault(key or "declarations", []).append(rest.strip() if key else line)
    return {k: "\n\n".join(v) for k, v in out.items()}


def build_manuscript_dict_from_docx(path: str | Path) -> Dict[str, Any]:
    path = Path(path)
    doc = Document(str(path))

    paragraphs, styles, tables, figures = _extract_blocks(doc)

    # Word's "Title" style marks the title; anything before it (for example a banner line) is front matter.
    front_matter: List[str] = []
    if "Title" in styles:
        title_idx = styles.index("Title")
        front_matter = paragraphs[:title_idx]
        paragraphs = paragraphs[title_idx:]

    sections = _split_into_sections(paragraphs)

    preamble_paras = sections.get("_preamble", [])
    preamble_info = _parse_preamble(preamble_paras)
    preamble_text = "\n".join(preamble_paras)

    keywords_payload = _extract_keywords_payload(sections)
    keywords = _parse_keywords(keywords_payload)

    affiliations, label_map = _parse_affiliations(preamble_info["affiliation_lines"], preamble_text)
    authors = _parse_authors(preamble_info["author_lines"], label_map)

    # invariant: affiliation_indices always present
    for a in authors:
        if "affiliation_indices" not in a or not isinstance(a["affiliation_indices"], list):
            a["affiliation_indices"] = []

    # default affiliation if exactly 1 and nobody has any
    if affiliations and all(not a.get("affiliation_indices") for a in authors):
        default_idx = affiliations[0]["index"]
        for a in authors:
            a["affiliation_indices"] = [default_idx]

    # corresponding
    corr_email = ""
    m = EMAIL_RE.search(preamble_text)
    if m:
        corr_email = m.group(0)

    corr_author_idx = 0
    for i, a in enumerate(authors):
        if a.get("is_corresponding"):
            corr_author_idx = i
            break
    else:
        corr_line = preamble_info.get("corresponding_line", "")
        for i, a in enumerate(authors):
            if a["name"] and a["name"] in corr_line:
                corr_author_idx = i
                break

    # schema v1: remove is_corresponding from authors (single source of truth in "corresponding")
    for a in authors:
        if "is_corresponding" in a:
            del a["is_corresponding"]

    # invariant: corresponding always valid
    if not isinstance(corr_author_idx, int) or corr_author_idx < 0 or corr_author_idx >= len(authors):
        corr_author_idx = 0
    if not isinstance(corr_email, str):
        corr_email = ""

    sections_out: Dict[str, Any] = {
        "abstract": _join_section(sections.get("abstract", [])),
        "introduction": _join_section(sections.get("introduction", [])),
        "methods": _join_section(sections.get("methods", [])),
        "results": _join_section(sections.get("results", [])),
        "discussion": _join_section(sections.get("discussion", [])),
        "conclusion": _join_section(sections.get("conclusion", [])),
        "abbreviations": _join_section(sections.get("abbreviations", [])),
        "acknowledgements": _join_section(sections.get("acknowledgements", [])),
        "funding": _join_section(sections.get("funding", [])),
        "author_contributions": _join_section(sections.get("author_contributions", [])),
        "ai_disclosure": _join_section(sections.get("ai_disclosure", [])),
        "disclosure_statement": _join_section(sections.get("disclosure_statement", [])),
        "ethics": "",
        "data_availability": "",
        "references": _parse_references(sections.get("references", [])),
    }
    # a "Declarations" section carries labelled lines (Ethics approval: ..., Funding: ...)
    for key, text in _parse_declarations(sections.get("declarations", [])).items():
        sections_out[key] = "\n\n".join(x for x in (sections_out.get(key, ""), text) if x)

    return {
        "schema_version": "1.0",
        "template_id": None,  # set by runner/GUI

        "manuscript_id": "DOCX001",
        "title": preamble_info.get("title", ""),
        "journal": "",
        "article_type": "",

        "doi": "",
        "volume": "",
        "issue": "",
        "first_page": "",
        "last_page": "",

        "dates": {},
        "urls": {"pdf": "#", "html": "", "supplementary": []},
        "xml_settings": {"pubmed": {}, "crossref": {}},

        "authors": authors,
        "affiliations": affiliations,
        "corresponding": {"author_index": corr_author_idx, "email": corr_email},

        "keywords": keywords,
        "front_matter": front_matter,
        "sections": sections_out,
        "tables": tables,
        "figures": figures,
    }
