from __future__ import annotations
import re
from ctk.text import _SECRET_PATTERNS

EMAIL = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
IPV6 = re.compile(r"\b(?:[A-Fa-f0-9]{1,4}:){2,7}[A-Fa-f0-9]{1,4}\b|\b(?:[A-Fa-f0-9]{1,4}:){1,7}:\b|::(?:[A-Fa-f0-9]{1,4}:){0,6}[A-Fa-f0-9]{1,4}\b")
HOME_USER = re.compile(r"(?:/home/|/Users/|\\Users\\)([A-Za-z0-9_.\-]+)")


def find_leaks(text: str, known_names=None) -> list:
    findings = []
    for m in EMAIL.finditer(text):
        findings.append({"kind": "email", "value": m.group(0)})
    for m in IPV4.finditer(text):
        findings.append({"kind": "ip", "value": m.group(0)})
    for m in IPV6.finditer(text):
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
    out = IPV6.sub("[ip]", out)
    out = HOME_USER.sub(r"[user]", out)
    for pat in _SECRET_PATTERNS:
        out = pat.sub("[redacted]", out)
    for name in (known_names or []):
        if name:
            out = out.replace(name, "[name]")
    return out
