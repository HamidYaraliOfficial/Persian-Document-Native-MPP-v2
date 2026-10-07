from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from .models import Dependency, ProjectSpec, TaskSpec
from .text_utils import normalize_text, parse_dependencies, parse_duration_days, parse_iso_or_local_date, extract_field

SUPPORTED = {".pdf", ".docx", ".doc"}


def extract_pdf(path: Path) -> str:
    from pypdf import PdfReader
    chunks: list[str] = []
    with path.open("rb") as fh:
        reader = PdfReader(fh)
        for i, page in enumerate(reader.pages, start=1):
            chunks.append(f"\n[PAGE {i}]\n{page.extract_text() or ''}")
    return "\n".join(chunks)


def _iter_docx_blocks(path: Path) -> Iterable[tuple[str, object]]:
    from docx import Document
    doc = Document(path)
    # Preserve document order as much as python-docx exposes it through the body.
    for p in doc.paragraphs:
        if p.text.strip():
            yield "paragraph", p
    for idx, table in enumerate(doc.tables, start=1):
        yield f"table:{idx}", table


def _heading_level(paragraph) -> int | None:
    style = getattr(paragraph, "style", None)
    name = (getattr(style, "name", "") or "").lower()
    m = re.search(r"(?:heading|عنوان|تیتر)\s*([1-9][0-9]?)", name)
    if m:
        return min(20, int(m.group(1)))
    text = normalize_text(paragraph.text)
    m = re.match(r"^((?:\d+[.)/-]?\s*){1,8})(\S.*)$", text)
    if m:
        return min(20, len(re.findall(r"\d+", m.group(1))))
    return None


def _list_level(paragraph) -> int | None:
    style_name = (getattr(getattr(paragraph, "style", None), "name", "") or "").lower()
    if any(x in style_name for x in ("list bullet", "list number", "bullet", "number", "فهرست")):
        return 2
    text = normalize_text(paragraph.text)
    if re.match(r"^(?:[-*•▪◦●○] |\d+[.)]\s+|[الفبجده][.)]\s+)", text):
        return 2
    return None


def _clean_task_name(name: str) -> str:
    name = normalize_text(name)
    name = re.sub(r"^(?:[-*•▪◦●○]|\d+[.)]|[الفبجده][.)])\s*", "", name)
    name = re.split(
        r"\s*[—–-]\s*(?=(?:مدت|زمان|duration|شروع|تاریخ شروع|start|پایان|تاریخ پایان|finish|end|پیش(?:‌|\s*)نیاز|پیشنیاز|predecessors?|depends\s*on|مسئول|منبع|resource)\s*[:=])",
        name,
        maxsplit=1,
        flags=re.I,
    )[0]
    return name.strip(" :-–—") or "وظیفه بدون عنوان"


def _header_index(headers: list[str], candidates: tuple[str, ...]) -> int | None:
    for i, h in enumerate(headers):
        n = normalize_text(h).lower()
        if any(c in n for c in candidates):
            return i
    return None


def _table_tasks(table, table_index: int) -> list[TaskSpec]:
    rows = [[normalize_text(cell.text) for cell in row.cells] for row in table.rows]
    rows = [r for r in rows if any(r)]
    if len(rows) < 2:
        return []
    headers = rows[0]
    name_i = _header_index(headers, ("task", "name", "activity", "عنوان", "فعالیت", "وظیفه", "کار"))
    dur_i = _header_index(headers, ("duration", "مدت", "زمان"))
    start_i = _header_index(headers, ("start", "شروع", "تاریخ شروع"))
    finish_i = _header_index(headers, ("finish", "end", "پایان", "تاریخ پایان"))
    pred_i = _header_index(headers, ("predecessor", "dependency", "depends", "پیش نیاز", "پیش‌نیاز", "پیشنیاز", "وابستگی"))
    res_i = _header_index(headers, ("resource", "مسئول", "منبع", "مجری"))
    note_i = _header_index(headers, ("note", "notes", "شرح", "توضیحات"))
    level_i = _header_index(headers, ("level", "outline", "سطح", "سطح wbs", "wbs"))
    if name_i is None:
        name_i = 0 if len(headers) >= 2 else None
    if name_i is None:
        return []

    out: list[TaskSpec] = []
    for ridx, row in enumerate(rows[1:], start=2):
        def get(i):
            return row[i] if i is not None and i < len(row) else ""
        if not get(name_i).strip():
            continue
        dur = parse_duration_days(get(dur_i))
        deps = [Dependency(*x) for x in parse_dependencies(get(pred_i))]
        lvl_num = None
        if get(level_i):
            try:
                lvl_num = int(parse_duration_days(get(level_i)) or 1)
            except Exception:
                lvl_num = 1
        resources = [x.strip() for x in re.split(r"[,;،؛/]+", get(res_i)) if x.strip()]
        out.append(TaskSpec(
            name=_clean_task_name(get(name_i)),
            level=max(1, min(20, lvl_num or 1)),
            duration_days=dur,
            start=parse_iso_or_local_date(get(start_i)),
            finish=parse_iso_or_local_date(get(finish_i)),
            predecessors=deps,
            resource_names=resources,
            notes=get(note_i),
            milestone=(dur == 0),
            source_table=table_index,
        ))
    return out


