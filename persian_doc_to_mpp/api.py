from __future__ import annotations

import json
import tempfile
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from starlette.background import BackgroundTask

from .converter import convert_to_mpp
from .native_writer import dotnet_available, HELPER_DLL
from .parsers import parse_file
from .planner import normalize_project

app = FastAPI(title="Persian Doc → Native MPP", version="2.0.0")
ALLOWED = {".pdf", ".docx"}
MAX_BYTES = 75 * 1024 * 1024


def serialize_project(project):
    return {
        "name": project.name,
        "start": project.start.isoformat() if project.start else None,
        "task_count": len(project.tasks),
        "resources": sorted({r for t in project.tasks for r in t.resource_names}),
        "tasks": [
            {
                "id": i,
                "name": t.name,
                "level": t.level,
                "duration_days": t.duration_days,
                "start": t.start.isoformat() if t.start else None,
                "finish": t.finish.isoformat() if t.finish else None,
                "milestone": bool(t.milestone),
                "predecessors": [{"task": d.predecessor, "type": d.link, "lag_days": d.lag_days} for d in t.predecessors],
                "resources": t.resource_names,
                "notes": t.notes,
            }
            for i, t in enumerate(project.tasks, start=1)
        ],
    }


def _save_upload(file: UploadFile):
    suffix = Path(file.filename or "input").suffix.lower()
    if suffix not in ALLOWED:
        raise HTTPException(400, "فقط PDF و DOCX در نسخه 2 پشتیبانی می‌شود.")
    temp_dir = tempfile.TemporaryDirectory(prefix="persian_mpp_v2_")
    src = Path(temp_dir.name) / Path(file.filename or "input").name
    return temp_dir, src, suffix


@app.get("/", response_class=HTMLResponse)
def home():
    return (Path(__file__).resolve().parent.parent / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": "2.0.0",
        "dotnet": dotnet_available(),
        "writer_ready": HELPER_DLL.exists(),
        "native_mpp": True,
    }


@app.post("/analyze")
async def analyze(file: UploadFile = File(...), project_name: str = Form("")):
    temp_dir, src, _ = _save_upload(file)
    try:
        data = await file.read()
        if len(data) > MAX_BYTES:
            raise HTTPException(413, "حجم فایل بیشتر از 75MB است.")
        src.write_bytes(data)
        project = normalize_project(parse_file(src, project_name=project_name or None))
        return serialize_project(project)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(422, str(exc)) from exc
    finally:
        temp_dir.cleanup()


@app.post("/convert")
async def convert(file: UploadFile = File(...), project_name: str = Form("")):
    temp_dir, src, _ = _save_upload(file)
    persistent: Path | None = None
    try:
        data = await file.read()
        if len(data) > MAX_BYTES:
            raise HTTPException(413, "حجم فایل بیشتر از 75MB است.")
        src.write_bytes(data)
        out = Path(temp_dir.name) / f"{src.stem}.mpp"
        result = convert_to_mpp(src, out, project_name=project_name or None)
        persistent = Path(tempfile.gettempdir()) / f"persian-mpp-v2-{uuid.uuid4().hex}.mpp"
        persistent.write_bytes(result.output.read_bytes())
        return FileResponse(
            persistent,
            media_type="application/vnd.ms-project",
            filename=f"{src.stem}.mpp",
            background=BackgroundTask(lambda: persistent.unlink(missing_ok=True)),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(503, str(exc)) from exc
    finally:
        temp_dir.cleanup()
