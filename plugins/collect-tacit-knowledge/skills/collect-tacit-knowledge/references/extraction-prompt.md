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

PRIVACY RULES — tiered. The report is for the author's own TEAM, so keep useful
internal context; only the hard bans below are non-negotiable.

NEVER include (a violation makes the report unusable):
- Secrets, API keys, tokens, passwords, connection strings, or .env values.
- Real PERSONAL names, emails, IPs, hostnames, or filesystem paths containing a username.
- EXTERNAL client / customer names or any customer data. GENERALIZE these.
  Example: "Globex (the customer) asked for X" -> "a customer asked for X".
- Source-code bodies. Describe the pattern, not the code.

OK TO KEEP (do not over-mask — these are context for teammates):
- The author's own company name and INTERNAL product / project / repo names
  (e.g. a repo or product codename). They make the know-how concrete and reusable.
- Public technology names (libraries, frameworks, APIs, file formats).

QUALITY RULES:
- Prefer durable, generalizable lessons over one-off task facts.
- If the session contains no transferable know-how, return `[]`.
- `evidence.project` should be the short project/repo name, never a raw filesystem
  path (which leaks a username) and never an external client name.
