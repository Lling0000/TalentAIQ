"""Core orchestration for TalentAIQ Lite."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .assessment import build_assessment
from .collectors import collect_claude, collect_codex, collect_git, collect_github, collect_project_traces
from .redaction import Redactor
from .renderers import write_outputs


@dataclass
class RunConfig:
    candidate_label: str = "candidate"
    repos: list[str] = field(default_factory=lambda: ["."])
    output_dir: str = "reports"
    codex_dir: str | None = None
    claude_dir: str | None = None
    github_json: str | None = None
    github_user: str | None = None
    enable_github: bool = False
    authorized: bool = False


def run_assessment(config: RunConfig) -> dict[str, Any]:
    if not config.authorized:
        raise PermissionError("Candidate authorization is required. Re-run with --authorize.")

    redactor = Redactor()
    candidate_label = redactor.redact_text(config.candidate_label or "candidate")
    sources = [
        collect_claude(config.claude_dir, redactor),
        collect_codex(config.codex_dir, redactor),
        collect_git(config.repos, redactor),
        collect_project_traces(config.repos, redactor),
        collect_github(config.github_json, config.github_user, config.enable_github, redactor),
    ]
    redaction_report = redactor.report().__dict__
    assessment = build_assessment(
        candidate_label=candidate_label,
        sources=sources,
        redaction_report=redaction_report,
        authorized=True,
    )
    output_paths = write_outputs(assessment, config.output_dir, redactor)
    assessment["output_paths"] = output_paths
    assessment["privacy"]["redaction_report"] = redactor.report().__dict__
    return assessment
