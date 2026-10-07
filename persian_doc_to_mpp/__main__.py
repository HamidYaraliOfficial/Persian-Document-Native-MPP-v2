from __future__ import annotations

import argparse
import json
from pathlib import Path
from .converter import convert_to_mpp


def main() -> int:
    p = argparse.ArgumentParser(description="Persian PDF/DOCX -> native MPP converter")
    p.add_argument("input")
    p.add_argument("-o", "--output", required=False)
    p.add_argument("--project-name", default="")
    p.add_argument("--analyze", action="store_true")
    args = p.parse_args()
    result = convert_to_mpp(args.input, args.output, project_name=args.project_name or None)
    print(json.dumps({"output": str(result.output), "tasks": len(result.project.tasks), "project": result.project.name}, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
