"""Plain-text demo: examples/manuscript.txt -> schema v1 -> HTML.

Usage (from the repository root):
    python -m galleyforge_core.run_example
"""

import json
import shutil
from pathlib import Path

from galleyforge_core.figures import find_figures_in_directory
from galleyforge_core.html_renderer import render_html
from galleyforge_core.parser import manuscript_to_schema_v1, parse_manuscript_file
from galleyforge_core.schema_v1 import ensure_schema_defaults
from galleyforge_core.validator_v1 import validate_manuscript_v1

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main():
    manuscript_path = PROJECT_ROOT / "examples" / "manuscript.txt"
    figures_dir = PROJECT_ROOT / "examples" / "figures"
    template_path = PROJECT_ROOT / "templates" / "base_template.html"

    data = ensure_schema_defaults(manuscript_to_schema_v1(parse_manuscript_file(str(manuscript_path))))
    data["figures"] = [
        {"label": f.label, "file": f.filename, "caption": f.caption}
        for f in find_figures_in_directory(str(figures_dir))
    ]

    for issue in validate_manuscript_v1(data):
        print(f"[{issue.severity.upper()}] {issue.code}: {issue.message} ({issue.path})")

    out_dir = PROJECT_ROOT / "output" / data["manuscript_id"]
    (out_dir / "figures").mkdir(parents=True, exist_ok=True)
    for fig in data["figures"]:
        shutil.copy2(figures_dir / fig["file"], out_dir / "figures" / fig["file"])

    (out_dir / "manuscript.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "index.html").write_text(render_html(data, template_path), encoding="utf-8")
    print(f"\nOutput written to {out_dir}\n")


if __name__ == "__main__":
    main()
