from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from .models import ProjectSpec

ROOT = Path(__file__).resolve().parent.parent
HELPER_PROJECT = ROOT / "native_writer" / "native_mpp_writer.csproj"
HELPER_DLL = ROOT / "native_writer" / "bin" / "Release" / "net8.0" / "native_mpp_writer.dll"


def dotnet_available() -> bool:
    return shutil.which("dotnet") is not None


def ensure_helper_built() -> None:
    if not dotnet_available():
        raise RuntimeError("برای تولید MPP واقعی بدون Microsoft Project، .NET 8 SDK لازم است. از https://dotnet.microsoft.com/download/dotnet/8.0 نصب کنید و دوباره اجرا کنید.")
    if HELPER_DLL.exists():
        return
    proc = subprocess.run(
        ["dotnet", "build", str(HELPER_PROJECT), "-c", "Release", "--nologo"],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
    )
    if proc.returncode != 0:
        tail = (proc.stdout + "\n" + proc.stderr)[-6000:]
        raise RuntimeError("ساخت موتور MPP ناموفق بود:\n" + tail)


def _payload(project: ProjectSpec) -> dict:
    return {
        "name": project.name,
        "start": project.start.isoformat() if project.start else None,
        "defaultDurationDays": project.default_duration_days,
        "calendarName": project.calendar_name,
        "metadata": project.metadata,
        "tasks": [
            {
                "name": t.name,
                "level": t.level,
                "durationDays": t.duration_days,
                "start": t.start.isoformat() if t.start else None,
                "finish": t.finish.isoformat() if t.finish else None,
                "milestone": t.milestone,
                "resourceNames": t.resource_names,
                "notes": t.notes,
                "sourceLine": t.source_line,
                "sourceTable": t.source_table,
                "predecessors": [
                    {"predecessor": d.predecessor, "link": d.link, "lagDays": d.lag_days}
                    for d in t.predecessors
                ],
            }
            for t in project.tasks
        ],
    }


def write_native_mpp(project: ProjectSpec, output: str | Path) -> Path:
    ensure_helper_built()
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    payload_path = output.with_suffix(".project.json")
    payload_path.write_text(json.dumps(_payload(project), ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        proc = subprocess.run(
            ["dotnet", str(HELPER_DLL), str(payload_path), str(output)],
            cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
        )
        if proc.returncode != 0:
            raise RuntimeError((proc.stdout + "\n" + proc.stderr).strip()[-8000:])
        if not output.exists() or output.stat().st_size < 1024:
            raise RuntimeError("موتور MPP اجرا شد ولی فایل خروجی معتبر تولید نشد.")
        return output
    finally:
        payload_path.unlink(missing_ok=True)
