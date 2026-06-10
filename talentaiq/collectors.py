"""Local data collectors for TalentAIQ Lite."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import re
from typing import Any, Iterable

from .redaction import Redactor


MAX_JSONL_FILES = 200
MAX_JSONL_RECORDS = 20000

PROJECT_TRACE_RULES: dict[str, list[str]] = {
    "readme_files": ["README.md", "README.zh-CN.md", "README"],
    "docs": ["docs"],
    "test_dirs": ["tests", "test", "__tests__"],
    "test_reports": ["coverage.xml", "junit.xml", "test-results", "playwright-report", "coverage"],
    "scripts": ["scripts"],
    "ci_configs": [".github/workflows", ".gitlab-ci.yml", ".circleci"],
    "package_manifests": ["package.json", "pyproject.toml", "requirements.txt", "Cargo.toml", "go.mod"],
    "lockfiles": [
        "package-lock.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "poetry.lock",
        "uv.lock",
        "Pipfile.lock",
        "Cargo.lock",
        "go.sum",
    ],
    "mcp_config_files": [".mcp.json", "mcp.json"],
    "agent_config_files": ["AGENTS.md", "CLAUDE.md", "agents", ".codex/agents", "openai.yaml"],
    "prompt_files": ["prompts", "prompt", ".cursor/rules", ".windsurfrules", "rules", "instructions"],
    "skill_files": ["skills"],
}


def collect_codex(codex_dir: str | None, redactor: Redactor) -> dict[str, Any]:
    root = Path(codex_dir or "~/.codex").expanduser()
    return _collect_ai_jsonl_source(
        source_name="codex",
        root=root,
        redactor=redactor,
        preferred_subdir="sessions",
    )


def collect_claude(claude_dir: str | None, redactor: Redactor) -> dict[str, Any]:
    root = Path(claude_dir or "~/.claude").expanduser()
    return _collect_ai_jsonl_source(
        source_name="claude",
        root=root,
        redactor=redactor,
        preferred_subdir="projects",
    )


def collect_git(repos: list[str], redactor: Redactor) -> dict[str, Any]:
    source = _empty_source("git", "available")
    repo_paths = [Path(repo).expanduser().resolve() for repo in (repos or ["."])]
    metrics: dict[str, Any] = {
        "repos_requested": len(repo_paths),
        "repos_analyzed": 0,
        "repos_missing": 0,
        "commits": 0,
        "dirty_repos": 0,
        "files_changed_in_worktree": 0,
        "files_touched_by_commits": 0,
        "additions": 0,
        "deletions": 0,
        "extensions_touched": Counter(),
        "date_windows": [],
        "active_days": 0,
    }
    repo_items: list[dict[str, Any]] = []
    errors: list[str] = []

    for repo in repo_paths:
        item: dict[str, Any] = {
            "path": redactor.redact_path(repo),
            "status": "unknown",
            "branch": None,
            "commits": 0,
            "worktree_changes": 0,
        }
        if not repo.exists():
            metrics["repos_missing"] += 1
            item["status"] = "missing"
            item["summary"] = "Repository path does not exist."
            repo_items.append(item)
            continue

        inside = _run_git(repo, ["rev-parse", "--is-inside-work-tree"])
        if inside.returncode != 0 or inside.stdout.strip() != "true":
            metrics["repos_missing"] += 1
            item["status"] = "not_git"
            item["summary"] = "Path is not a Git repository."
            repo_items.append(item)
            continue

        metrics["repos_analyzed"] += 1
        item["status"] = "available"
        branch = _run_git(repo, ["branch", "--show-current"])
        item["branch"] = redactor.redact_text(branch.stdout.strip() or "detached")

        status = _run_git(repo, ["status", "--porcelain"])
        status_lines = [line for line in status.stdout.splitlines() if line.strip()]
        item["worktree_changes"] = len(status_lines)
        metrics["files_changed_in_worktree"] += len(status_lines)
        if status_lines:
            metrics["dirty_repos"] += 1

        parsed = _parse_git_log(repo, redactor)
        item.update(
            {
                "commits": parsed["commits"],
                "files_touched_by_commits": parsed["files_touched"],
                "first_commit_at": parsed["first_commit_at"],
                "last_commit_at": parsed["last_commit_at"],
            }
        )
        metrics["commits"] += parsed["commits"]
        metrics["files_touched_by_commits"] += parsed["files_touched"]
        metrics["additions"] += parsed["additions"]
        metrics["deletions"] += parsed["deletions"]
        metrics["extensions_touched"].update(parsed["extensions_touched"])
        metrics["active_days"] += parsed["active_days"]
        if parsed["first_commit_at"] or parsed["last_commit_at"]:
            metrics["date_windows"].append(
                {
                    "repo": item["path"],
                    "first_commit_at": parsed["first_commit_at"],
                    "last_commit_at": parsed["last_commit_at"],
                }
            )
        repo_items.append(item)

    if metrics["repos_analyzed"] == 0:
        source["status"] = "missing"
    elif metrics["repos_missing"] > 0:
        source["status"] = "partial"

    metrics["extensions_touched"] = dict(metrics["extensions_touched"])
    source["metrics"] = metrics
    source["items"] = repo_items
    source["errors"] = errors
    source["evidence"] = [
        {
            "id": "git.repositories",
            "source": "git",
            "evidence_level": "observed" if metrics["repos_analyzed"] else "missing",
            "summary": f"{metrics['repos_analyzed']} Git repositories analyzed from {metrics['repos_requested']} requested.",
            "count": metrics["repos_analyzed"],
        },
        {
            "id": "git.commits",
            "source": "git",
            "evidence_level": "observed" if metrics["commits"] else "missing",
            "summary": f"{metrics['commits']} commits parsed with numstat metadata.",
            "count": metrics["commits"],
        },
        {
            "id": "git.delivery_artifacts",
            "source": "git",
            "evidence_level": "observed" if metrics["commits"] else "missing",
            "summary": f"{metrics['commits']} Git commits available for delivery review.",
            "count": metrics["commits"],
        },
    ]
    source["privacy"] = {
        "raw_commit_subjects_included": False,
        "raw_remote_urls_included": False,
        "raw_author_emails_included": False,
    }
    return source


def collect_project_traces(repos: list[str], redactor: Redactor) -> dict[str, Any]:
    source = _empty_source("project_traces", "available")
    repo_paths = [Path(repo).expanduser().resolve() for repo in (repos or ["."])]
    metrics: dict[str, Any] = {
        "repos_requested": len(repo_paths),
        "repos_scanned": 0,
        "repos_missing": 0,
        "trace_categories": Counter(),
        "trace_items": 0,
        "raw_file_contents_included": False,
        "raw_paths_included": False,
    }
    for category in PROJECT_TRACE_RULES:
        metrics[category] = 0

    items: list[dict[str, Any]] = []
    for repo in repo_paths:
        item: dict[str, Any] = {
            "path": redactor.redact_path(repo),
            "status": "unknown",
            "categories": {},
        }
        if not repo.exists() or not repo.is_dir():
            metrics["repos_missing"] += 1
            item["status"] = "missing"
            items.append(item)
            continue

        metrics["repos_scanned"] += 1
        item["status"] = "available"
        category_counts = _project_trace_counts(repo)
        item["categories"] = category_counts
        for category, count in category_counts.items():
            metrics[category] += count
            if count:
                metrics["trace_categories"][category] += 1
                metrics["trace_items"] += count
        items.append(item)

    if metrics["repos_scanned"] == 0:
        source["status"] = "missing"
    elif metrics["repos_missing"]:
        source["status"] = "partial"

    metrics["trace_categories"] = dict(metrics["trace_categories"])
    source["metrics"] = metrics
    source["items"] = items
    source["evidence"] = [
        {
            "id": "project_traces.local_artifacts",
            "source": "project_traces",
            "evidence_level": "observed" if metrics["trace_items"] else "missing",
            "summary": f"{metrics['trace_items']} local project trace items detected across {len(metrics['trace_categories'])} categories.",
            "count": metrics["trace_items"],
        },
        {
            "id": "project_traces.workflow_artifacts",
            "source": "project_traces",
            "evidence_level": "observed"
            if _workflow_trace_count(metrics)
            else "missing",
            "summary": f"{_workflow_trace_count(metrics)} workflow, agent, prompt, skill, CI, or script traces detected.",
            "count": _workflow_trace_count(metrics),
        },
        {
            "id": "project_traces.delivery_artifacts",
            "source": "project_traces",
            "evidence_level": "observed"
            if _delivery_trace_count(metrics)
            else "missing",
            "summary": f"{_delivery_trace_count(metrics)} README, test, package, lockfile, or CI delivery traces detected.",
            "count": _delivery_trace_count(metrics),
        },
    ]
    source["privacy"] = {
        "raw_file_contents_included": False,
        "raw_paths_included": False,
        "raw_prompt_text_included": False,
        "secret_scan_applied_to_outputs": True,
        "ignored_dirs": [".git", "node_modules", "dist", "build", "coverage", ".venv", "__pycache__"],
    }
    return source


def collect_github(
    github_json: str | None,
    github_user: str | None,
    enable_github: bool,
    redactor: Redactor,
) -> dict[str, Any]:
    source = _empty_source("github", "skipped")
    metrics: dict[str, Any] = {
        "mode": "skipped",
        "records": 0,
        "pull_request_signals": 0,
        "issue_signals": 0,
        "repo_signals": 0,
        "stars": 0,
    }
    evidence_level = "missing"

    if github_json:
        path = Path(github_json).expanduser()
        metrics["mode"] = "local_json"
        if not path.exists():
            source["status"] = "missing"
            source["errors"] = [f"GitHub JSON file not found: {redactor.redact_path(path)}"]
        else:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                redacted = redactor.redact_obj(data)
                flat = list(_walk(redacted))
                metrics["records"] = _count_records(redacted)
                metrics["pull_request_signals"] = sum(
                    1 for key, value in flat if "pull" in key.lower() or "pr" == str(value).lower()
                )
                metrics["issue_signals"] = sum(1 for key, value in flat if "issue" in key.lower())
                metrics["repo_signals"] = sum(1 for key, value in flat if "repo" in key.lower())
                metrics["stars"] = _count_stars(redacted)
                source["status"] = "available"
                source["items"] = [{"path": redactor.redact_path(path), "status": "available"}]
                evidence_level = "observed"
            except Exception as exc:  # noqa: BLE001
                source["status"] = "partial"
                source["errors"] = [f"Could not parse GitHub JSON: {exc.__class__.__name__}"]

    elif enable_github and github_user:
        metrics["mode"] = "gh_api"
        if not shutil.which("gh"):
            source["status"] = "missing"
            source["errors"] = ["GitHub CLI 'gh' is not installed or not on PATH."]
        else:
            user = redactor.redact_text(github_user)
            api_result = _run_command(["gh", "api", f"/users/{github_user}"], timeout=15)
            if api_result.returncode != 0:
                source["status"] = "partial"
                source["errors"] = [redactor.redact_text(api_result.stderr.strip() or "gh api failed")]
            else:
                try:
                    data = json.loads(api_result.stdout)
                    metrics["records"] = 1
                    metrics["repo_signals"] = int(data.get("public_repos") or 0)
                    source["status"] = "available"
                    source["items"] = [{"github_user": user, "status": "available"}]
                    evidence_level = "observed"
                except Exception as exc:  # noqa: BLE001
                    source["status"] = "partial"
                    source["errors"] = [f"Could not parse gh api output: {exc.__class__.__name__}"]
    else:
        source["status"] = "skipped"
        source["errors"] = []

    source["metrics"] = metrics
    source["evidence"] = [
        {
            "id": "github.optional_data",
            "source": "github",
            "evidence_level": evidence_level,
            "summary": f"GitHub source status: {source['status']} via {metrics['mode']}.",
            "count": metrics["records"],
        }
    ]
    source["privacy"] = {
        "requires_explicit_enable_for_api": True,
        "raw_github_json_included": False,
        "raw_tokens_included": False,
    }
    return source


def _project_trace_counts(repo: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for category, candidates in PROJECT_TRACE_RULES.items():
        if category == "prompt_files":
            counts[category] = _count_prompt_files(repo, candidates)
        elif category == "skill_files":
            counts[category] = _count_skill_files(repo, candidates)
        elif category == "agent_config_files":
            counts[category] = _count_agent_config_files(repo, candidates)
        else:
            counts[category] = sum(1 for candidate in candidates if (repo / candidate).exists())
    return counts


def _count_prompt_files(repo: Path, candidates: list[str]) -> int:
    count = 0
    for candidate in candidates:
        path = repo / candidate
        if path.is_file():
            count += 1
        elif path.is_dir():
            count += _count_text_like_files(path)
    return count


def _count_skill_files(repo: Path, candidates: list[str]) -> int:
    count = 0
    for candidate in candidates:
        path = repo / candidate
        if path.is_file():
            count += 1
        elif path.is_dir():
            named = _count_named_files(path, "SKILL.md")
            count += named if named else _count_text_like_files(path)
    return count


def _count_agent_config_files(repo: Path, candidates: list[str]) -> int:
    count = 0
    for candidate in candidates:
        path = repo / candidate
        if path.is_file():
            count += 1
        elif path.is_dir():
            count += _count_text_like_files(path)
    return count


def _count_named_files(root: Path, name: str) -> int:
    try:
        return sum(1 for path in root.rglob(name) if path.is_file())
    except OSError:
        return 0


def _count_text_like_files(root: Path) -> int:
    suffixes = {".md", ".txt", ".yaml", ".yml", ".json", ".toml"}
    try:
        return sum(1 for path in root.rglob("*") if path.is_file() and path.suffix.lower() in suffixes)
    except OSError:
        return 0


def _workflow_trace_count(metrics: dict[str, Any]) -> int:
    return sum(
        int(metrics.get(key) or 0)
        for key in (
            "scripts",
            "ci_configs",
            "mcp_config_files",
            "agent_config_files",
            "prompt_files",
            "skill_files",
        )
    )


def _delivery_trace_count(metrics: dict[str, Any]) -> int:
    return sum(
        int(metrics.get(key) or 0)
        for key in (
            "readme_files",
            "docs",
            "test_dirs",
            "test_reports",
            "package_manifests",
            "lockfiles",
            "ci_configs",
        )
    )


def _collect_ai_jsonl_source(
    source_name: str,
    root: Path,
    redactor: Redactor,
    preferred_subdir: str,
) -> dict[str, Any]:
    source = _empty_source(source_name, "available")
    metrics: dict[str, Any] = {
        "root": redactor.redact_path(root),
        "files_scanned": 0,
        "records": 0,
        "parse_errors": 0,
        "active_days": 0,
        "first_seen_at": None,
        "last_seen_at": None,
        "user_turns": 0,
        "assistant_turns": 0,
        "tool_events": 0,
        "tool_names": Counter(),
        "tool_families": Counter(),
        "slash_commands": Counter(),
        "token_usage": Counter(),
        "planning_signals": 0,
        "context_signals": 0,
        "workflow_signals": 0,
        "long_context_records": 0,
        "secret_like_records_seen": 0,
    }
    if not root.exists():
        source["status"] = "missing"
        source["metrics"] = metrics
        source["evidence"] = [
            {
                "id": f"{source_name}.local_records",
                "source": source_name,
                "evidence_level": "missing",
                "summary": f"{source_name} directory was not found.",
                "path": redactor.redact_path(root),
                "count": 0,
            }
        ]
        source["privacy"] = _ai_privacy_policy()
        return source

    scan_root = root / preferred_subdir if (root / preferred_subdir).exists() else root
    files = _recent_jsonl_files(scan_root)
    metrics["files_scanned"] = len(files)
    if not files:
        source["status"] = "missing"
        source["metrics"] = metrics
        source["evidence"] = [
            {
                "id": f"{source_name}.local_records",
                "source": source_name,
                "evidence_level": "missing",
                "summary": f"No JSONL records were found under {redactor.redact_path(scan_root)}.",
                "path": redactor.redact_path(scan_root),
                "count": 0,
            }
        ]
        source["privacy"] = _ai_privacy_policy()
        return source

    parse_errors: list[str] = []
    record_budget = MAX_JSONL_RECORDS
    active_days: set[str] = set()
    seen_times: list[str] = []
    for file_path in files:
        if record_budget <= 0:
            break
        file_seen = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc).isoformat()
        seen_times.append(file_seen)
        active_days.add(file_seen[:10])
        file_cumulative_token_usage: Counter[str] = Counter()
        try:
            for line_no, line in enumerate(file_path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if record_budget <= 0:
                    break
                if not line.strip():
                    continue
                record_budget -= 1
                metrics["records"] += 1
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    metrics["parse_errors"] += 1
                    if len(parse_errors) < 5:
                        parse_errors.append(f"{redactor.redact_path(file_path)}:{line_no}")
                    continue
                record_time = _record_time(record)
                if record_time:
                    seen_times.append(record_time)
                    active_days.add(record_time[:10])
                _update_ai_metrics(metrics, record, redactor)
                token_usage, is_cumulative = _extract_token_usage(record)
                if is_cumulative:
                    file_cumulative_token_usage = token_usage
                else:
                    metrics["token_usage"].update(token_usage)
        except OSError as exc:
            metrics["parse_errors"] += 1
            if len(parse_errors) < 5:
                parse_errors.append(f"{redactor.redact_path(file_path)}: {exc.__class__.__name__}")
        if file_cumulative_token_usage:
            metrics["token_usage"].update(file_cumulative_token_usage)

    if metrics["parse_errors"]:
        source["status"] = "partial"
    if metrics["records"] == 0:
        source["status"] = "missing"

    metrics["active_days"] = len(active_days)
    if seen_times:
        seen_times.sort()
        metrics["first_seen_at"] = seen_times[0]
        metrics["last_seen_at"] = seen_times[-1]
    metrics["tool_names"] = dict(metrics["tool_names"].most_common(30))
    metrics["tool_families"] = dict(metrics["tool_families"])
    metrics["slash_commands"] = dict(metrics["slash_commands"].most_common(20))
    metrics["token_usage"] = dict(metrics["token_usage"])
    source["metrics"] = metrics
    source["errors"] = parse_errors
    source["evidence"] = [
        {
            "id": f"{source_name}.local_records",
            "source": source_name,
            "evidence_level": "observed" if metrics["records"] else "missing",
            "summary": f"{metrics['records']} JSONL records scanned from {metrics['files_scanned']} files.",
            "path": redactor.redact_path(scan_root),
            "count": metrics["records"],
        },
        {
            "id": f"{source_name}.tool_events",
            "source": source_name,
            "evidence_level": "observed" if metrics["tool_events"] else "missing",
            "summary": f"{metrics['tool_events']} tool events detected across {len(metrics['tool_families'])} tool families.",
            "count": metrics["tool_events"],
        },
        {
            "id": f"{source_name}.planning_context_workflow",
            "source": source_name,
            "evidence_level": "observed"
            if (metrics["planning_signals"] or metrics["context_signals"] or metrics["workflow_signals"])
            else "limited",
            "summary": (
                f"Planning={metrics['planning_signals']}, "
                f"context={metrics['context_signals']}, workflow={metrics['workflow_signals']} signals."
            ),
            "count": metrics["planning_signals"] + metrics["context_signals"] + metrics["workflow_signals"],
        },
    ]
    source["privacy"] = _ai_privacy_policy()
    return source


def _update_ai_metrics(metrics: dict[str, Any], record: Any, redactor: Redactor) -> None:
    serialized = json.dumps(record, ensure_ascii=False, default=str)
    if len(serialized) > 8000:
        metrics["long_context_records"] += 1
    if redactor.contains_secret_like_value(serialized[:12000]):
        metrics["secret_like_records_seen"] += 1

    for key, value in _walk(record):
        lowered_key = key.lower()
        if lowered_key.endswith("role") and str(value).lower() == "user":
            metrics["user_turns"] += 1
        if lowered_key.endswith("role") and str(value).lower() == "assistant":
            metrics["assistant_turns"] += 1
        if _looks_like_tool_key(lowered_key, value):
            tool_name = str(value)
            metrics["tool_events"] += 1
            metrics["tool_names"][tool_name] += 1
            metrics["tool_families"][_tool_family(tool_name)] += 1

    lower = serialized.lower()
    if any(term in lower for term in ("update_plan", "todowrite", "todo", "plan", "checklist", "break down", "任务拆解")):
        metrics["planning_signals"] += 1
    if any(term in lower for term in ("context", "memory", "summary", "compact", "resume", "上下文", "记忆")):
        metrics["context_signals"] += 1
    if any(term in lower for term in ("workflow", "automation", "skill", "script", "ci", "github actions", "工作流")):
        metrics["workflow_signals"] += 1
    for command in re.findall(r"(?<![\w:/.-])/[A-Za-z][A-Za-z0-9_-]{1,30}\b", serialized):
        metrics["slash_commands"][command.lower()] += 1


def _looks_like_tool_key(key: str, value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    lowered_value = value.lower()
    if lowered_value in {"tool_use", "tool_result", "function_call", "response", "assistant", "user"}:
        return False
    if key.endswith("name") and any(
        token in lowered_value
        for token in (
            "tool",
            "bash",
            "read",
            "write",
            "edit",
            "grep",
            "glob",
            "todowrite",
            "exec_command",
            "apply_patch",
            "web",
            "browser",
            "github",
            "task",
            "agent",
        )
    ):
        return True
    if key.endswith("recipient_name") or key.endswith("tool_name"):
        return True
    if key.endswith("type") and "tool" in value.lower():
        return True
    return False


def _tool_family(tool_name: str) -> str:
    lowered = tool_name.lower()
    if any(token in lowered for token in ("bash", "shell", "exec_command", "terminal", "command")):
        return "shell"
    if any(token in lowered for token in ("read", "grep", "glob", "rg", "search", "find")):
        return "search_read"
    if any(token in lowered for token in ("edit", "write", "patch", "multiedit", "apply_patch")):
        return "edit"
    if any(token in lowered for token in ("plan", "todo", "task")):
        return "planning"
    if any(token in lowered for token in ("web", "browser", "github", "gh")):
        return "external_context"
    if any(token in lowered for token in ("agent", "subagent", "multi_agent")):
        return "agent_orchestration"
    return "other_tool"


def _extract_token_usage(record: Any) -> tuple[Counter[str], bool]:
    if not isinstance(record, dict):
        return Counter(), False
    payload = record.get("payload")
    if isinstance(payload, dict) and payload.get("type") == "token_count":
        info = payload.get("info")
        if isinstance(info, dict) and isinstance(info.get("total_token_usage"), dict):
            return _normalize_token_usage(info["total_token_usage"]), True

    usage = record.get("usage")
    if isinstance(usage, dict):
        return _normalize_token_usage(usage), False
    return Counter(), False


def _normalize_token_usage(usage: dict[str, Any]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for key, value in usage.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
            continue
        amount = int(value)
        normalized = key.lower().replace("-", "_")
        if normalized in {"input_tokens", "prompt_tokens"}:
            counter["input_tokens"] += amount
        elif normalized in {"cached_input_tokens", "cached_tokens", "cache_read_input_tokens"}:
            counter["cached_tokens"] += amount
        elif normalized in {"cache_creation_input_tokens", "cache_creation_tokens"}:
            counter["cache_creation_tokens"] += amount
        elif normalized in {"output_tokens", "completion_tokens"}:
            counter["output_tokens"] += amount
        elif normalized in {"reasoning_output_tokens", "reasoning_tokens"}:
            counter["reasoning_output_tokens"] += amount
        elif normalized == "total_tokens":
            counter["total_tokens"] += amount
    if not counter.get("total_tokens"):
        counter["total_tokens"] = counter["input_tokens"] + counter["output_tokens"]
    return counter


def _record_time(record: Any) -> str | None:
    for key, value in _walk(record):
        lowered = key.lower()
        if not any(token in lowered for token in ("timestamp", "created_at", "updated_at", "time", "date")):
            continue
        if isinstance(value, (int, float)) and value > 1_000_000_000:
            seconds = value / 1000 if value > 10_000_000_000 else value
            try:
                return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat()
            except (OSError, ValueError):
                continue
        if isinstance(value, str) and len(value) >= 10:
            text = value.replace("Z", "+00:00")
            try:
                return datetime.fromisoformat(text).astimezone(timezone.utc).isoformat()
            except ValueError:
                continue
    return None


def _recent_jsonl_files(root: Path) -> list[Path]:
    try:
        files = [path for path in root.rglob("*.jsonl") if path.is_file()]
    except OSError:
        return []
    files.sort(key=lambda path: path.stat().st_mtime if path.exists() else 0, reverse=True)
    return files[:MAX_JSONL_FILES]


def _parse_git_log(repo: Path, redactor: Redactor) -> dict[str, Any]:
    log = _run_git(
        repo,
        [
            "log",
            "--max-count=200",
            "--numstat",
            "--date=iso-strict",
            "--pretty=format:@@@%x1f%H%x1f%an%x1f%ae%x1f%ad%x1f%s",
        ],
    )
    result = {
        "commits": 0,
        "files_touched": 0,
        "additions": 0,
        "deletions": 0,
        "extensions_touched": Counter(),
        "first_commit_at": None,
        "last_commit_at": None,
        "active_days": 0,
    }
    if log.returncode != 0:
        return result

    dates: list[str] = []
    active_days: set[str] = set()
    touched_files: set[str] = set()
    for line in log.stdout.splitlines():
        if line.startswith("@@@"):
            result["commits"] += 1
            parts = line.split("\x1f")
            if len(parts) >= 5:
                date = redactor.redact_text(parts[4])
                dates.append(date)
                active_days.add(date[:10])
            continue
        cols = line.split("\t")
        if len(cols) == 3:
            add, delete, file_path = cols
            if add.isdigit():
                result["additions"] += int(add)
            if delete.isdigit():
                result["deletions"] += int(delete)
            redacted_path = redactor.redact_text(file_path)
            touched_files.add(redacted_path)
            ext = Path(file_path).suffix.lower() or "[no_ext]"
            result["extensions_touched"][ext] += 1
    result["files_touched"] = len(touched_files)
    result["extensions_touched"] = dict(result["extensions_touched"].most_common(20))
    if dates:
        result["last_commit_at"] = dates[0]
        result["first_commit_at"] = dates[-1]
        result["active_days"] = len(active_days)
    return result


def _count_stars(value: Any) -> int:
    total = 0
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in {"stargazers_count", "stars", "star_count"} and isinstance(item, int):
                total += item
            else:
                total += _count_stars(item)
    elif isinstance(value, list):
        for item in value:
            total += _count_stars(item)
    return total


def _run_git(repo: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return _run_command(["git", "-C", str(repo), *args], timeout=15)


def _run_command(args: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except Exception as exc:  # noqa: BLE001
        return subprocess.CompletedProcess(args=args, returncode=1, stdout="", stderr=str(exc))


def _walk(value: Any, prefix: str = "") -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            yield path, item
            yield from _walk(item, path)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            path = f"{prefix}[{index}]"
            yield path, item
            yield from _walk(item, path)


def _count_records(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        for key in ("items", "nodes", "records", "data"):
            item = value.get(key)
            if isinstance(item, list):
                return len(item)
        return 1
    return 0


def _empty_source(name: str, status: str) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "metrics": {},
        "items": [],
        "evidence": [],
        "privacy": {},
        "errors": [],
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }


def _ai_privacy_policy() -> dict[str, Any]:
    return {
        "raw_prompt_content_included": False,
        "raw_completion_content_included": False,
        "raw_tool_arguments_included": False,
        "aggregated_counts_only": True,
    }