def parse_docx(path: Path, project_name: str | None = None) -> ProjectSpec:
    from docx import Document
    doc = Document(path)
    inferred_project = project_name or path.stem
    tasks: list[TaskSpec] = []
    last_level = 1

    for pidx, p in enumerate(doc.paragraphs, start=1):
        text = normalize_text(p.text)
        if not text:
            continue
        level = _heading_level(p) or _list_level(p)
        if level is None:
            if re.search(r"(?:مدت|duration|شروع|start|پیش(?:‌|\s*)نیاز|predecessors?|مسئول|resource)\s*[:=]", text, re.I):
                level = last_level
            else:
                continue
        last_level = max(1, min(20, level))
        duration_txt = extract_field(text, [r"(?:مدت|duration|زمان)\s*[:=]\s*([^,؛;|]+)"])
        start_txt = extract_field(text, [r"(?:شروع|تاریخ شروع|start)\s*[:=]\s*([^,؛;|]+)"])
        finish_txt = extract_field(text, [r"(?:پایان|تاریخ پایان|finish|end)\s*[:=]\s*([^,؛;|]+)"])
        dep_field = extract_field(text, [r"(?:پیش(?:‌|\s*)نیاز|پیشنیاز|predecessors?|depends\s*on|بعد از|پس از)\s*[:=]\s*(.+)$"])
        res_field = extract_field(text, [r"(?:مسئول|مجری|resource|منبع)\s*[:=]\s*([^,؛;|]+)"])
        task = TaskSpec(
            name=_clean_task_name(text),
            level=last_level,
            duration_days=parse_duration_days(duration_txt or ""),
            start=parse_iso_or_local_date(start_txt or ""),
            finish=parse_iso_or_local_date(finish_txt or ""),
            predecessors=[Dependency(*x) for x in parse_dependencies(dep_field or "")],
            resource_names=[x.strip() for x in re.split(r"[,;،؛/]+", res_field or "") if x.strip()],
            notes="",
            milestone=(parse_duration_days(duration_txt or "") == 0),
            source_line=pidx,
        )
        tasks.append(task)

    for tindex, table in enumerate(doc.tables, start=1):
        tasks.extend(_table_tasks(table, tindex))

    return ProjectSpec(name=inferred_project, start=next((t.start for t in tasks if t.start), None), tasks=tasks)


def parse_pdf(path: Path, project_name: str | None = None) -> ProjectSpec:
    text = extract_pdf(path)
    lines = [normalize_text(x) for x in text.splitlines() if normalize_text(x)]
    tasks: list[TaskSpec] = []
    inferred_project = project_name or path.stem
    current_level = 1
    for idx, line in enumerate(lines, start=1):
        if re.fullmatch(r"\[PAGE\s+\d+\]", line, re.I):
            continue
        heading = re.match(r"^((?:\d+[.)/-]?\s*){1,8})(.+)$", line)
        bullet = re.match(r"^(?:[-*•▪◦●○]|\d+[.)]|[الفبجده][.)])\s+(.+)$", line)
        if heading:
            nums = re.findall(r"\d+", heading.group(1))
            current_level = max(1, min(20, len(nums)))
            raw_name = heading.group(2)
        elif bullet:
            raw_name = bullet.group(1)
        elif re.search(r"(?:مدت|duration|شروع|start|پیش(?:‌|\s*)نیاز|predecessors?|مسئول|resource)\s*[:=]", line, re.I):
            raw_name = line
        else:
            continue
        duration_txt = extract_field(line, [r"(?:مدت|duration|زمان)\s*[:=]\s*([^,؛;|]+)"])
        start_txt = extract_field(line, [r"(?:شروع|تاریخ شروع|start)\s*[:=]\s*([^,؛;|]+)"])
        finish_txt = extract_field(line, [r"(?:پایان|تاریخ پایان|finish|end)\s*[:=]\s*([^,؛;|]+)"])
        pred_txt = extract_field(line, [r"(?:پیش(?:‌|\s*)نیاز|پیشنیاز|predecessors?|depends\s*on|بعد از|پس از)\s*[:=]\s*(.+)$"])
        res_txt = extract_field(line, [r"(?:مسئول|مجری|resource|منبع)\s*[:=]\s*([^,؛;|]+)"])
        dur = parse_duration_days(duration_txt or "")
        tasks.append(TaskSpec(
            name=_clean_task_name(raw_name), level=current_level,
            duration_days=dur,
            start=parse_iso_or_local_date(start_txt or ""),
            finish=parse_iso_or_local_date(finish_txt or ""),
            predecessors=[Dependency(*x) for x in parse_dependencies(pred_txt or "")],
            resource_names=[x.strip() for x in re.split(r"[,;،؛/]+", res_txt or "") if x.strip()],
            milestone=(dur == 0), source_line=idx,
        ))
    return ProjectSpec(name=inferred_project, start=next((t.start for t in tasks if t.start), None), tasks=tasks)


def parse_file(path: str | Path, project_name: str | None = None) -> ProjectSpec:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    if p.suffix.lower() == ".doc":
        raise ValueError("فایل DOC قدیمی در نسخه 2 بدون Microsoft Word پشتیبانی نمی‌شود. فایل را به DOCX تبدیل کنید.")
    if p.suffix.lower() not in SUPPORTED:
        raise ValueError("فرمت پشتیبانی نمی‌شود. فقط PDF و DOCX در نسخه 2 پشتیبانی می‌شوند.")
    return parse_docx(p, project_name) if p.suffix.lower() == ".docx" else parse_pdf(p, project_name)
