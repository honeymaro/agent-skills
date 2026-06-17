from __future__ import annotations
import os
import re
from ctk.registry import supported_adapters


def gather_all():
    """Yield (adapter, NormalizedSession) for every detected session.

    Each adapter is isolated: a failure in one adapter's detect()/parse()
    (e.g. a malformed DB raising RecursionError/PermissionError) is skipped
    rather than aborting enumeration of the remaining adapters.
    """
    for adapter in supported_adapters():
        try:
            paths = adapter.detect()
        except Exception:
            continue
        for path in paths:
            try:
                for session in adapter.parse(path):
                    yield adapter, session
            except Exception:
                continue


def project_alias(project):
    """Readable project label: the leaf folder name (= product/repo name), with
    the username-bearing full path dropped. Internal product names are kept on
    purpose — the report is for teammates; use sanitize --known-names to mask
    company/product names when sharing externally. None stays None."""
    if not project:
        return None
    leaf = re.split(r"[\\/]", project.rstrip("\\/"))[-1]
    return leaf or project


def output_dict(session):
    """Session as a dict for emission. The project path is reduced to its leaf
    name so the username and full filesystem path (PII) never reach the
    extraction step, while the product/repo name is preserved for context."""
    d = session.to_dict()
    d["project"] = project_alias(d.get("project"))
    return d


def session_summary(session, file_name, byte_size):
    """Per-session metadata for the manifest the orchestrator reads to plan
    balanced, size-proportional extraction (coverage across projects/time +
    extraction depth scaled to session size)."""
    return {
        "file": file_name,
        "provider": session.provider,
        "project": project_alias(session.project),
        "started_at": session.started_at,
        "turns": len(session.turns),
        "bytes": byte_size,
    }


def _norm(p):
    return os.path.normcase(os.path.abspath(p)) if p else p


def filter_by_mode(sessions, mode, project):
    if mode == "all":
        return list(sessions)
    if mode in ("current", "selected"):
        target = _norm(project)
        return [s for s in sessions if s.project and _norm(s.project) == target]
    raise ValueError(f"unknown mode: {mode}")


def filter_by_contains(sessions, substr):
    """Keep sessions whose project path contains `substr` (case-insensitive).
    Use for directory-scope selection, e.g. all projects under a parent dir."""
    if not substr:
        return list(sessions)
    needle = substr.lower()
    return [s for s in sessions if s.project and needle in s.project.lower()]


def list_projects(sessions):
    seen = set()
    out = []
    for s in sessions:
        if s.project and s.project not in seen:
            seen.add(s.project)
            out.append(s.project)
    return out
