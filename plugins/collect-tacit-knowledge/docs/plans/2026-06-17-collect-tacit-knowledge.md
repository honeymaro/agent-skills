# collect-tacit-knowledge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a distributable agent skill that mines transferable know-how (tacit knowledge) from local LLM-CLI conversation logs across many tools and emits one anonymized, shareable one-page markdown report.

**Architecture:** A pure-Python-stdlib normalization layer (pluggable `ProviderAdapter` registry → `NormalizedSession`) reduces volume and strips code/secrets. A map-reduce agent pipeline (parallel extraction subagents → cluster/rank → assemble) builds the report. A 3-layer privacy defense (normalize-strip → extraction-abstract → sanitize-rescan) keeps credentials/proper-nouns/source/PII out. SKILL.md orchestrates.

**Tech Stack:** Python 3 standard library only (`json`, `sqlite3`, `pathlib`, `glob`, `re`, `unittest`). No `pip install`. Markdown skill + reference prompts.

**Phasing:**
- **Phase 1 (Tasks 0–11):** Vertical slice — bases, helpers, the verified **Claude Code** adapter, normalize CLI, sanitize, references, SKILL.md, README. Produces a working skill on Claude Code alone.
- **Phase 2 (Tasks 12–18):** Add remaining adapters (Codex, Copilot CLI, Factory, OpenClaw, Kimi, Vibe, Cursor, OpenCode, Crush, Hermes, Gemini, Qwen, Aider) on the shared bases.

**Conventions for every task:** all paths are relative to the project root `collect-tacit-knowledge/`. Run tests with `python -m unittest discover -s tests -v`. Commit messages follow Conventional Commits. Do **not** run `git init`/commit until Task 0 Step 1 confirms the repo is initialized.

---

## File Structure

```
collect-tacit-knowledge/
  SKILL.md                       # orchestration (skill entry point)            [Task 10]
  README.md                      # OSS install/use/add-a-provider docs           [Task 11]
  scripts/
    normalize.py                 # CLI: registry + modes + emit sessions         [Task 9]
    sanitize.py                  # CLI: leak rescan / mask                        [Task 8]
    ctk/                         # importable package (collect-tacit-knowledge)
      __init__.py
      model.py                   # Turn, NormalizedSession dataclasses           [Task 2]
      text.py                    # text extraction, code-strip, secret-mask       [Task 3]
      base.py                    # ProviderAdapter, JsonlFileSessionAdapter,
                                 #   SqliteAdapter                                [Tasks 4,5,6]
      registry.py                # ADAPTERS list + helpers                        [Task 7]
      providers/
        __init__.py
        claude_code.py           # Tier 1 (VERIFIED)                             [Task 7]
        codex.py                 # Tier 1 (jsonl rollout + legacy sqlite)        [Task 12]
        copilot_cli.py           # Tier 1                                         [Task 13]
        factory.py openclaw.py kimi.py vibe.py   # Tier 1                         [Task 14]
        cursor.py opencode.py crush.py hermes.py # Tier 2 (sqlite)               [Tasks 15,16]
        gemini.py qwen.py aider.py               # Tier 3 (json/md)              [Tasks 17,18]
  references/
    extraction-prompt.md         # map-step subagent prompt                      [Task 1a... -> Task 10 prep]
    report-template.md           # report layout                                 [Task 10 prep]
  tests/
    fixtures/                    # sample logs + planted secrets
    test_model.py test_text.py test_base.py test_claude_code.py
    test_sanitize.py test_registry.py ...
  docs/
    specs/2026-06-17-collect-tacit-knowledge-design.md   # (exists)
    plans/2026-06-17-collect-tacit-knowledge.md          # (this file)
```

---

## Task 0: Project scaffolding

**Files:**
- Create: `.gitignore`, `scripts/ctk/__init__.py`, `scripts/ctk/providers/__init__.py`, `tests/__init__.py`, `tests/fixtures/.gitkeep`

- [ ] **Step 1: Confirm/initialize git repo**

