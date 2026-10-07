from __future__ import annotations

from pathlib import Path

from .models import ProjectSpec
from .parsers import parse_file
from .planner import normalize_project
from .native_writer import write_native_mpp


class ConversionResult:
    def __init__(self, project: ProjectSpec, output: Path):
        self.project = project
        self.output = output
        self.native_mpp = True


def convert_to_mpp(input_file: str | Path, output_file: str | Path | None = None, *, project_name: str | None = None) -> ConversionResult:
    source = Path(input_file)
    project = normalize_project(parse_file(source, project_name=project_name))
    target = Path(output_file) if output_file else source.with_suffix(".mpp")
    actual = write_native_mpp(project, target)
    return ConversionResult(project, actual)
