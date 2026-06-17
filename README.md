# honeymaro/agent-skills

Portable agent skills for LLM CLIs. The skills themselves are harness-agnostic (the heavy
lifting is plain Python stdlib); each harness gets its own thin packaging layer.

**Harness support**
- ✅ **Claude Code** — install via the marketplace below.
- 🛠 **Codex / Gemini / others** — planned (the skill scripts are already portable; only the
  per-harness packaging + tool-name mapping needs adding).

## Install on Claude Code
```
/plugin marketplace add honeymaro/agent-skills
/plugin install <plugin-name>@honeymaro-plugins
```

## Skills
| Skill | Description |
|---|---|
| [collect-tacit-knowledge](plugins/collect-tacit-knowledge/) | Extract transferable know-how from your local LLM-CLI conversation history (Claude Code, Codex, Gemini, …) into one anonymized, shareable report. Read-only, privacy-first, Python stdlib only. |

Install it (Claude Code):
```
/plugin marketplace add honeymaro/agent-skills
/plugin install collect-tacit-knowledge@honeymaro-plugins
```