Run: `git -C . rev-parse --is-inside-work-tree 2>/dev/null || echo "NO_REPO"`
If output is `NO_REPO`, ask the user for permission to `git init` (per user's no-git-without-ask rule), then: `git init`.
Expected: a git repo at project root.

- [ ] **Step 2: Create package + test directories with init files**

Create `scripts/ctk/__init__.py`:
```python
"""collect-tacit-knowledge core package (stdlib only)."""
```
Create `scripts/ctk/providers/__init__.py`:
```python
"""Provider adapters."""
```
Create `tests/__init__.py` (empty file).
Create `tests/fixtures/.gitkeep` (empty file).

- [ ] **Step 3: Create `.gitignore`**

```gitignore
__pycache__/
*.pyc
.ctk-work/
*.report.md
.DS_Store
```

- [ ] **Step 4: Verify unittest discovery works on empty tree**

Run: `python -m unittest discover -s tests -v`
Expected: `Ran 0 tests` (no error).

- [ ] **Step 5: Commit**

```bash
git add .gitignore scripts/ctk tests
git commit -m "chore: scaffold collect-tacit-knowledge package and test layout"
```

---

## Task 1: Map-step extraction prompt (reference doc)

This is content, not code, but it is the contract the extraction subagents follow. Writing it first locks the `NormalizedSession`-in / candidate-JSON-out interface used by later tasks.

**Files:**
- Create: `references/extraction-prompt.md`

- [ ] **Step 1: Write `references/extraction-prompt.md`**

```markdown
# Tacit-Knowledge Extraction Prompt (map step)

You are given the normalized transcript of ONE LLM-CLI session as JSON:
`{ "provider", "session_id", "project", "turns": [ {"role","text"}, ... ] }`.

Your job: extract **transferable know-how** a teammate could reuse. Return ONLY a JSON
array of candidate objects. No prose.

Each candidate:
{
  "category": "tool-workflow" | "tech-decision" | "pitfall" | "domain" | "style",
  "claim":     "<one abstracted, reusable sentence>",
  "rationale": "<why / when to apply>",
  "evidence":  { "project": "<generalized alias>", "signal": "<frequency or context>" }
}

ABSOLUTE PRIVACY RULES (a violation makes the whole report unusable):
- NEVER copy secrets, API keys, tokens, passwords, connection strings, or .env values.
- NEVER copy real personal names, company names, client names, or unreleased product
  names. GENERALIZE them. Example: "Acme Corp's order-fulfillment pipeline" ->
  "an order-fulfillment pipeline".
- NEVER copy source code bodies. Describe the pattern, not the code.
- NEVER include emails, IPs, hostnames, or filesystem paths containing a username.

QUALITY RULES:
- Prefer durable, generalizable lessons over one-off task facts.
- If the session contains no transferable know-how, return `[]`.
- `evidence.project` must be a generalized alias, never a raw path or client name.
```

- [ ] **Step 2: Commit**

```bash
git add references/extraction-prompt.md
git commit -m "docs: add map-step extraction prompt contract"
```

---

## Task 2: Core data model

**Files:**
- Create: `scripts/ctk/model.py`
- Test: `tests/test_model.py`

- [ ] **Step 1: Write the failing test**

`tests/test_model.py`:
```python
import unittest
from ctk.model import Turn, NormalizedSession


class TestModel(unittest.TestCase):
    def test_to_dict_roundtrips_turns(self):
        s = NormalizedSession(
            provider="claude-code",
            session_id="abc",
            project="/home/u/proj",
            started_at="2026-06-17T00:00:00Z",
            turns=[Turn(role="user", text="hi"), Turn(role="assistant", text="yo")],
        )
        d = s.to_dict()
        self.assertEqual(d["provider"], "claude-code")
        self.assertEqual(d["turns"], [
            {"role": "user", "text": "hi"},
            {"role": "assistant", "text": "yo"},
        ])

    def test_defaults_empty_turns(self):
        s = NormalizedSession(provider="x", session_id="y", project=None, started_at=None)
        self.assertEqual(s.turns, [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_model -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ctk'` (or import error). Note: tests import `ctk`, so they must run with `scripts/` on `PYTHONPATH`. Fix in Step 3b.

- [ ] **Step 3: Write `scripts/ctk/model.py`**

```python
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
    turns: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "session_id": self.session_id,
            "project": self.project,
            "started_at": self.started_at,
            "turns": [asdict(t) for t in self.turns],
        }
```

- [ ] **Step 3b: Make `ctk` importable from tests**

Create `tests/conftestpath.py` is NOT used (no pytest). Instead create `tests/_path.py`:
```python
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
```
Add to the TOP of every test file (above other imports):
```python
import tests._path  # noqa: F401  (puts scripts/ on sys.path)
```
Update `tests/test_model.py` to start with that import line.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_model -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/ctk/model.py tests/test_model.py tests/_path.py
git commit -m "feat: add NormalizedSession/Turn data model"
```

---

## Task 3: Text helpers — extraction, code-strip, secret-mask (privacy layer 1)

**Files:**
- Create: `scripts/ctk/text.py`
- Test: `tests/test_text.py`

- [ ] **Step 1: Write the failing test**

`tests/test_text.py`:
```python
import tests._path  # noqa: F401
import unittest
from ctk.text import extract_text, strip_code_blocks, mask_secrets, clean


class TestText(unittest.TestCase):
    def test_extract_from_string(self):
        self.assertEqual(extract_text("hello"), "hello")

    def test_extract_from_blocks_keeps_only_text(self):
        content = [
            {"type": "text", "text": "do the thing"},
            {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}},
            {"type": "tool_result", "content": "huge file dump"},
            {"type": "thinking", "thinking": "secret reasoning"},
        ]
        self.assertEqual(extract_text(content), "do the thing")

    def test_strip_long_code_block(self):
        code = "```python\n" + ("x = 1\n" * 50) + "```"
        out = strip_code_blocks(code, max_chars=40)
        self.assertIn("[code omitted]", out)
        self.assertNotIn("x = 1", out)

    def test_keep_short_inline_snippet(self):
        text = "use `pnpm i` to install"
        self.assertEqual(strip_code_blocks(text, max_chars=40), text)

    def test_mask_api_key(self):
        out = mask_secrets("key sk-ABCDEF0123456789ABCDEF0123 done")
        self.assertNotIn("ABCDEF0123456789", out)
        self.assertIn("[redacted]", out)

    def test_mask_env_assignment(self):
        out = mask_secrets("SECRET_TOKEN=hunter2supersecretvalue")
        self.assertNotIn("hunter2supersecretvalue", out)

    def test_clean_composes_strip_and_mask(self):
        # code block must exceed clean()'s default 200-char threshold to be omitted
        text = "AWS_SECRET=abcd1234abcd1234abcd\n```\n" + ("y\n" * 200) + "```"
        out = clean(text)
        self.assertNotIn("abcd1234abcd1234abcd", out)
        self.assertIn("[code omitted]", out)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_text -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ctk.text'`.

- [ ] **Step 3: Write `scripts/ctk/text.py`**

```python
from __future__ import annotations
import re

CODE_FENCE = re.compile(r"```.*?```", re.DOTALL)

# Secret patterns (conservative; layer-1 only — sanitize.py rescans later).
_SECRET_PATTERNS = [
    re.compile(r"\b(sk|pk|rk|ghp|gho|ghs|xox[baprs])[-_][A-Za-z0-9\-_]{16,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),                       # AWS access key id
    re.compile(r"\bBearer\s+[A-Za-z0-9\-._~+/]{16,}=*", re.I),  # bearer tokens
    re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b"),  # JWT
    # KEY=VALUE where key name looks sensitive
    re.compile(
        r"\b([A-Z0-9_]*(SECRET|TOKEN|PASSWORD|PASSWD|APIKEY|API_KEY|PRIVATE_KEY)[A-Z0-9_]*)\s*[:=]\s*\S+",
        re.I,
    ),
    re.compile(r"\b[A-Fa-f0-9]{40,}\b"),                        # long hex blobs
]


def extract_text(content) -> str:
    """Return only human/assistant text. Drop tool_use/tool_result/thinking blocks."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(p for p in parts if p)
    return ""


def strip_code_blocks(text: str, max_chars: int = 200) -> str:
    """Replace fenced code blocks longer than max_chars with a placeholder."""
    def repl(m):
        block = m.group(0)
        return block if len(block) <= max_chars else "[code omitted]"
    return CODE_FENCE.sub(repl, text)


def mask_secrets(text: str) -> str:
    out = text
    for pat in _SECRET_PATTERNS:
        out = pat.sub("[redacted]", out)
    return out


def clean(text: str, max_code_chars: int = 200) -> str:
    return mask_secrets(strip_code_blocks(text, max_chars=max_code_chars))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_text -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/ctk/text.py tests/test_text.py
git commit -m "feat: add text extraction, code-strip, secret-mask (privacy layer 1)"
```

