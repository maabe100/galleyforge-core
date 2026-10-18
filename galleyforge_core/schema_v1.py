# galleyforge_core/schema_v1.py

DEFAULT_SCHEMA_VERSION = "1.0"

# In Open-Core bleibt template_id optional/neutral.
DEFAULT_TEMPLATE_ID_FALLBACK = "base"


def ensure_schema_defaults(data: dict) -> dict:
    """
    Minimal helper: ensures core keys exist so downstream code can rely on them.
    Does NOT attempt to 'fix' semantics, only guarantees presence/types.
    """
    if not isinstance(data, dict):
        data = {}

    data.setdefault("schema_version", DEFAULT_SCHEMA_VERSION)
    data.setdefault("template_id", None)

    data.setdefault("manuscript_id", "DOCX001")
    data.setdefault("title", "")
    data.setdefault("journal", "")
    data.setdefault("article_type", "")

    data.setdefault("authors", [])
    data.setdefault("affiliations", [])
    data.setdefault("corresponding", {"author_index": 0, "email": ""})

    data.setdefault("keywords", [])
    data.setdefault("sections", {})
    data.setdefault("front_matter", [])
    data.setdefault("tables", [])
    data.setdefault("figures", [])

    data.setdefault("dates", {})
    data.setdefault("urls", {"pdf": "#", "html": "", "supplementary": []})
    data.setdefault("xml_settings", {"pubmed": {}, "crossref": {}})

    return data
