# collect-tacit-knowledge — Design Document

_Written: 2026-06-17_

## 1. Summary

A deployable (company-wide / open-source) agent skill that uses map-reduce to extract **transferable know-how (tacit knowledge)** from the local conversation history of multiple LLM CLI tools, and produces a **one-page, shareable Markdown report** with strong anonymization of sensitive information.

## 2. Purpose and Motivation

- Conversations an individual has with LLM CLIs (coding agents) implicitly embed their working style, technical preferences, recurring pitfalls, and domain knowledge. This know-how usually lives only in their head and is never shared with the team.
- This skill reads those conversation logs and distills them into **know-how in a form others can pick up and use**.
- Because the output must be shareable internally or externally (with open-source contributors), **sensitive information must never end up in the report.**

### Audience and Focus (confirmed during brainstorming)

The report is aimed at the team/colleagues and includes all of the following:

- **Team-reusable know-how** — practical tips, patterns, and pitfall-avoidance techniques a colleague can immediately follow
- **Tools / workflows** — how the LLM CLI was used effectively, plus prompts and approaches
- **Rationale for decisions** — why a given technology/architecture was chosen and the trade-offs
- **Domain knowledge** — specialized knowledge and terminology needed for work in the field

## 3. Goals / Non-Goals

### Goals
- Support multiple LLM CLI tools in a **source-agnostic** way (provider adapters).
- **Three collection modes**: (1) all detected tools (2) current project (3) projects the user selects.
- A **triple anonymization defense line** to guarantee that credentials, proper nouns, source-code bodies, and PII never leak into the report.
- Normalization using **pure Python 3 standard library** only (zero `pip install`).
- Thoroughly handle large corpora via **map-reduce parallel processing**.

### Non-Goals (Out of scope)
- We do not build a **server that aggregates/stores** multiple people's reports in one place. This skill produces a single-person report, and sharing is done manually by the user.
- **Encrypted sources** (e.g., ChatGPT desktop v2+) are not supported — explicitly skipped with a notice.
- We do not **modify, delete, or regenerate** conversation history (read-only).
- We do not implement all 20+ tools on day 1 (incremental expansion by tier).

## 4. Source Landscape (research results, 2026-06)

The actual storage methods confirmed by unified-indexing OSS projects such as `coding_agent_session_search` and `agent-sessions`. **Storage methods are fragmented, and there is no guarantee that any one tool is dominant.**

| Tool | Location | Format | Tier |
|---|---|---|---|
| Claude Code | `~/.claude/projects/<path-encoded>/*.jsonl` | JSONL | 1 |
| Codex (current) | `~/.codex/sessions/Y/M/D/rollout-*.jsonl` | JSONL | 1 |
| Codex (legacy) | `~/.codex/logs_*.sqlite` | SQLite | 1 (secondary) |
| Copilot CLI | `~/.copilot/session-state/*/events.jsonl` (+ legacy, sqlite index) | JSONL | 1 |
| Factory (Droid) | `~/.factory/sessions/*.jsonl` | JSONL | 1 |
| OpenClaw | `~/.openclaw/agents/*/sessions/*.jsonl` | JSONL | 1 |
| Kimi Code | `~/.kimi/sessions/*/*/wire.jsonl` | JSONL | 1 |
| Vibe (Mistral) | `~/.vibe/logs/session/*/messages.jsonl` | JSONL | 1 |
| Cursor | `~/Library/.../Cursor/.../state.vscdb` | SQLite | 2 |
| OpenCode | `.opencode/`, `~/.local/share/opencode/storage` | SQLite/JSONL | 2 |
| Crush / Hermes | `~/.crush/crush.db`, `~/.hermes/state.db` | SQLite | 2 |
| Gemini CLI | `~/.gemini/tmp/<hash>/checkpoint*` (disabled by default) | JSON | 3 |
| Qwen Code | `~/.qwen/tmp/*/chats/session-*.json` | JSON | 3 |
| Aider | `.aider.chat.history.md` (per project) | Markdown | 3 |
| ChatGPT desktop | `~/Library/.../com.openai.chat` | JSON (encrypted) | unsupported |

**Common schema:** nearly all tools converge to `Conversation → Message(role: user/assistant/system) → content` → the basis for the normalized target format.

### Implementation scope — all feasible adapters (excluding only encrypted sources)
In v1 we **implement every adapter** that has an unencrypted, documented format. Tiers are just a guide to implementation order/difficulty, not a scope reduction.
- **Tier 1 (JSONL, easy):** Claude Code · Codex (current + legacy) · Copilot CLI · Factory ·
  OpenClaw · Kimi · Vibe
- **Tier 2 (SQLite):** Cursor · OpenCode · Crush · Hermes
- **Tier 3 (JSON/MD):** Gemini · Qwen · Aider
- **Excluded:** ChatGPT desktop (v2+ encrypted) and other encrypted/undocumented formats — the adapter
  skips after issuing an "unsupported" notice.
