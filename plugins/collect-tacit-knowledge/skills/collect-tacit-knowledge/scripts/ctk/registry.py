from __future__ import annotations
from ctk.providers.claude_code import ClaudeCodeAdapter
from ctk.providers.codex import CodexAdapter, CodexLegacyAdapter
from ctk.providers.copilot_cli import CopilotCliAdapter
from ctk.providers.factory import FactoryAdapter
from ctk.providers.openclaw import OpenClawAdapter
from ctk.providers.kimi import KimiAdapter
from ctk.providers.vibe import VibeAdapter
from ctk.providers.crush import CrushAdapter
from ctk.providers.hermes import HermesAdapter
from ctk.providers.opencode import OpenCodeAdapter
from ctk.providers.cursor import CursorAdapter
from ctk.providers.gemini import GeminiAdapter
from ctk.providers.antigravity import AntigravityAdapter
from ctk.providers.qwen import QwenAdapter
from ctk.providers.aider import AiderAdapter

# All implemented provider adapters. Add a new adapter class here to register it.
_ADAPTER_CLASSES = [
    ClaudeCodeAdapter,
    CodexAdapter,
    CodexLegacyAdapter,
    CopilotCliAdapter,
    FactoryAdapter,
    OpenClawAdapter,
    KimiAdapter,
    VibeAdapter,
    CrushAdapter,
    HermesAdapter,
    OpenCodeAdapter,
    CursorAdapter,
    GeminiAdapter,
    AntigravityAdapter,
    QwenAdapter,
    AiderAdapter,
]


def all_adapters() -> list:
    return [cls() for cls in _ADAPTER_CLASSES]


def supported_adapters() -> list:
    return [a for a in all_adapters() if a.supported()]