---

## Task 4: ProviderAdapter base + JsonlFileSessionAdapter

**Files:**
- Create: `scripts/ctk/base.py`
- Test: `tests/test_base.py`

- [ ] **Step 1: Write the failing test**

`tests/test_base.py`:
```python
import tests._path  # noqa: F401
import os
import tempfile
import unittest
from ctk.base import JsonlFileSessionAdapter
from ctk.model import Turn


class _FakeAdapter(JsonlFileSessionAdapter):
    name = "fake"

    def __init__(self, files):
        self._files = files

    def session_files(self):
        return self._files

    def turn_of(self, rec):
        if rec.get("role") in ("user", "assistant"):
            return Turn(role=rec["role"], text=rec.get("text", ""))
        return None

    def project_path(self, path, first):
        return (first or {}).get("cwd")


class TestJsonlBase(unittest.TestCase):
    def _write(self, lines):
        fd, p = tempfile.mkstemp(suffix=".jsonl")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return p

    def test_parses_turns_and_skips_noise_and_bad_lines(self):
        p = self._write([
            '{"role": "user", "text": "hi", "cwd": "/proj"}',
            'NOT JSON',
            '{"role": "system", "text": "ignore me"}',
            '{"role": "assistant", "text": "hello"}',
            '',
        ])
        adapter = _FakeAdapter([p])
        sessions = list(adapter.parse(p))
        self.assertEqual(len(sessions), 1)
        s = sessions[0]
        self.assertEqual([t.role for t in s.turns], ["user", "assistant"])
        self.assertEqual(s.project, "/proj")
        os.unlink(p)

    def test_empty_session_yields_nothing(self):
        p = self._write(['{"role": "system", "text": "x"}'])
        self.assertEqual(list(_FakeAdapter([p]).parse(p)), [])
        os.unlink(p)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_base -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ctk.base'`.

- [ ] **Step 3: Write `scripts/ctk/base.py`**

```python
from __future__ import annotations
import json
from pathlib import Path
from typing import Iterable, Optional
from ctk.model import NormalizedSession, Turn


class ProviderAdapter:
    name: str = "base"

    def detect(self) -> list:
        """Return session file/db paths that exist for this tool ([] if not installed)."""
        raise NotImplementedError

    def parse(self, path) -> Iterable[NormalizedSession]:
        raise NotImplementedError

    def project_of(self, session: NormalizedSession) -> Optional[str]:
        return session.project

    def supported(self) -> bool:
        """False for encrypted/undocumented providers that should be skipped."""
        return True


class JsonlFileSessionAdapter(ProviderAdapter):
    """One .jsonl file == one session. Each line is a record; subclasses map records."""

    def session_files(self) -> list:
        raise NotImplementedError

    def detect(self) -> list:
        return list(self.session_files())

    def parse(self, path) -> Iterable[NormalizedSession]:
        path = Path(path)
        turns = []
        first = None
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except (ValueError, json.JSONDecodeError):
                continue
            if first is None:
                first = rec
            turn = self.turn_of(rec)
            if turn is not None and turn.text and turn.text.strip():
                turns.append(turn)
        if not turns:
            return
        yield NormalizedSession(
            provider=self.name,
            session_id=self.session_id(path, first),
            project=self.project_path(path, first),
            started_at=self.started_at(path, first),
            turns=turns,
        )

    # ---- hooks for subclasses ----
    def turn_of(self, rec) -> Optional[Turn]:
        raise NotImplementedError

    def session_id(self, path, first) -> str:
        return Path(path).stem

    def project_path(self, path, first) -> Optional[str]:
        return None

    def started_at(self, path, first) -> Optional[str]:
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_base -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/ctk/base.py tests/test_base.py
git commit -m "feat: add ProviderAdapter + JsonlFileSessionAdapter base"
```

---

## Task 5: SqliteAdapter base

**Files:**
- Modify: `scripts/ctk/base.py` (append `SqliteAdapter`)
- Test: `tests/test_sqlite_base.py`

- [ ] **Step 1: Write the failing test**

`tests/test_sqlite_base.py`:
```python
import tests._path  # noqa: F401
import os
import sqlite3
import tempfile
import unittest
from ctk.base import SqliteAdapter
from ctk.model import Turn


class _FakeSqlite(SqliteAdapter):
    name = "fakedb"

    def __init__(self, paths):
        self._paths = paths

    def db_paths(self):
        return self._paths

    def iter_sessions(self, conn, path):
        rows = conn.execute(
            "SELECT session_id, role, text FROM msg ORDER BY id"
        ).fetchall()
        by_sid = {}
        for sid, role, text in rows:
            by_sid.setdefault(sid, []).append(Turn(role=role, text=text))
        for sid, turns in by_sid.items():
            yield self.make_session(sid, turns, project=None, started_at=None)


class TestSqliteBase(unittest.TestCase):
    def test_reads_sessions_from_db(self):
        fd, p = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        conn = sqlite3.connect(p)
        conn.execute("CREATE TABLE msg (id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, text TEXT)")
        conn.executemany(
            "INSERT INTO msg (session_id, role, text) VALUES (?,?,?)",
            [("s1", "user", "hi"), ("s1", "assistant", "yo"), ("s2", "user", "q")],
        )
        conn.commit()
        conn.close()
        sessions = list(_FakeSqlite([p]).parse(p))
        self.assertEqual(len(sessions), 2)
        self.assertEqual(sessions[0].provider, "fakedb")
        os.unlink(p)

    def test_missing_db_skipped(self):
        self.assertEqual(_FakeSqlite([]).detect(), [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_sqlite_base -v`
Expected: FAIL — `ImportError: cannot import name 'SqliteAdapter'`.

- [ ] **Step 3: Append `SqliteAdapter` to `scripts/ctk/base.py`**