- For adapters whose format is unknown, leave them best-effort if no sample fixture is available during implementation, but fill in the full interface.

### Empirical corrections during implementation (2026-06-17)
While verifying against actual local data, some §4 assumptions were corrected:
- **The Codex legacy `~/.codex/logs_*.sqlite` is not a conversation store but a Rust diagnostic/tracing log**
  (table `logs`: ts·level·target·feedback_log_body…, with no role/text). The legacy adapter degrades to producing
  nothing when role/text columns are absent. Codex's actual conversation path is only the current rollout JSONL
  (`~/.codex/sessions/.../rollout-*.jsonl`).
- **Gemini's actual conversations live not in checkpoints but in `~/.gemini/tmp/<hash>/chats/session-*.json`**
  (`{sessionId, projectHash, startTime, messages:[{type:"user"|"gemini", content}]}`). The adapter handles
  **both** the documented checkpoint-array form and this observed form. Claude Code and Gemini are verified
  against real data; the remaining adapters are based on documented formats + validated with synthetic fixtures (not confirmed against real data).

## 5. Architecture

### 5.1 Provider Adapter Registry

The source layer is not hardcoded to Claude Code but is a set of **pluggable adapters**. Each adapter implements a common interface:

```
class ProviderAdapter:
    name: str
    def detect(self) -> list[Path]:       # session file paths for this tool (empty [] if none)
    def parse(self, path) -> Iterable[NormalizedSession]
    def project_of(self, session) -> str | None   # project path/identifier the session belongs to
```

- Supporting a new tool = adding one adapter file. The core pipeline is unchanged.
- Adapters for tools that are not installed/found are silently skipped. Only what is found is processed.
- For encrypted/unsupported sources, the adapter explicitly issues an "unsupported" notice.

### 5.2 Normalized Target Format (`NormalizedSession`)

```json
{
  "provider": "claude-code",
  "session_id": "<opaque ID>",
  "project": "<project identifier supplied by the provider>",
  "started_at": "<ISO ts | null>",
  "turns": [
    { "role": "user" | "assistant", "text": "<plain text, after removing code/tool output>" }
  ]
}
```

### 5.3 Six-Stage Pipeline

```
① Select    → Determine mode (all/current/selected) + detect adapters + show session count & estimated cost, then confirmation gate
② Normalize → Convert sessions into NormalizedSession via each adapter (Python stdlib; remove noise·code·tool-output·
              file-dumps·large code blocks = first anonymization)
③ Map       → Parallel subagent extraction per session (or batch) → anonymized know-how candidates (JSON)
④ Reduce    → Cluster candidates, dedupe, rank by frequency/recency, drop low-signal items (main agent)
⑤ Verify    → Re-scan the fully assembled report for leak patterns (sanitize.py, second automated pass + final agent check)
⑥ Output    → One-page Markdown report file + on-screen output
```

## 6. Component Details

### 6.1 Normalization (②) — volume reduction + first anonymization (`scripts/normalize.py`, Python stdlib)
- Input: mode and selected providers. Output: per-session `NormalizedSession` JSON (intermediate artifact, temporary directory).
- Preserve **only user/assistant text**. The following are **discarded**:
  - Noise records such as file snapshots, attachments, and `tool_result` (file dumps)
  - Large code blocks (exceeding a length threshold) — replaced with a "[code omitted]" placeholder
  - Obvious secret patterns (keys, tokens, .env values) are masked at this stage
- Effect: **source-code bodies never enter the extraction pipeline in the first place** = the largest leak vector is structurally eliminated.
- stdlib only: `json`, `sqlite3`, `pathlib`, `glob`, `re`.

### 6.2 Map-Extract (③) — extraction with built-in anonymization
- Per session (or batch within a token limit), a subagent reads the normalized conversation and returns structured candidates:
```json
{
  "category": "tool-workflow | tech-decision | pitfall | domain | style",
  "claim": "one-line abstracted know-how",
  "rationale": "why / when to apply",
  "evidence": { "project": "<anonymized alias>", "signal": "observation frequency·context" }
}
```
- The subagent prompt (`references/extraction-prompt.md`) **explicitly forbids**:
  copying secret values, API keys, real names/company names/customer names, or source-code bodies.
- Proper nouns are **generalized**. Example: "Acme's order-processing pipeline" → "order-processing pipeline" (company name removed).
- Parallel dispatch uses the `dispatching-parallel-agents` pattern (or Workflow if the user opts into the Workflow option).

### 6.3 Reduce-Synthesize (④) — main agent
- Collect all candidates and cluster/dedupe them by semantic unit.
- Rank by frequency (does it recur across multiple sessions/projects?) and recency. Drop low-signal, one-off items.
- Assemble report sections by category. Attach a compact rationale (which projects · how many times) to each item.

