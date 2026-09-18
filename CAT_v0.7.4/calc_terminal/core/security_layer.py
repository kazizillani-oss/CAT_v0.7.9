"""
CAT Security, Privacy & Safe Execution Layer per §27:
- Tiered permission model & approval gates for irreversible actions
- Automated secret redaction for API keys, tokens, and credentials
- Prompt injection and malicious command heuristic defenses
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


class PermissionTier(str, enum.Enum):
    READ_ONLY = "read_only"
    WORKSPACE_WRITE = "workspace_write"
    TERMINAL_EXECUTE = "terminal_execute"
    NETWORK_ACCESS = "network_access"
    DESTRUCTIVE_OPERATIONS = "destructive_operations"


# Regex patterns for common secret credentials
SECRET_PATTERNS = [
    (re.compile(r"(sk-[a-zA-Z0-9]{20,})"), "[REDACTED_API_KEY]"),
    (re.compile(r"(ghp_[a-zA-Z0-9]{36,})"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"(gho_[a-zA-Z0-9]{36,})"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"(hf_[a-zA-Z0-9]{34,})"), "[REDACTED_HF_TOKEN]"),
    (re.compile(r"(AKIA[0-9A-Z]{16})"), "[REDACTED_AWS_KEY]"),
    (re.compile(r"(AIza[0-9A-Za-z-_]{35})"), "[REDACTED_GOOGLE_KEY]"),
    (re.compile(r"Bearer\s+([a-zA-Z0-9_\-\.]{20,})"), "Bearer [REDACTED_BEARER_TOKEN]"),
    (re.compile(r"(?i)(password|secret|token|api_key)\s*[:=]\s*['\"]([^'\"]{4,})['\"]"), r"\1='[REDACTED]'"),
]

# Patterns representing high-risk or destructive actions requiring approval
DESTRUCTIVE_COMMAND_PATTERNS = [
    re.compile(r"rm\s+(-rf|-fr|--recursive)\s+[/~]"),
    re.compile(r"git\s+push\s+.*--force"),
    re.compile(r"mkfs"),
    re.compile(r"dd\s+if="),
    re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:"),  # Fork bomb
    re.compile(r"drop\s+(database|table)", re.IGNORECASE),
]

# Suspicious prompt injection indicators
PROMPT_INJECTION_PATTERNS = [
    re.compile(r"(?i)(ignore|disregard)\s+(all\s+)?(previous\s+)?(instructions|prompts|safety\s+guidelines)"),
    re.compile(r"(?i)you\s+are\s+now\s+in\s+developer\s+mode"),
    re.compile(r"(?i)<system>.*ignore.*</system>"),
    re.compile(r"(?i)reveal\s+(system\s+prompt|secret\s+keys)"),
]


@dataclass
class SecurityCheckResult:
    allowed: bool
    requires_confirmation: bool = False
    reason: Optional[str] = None
    category: str = "ok"


class SecurityLayer:
    """Enforces execution safety, secret protection, and input sanitization."""

    def __init__(self, current_tier: PermissionTier = PermissionTier.TERMINAL_EXECUTE):
        self.current_tier = current_tier
        self.approved_actions: Set[str] = set()

    def redact_secrets(self, text: str) -> str:
        """Scan text and redact sensitive API keys, tokens, and credentials."""
        if not text:
            return ""
        redacted = text
        for pattern, replacement in SECRET_PATTERNS:
            redacted = pattern.sub(replacement, redacted)
        return redacted

    def evaluate_command(self, command: str) -> SecurityCheckResult:
        """Inspect terminal command before execution."""
        cmd_clean = command.strip()

        # 1. Check destructive patterns
        for pat in DESTRUCTIVE_COMMAND_PATTERNS:
            if pat.search(cmd_clean):
                return SecurityCheckResult(
                    allowed=False,
                    requires_confirmation=True,
                    reason=f"Potentially destructive command detected: '{cmd_clean}'. Explicit approval required.",
                    category="destructive",
                )

        # 2. Check permission tier
        if self.current_tier == PermissionTier.READ_ONLY:
            return SecurityCheckResult(
                allowed=False,
                requires_confirmation=False,
                reason="Current permission tier is READ_ONLY. Terminal execution denied.",
                category="permission_denied",
            )

        return SecurityCheckResult(allowed=True, category="ok")

    def inspect_untrusted_input(self, content: str) -> Tuple[bool, Optional[str]]:
        """Detect potential prompt injection in external data or tool outputs."""
        for pat in PROMPT_INJECTION_PATTERNS:
            if pat.search(content):
                return False, f"Potential prompt injection pattern detected: {pat.pattern}"
        return True, None


security_layer = SecurityLayer()
