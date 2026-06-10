"""Redaction helpers for privacy-first report generation."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any


@dataclass
class RedactionReport:
    enabled: bool = True
    redaction_enabled: bool = True
    redaction_mode: str = "default_safe"
    redacted_fields: list[str] = field(
        default_factory=lambda: ["email", "secret", "token", "api_key", "local_path", "private_key"]
    )
    redacted_placeholders: list[str] = field(
        default_factory=lambda: [
            "[REDACTED_EMAIL]",
            "[REDACTED_SECRET]",
            "[REDACTED_LOCAL_PATH]",
            "[REDACTED_PRIVATE_KEY]",
        ]
    )
    replacements: dict[str, int] = field(default_factory=dict)
    secret_like_values_detected: int = 0
    raw_prompt_or_completion_included: bool = False


class Redactor:
    """Redacts common secrets and local identifiers from output objects."""

    def __init__(self, home: str | None = None) -> None:
        self.home = str(Path(home).expanduser()) if home else str(Path.home())
        self.stats: Counter[str] = Counter()
        self._patterns: list[tuple[str, re.Pattern[str], str | None]] = [
            (
                "private_key_block",
                re.compile(
                    r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
                    re.DOTALL,
                ),
                "[REDACTED_PRIVATE_KEY]",
            ),
            (
                "anthropic_key",
                re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b"),
                "[REDACTED_ANTHROPIC_KEY]",
            ),
            (
                "openai_key",
                re.compile(r"\bsk-(?!ant-)[A-Za-z0-9_-]{20,}\b"),
                "[REDACTED_OPENAI_KEY]",
            ),
            (
                "github_token",
                re.compile(r"\bgh[opusr]_[A-Za-z0-9_]{20,}\b"),
                "[REDACTED_GITHUB_TOKEN]",
            ),
            (
                "aws_access_key",
                re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
                "[REDACTED_AWS_ACCESS_KEY]",
            ),
            (
                "sensitive_assignment",
                re.compile(
                    r"(?i)\b((?:api[_-]?key|access[_-]?token|token|secret|password|passwd|authorization|bearer)\s*[:=]\s*[\"']?)([^\"'\s,;]{8,})"
                ),
                None,
            ),
            (
                "sensitive_url_query",
                re.compile(
                    r"(?i)([?&](?:token|access_token|api_key|signature|secret|key)=)([^&#\s]+)"
                ),
                None,
            ),
            (
                "email",
                re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
                "[REDACTED_EMAIL]",
            ),
        ]

    def redact_text(self, value: Any) -> str:
        text = "" if value is None else str(value)
        if self.home and self.home in text:
            count = text.count(self.home)
            self.stats["home_path"] += count
            text = text.replace(self.home, "~")

        for name, pattern, replacement in self._patterns:
            if name in {"sensitive_assignment", "sensitive_url_query"}:
                text, count = pattern.subn(lambda m: f"{m.group(1)}[REDACTED_SECRET]", text)
            else:
                text, count = pattern.subn(replacement or "[REDACTED]", text)
            if count:
                self.stats[name] += count
        return text

    def redact_path(self, path: str | Path | None) -> str | None:
        if path is None:
            return None
        raw = str(path)
        redacted = self.redact_text(raw)
        if redacted.startswith("~") or not Path(raw).is_absolute():
            return redacted
        self.stats["local_path"] += 1
        name = Path(raw).name or "path"
        return f"[REDACTED_LOCAL_PATH]/{name}"

    def redact_obj(self, value: Any) -> Any:
        if isinstance(value, dict):
            redacted: dict[str, Any] = {}
            for key, item in value.items():
                if self._is_sensitive_key(str(key)):
                    self.stats["sensitive_key"] += 1
                    redacted[key] = "[REDACTED_SECRET]"
                else:
                    redacted[key] = self.redact_obj(item)
            return redacted
        if isinstance(value, list):
            return [self.redact_obj(item) for item in value]
        if isinstance(value, tuple):
            return tuple(self.redact_obj(item) for item in value)
        if isinstance(value, str):
            return self.redact_text(value)
        return value

    def contains_secret_like_value(self, value: Any) -> bool:
        before = dict(self.stats)
        redacted = self.redact_text(value)
        changed = redacted != str(value)
        if changed:
            self.stats["secret_like_values_detected"] += 1
        for key, count in before.items():
            if self.stats[key] == count:
                continue
        return changed

    def report(self) -> RedactionReport:
        replacements = dict(sorted(self.stats.items()))
        secret_count = sum(
            count
            for key, count in replacements.items()
            if key
            in {
                "private_key_block",
                "openai_key",
                "anthropic_key",
                "github_token",
                "aws_access_key",
                "sensitive_assignment",
                "sensitive_url_query",
                "sensitive_key",
                "secret_like_values_detected",
            }
        )
        return RedactionReport(
            enabled=True,
            redaction_enabled=True,
            redaction_mode="default_safe",
            replacements=replacements,
            secret_like_values_detected=secret_count,
            raw_prompt_or_completion_included=False,
        )

    @staticmethod
    def _is_sensitive_key(key: str) -> bool:
        lowered = key.lower()
        exact_terms = {
            "api_key",
            "apikey",
            "access_token",
            "token",
            "secret",
            "password",
            "passwd",
            "authorization",
            "bearer",
            "private_key",
        }
        suffix_terms = (
            "_api_key",
            "_apikey",
            "_access_token",
            "_token",
            "_secret",
            "_password",
            "_passwd",
            "_private_key",
        )
        return lowered in exact_terms or lowered.endswith(suffix_terms)
