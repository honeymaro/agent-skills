from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Turn:
    role: str          # "user" | "assistant"
    text: str


@dataclass
class NormalizedSession:
    provider: str
    session_id: str
    project: Optional[str]
    started_at: Optional[str]
    turns: list[Turn] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "session_id": self.session_id,
            "project": self.project,
            "started_at": self.started_at,
            "turns": [asdict(t) for t in self.turns],
        }