```python
import sqlite3


class SqliteAdapter(ProviderAdapter):
    """Sessions stored in a SQLite DB. Subclasses implement iter_sessions()."""

    def db_paths(self) -> list:
        raise NotImplementedError

    def detect(self) -> list:
        return [p for p in self.db_paths() if Path(p).exists()]

    def parse(self, path) -> Iterable[NormalizedSession]:
        try:
            conn = sqlite3.connect(f"file:{Path(path)}?mode=ro", uri=True)
        except sqlite3.Error:
            return
        try:
            yield from self.iter_sessions(conn, Path(path))
        except sqlite3.Error:
            return
        finally:
            conn.close()

    def iter_sessions(self, conn, path) -> Iterable[NormalizedSession]:
        raise NotImplementedError

    def make_session(self, session_id, turns, project=None, started_at=None) -> NormalizedSession:
        return NormalizedSession(
            provider=self.name,
            session_id=str(session_id),
            project=project,
            started_at=started_at,
            turns=list(turns),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_sqlite_base -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/ctk/base.py tests/test_sqlite_base.py
git commit -m "feat: add SqliteAdapter base (read-only)"
```

---

## Task 6: Claude Code adapter (VERIFIED reference adapter)

**Files:**
- Create: `scripts/ctk/providers/claude_code.py`
- Create: `tests/fixtures/claude_code_session.jsonl`
- Test: `tests/test_claude_code.py`

- [ ] **Step 1: Create the fixture (mirrors real Claude Code format)**

`tests/fixtures/claude_code_session.jsonl`:
```jsonl
{"type":"user","cwd":"/home/u/projects/demo","sessionId":"sess-123","timestamp":"2026-06-17T09:00:00Z","message":{"role":"user","content":"Cache big Float32 arrays. My key is sk-ABCDEF0123456789ABCDEF0123."}}
{"type":"assistant","sessionId":"sess-123","timestamp":"2026-06-17T09:00:05Z","message":{"role":"assistant","content":[{"type":"text","text":"Use OPFS over IndexedDB for large numeric blobs."},{"type":"tool_use","name":"Bash","input":{"command":"ls"}}]}}
{"type":"file-history-snapshot","snapshot":{"huge":"noise"}}
{"type":"user","sessionId":"sess-123","timestamp":"2026-06-17T09:00:10Z","message":{"role":"user","content":[{"type":"tool_result","content":"<10kb of file dump>"},{"type":"text","text":"Thanks, it works."}]}}
```

- [ ] **Step 2: Write the failing test**

`tests/test_claude_code.py`:
```python
import tests._path  # noqa: F401
import os
import unittest
from ctk.providers.claude_code import ClaudeCodeAdapter

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "claude_code_session.jsonl")


class TestClaudeCode(unittest.TestCase):
    def test_parses_only_text_turns(self):
        sessions = list(ClaudeCodeAdapter().parse(FIXTURE))
        self.assertEqual(len(sessions), 1)
        s = sessions[0]
        self.assertEqual(s.provider, "claude-code")
        self.assertEqual(s.session_id, "sess-123")
        self.assertEqual(s.project, "/home/u/projects/demo")
        self.assertEqual(s.started_at, "2026-06-17T09:00:00Z")
        # 3 text-bearing turns (user, assistant text-only, user text-only)
        self.assertEqual([t.role for t in s.turns], ["user", "assistant", "user"])

    def test_secret_is_masked_and_no_tool_noise(self):
        s = list(ClaudeCodeAdapter().parse(FIXTURE))[0]
        joined = "\n".join(t.text for t in s.turns)
        self.assertNotIn("sk-ABCDEF0123456789", joined)
        self.assertNotIn("file dump", joined)
        self.assertNotIn("ls", joined.split("\n")[1] if len(joined.split("\n")) > 1 else "")
        self.assertIn("OPFS", joined)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m unittest tests.test_claude_code -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ctk.providers.claude_code'`.

- [ ] **Step 4: Write `scripts/ctk/providers/claude_code.py`**

```python
from __future__ import annotations
from pathlib import Path
from typing import Optional
from ctk.base import JsonlFileSessionAdapter
from ctk.model import Turn
from ctk.text import extract_text, clean


class ClaudeCodeAdapter(JsonlFileSessionAdapter):
    name = "claude-code"

    def session_files(self) -> list:
        base = Path.home() / ".claude" / "projects"
        if not base.exists():
            return []
        return sorted(base.glob("*/*.jsonl"))

    def turn_of(self, rec) -> Optional[Turn]:
        if rec.get("type") not in ("user", "assistant"):
            return None
        msg = rec.get("message")
        if not isinstance(msg, dict):
            return None
        role = msg.get("role")
        if role not in ("user", "assistant"):
            return None
        text = clean(extract_text(msg.get("content")))
        if not text.strip():
            return None
        return Turn(role=role, text=text)

    def session_id(self, path, first) -> str:
        sid = (first or {}).get("sessionId")
        return sid or Path(path).stem

    def project_path(self, path, first) -> Optional[str]:
        return (first or {}).get("cwd")

    def started_at(self, path, first) -> Optional[str]:
        return (first or {}).get("timestamp")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m unittest tests.test_claude_code -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Smoke-test against real local data (manual, read-only)**

Run: `python -c "import sys; sys.path.insert(0,'scripts'); from ctk.providers.claude_code import ClaudeCodeAdapter; a=ClaudeCodeAdapter(); fs=a.detect(); print('files:',len(fs)); print('sessions in first:', sum(1 for _ in a.parse(fs[0])) if fs else 0)"`
Expected: prints a nonzero file count on a machine with Claude Code history; no crash.

- [ ] **Step 7: Commit**

```bash
git add scripts/ctk/providers/claude_code.py tests/test_claude_code.py tests/fixtures/claude_code_session.jsonl
git commit -m "feat: add verified Claude Code provider adapter"
```

---

## Task 7: Adapter registry

**Files:**
- Create: `scripts/ctk/registry.py`
- Test: `tests/test_registry.py`

- [ ] **Step 1: Write the failing test**

`tests/test_registry.py`:
```python
import tests._path  # noqa: F401
import unittest
from ctk.registry import all_adapters, supported_adapters
from ctk.providers.claude_code import ClaudeCodeAdapter


class TestRegistry(unittest.TestCase):
    def test_includes_claude_code(self):
        names = {a.name for a in all_adapters()}
        self.assertIn("claude-code", names)

    def test_supported_excludes_unsupported(self):
        for a in supported_adapters():
            self.assertTrue(a.supported())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_registry -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ctk.registry'`.

- [ ] **Step 3: Write `scripts/ctk/registry.py`**

```python
from __future__ import annotations
from ctk.providers.claude_code import ClaudeCodeAdapter

# Phase 2 adapters get appended here as they are implemented.
_ADAPTER_CLASSES = [
    ClaudeCodeAdapter,
]


def all_adapters() -> list:
    return [cls() for cls in _ADAPTER_CLASSES]


def supported_adapters() -> list:
    return [a for a in all_adapters() if a.supported()]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_registry -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/ctk/registry.py tests/test_registry.py
git commit -m "feat: add adapter registry"
```

