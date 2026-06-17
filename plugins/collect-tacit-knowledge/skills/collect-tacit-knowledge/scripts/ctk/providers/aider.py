from __future__ import annotations
from pathlib import Path
from typing import Iterable, Optional
from ctk.base import ProviderAdapter
from ctk.model import NormalizedSession, Turn
from ctk.text import clean


class AiderAdapter(ProviderAdapter):
    """Aider: per-project `.aider.chat.history.md` (Markdown).

    Aider's convention in the history file:
    - `# aider chat started at <ts>` lines mark a new run (used as a turn break,
      not a session split — one file == one session here).
    - Lines beginning with `#### ` are USER messages (the `####` prefix is
      stripped). Consecutive `####` lines form one user turn.
    - All other prose is ASSISTANT output. `>` lines are command echoes/tool
      output and are dropped. Fenced code blocks are kept verbatim in the buffer
      and then reduced by clean() (long fences -> "[code omitted]").

    Parses into alternating user/assistant turns and yields ONE
    NormalizedSession. detect() finds the file under Path.home() and Path.cwd()."""

    name = "aider"

    def detect(self) -> list:
        out = []
        for base in (Path.home(), Path.cwd()):
            p = base / ".aider.chat.history.md"
            if p.exists() and str(p) not in out:
                out.append(str(p))
        return out

    def parse(self, path) -> Iterable[NormalizedSession]:
        path = Path(path)
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return

        turns = []
        cur_role = None
        buf = []

        def flush():
            if cur_role is None:
                return
            text = clean("\n".join(buf).strip())
            if text.strip():
                turns.append(Turn(role=cur_role, text=text))

        in_fence = False
        for line in raw.splitlines():
            stripped = line.strip()

            # Track fenced code blocks so a "####"/">" inside code isn't mistaken
            # for a header.
            if stripped.startswith("```"):
                if cur_role is None:
                    cur_role = "assistant"
                    buf = []
                in_fence = not in_fence
                buf.append(line)
                continue

            if not in_fence:
                # Aider run banner — a turn boundary, not content.
                if stripped.startswith("# aider chat started at"):
                    flush()
                    cur_role = None
                    buf = []
                    continue
                # User message line.
                if line.startswith("#### "):
                    if cur_role != "user":
                        flush()
                        cur_role = "user"
                        buf = []
                    buf.append(line[len("#### "):])
                    continue
                if stripped == "####":
                    if cur_role != "user":
                        flush()
                        cur_role = "user"
                        buf = []
                    buf.append("")
                    continue
                # `>` lines are command echoes / tool output -> drop.
                if stripped.startswith(">"):
                    continue

            # Anything else is assistant prose (or inside a fence).
            if cur_role is None:
                cur_role = "assistant"
                buf = []
            if cur_role == "user" and not in_fence and stripped == "":
                # blank line after a user block: keep accumulating user lines
                buf.append("")
                continue
            if cur_role == "user" and not in_fence:
                # non-#### prose right after user header -> assistant turn begins
                flush()
                cur_role = "assistant"
                buf = []
            buf.append(line)

        flush()

        if not turns:
            return
        yield NormalizedSession(
            provider=self.name,
            session_id=self.session_id(path),
            project=str(path.parent),
            started_at=None,
            turns=turns,
        )

    def session_id(self, path) -> str:
        return str(Path(path).parent.name) or Path(path).stem
