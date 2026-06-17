from __future__ import annotations
from pathlib import Path
from ctk.base import FlexibleMessageSqliteAdapter


class CrushAdapter(FlexibleMessageSqliteAdapter):
    """Crush: SQLite at ~/.crush/crush.db (+ project-local .crush/crush.db).

    Conversations live in a `messages` table whose exact column names vary;
    the shared FlexibleMessageSqliteAdapter discovers them via PRAGMA table_info
    and yields nothing if the table/columns are absent.

    Validated against a synthetic `messages` table in tests/test_crush.py."""

    name = "crush"

    def db_paths(self) -> list:
        if self._paths is not None:
            return list(self._paths)
        return [
            str(Path.home() / ".crush" / "crush.db"),
            str(Path.cwd() / ".crush" / "crush.db"),
        ]
