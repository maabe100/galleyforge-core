# galleyforge_core/validator_v1.py

from dataclasses import dataclass
from typing import Any, Dict, List, Literal
import re


Severity = Literal["error", "warning", "info"]


@dataclass
class ValidationIssue:
    severity: Severity
    code: str
    message: str
    path: str = ""


EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def validate_manuscript_v1(data: Dict[str, Any]) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []

    def err(code: str, msg: str, path: str = ""):
        issues.append(ValidationIssue("error", code, msg, path))

    def warn(code: str, msg: str, path: str = ""):
        issues.append(ValidationIssue("warning", code, msg, path))

    def info(code: str, msg: str, path: str = ""):
        issues.append(ValidationIssue("info", code, msg, path))

    if not isinstance(data, dict):
        err("TYPE", "Manuscript data must be an object.", "")
        return issues

    if str(data.get("schema_version", "")).strip() != "1.0":
        warn("SCHEMA_VERSION", "schema_version should be '1.0'.", "schema_version")

    if not str(data.get("manuscript_id", "")).strip():
        err("MISSING_FIELD", "Missing manuscript_id.", "manuscript_id")

    if not str(data.get("title", "")).strip():
        err("MISSING_FIELD", "Missing title.", "title")

    # Authors
    authors = data.get("authors", [])
    if not isinstance(authors, list) or len(authors) == 0:
        err("NO_AUTHORS", "At least one author is required.", "authors")
        authors = []

    for i, a in enumerate(authors):
        if not isinstance(a, dict):
            err("AUTHOR_TYPE", "Author must be an object.", f"authors[{i}]")
            continue

        name = str(a.get("name", "")).strip()
        if not name:
            err("AUTHOR_NAME_EMPTY", "Author name is empty.", f"authors[{i}].name")

        affs = a.get("affiliation_indices", [])
        if affs is None:
            affs = []
        if not isinstance(affs, list):
            err("AUTHOR_AFFILIATIONS_TYPE", "affiliation_indices must be a list.", f"authors[{i}].affiliation_indices")
        else:
            for j, x in enumerate(affs):
                if not isinstance(x, int) or x < 1:
                    err("AUTHOR_AFFILIATION_INVALID", "Affiliation index must be int >= 1.", f"authors[{i}].affiliation_indices[{j}]")

    # Affiliations
    affiliations = data.get("affiliations", [])
    if affiliations is None:
        affiliations = []
    if not isinstance(affiliations, list):
        err("AFFILIATIONS_TYPE", "affiliations must be a list.", "affiliations")
        affiliations = []

    seen = set()
    for i, aff in enumerate(affiliations):
        if not isinstance(aff, dict):
            err("AFFILIATION_TYPE", "Affiliation must be an object.", f"affiliations[{i}]")
            continue

        idx = aff.get("index")
        txt = str(aff.get("text", "")).strip()
        if not isinstance(idx, int) or idx < 1:
            err("AFFILIATION_INDEX", "Affiliation index must be int >= 1.", f"affiliations[{i}].index")
        else:
            if idx in seen:
                warn("AFFILIATION_DUP_INDEX", f"Duplicate affiliation index {idx}.", f"affiliations[{i}].index")
            seen.add(idx)

        if not txt:
            err("AFFILIATION_TEXT", "Affiliation text is empty.", f"affiliations[{i}].text")

    if len(affiliations) == 0:
        warn("NO_AFFILIATIONS", "No affiliations detected (may be fine for demo).", "affiliations")

    # Corresponding
    corr = data.get("corresponding", {})
    if corr is None:
        corr = {}
    if not isinstance(corr, dict):
        warn("CORR_TYPE", "corresponding should be an object.", "corresponding")
        corr = {}

    ai = corr.get("author_index", 0)
    if not isinstance(ai, int) or ai < 0 or ai >= max(len(authors), 1):
        warn("CORR_AUTHOR_INDEX", "corresponding.author_index is out of range; GUI should correct.", "corresponding.author_index")

    email = str(corr.get("email", "") or "")
    if email and not EMAIL_RE.search(email):
        warn("CORR_EMAIL", "Corresponding email does not look valid.", "corresponding.email")

    # Sections
    sections = data.get("sections", {})
    if not isinstance(sections, dict):
        err("SECTIONS_TYPE", "sections must be an object.", "sections")
        sections = {}

    if not str(sections.get("abstract", "")).strip() and not str(sections.get("introduction", "")).strip():
        warn("NO_ABSTRACT_INTRO", "Neither abstract nor introduction present (check section detection).", "sections")

    # Keywords
    kws = data.get("keywords", [])
    if kws is None:
        kws = []
    if not isinstance(kws, list):
        err("KEYWORDS_TYPE", "keywords must be a list.", "keywords")
    elif len(kws) == 0:
        warn("NO_KEYWORDS", "No keywords detected.", "keywords")

    return issues
