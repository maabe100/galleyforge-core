# Galleyforge Core

Galleyforge Core is an early **prototype** that turns a manuscript file into structured data and a basic HTML article.
It is the experimental foundation of the GalleyForge publishing software project, which targets small scientific journals.

> **Status: active development prototype.** Interfaces and the schema may change. No release has been published,
> and no release date has been set.

## What works today

Checked against the fictional test manuscript `examples/fictional_test_manuscript.docx` (see the tests):

| Element | Result |
|---|---|
| Title (Word "Title" style, or first paragraph) | recognised |
| Front-matter lines before the title (for example a notice banner) | kept as `front_matter` and shown in the HTML |
| Authors with affiliation labels | recognised: Unicode superscripts (`¹ ²`), Word superscript formatting, double-space-separated and `Name 1,2` layouts |
| Affiliations (one per line, labelled `1`, `a)` ...) | recognised and linked to the authors |
| Correspondence line | e-mail address and corresponding author recognised; the line is no longer mistaken for an author |
| `Keywords:` line | recognised (split at `;` or `,`) |
| Sections: Abstract, Introduction, Methods, Results, Discussion, Conclusion, Acknowledgements, Funding, References and a few more | recognised by heading text |
| `Declarations` block with `Label: text` lines | split into ethics, funding, conflicts of interest, data availability, author contributions |
| Table | rows and caption (`Table N. ...` before or after the table) extracted and rendered as an HTML table |
| Figure legend (`Figure N. ...` / `Fig. N. ...`) | extracted as a figure entry; an image file is optional (`--figures`) |
| Validation | rule-based errors, warnings and hints on the result |
| Output | `manuscript.json` (schema v1, described in `galleyforge_core/manuscript_v1.schema.json`) and a basic `index.html` |

There is also a simple plain-text demo (`examples/manuscript.txt`). Python 3 and `python-docx` are required;
it runs on Windows, macOS and Linux.

## What does not work (yet)

- **Layout conventions.** The parser relies on them. Headings are recognised by their text (no heading styles are
  evaluated), and authors must either carry superscript labels, be separated by double spaces, or be followed by plain
  digits. Comma-separated authors without labels in a multi-affiliation paper and introductory lines such as
  "Authors' Affiliations:" (typical of real manuscripts) are **not handled reliably**.
- **Unknown headings** are not detected; their text is appended to the previous section.
- **Structured abstracts** stay one block of text ("Background: ... Methods: ..." is not split).
- **Tables and figures are collected** in their own blocks after the main text, not at their position in the text, and in-text
  references ("Table 1", "Figure 1") are not linked. The first table row is always treated as the header; merged cells,
  nested tables, table notes and images embedded in the DOCX are not handled.
- **References** are kept as plain text lines. A note such as "No external references" is also stored as a reference
  entry. No in-text citation handling, footnotes or equations.
- **Only superscript digits** are used as affiliation labels from Word formatting; letters, `*` or `†` markers
  with superscript formatting are not interpreted.
- **No DOI/volume/page extraction.** The fields exist but stay empty. No dates, no ORCID, no funding identifiers.
- **No PDF, JATS, Crossref or PubMed XML output.** The `xml_settings` fields in the schema are empty placeholders.
- **No journal templates**; a single plain HTML template. No accessibility audit of the output.
- **IDML and PDF are not supported as input.**
- **No packaging, no installation as a library.** The test set is small (13 tests), all with fictional data.
- The schema file is a description only; the code does not enforce it (the tests validate the demo output against it).

## Quick start

```bash
pip install -r requirements.txt
python -m galleyforge_core.run_docx_example examples/fictional_test_manuscript.docx
python -m galleyforge_core.run_example        # plain-text demo
```

Each run writes `index.html` and `manuscript.json` to `output/<id>/` (`output/` is not versioned).
Optional images: `python -m galleyforge_core.run_docx_example my.docx --figures path/to/images` attaches files named
like `Fig_1.jpg` to the figure with the same number.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest tests
```

## Repository structure

```text
galleyforge_core/
 ├─ schema_v1.py                  # defaults for the manuscript schema
 ├─ manuscript_v1.schema.json     # JSON schema (v1) describing the output
 ├─ validator_v1.py               # validation rules
 ├─ docx_parser_v1.py             # DOCX -> schema v1 (heuristic)
 ├─ parser.py                     # plain text -> schema v1
 ├─ figures.py                    # figure image discovery and attachment
 ├─ html_renderer.py              # schema v1 -> HTML
 ├─ run_docx_example.py           # DOCX demo
 └─ run_example.py                # TXT demo
examples/                         # fictional test manuscript (DOCX), plain-text demo, two hand-drawn images
templates/base_template.html
tests/
```

## Example data

All example data is fictional or created by the maintainer: `examples/fictional_test_manuscript.docx` (invented
people, institutions and data, generated with python-docx), `examples/manuscript.txt`, and two hand-drawn figures.
Please do not add real manuscripts, author names, e-mail addresses or reviewer data to this repository.

## Roadmap

Nothing below is scheduled; priorities may change.

**Next (parser quality)**
- Evaluate Word heading styles and report unrecognised headings
- More robust author and affiliation detection for real-world layouts; clear warnings when a layout is not recognised
- Table notes, merged cells and placement of tables and figures at their position in the text
- Reference parsing and in-text citation links
- More validation rules and tests with additional fictional layouts

**Later**
- Journal templates and theme options
- Metadata fields (DOI, volume, pages, dates)
- Further output formats: PDF, and XML formats such as JATS, Crossref and PubMed (none exist yet)
- Interactive review and correction by an editor, in a separate application (not part of this repository)
- Possibly AI-assisted structure analysis, only ever as a suggestion under editorial control

## License

MIT, see `LICENSE`.
