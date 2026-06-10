"""Transforms collected signals into evidence-level interview material."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from . import __version__


DIMENSIONS = [
    ("ai_tool_fluency", "AI 工具熟练度"),
    ("task_decomposition", "任务拆解"),
    ("context_management", "上下文管理"),
    ("multi_tool_orchestration", "多工具编排"),
    ("ai_workflow_building", "AI 工作流建设"),
    ("engineering_delivery_linkage", "工程交付关联"),
]

EVIDENCE_LEVELS = ("observed", "inferred", "limited", "missing")


def build_assessment(
    candidate_label: str,
    sources: list[dict[str, Any]],
    redaction_report: dict[str, Any],
    authorized: bool,
) -> dict[str, Any]:
    source_map = {source["name"]: source for source in sources}
    evidence_catalog = [
        evidence
        for source in sources
        for evidence in source.get("evidence", [])
        if isinstance(evidence, dict)
    ]
    dimensions = [
        _dimension_ai_tool_fluency(source_map),
        _dimension_task_decomposition(source_map),
        _dimension_context_management(source_map),
        _dimension_multi_tool_orchestration(source_map),
        _dimension_ai_workflow(source_map),
        _dimension_delivery_linkage(source_map),
    ]
    questions = _build_interview_questions(dimensions)
    privacy_checklist = _build_privacy_checklist(sources, redaction_report, authorized)

    assessment = {
        "schema_version": "talentaiq-lite.v1",
        "tool_version": __version__,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "subject": {
            "candidate_label": candidate_label,
            "identity_redaction": "pseudonymous label only; legal identity is not inferred.",
        },
        "candidate_label": candidate_label,
        "candidate_authorization": {
            "authorized": authorized,
            "evidence_level": "observed" if authorized else "missing",
            "note": "CLI requires --authorize before local data collection.",
        },
        "assessment_boundaries": {
            "evidence_level": "observed",
            "no_auto_ranking": True,
            "no_auto_rejection": True,
            "no_hiring_recommendation": True,
            "statement": (
                "This report is evidence material for human interview preparation. "
                "It is not a candidate ranking, rejection, or hiring recommendation."
            ),
        },
        "policy": {
            "no_automatic_ranking": True,
            "no_elimination_decision": True,
            "no_hire_recommendation": True,
            "human_review_required": True,
            "protected_attributes_not_used": True,
            "evidence_only": True,
        },
        "evidence_levels": {
            "observed": "Directly visible in local records, local Git, or explicit optional GitHub input.",
            "inferred": "Derived from multiple observed signals; must be validated in interview.",
            "limited": "Sparse or partial evidence; use only as a follow-up prompt.",
            "missing": "No accessible evidence; do not draw a conclusion.",
        },
        "sources": sources,
        "evidence_catalog": evidence_catalog,
        "dimensions": dimensions,
        "findings": [
            conclusion
            for dimension in dimensions
            for conclusion in dimension.get("conclusions", [])
        ],
        "interview_questions": questions,
        "privacy_checklist": privacy_checklist,
        "limitations": _build_limitations(sources),
        "privacy": {
            "redaction_default": True,
            "redaction_enabled": True,
            "redaction_mode": redaction_report.get("redaction_mode", "default_safe"),
            "redacted_fields": redaction_report.get("redacted_fields", []),
            "redaction_report": redaction_report,
            "raw_prompt_or_completion_included": False,
            "raw_secrets_included": False,
            "raw_data_cache_written": False,
            "source_risks": _build_source_risks(sources),
        },
        "artifacts": {
            "markdown": "talentaiq_report.md",
            "json": "talentaiq_report.json",
            "interview_questions": "interview_questions.md",
            "privacy_checklist": "privacy_checklist.md",
            "poster_html": "poster.html",
            "svg": "interview_profile.svg",
        },
    }
    _assert_evidence_levels(assessment)
    return assessment


def _dimension_ai_tool_fluency(sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ai = _ai_metrics(sources)
    tool_events = ai["tool_events"]
    available_tools = [name for name in ("claude", "codex") if sources.get(name, {}).get("status") in {"available", "partial"}]
    refs = _refs(sources, ["claude.tool_events", "codex.tool_events", "claude.local_records", "codex.local_records"])
    if tool_events:
        level = "observed"
        claim = (
            f"本地 AI coding 记录显示 {', '.join(available_tools) or 'AI 工具'} 有工具调用活动，"
            f"共检测到 {tool_events} 个工具事件，覆盖 {len(ai['tool_families'])} 类工具家族。"
        )
    elif available_tools:
        level = "limited"
        claim = "本地 AI coding 目录可访问，但可解析的工具调用证据较少，只能作为面试追问线索。"
    else:
        level = "missing"
        claim = "未发现可访问的 Claude 或 Codex 本地记录，不能判断 AI 工具熟练度。"
    return _dimension(
        "ai_tool_fluency",
        "AI 工具熟练度",
        level,
        [_claim(claim, level, refs)],
        refs,
        [
            f"Claude status: {sources.get('claude', {}).get('status', 'missing')}",
            f"Codex status: {sources.get('codex', {}).get('status', 'missing')}",
            f"Tool families: {', '.join(sorted(ai['tool_families'])) if ai['tool_families'] else 'none'}",
        ],
        "请候选人现场解释最近一次使用 AI coding 工具完成任务时，哪些步骤交给 AI，哪些步骤自己复核。",
    )


def _dimension_task_decomposition(sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ai = _ai_metrics(sources)
    planning = ai["planning_signals"]
    git_commits = _git_metric(sources, "commits")
    project = sources.get("project_traces", {}).get("metrics", {})
    project_planning_traces = (
        int(project.get("agent_config_files") or 0)
        + int(project.get("prompt_files") or 0)
        + int(project.get("skill_files") or 0)
    )
    refs = _refs(
        sources,
        [
            "claude.planning_context_workflow",
            "codex.planning_context_workflow",
            "git.commits",
            "project_traces.local_artifacts",
        ],
    )
    if planning:
        level = "observed"
        claim = f"本地记录检测到 {planning} 个计划、todo 或任务拆解相关信号。"
    elif git_commits >= 3:
        level = "inferred"
        claim = f"Git 历史包含 {git_commits} 次提交，可作为任务拆解讨论入口，但没有直接证明 AI 协作中的拆解方式。"
    elif project_planning_traces:
        level = "limited"
        claim = f"检测到 {project_planning_traces} 个 agent/prompt/skill 相关本地工程痕迹，可作为任务拆解方式的追问入口。"
    elif git_commits:
        level = "limited"
        claim = "Git 提交数量较少，任务拆解证据稀疏，需要通过面试样例验证。"
    else:
        level = "missing"
        claim = "没有可访问的计划信号或提交历史，不能判断任务拆解能力。"
    return _dimension(
        "task_decomposition",
        "任务拆解",
        level,
        [_claim(claim, level, refs)],
        refs,
        [f"Planning signals: {planning}", f"Git commits: {git_commits}", f"Project planning traces: {project_planning_traces}"],
        "请候选人拿一个真实任务说明如何拆目标、定验收标准、安排 AI 迭代顺序。",
    )


def _dimension_context_management(sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ai = _ai_metrics(sources)
    project = sources.get("project_traces", {}).get("metrics", {})
    project_context_traces = (
        int(project.get("agent_config_files") or 0)
        + int(project.get("prompt_files") or 0)
        + int(project.get("skill_files") or 0)
        + int(project.get("mcp_config_files") or 0)
    )
    refs = _refs(
        sources,
        [
            "claude.planning_context_workflow",
            "codex.planning_context_workflow",
            "claude.local_records",
            "codex.local_records",
            "project_traces.workflow_artifacts",
        ],
    )
    if ai["context_signals"]:
        level = "observed"
        claim = f"本地记录检测到 {ai['context_signals']} 个上下文、记忆、摘要或续接相关信号。"
    elif ai["long_context_records"]:
        level = "limited"
        claim = f"检测到 {ai['long_context_records']} 条较长记录，但没有足够证据说明候选人如何管理上下文。"
    elif ai["records"]:
        level = "limited"
        claim = "AI 工具记录可访问，但上下文管理证据不足。"
    elif project_context_traces:
        level = "limited"
        claim = f"检测到 {project_context_traces} 个 agent、prompt、skill 或 MCP 配置痕迹，可作为上下文管理方式的追问线索。"
    else:
        level = "missing"
        claim = "没有可访问的 AI 工具记录，不能判断上下文管理。"
    return _dimension(
        "context_management",
        "上下文管理",
        level,
        [_claim(claim, level, refs)],
        refs,
        [
            f"Context signals: {ai['context_signals']}",
            f"Long-context records: {ai['long_context_records']}",
            f"Project context traces: {project_context_traces}",
        ],
        "请候选人说明在长任务中如何让 AI 保持约束、历史决策和未完成事项不丢失。",
    )


def _dimension_multi_tool_orchestration(sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ai = _ai_metrics(sources)
    git_available = sources.get("git", {}).get("status") in {"available", "partial"}
    project = sources.get("project_traces", {}).get("metrics", {})
    families = set(ai["tool_families"])
    if git_available:
        families.add("git")
    if any(int(project.get(key) or 0) for key in ("mcp_config_files", "agent_config_files", "scripts", "ci_configs")):
        families.add("project_traces")
    refs = _refs(sources, ["claude.tool_events", "codex.tool_events", "git.repositories", "project_traces.workflow_artifacts"])
    if len(families) >= 4:
        level = "observed"
        claim = f"本地证据显示候选人工作流涉及 {len(families)} 类工具/数据源：{', '.join(sorted(families))}。"
    elif len(families) >= 2:
        level = "inferred"
        claim = f"可见 {len(families)} 类工具/数据源协同痕迹，但编排策略需要面试复核。"
    elif families:
        level = "limited"
        claim = "只看到单一工具或数据源信号，不足以判断多工具编排能力。"
    else:
        level = "missing"
        claim = "没有可访问的多工具使用证据。"
    return _dimension(
        "multi_tool_orchestration",
        "多工具编排",
        level,
        [_claim(claim, level, refs)],
        refs,
        [f"Tool/data families: {', '.join(sorted(families)) if families else 'none'}"],
        "请候选人展示一个跨 AI 工具、终端、Git、测试或文档工具协作完成的任务，并解释每个工具的边界。",
    )


def _dimension_ai_workflow(sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ai = _ai_metrics(sources)
    project = sources.get("project_traces", {}).get("metrics", {})
    project_workflow_count = _project_workflow_count(project)
    refs = _refs(
        sources,
        [
            "claude.planning_context_workflow",
            "codex.planning_context_workflow",
            "project_traces.workflow_artifacts",
            "project_traces.local_artifacts",
        ],
    )
    workflow_count = ai["workflow_signals"] + project_workflow_count
    if workflow_count >= 3:
        level = "observed"
        claim = f"检测到 {workflow_count} 个 AI 工作流或工程化资产信号，包括脚本、CI、测试、Skill 或自动化相关痕迹。"
    elif workflow_count:
        level = "limited"
        claim = f"检测到 {workflow_count} 个工作流建设信号，但不足以单独判断稳定复用能力。"
    else:
        level = "missing"
        claim = "未发现 AI 工作流建设或工程自动化相关证据。"
    return _dimension(
        "ai_workflow_building",
        "AI 工作流建设",
        level,
        [_claim(claim, level, refs)],
        refs,
        [
            f"Workflow signals in AI logs: {ai['workflow_signals']}",
            f"Project trace workflow artifacts: {project_workflow_count}",
        ],
        "请候选人说明是否沉淀过可复用 prompt、脚本、检查清单、CI 或团队工作流，并给出失败后的改进例子。",
    )


def _dimension_delivery_linkage(sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ai = _ai_metrics(sources)
    git_commits = _git_metric(sources, "commits")
    files_touched = _git_metric(sources, "files_touched_by_commits")
    project = sources.get("project_traces", {}).get("metrics", {})
    project_delivery_count = _project_delivery_count(project)
    refs = _refs(
        sources,
        [
            "git.commits",
            "git.delivery_artifacts",
            "project_traces.delivery_artifacts",
            "claude.local_records",
            "codex.local_records",
        ],
    )
    if ai["records"] and git_commits:
        level = "inferred"
        claim = (
            f"报告同时观察到 {ai['records']} 条 AI 工具记录和 {git_commits} 次 Git 提交；"
            "这支持面试追问 AI 工作与工程交付的关联，但不自动声称因果关系。"
        )
    elif git_commits:
        level = "limited"
        claim = f"可见 {git_commits} 次 Git 提交和 {files_touched} 个变更文件，但缺少 AI 工具侧证据。"
    elif ai["records"]:
        level = "limited"
        if project_delivery_count:
            claim = (
                f"可见 AI 工具记录和 {project_delivery_count} 个本地工程痕迹，"
                "但缺少 Git commit、PR 或代码 diff 级交付证据。"
            )
        else:
            claim = "可见 AI 工具记录，但缺少本地 Git 交付证据。"
    elif project_delivery_count:
        level = "limited"
        claim = (
            f"可见 {project_delivery_count} 个 README、测试、CI、package 或 lockfile 等本地工程痕迹，"
            "但缺少 AI 工具记录和 Git commit/PR 级交付证据。"
        )
    else:
        level = "missing"
        claim = "缺少 AI 工具记录和 Git 交付证据，不能判断工程交付关联。"
    return _dimension(
        "engineering_delivery_linkage",
        "工程交付关联",
        level,
        [_claim(claim, level, refs)],
        refs,
        [
            f"AI records: {ai['records']}",
            f"Git commits: {git_commits}",
            f"Files touched: {files_touched}",
            f"Project delivery traces: {project_delivery_count}",
        ],
        "请候选人选一个提交或 PR，说明 AI 参与了哪些环节、如何测试、如何处理 AI 生成错误。",
    )


def _dimension(
    dimension_id: str,
    title: str,
    evidence_level: str,
    conclusions: list[dict[str, Any]],
    evidence_refs: list[str],
    observations: list[str],
    interview_focus: str,
) -> dict[str, Any]:
    return {
        "id": dimension_id,
        "name": title,
        "title": title,
        "summary": conclusions[0]["claim"] if conclusions else "",
        "evidence_level": evidence_level,
        "conclusions": conclusions,
        "evidence_refs": evidence_refs,
        "evidence": [{"ref": ref} for ref in evidence_refs],
        "observations": observations,
        "limitations": [_limitation_for_level(evidence_level)],
        "interview_focus": interview_focus,
        "interview_questions": [interview_focus],
        "allowed_use": "Human interview preparation only; not ranking, rejection, or hiring recommendation.",
    }


def _claim(text: str, evidence_level: str, evidence_refs: list[str]) -> dict[str, Any]:
    return {
        "claim": text,
        "evidence_level": evidence_level,
        "evidence_refs": evidence_refs,
        "evidence": [{"ref": ref} for ref in evidence_refs],
    }


def _build_interview_questions(dimensions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    for dimension in dimensions:
        level = dimension["evidence_level"]
        if level == "missing":
            question = f"这个维度缺少本地证据：请候选人现场提供一个能证明「{dimension['title']}」的真实任务样例。"
        elif level == "limited":
            question = f"这个维度只有稀疏证据：请候选人用一个端到端案例补充「{dimension['title']}」的具体做法。"
        else:
            question = dimension["interview_focus"]
        questions.append(
            {
                "dimension_id": dimension["id"],
                "dimension_title": dimension["title"],
                "question": question,
                "evidence_level": level,
                "evidence_refs": dimension["evidence_refs"],
                "source_refs": dimension["evidence_refs"],
                "purpose": "Validate evidence and surface concrete examples without making an automated hiring decision.",
            }
        )
    return questions


def _build_privacy_checklist(
    sources: list[dict[str, Any]],
    redaction_report: dict[str, Any],
    authorized: bool,
) -> list[dict[str, Any]]:
    checklist = [
        {
            "item": "candidate_authorization",
            "status": "complete" if authorized else "blocked",
            "evidence_level": "observed" if authorized else "missing",
            "note": "Local data collection requires explicit --authorize.",
        },
        {
            "item": "default_redaction",
            "status": "enabled",
            "evidence_level": "observed",
            "note": "Outputs are passed through secret and local identifier redaction.",
        },
        {
            "item": "raw_prompt_completion",
            "status": "not_included",
            "evidence_level": "observed",
            "note": "Collectors keep aggregate signals and do not include raw prompt/completion text.",
        },
        {
            "item": "secret_leak_prevention",
            "status": "checked",
            "evidence_level": "observed",
            "note": f"Secret-like redaction count: {redaction_report.get('secret_like_values_detected', 0)}.",
        },
    ]
    for source in sources:
        checklist.append(
            {
                "item": f"source_{source['name']}",
                "status": source.get("status", "missing"),
                "evidence_level": "observed" if source.get("status") in {"available", "partial", "skipped"} else "missing",
                "note": f"{source['name']} collection status recorded as {source.get('status')}.",
            }
        )
    return checklist


def _build_limitations(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    limitations = [
        {
            "id": "not_a_hiring_decision",
            "evidence_level": "observed",
            "text": "This report does not rank, reject, pass, fail, or recommend hiring a candidate.",
        },
        {
            "id": "no_causal_claim",
            "evidence_level": "observed",
            "text": "AI tool activity and Git delivery can be co-reported, but causality must be validated by interview.",
        },
        {
            "id": "raw_content_omitted",
            "evidence_level": "observed",
            "text": "Raw prompts, completions, and secret values are omitted by default, so findings are based on aggregate local signals.",
        },
    ]
    for source in sources:
        if source.get("status") in {"missing", "partial", "skipped"}:
            limitations.append(
                {
                    "id": f"source_{source['name']}_{source.get('status')}",
                    "evidence_level": "observed" if source.get("status") == "skipped" else "missing",
                    "text": f"{source['name']} source status is {source.get('status')}; related conclusions are limited or missing.",
                }
            )
    return limitations


def _build_source_risks(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    risks = []
    for source in sources:
        name = source["name"]
        if name in {"claude", "codex"}:
            risk = "Local AI logs can contain prompts, tool arguments, file paths, and secrets."
            handling = "Only aggregate counters and redacted path hints are emitted; raw prompt/completion content is omitted."
        elif name == "git":
            risk = "Git metadata can contain author emails, remote URLs, branch names, and commit subjects."
            handling = "Author emails, remote URLs, and raw commit subjects are not emitted."
        elif name == "project_traces":
            risk = "Local project traces can expose file names, repository structure, prompt specs, agent configs, MCP settings, and private project conventions."
            handling = "Only category counts and redacted repo-level paths are emitted; raw file contents, prompt text, config values, and full local paths are omitted."
        elif name == "github":
            risk = "GitHub data can expose private repository, issue, PR, or token context."
            handling = "GitHub is skipped unless local JSON is supplied or API mode is explicitly enabled."
        else:
            risk = "Unknown source risk."
            handling = "Source is recorded with status and redacted before output."
        risks.append(
            {
                "source": name,
                "status": source.get("status"),
                "risk": risk,
                "handling": handling,
                "evidence_level": "observed",
            }
        )
    return risks


def _limitation_for_level(evidence_level: str) -> str:
    if evidence_level == "observed":
        return "Observed evidence still requires human interpretation and candidate validation."
    if evidence_level == "inferred":
        return "Inference is based on aggregate signals and must be validated in interview."
    if evidence_level == "limited":
        return "Evidence is sparse; use only as a follow-up prompt."
    return "No accessible evidence; do not draw a conclusion."


def _ai_metrics(sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    combined = {
        "records": 0,
        "tool_events": 0,
        "tool_families": set(),
        "planning_signals": 0,
        "context_signals": 0,
        "workflow_signals": 0,
        "long_context_records": 0,
    }
    for name in ("claude", "codex"):
        metrics = sources.get(name, {}).get("metrics", {})
        combined["records"] += int(metrics.get("records") or 0)
        combined["tool_events"] += int(metrics.get("tool_events") or 0)
        combined["tool_families"].update((metrics.get("tool_families") or {}).keys())
        combined["planning_signals"] += int(metrics.get("planning_signals") or 0)
        combined["context_signals"] += int(metrics.get("context_signals") or 0)
        combined["workflow_signals"] += int(metrics.get("workflow_signals") or 0)
        combined["long_context_records"] += int(metrics.get("long_context_records") or 0)
    return combined


def _project_workflow_count(metrics: dict[str, Any]) -> int:
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


def _project_delivery_count(metrics: dict[str, Any]) -> int:
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


def _git_metric(sources: dict[str, dict[str, Any]], key: str) -> Any:
    return sources.get("git", {}).get("metrics", {}).get(key, 0)


def _refs(sources: dict[str, dict[str, Any]], wanted_ids: list[str]) -> list[str]:
    available = {
        evidence.get("id")
        for source in sources.values()
        for evidence in source.get("evidence", [])
        if isinstance(evidence, dict)
    }
    return [item for item in wanted_ids if item in available]


def _assert_evidence_levels(assessment: dict[str, Any]) -> None:
    for dimension in assessment["dimensions"]:
        if dimension["evidence_level"] not in EVIDENCE_LEVELS:
            raise ValueError(f"Invalid evidence level for {dimension['id']}")
        for conclusion in dimension["conclusions"]:
            if conclusion.get("evidence_level") not in EVIDENCE_LEVELS:
                raise ValueError(f"Conclusion missing evidence level in {dimension['id']}")
    for question in assessment["interview_questions"]:
        if question.get("evidence_level") not in EVIDENCE_LEVELS:
            raise ValueError(f"Question missing evidence level in {question['dimension_id']}")
    for item in assessment["privacy_checklist"]:
        if item.get("evidence_level") not in EVIDENCE_LEVELS:
            raise ValueError(f"Privacy checklist item missing evidence level in {item['item']}")
