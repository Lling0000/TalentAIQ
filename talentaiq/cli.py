"""Command-line interface for TalentAIQ Lite."""

from __future__ import annotations

import argparse
import sys

from .core import RunConfig, run_assessment


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="talentaiq",
        description="Local-first AI-native candidate evidence generator.",
    )
    parser.add_argument(
        "--authorize",
        action="store_true",
        help="Confirm the candidate authorized local evidence collection.",
    )
    parser.add_argument(
        "--candidate-label",
        default="candidate",
        help="Pseudonymous candidate label to show in outputs.",
    )
    parser.add_argument(
        "--repo",
        action="append",
        dest="repos",
        help="Local Git repository to analyze. May be repeated. Defaults to current directory.",
    )
    parser.add_argument("--codex-dir", default=None, help="Codex home directory. Defaults to ~/.codex.")
    parser.add_argument("--claude-dir", default=None, help="Claude home directory. Defaults to ~/.claude.")
    parser.add_argument(
        "--max-ai-jsonl-files",
        type=int,
        default=0,
        help="Max JSONL files to scan per AI source. Defaults to no limit; use 0 for no file limit.",
    )
    parser.add_argument(
        "--max-ai-jsonl-records",
        type=int,
        default=0,
        help="Max JSONL records to scan per AI source. Defaults to no limit; use 0 for no record limit.",
    )
    parser.add_argument("--github-json", default=None, help="Optional local GitHub JSON export.")
    parser.add_argument("--github-user", default=None, help="Optional GitHub username for gh api mode.")
    parser.add_argument(
        "--enable-github",
        action="store_true",
        help="Explicitly allow limited GitHub CLI API lookup when --github-user is set.",
    )
    parser.add_argument("--output-dir", default="reports", help="Directory for generated reports.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = RunConfig(
        candidate_label=args.candidate_label,
        repos=args.repos or ["."],
        output_dir=args.output_dir,
        codex_dir=args.codex_dir,
        claude_dir=args.claude_dir,
        max_ai_jsonl_files=args.max_ai_jsonl_files or None,
        max_ai_jsonl_records=args.max_ai_jsonl_records or None,
        github_json=args.github_json,
        github_user=args.github_user,
        enable_github=args.enable_github,
        authorized=args.authorize,
    )
    try:
        assessment = run_assessment(config)
    except PermissionError as exc:
        print(f"TalentAIQ Lite refused to run: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130

    print("TalentAIQ Lite generated evidence artifacts:")
    for label, path in assessment["output_paths"].items():
        print(f"- {label}: {path}")
    print("Boundary: evidence only; no ranking, rejection, or hiring recommendation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
