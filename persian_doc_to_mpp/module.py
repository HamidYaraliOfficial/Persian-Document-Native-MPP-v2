from __future__ import annotations

from pathlib import Path
from .converter import convert_to_mpp


def convert(input_file: str | Path, output_file: str | Path | None = None, *, project_name: str | None = None):
    """Convert a Persian PDF/DOCX project document into a native .mpp file without Microsoft Project."""
    return convert_to_mpp(input_file, output_file, project_name=project_name)