### 6.4 Privacy — Triple Defense Line
1. **Remove during normalization** — block code, file dumps, tool output, and obvious secrets from entering (②).
2. **Abstract during extraction** — the subagent generalizes proper nouns and secrets (③).
3. **Re-scan during verification** — block/mask if emails, key patterns, or residual proper nouns are detected in the final report (⑤).
   - `scripts/sanitize.py` (stdlib regex): auto-detects emails, API-key shapes, IPs, usernames inside paths, etc.
   - Then the main agent does a final human-eyes check of the report ("Is this OK to leave the company?").
   - A "known proper-noun list" can optionally be provided by the user (e.g., company name·product name·customer name) for forced masking.

### 6.5 Report Format (⑥) — one page
Team sharing + emphasis on rationale → **profile card + compact rationale footnotes**. **No verbatim quotes** (leak risk),
just signals of "observed in which projects · how many times."

```
# Know-How Report — <alias/role>
_Generated 2026-06-17 · Sources: Claude Code 23 projects · Codex 12 sessions_

## 🛠 Tools · Workflows
- Read the entire file before a large change, then make a single edit — observed repeatedly across 5 projects

## ⚙️ Technical Decisions (rationale)
- For caching large numeric data, OPFS > IndexedDB — chosen by directly measuring overhead

## ⚠️ Pitfalls · Lessons
- (e.g.) Repeatedly blocked on cross-platform path handling → avoided with a consistent abstraction

## 📚 Domain Knowledge
- (e.g.) Key stages of a large-scale batch data reconciliation·validation pipeline
```

- Output file: Markdown at a new project or user-specified path. Also printed to screen.
- Report language: matched to the user's conversation language (Korean by default, configurable).

## 7. Collection Modes and Project Mapping

- **All** = run every detected adapter. The session count can be large, so the **confirmation gate** in ① is mandatory.
- **Current project** = only sessions matching the current working path via each adapter's `project_of()`.
- **Selected projects** = present the list of discovered project identifiers to the user → they select.
- Because each tool's notion of "project" differs (Claude = path-encoded directory, Codex = cwd from rollout metadata,
  Aider = file location), project filtering is a **per-adapter capability**. Unsupported adapters participate only in "all" mode.

## 8. File Layout

```
collect-tacit-knowledge/
  SKILL.md                          # orchestration instructions (skill entry point)
  scripts/
    normalize.py                    # adapter registry + normalization (stdlib only)
    sanitize.py                     # final leak scan (stdlib only)
    providers/
      base.py                       # ProviderAdapter interface
      claude_code.py                # Tier 1
      codex.py                      # Tier 1 (current jsonl + legacy sqlite)
      copilot_cli.py                # Tier 1
      factory.py / openclaw.py / kimi.py / vibe.py   # Tier 1
      cursor.py / opencode.py / crush.py / hermes.py # Tier 2 (best-effort)
  references/
    extraction-prompt.md            # map-stage subagent prompt
    report-template.md              # report format
  tests/
    fixtures/                       # sample jsonl/sqlite/json/md + deliberately planted secrets
    test_normalize.py
    test_sanitize.py
  docs/specs/2026-06-17-collect-tacit-knowledge-design.md   # this document
  README.md                         # for OSS distribution (install·usage·how to add providers)
```

## 9. Error Handling & Edge Cases

- **Cost of "all" mode**: in ①, show the session count and estimated token cost, then require explicit confirmation. The user can choose to narrow the scope
  (last N days · top projects).
- Empty/corrupt JSONL lines·sessions are skipped and reflected in the count.
- Adapter finds the tool not installed → silently skip. SQLite locked/encrypted → warn and skip.
- Projects with 0 candidates → silently excluded, reflected in the final source count.
- If normalization yields nothing (nothing to extract) → instead of an empty report, show a "not enough history" notice.

## 10. Testing

- `test_normalize.py`: using fixtures (jsonl/sqlite/json/md), verify removal of noise·code·secrets and conformance to the
  normalization schema.
- `test_sanitize.py`: verify that deliberately planted keys·emails·proper nouns·IPs are filtered out (zero leaks).
- Extraction prompt: with conversation samples seeded with secrets, manually/golden-verify that the subagent does not leak.
- Adapters: verify `detect`/`parse`/`project_of` with each provider's sample fixtures.

## 11. Open-Source / Distribution Considerations

- Prerequisite: `python3` only. No `pip install` required.
- Document the supported-tools table·tiers·"how to add a new adapter" (implement the interface + fixtures) in `README.md`.
- State the privacy policy at the top of the README (read-only, triple anonymization, encrypted sources unsupported).
- Design adapters as a community contribution point (small and independent, fixture-based tests).

## 12. Open Decisions (to be finalized during implementation)

- Default values for batch size/parallelism and token budget.
- The input UX for the "known proper-noun list" (file vs. interactive prompt).
- The exact schemas of Tier 2/3 adapters — confirm with real samples during implementation (especially SQLite table structure).
