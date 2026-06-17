from __future__ import annotations
from pathlib import Path
from ctk.base import FlexibleMessageSqliteAdapter


class HermesAdapter(FlexibleMessageSqliteAdapter):
    """Hermes: SQLite at ~/.hermes/state.db (+ project-local .hermes/state.db).

    Conversations live in a `messages` table whose exact column names vary;
    the shared FlexibleMessageSqliteAdapter discovers them via PRAGMA table_info
    and yields nothing if the table/columns are absent.

    Validated against a synthetic `messages` table in tests/test_hermes.py."""

    name = "hermes"

    def db_paths(self) -> list:
        if self._paths is not None:
            return list(self._paths)
        return [
            str(Path.home() / ".hermes" / "state.db"),
            str(Path.cwd() / ".hermes" / "state.db"),
        ]
