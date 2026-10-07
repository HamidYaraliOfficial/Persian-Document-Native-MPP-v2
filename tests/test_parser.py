from pathlib import Path
from persian_doc_to_mpp.parsers import parse_file


def test_docx_sample():
    p = Path(__file__).parents[1] / "examples" / "sample_persian_project.docx"
    project = parse_file(p)
    assert project.tasks
