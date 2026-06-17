#!/usr/bin/env python3
"""Normalize LLM-CLI sessions to JSON. stdlib only.

Modes:
  --mode all                  every detected provider/session
  --mode current --project P  sessions whose project == P
  --mode selected --project P sessions whose project == P (from --list-projects)

Filters (applied after --mode):
  --project-contains SUBSTR   keep only sessions whose project path contains
                              SUBSTR (case-insensitive). Use for directory scope,
                              e.g. all projects under a parent dir.

Utility:
  --list-projects             print discovered projects (one per line) and exit
  --count-only                print {"sessions": N, "providers": [...]} and exit (confirm gate)
  --out DIR                   write one <provider>__<session_id>.json per session
"""
from __future__ import annotations
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ctk.collect import (
    gather_all,
    filter_by_mode,
    filter_by_contains,
    list_projects,
    output_dict,
    session_summary,
)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["all", "current", "selected"], default="all")
    ap.add_argument("--project")
    ap.add_argument("--project-contains", dest="project_contains")
    ap.add_argument("--out")
    ap.add_argument("--list-projects", action="store_true")
    ap.add_argument("--count-only", action="store_true")
    args = ap.parse_args(argv)

    pairs = list(gather_all())
    sessions = [s for _, s in pairs]

    if args.list_projects:
        for p in list_projects(sessions):
            print(p)
        return 0

    selected = filter_by_mode(sessions, args.mode, args.project)
    if args.project_contains:
        selected = filter_by_contains(selected, args.project_contains)

    if args.count_only:
        providers = sorted({s.provider for s in selected})
        print(json.dumps({"sessions": len(selected), "providers": providers}))
        return 0

    if not args.out:
        ap.error("--out DIR is required unless --count-only/--list-projects")
    os.makedirs(args.out, exist_ok=True)
    manifest = []
    for s in selected:
        safe = f"{s.provider}__{s.session_id}".replace(os.sep, "_").replace("/", "_")
        safe = os.path.basename(safe).replace("..", "_")  # no path traversal
        file_name = safe + ".json"
        data = json.dumps(output_dict(s), ensure_ascii=False)
        with open(os.path.join(args.out, file_name), "w", encoding="utf-8") as f:
            f.write(data)
        manifest.append(session_summary(s, file_name, len(data.encode("utf-8"))))
    # Manifest lets the orchestrator plan balanced, size-proportional extraction:
    # coverage across projects/time buckets + extraction depth scaled to turn count.
    manifest.sort(key=lambda m: (m["started_at"] or "", m["project"] or ""))
    with open(os.path.join(args.out, "_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(json.dumps({"written": len(manifest), "out": args.out, "manifest": "_manifest.json"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
