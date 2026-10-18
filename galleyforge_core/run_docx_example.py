# galleyforge_core/run_docx_example.py
"""DOCX demo: manuscript.docx -> schema v1 JSON + HTML in output/<manuscript_id>/.

Usage (from the repository root):
    python -m galleyforge_core.run_docx_example examples/fictional_test_manuscript.docx
    python -m galleyforge_core.run_docx_example my.docx --figures path/to/image_folder

Images are optional: with --figures, image files named like Fig_1.jpg / Figure2.png are attached to the
figure with the same number (or added as image-only figures if the document has no figure captions).
"""

import argparse
import json
import shutil
from pathlib import Path

from galleyforge_core.docx_parser_v1 import build_manuscript_dict_from_docx
from galleyforge_core.figures import attach_figure_files
from galleyforge_core.html_renderer import render_html
from galleyforge_core.schema_v1 import DEFAULT_TEMPLATE_ID_FALLBACK, ensure_schema_defaults
from galleyforge_core.validator_v1 import validate_manuscript_v1

BASE_DIR = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = BASE_DIR / "templates"
OUTPUT_DIR = BASE_DIR / "output"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Convert a DOCX manuscript to schema v1 JSON and HTML.")
    parser.add_argument("docx", type=Path, help="path to the DOCX manuscript")
    parser.add_argument("--figures", type=Path, default=None, help="optional folder with figure image files")
    args = parser.parse_args(argv)

    if not args.docx.is_file():
        parser.error(f"DOCX not found: {args.docx}")

    data = ensure_schema_defaults(build_manuscript_dict_from_docx(args.docx))
    if args.figures is not None:
        data["figures"] = attach_figure_files(data.get("figures", []), args.figures)

    data.setdefault("template_id", None)
    _ = data.get("template_id") or DEFAULT_TEMPLATE_ID_FALLBACK
    template_path = TEMPLATES_DIR / "base_template.html"  # open-core has a single template

    for issue in validate_manuscript_v1(data):
        print(f"[{issue.severity.upper()}] {issue.code}: {issue.message} ({issue.path})")

    out_dir = OUTPUT_DIR / data["manuscript_id"]
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.figures is not None:
        fig_dst = out_dir / "figures"
        fig_dst.mkdir(parents=True, exist_ok=True)
        for fig in data["figures"]:
            if fig.get("file"):
                shutil.copy2(args.figures / fig["file"], fig_dst / fig["file"])

    (out_dir / "manuscript.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "index.html").write_text(render_html(data, template_path=template_path), encoding="utf-8")

    print("\nDOCX parsed and exported:")
    print(f"   JSON: {out_dir / 'manuscript.json'}")
    print(f"   HTML: {out_dir / 'index.html'}\n")


if __name__ == "__main__":
    main()
