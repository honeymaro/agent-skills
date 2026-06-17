---
name: collect-tacit-knowledge
description: Use when the user wants to extract shareable know-how (tacit knowledge) from their local LLM-CLI conversation history across tools (Claude Code, Codex, Copilot CLI, etc.) and produce one anonymized one-page report. Triggers — "collect tacit knowledge", "know-how report", "extract know-how from my conversation history", "summarize what I've learned across projects".
---

# collect-tacit-knowledge

Mines transferable know-how from local LLM-CLI logs and produces ONE anonymized, shareable
markdown report. Read-only on all logs. Privacy is non-negotiable (3-layer defense).

## Prerequisite
`python3` on PATH. No `pip install` needed.

All scripts/references below are addressed via `${CLAUDE_SKILL_DIR}`, which resolves to this
skill's own directory at runtime regardless of the user's working directory (works at personal,
project, and plugin scope). Use it verbatim — do NOT assume the cwd is the skill folder.

## Procedure

1. **Pick a mode** (ask the user):
   - `all` — every detected tool
   - `current` — sessions in the current project (`--project "$(pwd)"`)
   - `selected` — run `python ${CLAUDE_SKILL_DIR}/scripts/normalize.py --list-projects`, show the list, let them pick
   - `directory / substring scope` — add `--project-contains "<substr>"` (e.g. a parent
     dir like `projects/acme`) to any mode to keep only projects whose path matches.
2. **Confirm scope (cost gate):** run
   `python ${CLAUDE_SKILL_DIR}/scripts/normalize.py --mode <mode> [--project P] --count-only`
   Show the user the session count + providers. If large (e.g. >40), offer to narrow scope.
   Proceed only on confirmation.
3. **Normalize:** run
   `python ${CLAUDE_SKILL_DIR}/scripts/normalize.py --mode <mode> [--project P] --out .ctk-work/sessions`
   This also writes `.ctk-work/sessions/_manifest.json` — one entry per session with
   `{file, provider, project, started_at, turns, bytes}`. Read it first to plan Map/Reduce.
4. **Map (parallel extraction) — depth scales with session size; cover every session.**
   Use `${CLAUDE_SKILL_DIR}/references/extraction-prompt.md` as the contract and
   `superpowers:dispatching-parallel-agents`. Plan from the manifest:
   - **Extraction depth ∝ size:** target ~1 candidate per 40–60 `turns`, minimum 3, with NO
     fixed upper cap. A 1300-turn session should yield ~20–30 candidates, not the same ~10 as
     a 30-turn one — do NOT flatten large/old sessions to a small fixed cap.
   - **Large sessions get their own subagent** (e.g. `turns > 400` or `bytes > 250_000`), and
     instruct that agent to read the file in turn-range chunks so nothing is truncated.
   - **Group only small sessions** together (keep each batch well under the read limit).
   - **Coverage guarantee:** every session in the manifest must be assigned to some agent, and
     every distinct `project` and every time bucket (group `started_at` by quarter) must have
     at least one extraction agent. Don't let the most-active repo crowd others out.
5. **Reduce — balanced coverage, NOT recency-ranked.** Cluster by meaning and dedupe, but:
   - **Do NOT rank by recency.** A lesson is not weaker because it is old or appeared once.
   - **Reserve slots per project and per time bucket** so older/low-volume projects are
     represented; a high-session-count repo must not dominate the page.
   - **Keep unique-but-valuable** items; only drop true noise and duplicates. If two items
     conflict, prefer the more general/transferable one.
   - Track how many items came from each project/bucket so coverage is auditable.
6. **Assemble:** fill `${CLAUDE_SKILL_DIR}/references/report-template.md` per category. Bullets
   are abstracted claims + evidence signal. No raw quotes, no secrets, no external client names.
   Internal product/repo names MAY appear as context (see privacy tiers below).
   - In the `{provider_summary}` line, state coverage: distinct projects and the date span
     (e.g. "6 repos · 2026-03 to 2026-06"), so recency/coverage skew is visible to the reader.
   - If one page can't hold balanced coverage, prefer trimming the dominant project's items
     over dropping a whole project/era.
7. **Sanitize (REQUIRED gate — do not skip):** run
   `python ${CLAUDE_SKILL_DIR}/scripts/sanitize.py <report> [--known-names names.txt]`.
   The scan always runs (catches emails/IPs/keys/username-paths). `--known-names` is OPT-IN
   force-masking: for the default internal audience you usually don't need it; supply a names
   file (company/product/any sensitive names) only when sharing the report EXTERNALLY/OSS.
   If findings > 0, re-run with `--mask` and re-review until clean (exit 0). IPs/hostnames in
   conversation text are only caught here, so the gate is mandatory. Then read the report
   yourself and confirm it's safe for the intended audience.
8. **Deliver:** write the final report to a user-chosen path (default `<project>/tacit-knowledge.md`)
   and print it. Clean up the temporary `.ctk-work/` directory (it holds normalized conversation data).

## Privacy rules — tiered (the report's default audience is the author's own team)
Always block (non-negotiable, enforced mechanically + in extraction):
- Secrets/credentials/keys/tokens, source-code bodies, PII (emails, personal names, IPs,
  filesystem paths containing a username), and EXTERNAL client/customer names or data.
Keep by default (do NOT over-mask — it removes useful context for teammates):
- The author's own company name and internal product/project/repo names.
- Public technology names (libraries, frameworks, formats).
For external/OSS sharing, mask the "keep by default" set via sanitize `--known-names`.
Encrypted/undocumented sources are skipped by their adapters; do not try to decrypt.
