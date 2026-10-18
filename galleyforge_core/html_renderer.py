from pathlib import Path
from html import escape
from typing import Dict, Any, List


# (section key, heading) in output order; sections without text are skipped
MAIN_SECTIONS = [
    ("abstract", "Abstract"),
    ("introduction", "Introduction"),
    ("methods", "Materials and Methods"),
    ("results", "Results"),
    ("discussion", "Discussion"),
    ("conclusion", "Conclusion"),
]
BACK_SECTIONS = [
    ("abbreviations", "Abbreviations"),
    ("acknowledgements", "Acknowledgements"),
    ("funding", "Funding"),
    ("ethics", "Ethics approval"),
    ("disclosure_statement", "Conflicts of interest"),
    ("data_availability", "Data availability"),
    ("author_contributions", "Author contributions"),
    ("ai_disclosure", "AI disclosure"),
    ("declarations", "Declarations"),
]


def _render_paragraphs(text: str) -> str:
    if not text:
        return ""
    parts = [p.strip() for p in str(text).replace("\r\n", "\n").split("\n\n") if p.strip()]
    out = []
    for p in parts:
        lines = [escape(x) for x in p.split("\n")]
        out.append("<p>" + "<br>".join(lines) + "</p>")
    return "\n".join(out)


def _render_authors_html(authors: List[Dict[str, Any]]) -> str:
    parts = []
    for a in authors or []:
        name = escape(str(a.get("name", "")).strip())
        affs = a.get("affiliation_indices", [])
        if not isinstance(affs, list):
            affs = []
        if affs:
            sup = ",".join(str(int(x)) for x in affs if isinstance(x, int))
            parts.append(f"{name}<sup>{sup}</sup>")
        else:
            parts.append(name)
    return ", ".join(parts)


def _render_affiliations_html(affiliations: List[Dict[str, Any]]) -> str:
    lines = []
    for aff in affiliations or []:
        idx = aff.get("index")
        txt = escape(str(aff.get("text", "")).strip())
        if isinstance(idx, int) and txt:
            lines.append(f"<p><sup>{idx}</sup> {txt}</p>")
    return "\n".join(lines)


def _render_references_html(refs: List[str]) -> str:
    if not refs:
        return ""
    items = [f"<li>{escape(str(r))}</li>" for r in refs if str(r).strip()]
    return "<ol>\n" + "\n".join(items) + "\n</ol>"


def _render_corresponding_html(data: Dict[str, Any]) -> str:
    corr = data.get("corresponding") or {}
    authors = data.get("authors") or []
    email = str(corr.get("email", "") or "").strip()
    idx = corr.get("author_index", 0)
    name = ""
    if isinstance(idx, int) and 0 <= idx < len(authors):
        name = str(authors[idx].get("name", "")).strip()
    if not (name or email):
        return ""
    who = escape(name)
    if email:
        who += f" ({escape(email)})" if name else escape(email)
    return f"<p><strong>Correspondence:</strong> {who}</p>"


def _render_tables_html(tables: List[Dict[str, Any]]) -> str:
    out = []
    for tbl in tables or []:
        if not isinstance(tbl, dict):
            continue
        label = escape(str(tbl.get("label", "")).strip())
        caption = escape(str(tbl.get("caption", "")).strip())
        rows = [r for r in (tbl.get("rows") or []) if isinstance(r, list)]
        parts = ["<table>"]
        if label or caption:
            parts.append(f"<caption><strong>{label}.</strong> {caption}</caption>")
        for n, row in enumerate(rows):
            if n == 0:
                parts.append("<thead>")
                cells = "".join(f'<th scope="col">{escape(str(c))}</th>' for c in row)
            else:
                if n == 1:
                    parts.append("<tbody>")
                cells = "".join(f"<td>{escape(str(c))}</td>" for c in row)
            parts.append(f"<tr>{cells}</tr>")
            if n == 0:
                parts.append("</thead>")
        if len(rows) > 1:
            parts.append("</tbody>")
        parts.append("</table>")
        out.append("\n".join(parts))
    return "\n\n".join(out)


def _render_figures_html(figures: List[Dict[str, Any]]) -> str:
    out = []
    for fig in figures or []:
        if not isinstance(fig, dict):
            continue
        file_ = str(fig.get("file") or fig.get("image") or "").strip()
        label = str(fig.get("label") or "").strip()
        caption = str(fig.get("caption") or fig.get("legend") or "").strip()
        if not (file_ or label or caption):
            continue
        if file_:
            img = f'<img src="figures/{escape(file_)}" alt="{escape(label)}">'
        else:
            img = '<p class="no-image">[No image file attached]</p>'
        if caption:
            cap = f"<strong>{escape(label)}.</strong> {escape(caption)}"
        else:
            cap = escape(label)
        out.append(f"<figure>{img}<figcaption>{cap}</figcaption></figure>")
    return "\n\n".join(out)


def render_html(data: Dict[str, Any], template_path: Path) -> str:
    """
    Open-Core HTML renderer for Schema v1.
    Expects template with {{ TITLE }} and {{ BODY }} placeholders.
    """
    tpl = Path(template_path).read_text(encoding="utf-8")

    sections = data.get("sections", {}) or {}

    body_parts: List[str] = []

    for note in data.get("front_matter") or []:
        if str(note).strip():
            body_parts.append(f'<p class="front-matter"><em>{escape(str(note).strip())}</em></p>')

    title = str(data.get("title", "") or "")
    if title:
        body_parts.append(f"<h1>{escape(title)}</h1>")

    authors_html = _render_authors_html(data.get("authors", []))
    if authors_html:
        body_parts.append(f"<p><strong>Authors:</strong> {authors_html}</p>")

    aff_html = _render_affiliations_html(data.get("affiliations", []))
    if aff_html:
        body_parts.append(aff_html)

    corr_html = _render_corresponding_html(data)
    if corr_html:
        body_parts.append(corr_html)

    keywords = [str(k).strip() for k in (data.get("keywords") or []) if str(k).strip()]
    if keywords:
        body_parts.append(f"<p><strong>Keywords:</strong> {escape('; '.join(keywords))}</p>")

    def add_sections(spec):
        for key, label in spec:
            if sections.get(key):
                body_parts.append(f"<h2>{label}</h2>")
                body_parts.append(_render_paragraphs(sections.get(key, "")))

    add_sections(MAIN_SECTIONS)

    tables_html = _render_tables_html(data.get("tables", []))
    if tables_html:
        body_parts.append("<h2>Tables</h2>")
        body_parts.append(tables_html)

    figures_html = _render_figures_html(data.get("figures", []))
    if figures_html:
        body_parts.append("<h2>Figures</h2>")
        body_parts.append(figures_html)

    add_sections(BACK_SECTIONS)

    if sections.get("references"):
        body_parts.append("<h2>References</h2>")
        body_parts.append(_render_references_html(sections.get("references", [])))

    body_html = "\n\n".join(body_parts)

    return tpl.replace("{{ TITLE }}", escape(title)).replace("{{ BODY }}", body_html)
