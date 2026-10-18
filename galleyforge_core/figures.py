import re
from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass
class Figure:
    filename: str
    label: str  # e.g. "Fig. 1"
    caption: str = ""


def find_figures_in_directory(figures_dir: str) -> List[Figure]:
    """
    Scan a directory for files with names like Fig_1.jpg, Fig_2.png etc.
    and create simple Figure objects.
    """
    path = Path(figures_dir)
    figures: List[Figure] = []

    if not path.exists():
        return figures

    for file in sorted(path.iterdir()):
        if not file.is_file():
            continue
        if file.suffix.lower() not in {".jpg", ".jpeg", ".png", ".tif", ".tiff"}:
            continue

        # Try to extract a figure number from file name, e.g. Fig_1.jpg
        m = re.search(r"(\d+)", file.stem)
        if m:
            num = m.group(1)
            label = f"Fig. {num}"
        else:
            label = file.stem

        figures.append(Figure(filename=file.name, label=label))

    return figures


def attach_figure_files(figures: list, figures_dir) -> list:
    """Attach image files from a folder to figure dicts by figure number.

    Files like Fig_1.jpg or Figure2.png match "Figure 1" / "Figure 2". Image files without a
    matching figure entry are appended as figures without caption.
    """
    result = [dict(f) for f in figures or []]
    by_number = {}
    for i, fig in enumerate(result):
        m = re.search(r"(\d+)", str(fig.get("label", "")))
        if m:
            by_number[m.group(1)] = i
    for found in find_figures_in_directory(str(figures_dir)):
        m = re.search(r"(\d+)", found.label)
        if m and m.group(1) in by_number:
            result[by_number[m.group(1)]]["file"] = found.filename
        else:
            result.append({"label": found.label, "caption": found.caption, "file": found.filename})
    return result