---

## Task 8: sanitize.py — leak rescan (privacy layer 3)

**Files:**
- Create: `scripts/sanitize.py`
- Test: `tests/test_sanitize.py`

- [ ] **Step 1: Write the failing test**

`tests/test_sanitize.py`:
```python
import tests._path  # noqa: F401
import unittest
from ctk.sanitize import find_leaks, mask_report


class TestSanitize(unittest.TestCase):
    def test_finds_email_key_ip(self):
        text = "contact a@b.com via 10.0.0.5 with sk-ABCDEF0123456789ABCDEF0123"
        kinds = {f["kind"] for f in find_leaks(text)}
        self.assertIn("email", kinds)
        self.assertIn("ip", kinds)
        self.assertIn("secret", kinds)

    def test_known_names_flagged(self):
        text = "We used the AcmeCorp internal API."
        kinds = {f["kind"] for f in find_leaks(text, known_names=["AcmeCorp"])}
        self.assertIn("known-name", kinds)

    def test_mask_replaces_all(self):
        text = "a@b.com and AcmeCorp"
        masked = mask_report(text, known_names=["AcmeCorp"])
        self.assertNotIn("a@b.com", masked)
        self.assertNotIn("AcmeCorp", masked)
        self.assertEqual(find_leaks(masked, known_names=["AcmeCorp"]), [])

    def test_clean_report_has_no_findings(self):
        self.assertEqual(find_leaks("Use OPFS for big numeric caches."), [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_sanitize -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ctk.sanitize'`.

- [ ] **Step 3: Write `scripts/ctk/sanitize.py`**

```python
from __future__ import annotations
import re
from ctk.text import _SECRET_PATTERNS

EMAIL = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
HOME_USER = re.compile(r"(?:/home/|/Users/|\\Users\\)([A-Za-z0-9_.\-]+)")


def find_leaks(text: str, known_names=None) -> list:
    findings = []
    for m in EMAIL.finditer(text):
        findings.append({"kind": "email", "value": m.group(0)})
    for m in IPV4.finditer(text):
        findings.append({"kind": "ip", "value": m.group(0)})
    for m in HOME_USER.finditer(text):
        findings.append({"kind": "path-username", "value": m.group(0)})
    for pat in _SECRET_PATTERNS:
        for m in pat.finditer(text):
            findings.append({"kind": "secret", "value": m.group(0)})
    for name in (known_names or []):
        if name and name in text:
            findings.append({"kind": "known-name", "value": name})
    return findings


def mask_report(text: str, known_names=None) -> str:
    out = EMAIL.sub("[email]", text)
    out = IPV4.sub("[ip]", out)
    out = HOME_USER.sub(r"[user]", out)
    for pat in _SECRET_PATTERNS:
        out = pat.sub("[redacted]", out)
    for name in (known_names or []):
        if name:
            out = out.replace(name, "[name]")
    return out
```

- [ ] **Step 4: Write the CLI wrapper `scripts/sanitize.py`**

```python
#!/usr/bin/env python3
"""Rescan a report for leaks; optionally mask them. stdlib only."""
from __future__ import annotations
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from ctk.sanitize import find_leaks, mask_report


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("report", help="path to report markdown")
    ap.add_argument("--known-names", help="path to newline-separated names file")
    ap.add_argument("--mask", action="store_true", help="write masked report back")
    args = ap.parse_args(argv)

    names = []
    if args.known_names and os.path.exists(args.known_names):
        names = [l.strip() for l in open(args.known_names, encoding="utf-8") if l.strip()]

    text = open(args.report, encoding="utf-8").read()
    findings = find_leaks(text, known_names=names)

    if args.mask:
        masked = mask_report(text, known_names=names)
        open(args.report, "w", encoding="utf-8").write(masked)
        print(json.dumps({"masked": True, "found": len(findings)}))
        return 0

    print(json.dumps({"found": len(findings), "findings": findings}, ensure_ascii=False))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m unittest tests.test_sanitize -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add scripts/ctk/sanitize.py scripts/sanitize.py tests/test_sanitize.py
git commit -m "feat: add sanitize leak rescan + CLI (privacy layer 3)"
```

---

## Task 9: normalize.py — CLI orchestrator (modes + emit)

**Files:**
- Create: `scripts/normalize.py`
- Create: `scripts/ctk/collect.py` (mode/filter logic, testable)
- Test: `tests/test_collect.py`

- [ ] **Step 1: Write the failing test**

`tests/test_collect.py`:
```python
import tests._path  # noqa: F401
import unittest
from ctk.model import NormalizedSession, Turn
from ctk.collect import filter_by_mode, list_projects


def _s(provider, project):
    return NormalizedSession(provider, "id", project, None, [Turn("user", "x")])


class TestCollect(unittest.TestCase):
    def test_all_mode_keeps_everything(self):
        sessions = [_s("a", "/p1"), _s("b", "/p2")]
        self.assertEqual(len(filter_by_mode(sessions, "all", None)), 2)

    def test_current_mode_matches_cwd(self):
        sessions = [_s("a", "/home/u/p1"), _s("b", "/home/u/p2")]
        out = filter_by_mode(sessions, "current", "/home/u/p1")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].project, "/home/u/p1")

    def test_selected_mode_matches_project(self):
        sessions = [_s("a", "/p1"), _s("b", "/p2")]
        out = filter_by_mode(sessions, "selected", "/p2")
        self.assertEqual(len(out), 1)

    def test_list_projects_dedups(self):
        sessions = [_s("a", "/p1"), _s("b", "/p1"), _s("c", "/p2")]
        self.assertEqual(sorted(list_projects(sessions)), ["/p1", "/p2"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_collect -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ctk.collect'`.

- [ ] **Step 3: Write `scripts/ctk/collect.py`**

