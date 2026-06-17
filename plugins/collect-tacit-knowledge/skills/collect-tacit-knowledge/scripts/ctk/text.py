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
    # GitHub fine-grained PAT
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    # JSON quoted sensitive key/value: "password": "...."
    re.compile(
        r'"[A-Za-z0-9_]*(secret|token|password|passwd|api[_-]?key|private[_-]?key)[A-Za-z0-9_]*"\s*:\s*"[^"]*"',
        re.I,
    ),
    # credentials embedded in a connection-string URI: scheme://user:pass@host
    re.compile(r"\b[a-z][a-z0-9+.\-]*://[^\s:@/]+:[^\s:@/]+@", re.I),
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