```python
from __future__ import annotations
import os
from ctk.registry import supported_adapters


def gather_all():
    """Yield (adapter, NormalizedSession) for every detected session."""
    for adapter in supported_adapters():
        for path in adapter.detect():
            for session in adapter.parse(path):
                yield adapter, session


def _norm(p):
    return os.path.normcase(os.path.abspath(p)) if p else p


def filter_by_mode(sessions, mode, project):
    if mode == "all":
        return list(sessions)
    if mode in ("current", "selected"):
        target = _norm(project)
        return [s for s in sessions if s.project and _norm(s.project) == target]
    raise ValueError(f"unknown mode: {mode}")


def list_projects(sessions):
    seen = []
    out = []
    for s in sessions:
        if s.project and s.project not in seen:
            seen.append(s.project)
            out.append(s.project)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_collect -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Write the CLI `scripts/normalize.py`**

```python
#!/usr/bin/env python3
"""Normalize LLM-CLI sessions to JSON. stdlib only.

Modes:
  --mode all                  every detected provider/session
  --mode current --project P  sessions whose project == P
  --mode selected --project P sessions whose project == P (from --list-projects)

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
from ctk.collect import gather_all, filter_by_mode, list_projects


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["all", "current", "selected"], default="all")
    ap.add_argument("--project")
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

    if args.count_only:
        providers = sorted({s.provider for s in selected})
        print(json.dumps({"sessions": len(selected), "providers": providers}))
        return 0

    if not args.out:
        ap.error("--out DIR is required unless --count-only/--list-projects")
    os.makedirs(args.out, exist_ok=True)
    n = 0
    for s in selected:
        safe = f"{s.provider}__{s.session_id}".replace(os.sep, "_").replace("/", "_")
        with open(os.path.join(args.out, safe + ".json"), "w", encoding="utf-8") as f:
            json.dump(s.to_dict(), f, ensure_ascii=False)
        n += 1
    print(json.dumps({"written": n, "out": args.out}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Smoke-test the CLI (manual, read-only)**

Run: `python scripts/normalize.py --count-only`
Expected: JSON like `{"sessions": <N>, "providers": ["claude-code"]}` with no crash.

- [ ] **Step 7: Commit**

```bash
git add scripts/ctk/collect.py scripts/normalize.py tests/test_collect.py
git commit -m "feat: add normalize CLI with all/current/selected modes"
```

---

## Task 10: SKILL.md + report template (orchestration)

**Files:**
- Create: `references/report-template.md`
- Create: `SKILL.md`

- [ ] **Step 1: Write `references/report-template.md`**

```markdown
# Know-How Report — {alias_or_role}
_Generated {date} · Sources: {provider_summary}_

## 🛠 Tools & Workflow
{tool_workflow_bullets}

## ⚙️ Technical Decisions (rationale)
{tech_decision_bullets}

## ⚠️ Pitfalls & Lessons
{pitfall_bullets}

## 📚 Domain Knowledge
{domain_bullets}
```
Each bullet: `- {claim} — {evidence.signal}` (no raw quotes, no proper nouns).

- [ ] **Step 2: Write `SKILL.md`**

```markdown
---
name: collect-tacit-knowledge
description: Use when the user wants to extract shareable know-how (tacit knowledge) from their local LLM-CLI conversation history across tools (Claude Code, Codex, Copilot CLI, etc.) and produce one anonymized one-page report. Triggers — "collect tacit knowledge", "know-how report", "extract know-how from my conversation history", "summarize what I've learned across projects".
---

# collect-tacit-knowledge

Mines transferable know-how from local LLM-CLI logs and produces ONE anonymized, shareable
markdown report. Read-only on all logs. Privacy is non-negotiable (3-layer defense).

## Prerequisite
`python3` on PATH. No `pip install` needed.

## Procedure

1. **Pick a mode** (ask the user):
   - `all` — every detected tool
   - `current` — sessions in the current project (`--project "$(pwd)"`)
   - `selected` — run `python scripts/normalize.py --list-projects`, show the list, let them pick
2. **Confirm scope (cost gate):** run
   `python scripts/normalize.py --mode <mode> [--project P] --count-only`
   Show the user the session count + providers. If large (e.g. >40), offer to narrow scope.
   Proceed only on confirmation.
3. **Normalize:** run
   `python scripts/normalize.py --mode <mode> [--project P] --out .ctk-work/sessions`
4. **Map (parallel extraction):** for each `*.json` in `.ctk-work/sessions/`, dispatch a
   subagent (use `superpowers:dispatching-parallel-agents`) with the contract in
   `references/extraction-prompt.md`. Collect the candidate JSON arrays.
   - Batch small sessions together to respect token budgets.
5. **Reduce:** cluster candidates by meaning, dedupe, rank by frequency/recency across
   sessions and projects, drop one-off/low-signal items.
6. **Assemble:** fill `references/report-template.md` per category. Bullets are abstracted
   claims + evidence signal ONLY. No raw quotes, no proper nouns.
7. **Sanitize (gate):** optionally ask the user for a known-names file (company/client/product
   names) to force-mask. Then run
   `python scripts/sanitize.py <report> [--known-names names.txt]`.
   If findings > 0, re-run with `--mask` and re-review. Then read the report yourself and
   confirm: "is this safe to share outside the team?"
8. **Deliver:** write the final report to a user-chosen path (default `<project>/tacit-knowledge.report.md`)
   and print it.

## Privacy rules (enforce at every step)
- Never let raw secrets, source-code bodies, real names (person/company/client/product),
  emails, IPs, or username paths reach the report.
- Encrypted/undocumented sources are skipped by their adapters; do not try to decrypt.
```

- [ ] **Step 3: Verify SKILL.md frontmatter parses**

Run: `python -c "import re,sys; t=open('SKILL.md',encoding='utf-8').read(); m=re.match(r'^---\n(.*?)\n---', t, re.S); print('OK' if m and 'name: collect-tacit-knowledge' in m.group(1) else 'BAD')"`
Expected: `OK`.

- [ ] **Step 4: Commit**

```bash
git add SKILL.md references/report-template.md
git commit -m "feat: add SKILL.md orchestration and report template"
```

---

## Task 11: README (OSS distribution)

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write `README.md`**

```markdown
# collect-tacit-knowledge

Extract transferable know-how from your local LLM-CLI conversation logs and produce one
anonymized, shareable one-page report. **Read-only. Privacy-first. Python stdlib only.**

## Install
Drop this folder into your agent's skills directory (e.g. `~/.claude/skills/collect-tacit-knowledge/`).
Requires `python3`. No `pip install`.

## Use
Invoke the skill and pick a mode: all tools / current project / a selected project.

## Privacy (3-layer defense)
1. **Normalize** strips code bodies, tool dumps, and obvious secrets before extraction.
2. **Extraction** subagents abstract proper nouns and never copy secrets/code.
3. **Sanitize** rescans the final report for emails/keys/IPs/known names and masks them.
Encrypted sources (e.g. ChatGPT desktop v2+) are not supported and are skipped.

## Supported tools
See `docs/specs/...-design.md` §4. Tier 1 (JSONL): Claude Code, Codex, Copilot CLI, Factory,
OpenClaw, Kimi, Vibe. Tier 2 (SQLite): Cursor, OpenCode, Crush, Hermes. Tier 3 (JSON/MD):
Gemini, Qwen, Aider.

## Add a provider
Subclass `JsonlFileSessionAdapter` or `SqliteAdapter` in `scripts/ctk/providers/`, register
it in `scripts/ctk/registry.py`, add a fixture under `tests/fixtures/`, and a test. See
`scripts/ctk/providers/claude_code.py` as the reference.

## Test
`python -m unittest discover -s tests -v`
```

- [ ] **Step 2: Run the full test suite**

Run: `python -m unittest discover -s tests -v`
Expected: all tests PASS (Phase 1 complete).

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add README for OSS distribution"
```

---

# Phase 2 — remaining adapters

Each adapter follows the same recipe and shares the bases from Tasks 4–5. **Recipe per adapter:**
(a) capture a real sample on a machine that has the tool (or use the documented format),
(b) add a fixture under `tests/fixtures/`, (c) write a test mirroring `test_claude_code.py`,
(d) implement the adapter, (e) register it in `registry.py`, (f) run tests, (g) commit.
Where a real sample is unavailable, implement against the documented format and mark the
test `@unittest.skip("needs real <tool> sample")` until validated — do NOT ship an
unvalidated parser as if verified.

## Task 12: Codex adapter (JSONL rollout + legacy SQLite)

**Files:** Create `scripts/ctk/providers/codex.py`; `tests/fixtures/codex_rollout.jsonl`; `tests/test_codex.py`; Modify `scripts/ctk/registry.py`.

Documented formats (design §4): current `~/.codex/sessions/Y/M/D/rollout-*.jsonl`; legacy `~/.codex/logs_*.sqlite` (table `logs`).

- [ ] **Step 1: Create fixture `tests/fixtures/codex_rollout.jsonl`** (representative rollout lines)
```jsonl
{"type":"message","role":"user","content":[{"type":"input_text","text":"How do I cache arrays?"}],"cwd":"/home/u/projects/demo","timestamp":"2026-06-17T09:00:00Z"}
{"type":"message","role":"assistant","content":[{"type":"output_text","text":"Prefer OPFS for big numeric blobs."}]}
{"type":"function_call","name":"shell","arguments":"{\"cmd\":\"ls\"}"}
```

- [ ] **Step 2: Write failing test `tests/test_codex.py`**
```python
import tests._path  # noqa: F401
import os, unittest
from ctk.providers.codex import CodexAdapter
FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "codex_rollout.jsonl")

class TestCodex(unittest.TestCase):
    def test_rollout_parses_text_turns(self):
        s = list(CodexAdapter().parse(FIXTURE))[0]
        self.assertEqual(s.provider, "codex")
        self.assertEqual([t.role for t in s.turns], ["user", "assistant"])
        self.assertIn("OPFS", "\n".join(t.text for t in s.turns))
        self.assertEqual(s.project, "/home/u/projects/demo")

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run test — expect FAIL** (`No module named 'ctk.providers.codex'`).

- [ ] **Step 4: Implement `scripts/ctk/providers/codex.py`**
```python
from __future__ import annotations
from pathlib import Path
from typing import Optional, Iterable
from ctk.base import JsonlFileSessionAdapter
from ctk.model import Turn, NormalizedSession
from ctk.text import extract_text, clean


def _codex_text(content) -> str:
    # Codex content blocks use input_text/output_text rather than "text".
    if isinstance(content, list):
        parts = []
        for b in content:
            if isinstance(b, dict) and b.get("type") in ("input_text", "output_text", "text"):
                parts.append(str(b.get("text", "")))
        return "\n".join(p for p in parts if p)
    return extract_text(content)


class CodexAdapter(JsonlFileSessionAdapter):
    name = "codex"

    def session_files(self) -> list:
        base = Path.home() / ".codex" / "sessions"
        files = sorted(base.glob("**/rollout-*.jsonl")) if base.exists() else []
        return files

    def turn_of(self, rec) -> Optional[Turn]:
        if rec.get("type") != "message":
            return None
        role = rec.get("role")
        if role not in ("user", "assistant"):
            return None
        text = clean(_codex_text(rec.get("content")))
        if not text.strip():
            return None
        return Turn(role=role, text=text)

    def project_path(self, path, first) -> Optional[str]:
        return (first or {}).get("cwd")

    def started_at(self, path, first) -> Optional[str]:
        return (first or {}).get("timestamp")

    # Legacy SQLite detection appended in Step 5.
```

- [ ] **Step 5: Add legacy SQLite support** — append a sibling `CodexLegacyAdapter(SqliteAdapter)` in the same file that detects `~/.codex/logs_*.sqlite` and reads the `logs` table. Before implementing the `iter_sessions` query, inspect the real schema:
  Run: `python -c "import sqlite3,glob,os; p=glob.glob(os.path.expanduser('~/.codex/logs_*.sqlite')); print(p); [print(r) for r in sqlite3.connect(p[0]).execute('PRAGMA table_info(logs)')] if p else None"`
  Then write the query to map rows → `Turn(role, text)` grouped by session, applying `clean()`. Add a `@unittest.skip` test if no local legacy DB exists.

- [ ] **Step 6: Register** — in `scripts/ctk/registry.py` add `from ctk.providers.codex import CodexAdapter, CodexLegacyAdapter` and append both to `_ADAPTER_CLASSES`.

- [ ] **Step 7: Run tests** `python -m unittest discover -s tests -v` — expect PASS.

- [ ] **Step 8: Commit** `git add -A && git commit -m "feat: add Codex adapter (rollout jsonl + legacy sqlite)"`

## Task 13: Copilot CLI adapter (JSONL)

**Files:** `scripts/ctk/providers/copilot_cli.py`; `tests/fixtures/copilot_events.jsonl`; `tests/test_copilot_cli.py`; register.

Documented format (design §4): `~/.copilot/session-state/<id>/events.jsonl` (+ legacy `~/.copilot/history-session-state/`).

- [ ] **Step 1:** Fixture with `events.jsonl` lines containing `{"role":"user","content":"..."}` / `{"role":"assistant","content":"..."}` events; include one tool/event line to be skipped.
- [ ] **Step 2:** Failing test mirroring `test_claude_code.py` (assert provider `copilot-cli`, only user/assistant text turns).
- [ ] **Step 3:** Run — expect FAIL.
- [ ] **Step 4:** Implement subclass of `JsonlFileSessionAdapter`: `session_files()` globs `~/.copilot/session-state/*/events.jsonl` and the legacy dir; `turn_of()` maps role+content via `clean(extract_text(...))`; `session_id()` from the parent dir name.
- [ ] **Step 5:** Register in `registry.py`.
- [ ] **Step 6:** Run tests — expect PASS.
- [ ] **Step 7:** Commit `feat: add Copilot CLI adapter`.

## Task 14: Tier-1 JSONL adapters — Factory, OpenClaw, Kimi, Vibe

For EACH tool, do the full recipe (fixture → failing test → implement → register → test → commit). Documented paths (design §4):
- **Factory(Droid):** `~/.factory/sessions/**/*.jsonl` → provider `factory`
- **OpenClaw:** `~/.openclaw/agents/*/sessions/*.jsonl` → provider `openclaw`
- **Kimi Code:** `~/.kimi/sessions/*/*/wire.jsonl` → provider `kimi`
- **Vibe (Mistral):** `~/.vibe/logs/session/*/messages.jsonl` → provider `vibe`

- [ ] **Step 1 (Factory):** fixture `tests/fixtures/factory_session.jsonl` with user/assistant lines.
- [ ] **Step 2 (Factory):** failing test → run → implement `JsonlFileSessionAdapter` subclass (map its role/content fields; apply `clean`) → register → test → commit.
- [ ] **Step 3 (OpenClaw):** repeat recipe.
- [ ] **Step 4 (Kimi):** repeat recipe (note nested `wire.jsonl`).
- [ ] **Step 5 (Vibe):** repeat recipe (`messages.jsonl`).
Where the exact line schema is unknown, implement against the documented role/content shape and `@unittest.skip("needs real <tool> sample")` the assertion until validated. Commit after each tool.

## Task 15: Tier-2 SQLite adapters — Crush, Hermes

Documented (design §4): `~/.crush/crush.db` (+ project-local `.crush/crush.db`); `~/.hermes/state.db` (+ project-local).

- [ ] **Step 1 (Crush):** Inspect real schema if available:
  `python -c "import sqlite3,os; p=os.path.expanduser('~/.crush/crush.db'); [print(r) for r in sqlite3.connect(p).execute('SELECT name FROM sqlite_master WHERE type=\"table\"')] if os.path.exists(p) else print('no db')"`
- [ ] **Step 2 (Crush):** Build an in-test SQLite fixture mirroring the real message table; write failing test (provider `crush`, grouped sessions).
- [ ] **Step 3 (Crush):** Implement `SqliteAdapter` subclass: `db_paths()` returns home + cwd-local db; `iter_sessions()` queries messages, groups by session, maps role/text with `clean()`. Register. Test. Commit.
- [ ] **Step 4 (Hermes):** repeat recipe against `~/.hermes/state.db`.
If schema can't be confirmed, `@unittest.skip` the live assertion but keep the in-test-fixture test running.

## Task 16: Tier-2 SQLite adapters — Cursor, OpenCode

Documented (design §4): Cursor `~/Library/Application Support/Cursor/User/**/state.vscdb` (VS Code SQLite; chat data in key-value blobs — needs JSON decode of values); OpenCode `~/.local/share/opencode/storage` (JSONL) and project-local `.opencode/` (SQLite).

- [ ] **Step 1 (OpenCode):** It is JSONL-based in the user-data dir → prefer `JsonlFileSessionAdapter` globbing `~/.local/share/opencode/storage/**/*.jsonl`; fixture + test + implement + register + commit.
- [ ] **Step 2 (Cursor):** Inspect `state.vscdb` keys to locate chat blobs:
  `python -c "import sqlite3,os,glob; ..."` (find the ItemTable rows whose key matches chat). Implement `SqliteAdapter` that reads the relevant key, `json.loads` the value, maps messages. This is the most format-fragile adapter — gate the live test with `@unittest.skip` until a real sample confirms the key path; keep an in-test fixture test.

## Task 17: Tier-3 JSON adapters — Gemini, Qwen

Documented (design §4): Gemini `~/.gemini/tmp/<hash>/checkpoint*` (JSON array of `{role:"user"|"model", parts:[...]}`, checkpointing off by default); Qwen `~/.qwen/tmp/*/chats/session-*.json` (JSON).

- [ ] **Step 1 (Gemini):** Create a small `JsonFileSessionAdapter` base if not present (one `.json` file = array of messages); OR implement directly: read JSON, iterate messages, map `role` (`model`→`assistant`), extract `parts[].text`, apply `clean()`. Fixture + test + implement + register + commit. Note: many machines have checkpointing disabled → `detect()` returns [] gracefully.
- [ ] **Step 2 (Qwen):** repeat recipe against `session-*.json`.

## Task 18: Tier-3 Markdown adapter — Aider

Documented (design §4): per-project `.aider.chat.history.md` (Markdown). Aider marks turns with `####`-style headers and `>` user lines.

- [ ] **Step 1:** Fixture `tests/fixtures/aider.chat.history.md` with a couple of user/assistant exchanges and a fenced code block.
- [ ] **Step 2:** Failing test (provider `aider`; user/assistant turns parsed; code block stripped by `clean`).
- [ ] **Step 3:** Implement a `ProviderAdapter` directly (not JSONL): `detect()` finds `.aider.chat.history.md` under home and cwd; `parse()` splits the markdown into turns by Aider's header convention, applies `clean()`. Register. Test. Commit.

## Task 19: Final integration pass

- [ ] **Step 1:** Run full suite `python -m unittest discover -s tests -v` — all pass (skips allowed for unvalidated live adapters).
- [ ] **Step 2:** Smoke-test end-to-end on real local data: `python scripts/normalize.py --mode all --count-only` then `--list-projects` — verify multiple providers detected, no crashes.
- [ ] **Step 3:** Update `README.md` supported-tools section to mark which adapters are verified vs. format-only.
- [ ] **Step 4:** Commit `chore: phase-2 adapters complete; mark verification status`.
```
