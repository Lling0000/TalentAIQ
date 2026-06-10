"""Report renderers for TalentAIQ Lite."""

from __future__ import annotations

from html import escape
import json
from pathlib import Path
import textwrap
from typing import Any

from .redaction import Redactor


def write_outputs(assessment: dict[str, Any], output_dir: str | Path, redactor: Redactor) -> dict[str, str]:
    out = Path(output_dir).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    safe_assessment = redactor.redact_obj(assessment)
    paths = {
        "json": out / "talentaiq_report.json",
        "markdown": out / "talentaiq_report.md",
        "questions": out / "interview_questions.md",
        "privacy": out / "privacy_checklist.md",
        "poster_html": out / "poster.html",
        "svg": out / "interview_profile.svg",
    }
    paths["json"].write_text(
        json.dumps(safe_assessment, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    paths["markdown"].write_text(render_markdown(safe_assessment), encoding="utf-8")
    paths["questions"].write_text(render_questions(safe_assessment), encoding="utf-8")
    paths["privacy"].write_text(render_privacy_checklist(safe_assessment), encoding="utf-8")
    paths["poster_html"].write_text(render_poster_html(safe_assessment), encoding="utf-8")
    paths["svg"].write_text(render_svg(safe_assessment), encoding="utf-8")
    return {key: str(value) for key, value in paths.items()}


def render_markdown(assessment: dict[str, Any]) -> str:
    source_map = {source["name"]: source for source in assessment.get("sources", [])}
    ai = _combined_ai_metrics(source_map)
    git = source_map.get("git", {}).get("metrics", {})
    project = source_map.get("project_traces", {}).get("metrics", {})
    github = source_map.get("github", {}).get("metrics", {})
    dimensions = {dimension["id"]: dimension for dimension in assessment.get("dimensions", [])}
    token_usage = ai.get("token_usage") or {}
    total_tokens = int(token_usage.get("total_tokens") or 0)
    cache_ratio = _cache_leverage(token_usage)
    project_delivery = _project_delivery_trace_count(project)
    tool_families = sorted((ai.get("tool_families") or {}).keys())
    visible_tools = tool_families[:]
    if source_map.get("git", {}).get("status") in {"available", "partial"}:
        visible_tools.append("git repository")
    if int(project.get("trace_items") or 0):
        visible_tools.append("project traces")
    has_ai = int(ai.get("records") or 0) > 0
    has_delivery = int(git.get("commits") or 0) > 0
    lines = [
        "# TalentAIQ Lite · AI Coding 证据摘要",
        "",
        "> 本文档仅用于人工面试准备。",
        "> 它不是候选人评分、排名、淘汰依据，也不是录用建议。",
        "> 所有观察都必须通过面试、代码讲解、补充材料或现场任务验证。",
        "",
        "---",
        "",
        "## 1. 生成对象",
        "",
        "| 字段 | 内容 |",
        "| --- | --- |",
        f"| 候选人标签 | `{assessment['candidate_label']}` |",
        "| 报告类型 | AI coding 证据摘要 |",
        "| 使用场景 | 技术面试前准备 |",
        "| 自动决策用途 | 禁止 |",
        "| 是否需要人工复核 | 是 |",
        "",
        "---",
        "",
        "## 2. 数据源概览",
        "",
        "| 数据源 | 状态 | 可见记录 | 说明 |",
        "| --- | --- | ---: | --- |",
        *_evidence_summary_source_rows(source_map),
        "",
        "---",
        "",
        "## 3. 证据等级说明",
        "",
        "| 等级 | 含义 | 使用方式 |",
        "| --- | --- | --- |",
        "| `observed` | 有直接可观察信号 | 可以作为面试追问依据 |",
        "| `limited` | 有部分信号，但关键证据不足 | 只能作为重点验证点 |",
        "| `missing` | 当前数据源未发现证据 | 不能反推出候选人没有该能力 |",
        "| `inferred` | 基于间接信号推断 | 只能作为假设，不能当作事实 |",
        "",
        "---",
        "",
        "## 4. 核心证据摘要",
        "",
        "### 4.1 AI coding 使用活跃度",
        "",
        f"**证据等级：`{_dimension_level(dimensions, 'ai_tool_fluency')}`**",
        "",
        "可见本地 AI coding 记录中的活动信号：",
        "",
        "| 指标 | 数值 |",
        "| --- | ---: |",
        f"| 扫描记录数 | {_format_table_int(ai['records'])} |",
        f"| 活跃天数 | {_format_table_int(ai['active_days'])} |",
        f"| 工具事件数 | {_format_table_int(ai['tool_events'])} |",
        f"| 工具家族数 | {_format_table_int(len(ai['tool_families']))} |",
        f"| 总 token 量 | {_format_compact(total_tokens) if total_tokens else 'missing'} |",
        f"| cache leverage | {cache_ratio if cache_ratio else 'missing'} |",
        "",
        "**可支持的观察：**",
        "",
        _ai_activity_observation(ai),
        "",
        "**不能直接推出：**",
        "",
        "这些信号不能直接证明候选人的工程能力、代码质量、测试能力、系统设计能力或交付稳定性。",
        "",
        "---",
        "",
        "### 4.2 任务拆解与上下文管理",
        "",
        f"**证据等级：`{_combined_level(dimensions, ['task_decomposition', 'context_management', 'ai_workflow_building'])}`**",
        "",
        "| 信号类型 | 数值 |",
        "| --- | ---: |",
        f"| planning / todo / task decomposition signals | {_format_table_int(ai['planning_signals'])} |",
        f"| context / memory / continuation signals | {_format_table_int(ai['context_signals'])} |",
        f"| workflow signals | {_format_table_int(ai['workflow_signals'])} |",
        f"| long-context records | {_format_table_int(ai['long_context_records'])} |",
        "",
        "**可支持的观察：**",
        "",
        "候选人在 AI coding 过程中可能存在任务规划、多轮上下文维护、工作流迭代等行为。",
        "",
        "**需要面试验证：**",
        "",
        "这些信号只能说明出现过相关行为，不能说明拆解质量高，也不能说明候选人能稳定管理复杂工程上下文。",
        "",
        "---",
        "",
        "### 4.3 多工具使用",
        "",
        f"**证据等级：`{_dimension_level(dimensions, 'multi_tool_orchestration')}`**",
        "",
        "可见工具或数据源包括：",
        "",
        "| 类型 | 观察 |",
        "| --- | --- |",
        *(_tool_or_source_rows(visible_tools) or ["| none | 当前没有可见痕迹 |"]),
        "",
        "**可支持的观察：**",
        "",
        "候选人可能具备跨 AI 工具、终端、代码编辑、搜索读取、本地仓库和工程文件的协作使用经验。",
        "",
        "**不能直接推出：**",
        "",
        "多工具使用痕迹不等于成熟工程工作流。需要验证候选人是否理解每个工具的边界、失败模式、回滚方式和验证方式。",
        "",
        "---",
        "",
        "### 4.4 工程交付关联",
        "",
        f"**证据等级：`{_dimension_level(dimensions, 'engineering_delivery_linkage')}`**",
        "",
        "当前交付证据：",
        "",
        "| 指标 | 数值 |",
        "| --- | ---: |",
        f"| Git commits | {_format_table_int(int(git.get('commits') or 0))} |",
        f"| PR / issue 数据 | {_format_table_int(int(github.get('pull_request_signals') or 0) + int(github.get('issue_signals') or 0))} |",
        f"| files touched by commits | {_format_table_int(int(git.get('files_touched_by_commits') or 0))} |",
        f"| 本地工程交付痕迹 | {_format_table_int(project_delivery)} |",
        "",
        "**风险说明：**",
        "",
        "当前证据能说明存在 AI coding 使用记录和部分工程结构痕迹，但不能充分证明这些 AI 使用已经转化为真实、可审查、可交付的工程成果。",
        "",
        "**必须补充验证：**",
        "",
        "面试中应要求候选人提供至少一个真实 commit、PR、项目交付物或代码 diff，并现场解释 AI 参与环节、人工修改点、测试方式和错误修正过程。",
        "",
        "---",
        "",
        "## 5. 六个面试验证维度",
        "",
    ]

    lines.extend(
        _verification_dimension_sections(dimensions)
    )
    lines.extend(
        [
            "---",
            "",
            "## 6. 面试官使用建议",
            "",
            "建议按以下流程使用本报告：",
            "",
            "1. 先让候选人选择一个真实 AI coding 项目；",
            "2. 要求展示需求、关键 prompt、AI 输出和最终代码；",
            "3. 要求说明人工修改点；",
            "4. 要求解释测试策略；",
            "5. 要求复盘一次 AI 出错案例；",
            "6. 最后安排一个小型现场修改或 bug 修复任务。",
            "",
            "---",
            "",
            "## 7. 禁用用途",
            "",
            "本报告不得用于：",
            "",
            "1. 自动候选人排名；",
            "2. 自动淘汰候选人；",
            "3. 自动推荐录用；",
            "4. 替代代码审查；",
            "5. 替代技术面试；",
            "6. 替代人工判断；",
            "7. 基于受保护属性进行筛选、评价或追问。",
            "",
            "---",
            "",
            "## 8. 最终一句话摘要",
            "",
            _final_one_sentence(has_ai, has_delivery, project_delivery),
            "",
        ]
    )
    return "\n".join(lines)


def _evidence_summary_source_rows(source_map: dict[str, dict[str, Any]]) -> list[str]:
    codex = source_map.get("codex", {})
    claude = source_map.get("claude", {})
    git = source_map.get("git", {})
    project = source_map.get("project_traces", {})
    github = source_map.get("github", {})
    codex_metrics = codex.get("metrics", {})
    claude_metrics = claude.get("metrics", {})
    git_metrics = git.get("metrics", {})
    project_metrics = project.get("metrics", {})
    github_metrics = github.get("metrics", {})
    git_commits = int(git_metrics.get("commits") or 0)
    git_repos = int(git_metrics.get("repos_analyzed") or 0)
    git_status = "available but empty" if git_repos and not git_commits else git.get("status", "missing")
    return [
        (
            f"| Codex 本地记录 | {codex.get('status', 'missing')} | "
            f"{_format_table_int(int(codex_metrics.get('records') or 0))} | {_source_note('codex', codex, codex_metrics)} |"
        ),
        (
            f"| Claude 本地记录 | {claude.get('status', 'missing')} | "
            f"{_format_table_int(int(claude_metrics.get('records') or 0))} | {_source_note('claude', claude, claude_metrics)} |"
        ),
        f"| Git commits | {git_status} | {_format_table_int(git_commits)} | {_source_note('git', git, git_metrics)} |",
        (
            f"| 本地工程痕迹 | {project.get('status', 'missing')} | "
            f"{_format_table_int(int(project_metrics.get('trace_items') or 0))} | {_project_trace_note(project_metrics)} |"
        ),
        (
            f"| GitHub | {github.get('status', 'missing')} | "
            f"{_format_table_int(int(github_metrics.get('records') or 0))} | {_source_note('github', github, github_metrics)} |"
        ),
    ]


def _project_trace_note(metrics: dict[str, Any]) -> str:
    labels = {
        "readme_files": "README",
        "docs": "docs",
        "test_dirs": "测试目录",
        "test_reports": "测试报告",
        "scripts": "scripts",
        "ci_configs": "CI",
        "package_manifests": "package",
        "lockfiles": "lockfile",
        "mcp_config_files": "MCP",
        "agent_config_files": "agent config",
        "prompt_files": "prompt",
        "skill_files": "skill",
    }
    visible = [label for key, label in labels.items() if int(metrics.get(key) or 0)]
    if visible:
        return "包含 " + "、".join(visible[:5]) + " 等工程结构信号"
    return "当前未发现 README、测试、package、MCP、agent、prompt 或 skill 等工程结构信号"


def _format_table_int(value: int) -> str:
    return f"{int(value):,}"


def _cache_leverage(token_usage: dict[str, Any]) -> str | None:
    cached_tokens = int(token_usage.get("cached_tokens") or 0)
    input_tokens = int(token_usage.get("input_tokens") or 0)
    cache_base = max(input_tokens - cached_tokens, 0)
    if not cached_tokens or not cache_base:
        return None
    return f"1:{cached_tokens / cache_base:.1f}"


def _dimension_level(dimensions: dict[str, dict[str, Any]], dimension_id: str) -> str:
    return dimensions.get(dimension_id, {}).get("evidence_level", "missing")


def _combined_level(dimensions: dict[str, dict[str, Any]], dimension_ids: list[str]) -> str:
    order = ["observed", "inferred", "limited", "missing"]
    levels = [_dimension_level(dimensions, dimension_id) for dimension_id in dimension_ids]
    return min(levels, key=lambda level: order.index(level) if level in order else len(order))


def _ai_activity_observation(ai: dict[str, Any]) -> str:
    tool_events = int(ai.get("tool_events") or 0)
    if tool_events:
        families = _format_tool_families(ai.get("tool_families") or {})
        return (
            "候选人存在较高频的 AI coding 工具使用行为，"
            f"并且使用过程涉及 {families} 等多类工具。"
        )
    if int(ai.get("records") or 0):
        return "候选人存在可见 AI coding 记录，但当前可解析的工具调用信号较少。"
    return "当前未发现可解析的 AI coding 本地记录，不能判断 AI coding 使用活跃度。"


def _tool_or_source_rows(names: list[str]) -> list[str]:
    labels = {
        "agent_orchestration": "agent orchestration",
        "search_read": "search/read",
        "shell": "shell",
        "edit": "edit",
        "external_context": "external context",
        "planning": "planning",
        "git repository": "git repository",
        "project traces": "project traces",
        "other_tool": "other tool",
    }
    rows = []
    for name in names:
        rows.append(f"| {labels.get(name, name)} | 有使用痕迹 |")
    return rows


def _verification_dimension_sections(dimensions: dict[str, dict[str, Any]]) -> list[str]:
    sections = [
        (
            "5.1 AI 工具熟练度",
            "ai_tool_fluency",
            [
                "哪些步骤交给 AI？",
                "哪些步骤由自己复核？",
                "AI 输出中有哪些错误？",
                "最终代码如何验证？",
            ],
        ),
        (
            "5.2 任务拆解",
            "task_decomposition",
            [
                "如何拆目标？",
                "如何定义验收标准？",
                "如何安排 AI 迭代顺序？",
                "哪些步骤不能直接交给 AI？",
            ],
        ),
        (
            "5.3 上下文管理",
            "context_management",
            [
                "如何保持需求约束？",
                "如何保存历史决策？",
                "如何维护未完成事项？",
                "如何记录已知错误和风险点？",
            ],
        ),
        (
            "5.4 多工具编排",
            "multi_tool_orchestration",
            [
                "每个工具负责什么？",
                "哪些步骤必须人工确认？",
                "如何避免 AI 误改无关文件？",
                "如何回滚和验证结果？",
            ],
        ),
        (
            "5.5 AI 工作流建设",
            "ai_workflow_building",
            [
                "是否沉淀过可复用 prompt？",
                "是否沉淀过脚本？",
                "是否沉淀过检查清单？",
                "是否沉淀过测试模板？",
                "是否接入过 CI 或团队工作流？",
            ],
        ),
        (
            "5.6 工程交付关联",
            "engineering_delivery_linkage",
            [
                "真实需求是什么？",
                "AI 参与了哪些环节？",
                "最终代码或交付物在哪里？",
                "如何测试？",
                "AI 生成过什么错误？",
                "候选人如何修正？",
                "为什么最终认为可以交付？",
            ],
        ),
    ]
    lines: list[str] = []
    for section_index, (title, dimension_id, questions) in enumerate(sections):
        lines.extend(
            [
                f"### {title}",
                "",
                f"**证据等级：`{_dimension_level(dimensions, dimension_id)}`**",
                "",
                "**面试追问：**",
                "",
            ]
        )
        if dimension_id == "engineering_delivery_linkage":
            lines.extend(["这个维度证据不足，应要求候选人用一个端到端案例补充说明：", ""])
        else:
            lines.extend(["请候选人现场结合真实任务说明：", ""])
        lines.extend(f"{index}. {question}" for index, question in enumerate(questions, 1))
        if dimension_id == "ai_workflow_building":
            lines.extend(["", "并要求候选人给出一次失败后的改进案例。"])
        if section_index < len(sections) - 1:
            lines.extend(["", "---", ""])
        else:
            lines.extend([""])
    return lines


def _final_one_sentence(has_ai: bool, has_delivery: bool, project_delivery: int) -> str:
    if has_ai and has_delivery:
        return (
            "当前证据同时显示 AI coding 使用和 Git 交付记录，可作为面试追问材料；"
            "但仍不能替代代码审查、技术面试或人工判断。"
        )
    if has_ai:
        if project_delivery:
            return (
                "当前证据显示候选人存在高频 AI coding 使用和部分本地工程结构痕迹，"
                "但缺少 Git commit、PR、代码 diff 和测试结果等交付级证据；因此，本报告最适合作为面试追问材料，而不是能力评分或录用判断依据。"
            )
        return (
            "当前证据显示候选人存在 AI coding 使用记录，但缺少工程交付级证据；"
            "因此，本报告只能作为面试追问材料。"
        )
    return "当前关键 AI coding 和工程交付证据不足，本报告主要用于列出证据缺口和后续验证问题。"


def _source_overview_rows(source_map: dict[str, dict[str, Any]]) -> list[str]:
    codex = source_map.get("codex", {})
    claude = source_map.get("claude", {})
    git = source_map.get("git", {})
    project = source_map.get("project_traces", {})
    github = source_map.get("github", {})
    codex_metrics = codex.get("metrics", {})
    claude_metrics = claude.get("metrics", {})
    git_metrics = git.get("metrics", {})
    project_metrics = project.get("metrics", {})
    github_metrics = github.get("metrics", {})
    git_commits = int(git_metrics.get("commits") or 0)
    git_repos = int(git_metrics.get("repos_analyzed") or 0)
    git_status = "available but empty" if git_repos and not git_commits else git.get("status", "missing")
    return [
        (
            f"| Codex local records | {codex.get('status', 'missing')} | "
            f"{int(codex_metrics.get('records') or 0)} | {_source_note('codex', codex, codex_metrics)} |"
        ),
        (
            f"| Claude local records | {claude.get('status', 'missing')} | "
            f"{int(claude_metrics.get('records') or 0)} | {_source_note('claude', claude, claude_metrics)} |"
        ),
        f"| Git commits | {git_status} | {git_commits} | {_source_note('git', git, git_metrics)} |",
        (
            f"| 本地工程痕迹 | {project.get('status', 'missing')} | "
            f"{int(project_metrics.get('trace_items') or 0)} | {_source_note('project_traces', project, project_metrics)} |"
        ),
        (
            f"| GitHub | {github.get('status', 'missing')} | "
            f"{int(github_metrics.get('records') or 0)} | {_source_note('github', github, github_metrics)} |"
        ),
    ]


def _source_note(name: str, source: dict[str, Any], metrics: dict[str, Any]) -> str:
    status = source.get("status", "missing")
    if name == "codex":
        records = int(metrics.get("records") or 0)
        return "检测到大量 AI coding 使用记录" if records else "当前未发现 Codex 本地记录"
    if name == "claude":
        records = int(metrics.get("records") or 0)
        return "检测到 Claude 本地使用记录" if records else "当前未发现 Claude 本地记录"
    if name == "git":
        commits = int(metrics.get("commits") or 0)
        repos = int(metrics.get("repos_analyzed") or 0)
        if commits:
            return "检测到提交级工程交付证据"
        if repos:
            return "当前缺少提交级工程交付证据"
        return "当前未发现可分析 Git 仓库"
    if name == "project_traces":
        count = int(metrics.get("trace_items") or 0)
        if count:
            return "扫描 README、tests、scripts、CI、package、MCP、agent、prompt、skill 等本地工程痕迹"
        return "当前未发现可用本地工程痕迹"
    if name == "github":
        if status == "available":
            return "已纳入可用 GitHub 数据"
        if status == "skipped":
            return "未纳入远程仓库或 PR 数据"
        return "当前未发现可用 GitHub 数据"
    return status


def _data_integrity_judgement(
    has_ai: bool,
    has_delivery: bool,
    source_map: dict[str, dict[str, Any]],
) -> str:
    if has_ai and has_delivery:
        return (
            "当前数据同时包含 AI coding 使用记录和本地 Git 提交痕迹，可用于准备 AI 协作开发、任务拆解和工程交付关联的面试追问。"
            "但报告仍不能替代代码审查、PR 复盘或现场技术验证。"
        )
    if has_ai:
        return (
            "当前数据能较好反映候选人的 AI coding 工具使用习惯，但不能充分证明最终工程交付质量。"
            "尤其是缺少 Git commit、PR、测试结果、代码 diff 和交付文件等证据，因此所有工程交付相关判断应标记为 `limited`。"
        )
    if any(source.get("status") == "available" for source in source_map.values()):
        return (
            "当前仅有部分工程痕迹或可用数据源，AI coding 过程证据不足。报告应主要用于定位证据缺口，不能据此判断候选人的 AI 工程能力。"
        )
    return (
        "当前关键数据源缺失，报告只能说明缺少可访问证据。`missing` 不代表候选人没有相关能力，必须通过补充材料或现场任务验证。"
    )


def _dimension_report_section(
    index: int,
    dimension: dict[str, Any],
    source_map: dict[str, dict[str, Any]],
    ai: dict[str, Any],
) -> list[str]:
    dimension_id = dimension["id"]
    profile = _dimension_profile(dimension_id, source_map, ai)
    display_title = {
        "task_decomposition": "任务拆解能力",
        "context_management": "上下文管理能力",
        "multi_tool_orchestration": "多工具编排能力",
        "ai_workflow_building": "AI 工作流建设能力",
    }.get(dimension_id, dimension["title"])
    lines = [
        f"### 3.{index} {display_title}",
        "",
        f"**Evidence level：{dimension['evidence_level']}**",
        "",
        f"**证据来源：** {profile['sources']}",
        "",
        "**观察结论：**",
        profile["observation"],
        "",
        "**不能直接推出：**",
        profile["cannot_infer"],
        "",
    ]
    if profile.get("risks"):
        lines.extend(["**关键风险：**", ""])
        lines.extend(f"{i}. {risk}" for i, risk in enumerate(profile["risks"], 1))
        lines.append("")
    lines.extend(["**面试验证重点：**", ""])
    lines.extend(f"{i}. {item}" for i, item in enumerate(profile["focus"], 1))
    lines.extend(
        [
            "",
            "**建议现场追问：**",
            profile["followup"],
            "",
            "---",
            "",
        ]
    )
    return lines


def _dimension_profile(
    dimension_id: str,
    source_map: dict[str, dict[str, Any]],
    ai: dict[str, Any],
) -> dict[str, Any]:
    git = source_map.get("git", {}).get("metrics", {})
    project = source_map.get("project_traces", {}).get("metrics", {})
    tool_events = int(ai.get("tool_events") or 0)
    planning = int(ai.get("planning_signals") or 0)
    context = int(ai.get("context_signals") or 0)
    workflow = int(ai.get("workflow_signals") or 0)
    long_context = int(ai.get("long_context_records") or 0)
    ai_records = int(ai.get("records") or 0)
    git_commits = int(git.get("commits") or 0)
    files_touched = int(git.get("files_touched_by_commits") or 0)
    families = _format_tool_families(ai.get("tool_families") or {})
    project_workflow = _project_workflow_trace_count(project)
    project_delivery = _project_delivery_trace_count(project)
    profiles: dict[str, dict[str, Any]] = {
        "ai_tool_fluency": {
            "sources": "Codex tool events, Claude/Codex local records",
            "observation": (
                f"检测到 {tool_events} 个 AI coding 工具事件，覆盖 {families} 等工具家族。"
                "这说明候选人存在使用 AI coding 工具的行为，而非只能从自述判断。"
            )
            if tool_events
            else "当前未检测到可解析的 AI coding 工具事件，不能判断候选人的 AI 工具熟练度。",
            "cannot_infer": "工具调用次数不能单独证明候选人具备高质量 AI 工程能力，也不能证明其具备代码审查、测试设计或系统设计能力。",
            "focus": [
                "候选人如何判断哪些任务适合交给 AI？",
                "候选人如何检查 AI 生成代码的正确性？",
                "候选人遇到 AI 生成错误时如何定位和修正？",
                "候选人是否能展示一次完整的 AI 协作开发过程？",
            ],
            "followup": "请候选人选择最近一个使用 AI coding 工具完成的任务，说明任务目标、使用的工具、关键 prompt、AI 输出、人工修改点、测试方式和最终结果。",
        },
        "task_decomposition": {
            "sources": "Codex/Claude planning and context workflow signals",
            "observation": (
                f"检测到 {planning} 个 planning、todo 或任务拆解相关信号，说明候选人在 AI coding 过程中存在任务规划、步骤拆分或迭代控制行为。"
            )
            if planning
            else "当前没有检测到 planning、todo 或任务拆解相关信号，不能判断候选人的任务拆解方式。",
            "cannot_infer": "planning 信号数量不能直接说明候选人拆解质量高，也不能说明其能在复杂工程场景中定义清晰验收标准。",
            "focus": [
                "是否能把模糊需求拆成可执行任务？",
                "是否能定义完成标准和测试标准？",
                "是否能安排 AI 迭代顺序，而不是一次性要求 AI 完成全部任务？",
                "是否能识别任务中的风险点和未知项？",
            ],
            "followup": "请候选人拿一个真实开发任务，现场拆成 5 到 8 个子任务，并说明每一步交给 AI 的输入、期望输出、人工复核点和验收标准。",
        },
        "context_management": {
            "sources": "Codex/Claude local records, planning/context workflow",
            "observation": (
                f"检测到 {context} 个上下文、摘要、续接或记忆相关信号，其中包含 {long_context} 条长上下文记录。"
                "说明候选人可能有长任务、多轮任务或持续上下文管理经验。"
            )
            if context or long_context
            else "当前没有检测到足够的上下文、摘要、续接或记忆相关信号，不能判断上下文管理能力。",
            "cannot_infer": "长上下文使用不等于上下文管理质量高。需要验证候选人是否能主动维护约束、历史决策、未完成事项和错误记录。",
            "focus": [
                "长任务中如何防止 AI 忘记约束？",
                "如何保存关键决策？",
                "如何处理 AI 在多轮对话中的漂移？",
                "如何让 AI 接续之前未完成的任务？",
            ],
            "followup": "请候选人说明一次超过 30 分钟或多轮迭代的 AI coding 任务，重点讲清楚如何维护背景信息、约束条件、任务状态和待办事项。",
        },
        "multi_tool_orchestration": {
            "sources": "Codex/Claude tool events, local tool family signals",
            "observation": (
                f"检测到 {families} 等多个工具或数据源信号，说明候选人可能使用过多工具协同完成任务。"
            )
            if ai.get("tool_families")
            else "当前没有检测到多工具协同信号，不能判断多工具编排能力。",
            "cannot_infer": "多工具痕迹不能直接说明候选人具备成熟工程工作流。需要验证其是否理解不同工具的边界、失败模式和协作顺序。",
            "focus": [
                "什么时候用 AI agent，什么时候自己写代码？",
                "什么时候用 shell、测试、搜索、文档或 Git？",
                "如何避免 AI 误改无关文件？",
                "如何回滚、验证和审查 AI 修改？",
            ],
            "followup": "请候选人展示一个跨 AI 工具、终端、测试和版本控制完成的任务，说明每个工具负责什么、哪些步骤必须人工确认、哪里曾经失败过。",
        },
        "ai_workflow_building": {
            "sources": "Codex/Claude workflow signals, project_traces workflow artifacts",
            "observation": (
                f"检测到 {workflow} 个 AI 工作流信号和 {project_workflow} 个本地工程工作流痕迹。"
                "说明候选人可能有把 AI 使用沉淀为脚本、测试、说明文档或工作流的行为。"
            )
            if workflow or project_workflow
            else "当前未检测到 AI 工作流沉淀或工程化资产相关证据，不能判断工作流建设能力。",
            "cannot_infer": "存在 workflow signals 不代表候选人建立了稳定、可复用、团队级工作流。需要查看具体资产质量。",
            "focus": [
                "是否沉淀过可复用 prompt？",
                "是否建立过 AI 使用检查清单？",
                "是否把 AI 输出接入测试、CI 或代码审查流程？",
                "是否能从失败案例中改进工作流？",
            ],
            "followup": "请候选人展示一个自己沉淀过的 prompt、脚本、测试模板、CI 流程或 AI 使用规范，并说明它解决了什么重复问题，以及后来如何改进。",
        },
        "engineering_delivery_linkage": {
            "sources": "Codex/Claude local records, Git delivery artifacts",
            "observation": (
                f"当前可见 {ai_records} 条 AI 使用记录、{git_commits} 次 Git commit 和 {files_touched} 个提交级变更文件。"
                "这可以作为追问 AI 工作与工程交付关联的入口，但不能自动声称因果关系。"
            )
            if git_commits
            else (
                f"当前可见 {ai_records} 条 AI 使用记录和 {project_delivery} 个本地工程交付痕迹，"
                "但没有发现 Git commits、files touched 或 PR 级交付证据。因此，报告只能证明候选人存在 AI coding 使用或工程结构痕迹，不能充分证明这些行为已经转化为真实工程交付。"
            ),
            "cannot_infer": "AI 使用记录不能直接证明工程质量、交付稳定性、团队协作能力或候选人本人对最终代码的理解程度。",
            "risks": [
                "可能存在大量 AI 交互，但缺少最终代码产出。",
                "可能存在本地实验，但缺少可审查提交。",
                "可能数据源没有覆盖真实工作仓库。",
                "不能据此判断候选人的工程质量、交付稳定性或团队协作能力。",
            ]
            if not git_commits
            else [],
            "focus": [
                "必须要求候选人提供一个真实 commit、PR、项目或交付物。",
                "必须查看 AI 参与前后的代码变化。",
                "必须询问测试方法和错误修正过程。",
                "必须验证候选人本人是否理解最终代码。",
            ],
            "followup": "请候选人选择一个真实 PR 或提交，说明 AI 参与了哪些环节、哪些代码是自己重写的、如何测试、遇到过哪些 AI 生成错误，以及最终为什么认为代码可以交付。",
        },
    }
    return profiles[dimension_id]


def _overall_judgement(has_ai: bool, has_delivery: bool, assessment: dict[str, Any]) -> str:
    observed = sum(1 for dimension in assessment.get("dimensions", []) if dimension.get("evidence_level") == "observed")
    if has_ai and has_delivery:
        return (
            f"当前证据显示，候选人在 {observed} 个维度上存在可观察 AI 工程行为，并且有本地 Git 交付痕迹可供追问。"
            "但报告仍只适合作为技术面试准备材料，不能作为能力评分、候选人排序或录用判断依据。"
        )
    if has_ai:
        return (
            "当前证据显示，候选人很可能是 AI coding 工具的高频使用者，并且在任务拆解、上下文管理、多工具使用和工作流建设方面存在可观察行为。"
            "\n\n"
            "但由于缺少 Git commit、PR、代码 diff 和测试结果，当前报告不能充分证明候选人的工程交付能力。因此，本报告最适合作为技术面试前的追问准备材料，而不是能力评分或录用判断依据。"
        )
    return (
        "当前关键 AI coding 和工程交付证据不足，不能对候选人的 AI 工程能力形成事实性判断。"
        "报告应主要用于列出补充材料需求和现场验证问题。"
    )


def _format_tool_families(counter: dict[str, Any]) -> str:
    if not counter:
        return "none"
    names = {
        "agent_orchestration": "agent orchestration",
        "search_read": "search/read",
        "shell": "shell",
        "edit": "edit",
        "external_context": "external context",
        "planning": "planning",
        "git": "git",
        "other_tool": "other tool",
    }
    return "、".join(names.get(key, key) for key in sorted(counter))


def _project_workflow_trace_count(metrics: dict[str, Any]) -> int:
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


def _project_delivery_trace_count(metrics: dict[str, Any]) -> int:
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


def render_questions(assessment: dict[str, Any]) -> str:
    lines = [
        "# TalentAIQ Lite 面试追问题",
        "",
        f"- 候选人标签：`{assessment['candidate_label']}`",
        "- 原则：追问只用于验证证据，不替代人工判断。",
        "",
    ]
    for index, question in enumerate(assessment["interview_questions"], 1):
        lines.extend(
            [
                f"## {index}. {question['dimension_title']}",
                "",
                f"- Evidence level：`{question['evidence_level']}`",
                f"- Evidence refs：{', '.join(f'`{ref}`' for ref in question['evidence_refs']) or '`none`'}",
                f"- 问题：{question['question']}",
                f"- 目的：{question['purpose']}",
                "",
            ]
        )
    return "\n".join(lines)


def render_privacy_checklist(assessment: dict[str, Any]) -> str:
    lines = [
        "# TalentAIQ Lite 隐私清单",
        "",
        f"- 候选人标签：`{assessment['candidate_label']}`",
        "- 默认脱敏：开启",
        "- 原始 prompt/completion：不输出",
        "- 原始 secret/token：不输出",
        "- 受保护属性：不用于分析、追问或评价",
        "",
        "## 清单",
        "",
    ]
    for item in assessment["privacy_checklist"]:
        lines.append(
            f"- `{item['item']}`：`{item['status']}`，evidence level `{item['evidence_level']}`。{item['note']}"
        )
    lines.extend(
        [
            "",
            "## 数据源隐私风险",
            "",
        ]
    )
    for risk in assessment["privacy"].get("source_risks", []):
        lines.append(
            f"- `{risk['source']}`：`{risk['status']}`。风险：{risk['risk']} 处理：{risk['handling']}"
        )
    lines.extend(
        [
            "",
            "## 脱敏统计",
            "",
            "```json",
            json.dumps(assessment["privacy"]["redaction_report"], ensure_ascii=False, indent=2),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def render_poster_html(assessment: dict[str, Any]) -> str:
    poster = _poster_model(assessment)
    cards = "\n".join(_poster_card(card) for card in poster["cards"])
    timeline = "\n".join(_timeline_item(item) for item in poster["timeline"])
    slash = "\n".join(_leader_item(item) for item in poster["slash_commands"])
    families = "\n".join(_leader_item(item) for item in poster["tool_families"])
    dimensions = "\n".join(_dimension_pill(item) for item in poster["dimensions"])
    source_chips = "\n".join(
        f'<span class="chip chip-{escape(source["status"])}">{escape(source["name"])} · {escape(source["status"])}</span>'
        for source in poster["sources"]
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>TalentAIQ Lite 画报 · {escape(str(assessment["candidate_label"]))}</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #0d1022;
      --panel: rgba(255, 255, 255, 0.075);
      --panel-strong: rgba(255, 255, 255, 0.105);
      --stroke: rgba(168, 190, 255, 0.28);
      --stroke-teal: rgba(56, 189, 184, 0.42);
      --text: #f7f5f0;
      --muted: #aaa9bd;
      --soft: #d8d5e8;
      --teal: #37c7b7;
      --violet: #8d77ff;
      --amber: #e8b65d;
      --slate: #1c2635;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      background:
        radial-gradient(circle at 15% 12%, rgba(141, 119, 255, 0.22), transparent 30%),
        radial-gradient(circle at 92% 88%, rgba(55, 199, 183, 0.20), transparent 31%),
        linear-gradient(135deg, #151032 0%, #10162a 46%, #0b2730 100%);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }}
    .page {{
      width: min(1180px, calc(100vw - 36px));
      margin: 0 auto;
      padding: 42px 0 52px;
    }}
    .hero {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 28px;
      align-items: end;
      margin-bottom: 34px;
    }}
    h1 {{
      margin: 0 0 10px;
      font-size: clamp(38px, 7vw, 76px);
      line-height: 0.92;
      font-weight: 820;
    }}
    .accent {{ color: var(--teal); }}
    .subtitle {{
      color: var(--muted);
      font-size: 18px;
      line-height: 1.6;
      max-width: 780px;
      margin: 0;
    }}
    .boundary {{
      max-width: 330px;
      padding: 16px 18px;
      border: 1px solid var(--stroke);
      background: rgba(13, 16, 34, 0.62);
      border-radius: 8px;
      color: var(--soft);
      font-size: 14px;
      line-height: 1.55;
    }}
    .chips {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin: 22px 0 0;
    }}
    .chip {{
      border: 1px solid var(--stroke);
      border-radius: 999px;
      padding: 7px 10px;
      color: var(--soft);
      background: rgba(255,255,255,0.055);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .chip-available, .chip-observed {{ border-color: rgba(55, 199, 183, 0.52); }}
    .chip-partial, .chip-inferred, .chip-limited {{ border-color: rgba(232, 182, 93, 0.62); }}
    .chip-missing, .chip-skipped {{ border-color: rgba(170, 169, 189, 0.38); }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 22px;
      margin-top: 34px;
    }}
    .metric {{
      min-height: 176px;
      border: 1px solid var(--stroke);
      border-radius: 8px;
      background:
        linear-gradient(145deg, rgba(255,255,255,0.090), rgba(255,255,255,0.046)),
        linear-gradient(135deg, rgba(141,119,255,0.08), rgba(55,199,183,0.05));
      padding: 28px 34px;
      box-shadow: inset 0 0 0 1px rgba(255,255,255,0.025);
    }}
    .metric:nth-child(even) {{ border-color: var(--stroke-teal); }}
    .label {{
      color: var(--muted);
      font-size: 14px;
      letter-spacing: 0.26em;
      text-transform: uppercase;
      font-weight: 760;
    }}
    .value {{
      margin-top: 14px;
      font-size: clamp(44px, 8vw, 78px);
      line-height: 0.96;
      font-weight: 860;
      white-space: nowrap;
    }}
    .note {{
      margin-top: 12px;
      color: var(--muted);
      font-size: 14px;
      line-height: 1.45;
    }}
    .section {{
      margin-top: 42px;
    }}
    .section h2 {{
      margin: 0 0 20px;
      color: var(--muted);
      font-size: 15px;
      text-transform: uppercase;
      letter-spacing: 0.28em;
    }}
    .timeline {{
      position: relative;
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 24px;
      padding-top: 18px;
    }}
    .timeline::before {{
      content: "";
      position: absolute;
      left: 0;
      right: 0;
      top: 28px;
      height: 1px;
      background: rgba(216, 213, 232, 0.34);
    }}
    .milestone {{
      position: relative;
      padding-top: 28px;
    }}
    .milestone::before {{
      content: "";
      position: absolute;
      top: 3px;
      left: 0;
      width: 18px;
      height: 18px;
      border-radius: 50%;
      background: linear-gradient(135deg, var(--violet), var(--teal));
      box-shadow: 0 0 0 4px rgba(13, 16, 34, 0.72);
    }}
    .date {{
      font-size: 22px;
      font-weight: 820;
    }}
    .event {{
      color: var(--muted);
      font-size: 15px;
      line-height: 1.45;
      margin-top: 8px;
    }}
    .bottom-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 22px;
      margin-top: 32px;
    }}
    .panel {{
      border: 1px solid rgba(168, 190, 255, 0.22);
      background: var(--panel);
      border-radius: 8px;
      padding: 24px 28px;
      min-height: 180px;
    }}
    .panel h3 {{
      margin: 0 0 18px;
      color: var(--muted);
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0.20em;
    }}
    .leader {{
      display: flex;
      justify-content: space-between;
      gap: 18px;
      color: var(--soft);
      font-size: 18px;
      line-height: 1.7;
    }}
    .leader strong {{ color: var(--text); }}
    .dimension-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
    }}
    .dimension {{
      min-height: 72px;
      padding: 13px 14px;
      border: 1px solid var(--stroke);
      border-radius: 8px;
      background: rgba(255,255,255,0.052);
    }}
    .dimension-title {{
      font-size: 14px;
      font-weight: 760;
      margin-bottom: 8px;
    }}
    .dimension-level {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.10em;
    }}
    .footer {{
      margin-top: 32px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.6;
      border-top: 1px solid rgba(216, 213, 232, 0.22);
      padding-top: 18px;
    }}
    @media (max-width: 820px) {{
      .hero, .metrics, .bottom-grid, .timeline, .dimension-grid {{
        grid-template-columns: 1fr;
      }}
      .boundary {{ max-width: none; }}
      .metric {{ min-height: 150px; padding: 24px; }}
      .timeline::before {{ display: none; }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <div>
        <h1>AI-Native<br><span class="accent">Evidence Portrait</span></h1>
        <p class="subtitle">{escape(str(assessment["candidate_label"]))} · {escape(poster["headline"])}</p>
        <div class="chips">{source_chips}</div>
      </div>
      <aside class="boundary">
        Evidence only. No automatic ranking, rejection, pass/fail label, or hiring recommendation. Missing data stays missing.
      </aside>
    </section>

    <section class="metrics" aria-label="Evidence metrics">
      {cards}
    </section>

    <section class="section">
      <h2>Evolution</h2>
      <div class="timeline">{timeline}</div>
    </section>

    <section class="bottom-grid">
      <div class="panel">
        <h3>Top Slash 命令</h3>
        {slash}
      </div>
      <div class="panel">
        <h3>Tool Families</h3>
        {families}
      </div>
    </section>

    <section class="section">
      <h2>Six Evidence Dimensions</h2>
      <div class="dimension-grid">{dimensions}</div>
    </section>

    <footer class="footer">
      Generated by TalentAIQ Lite at {escape(str(assessment["generated_at"]))}. Raw prompts, completions, secrets, emails, and local paths are redacted or omitted by default.
    </footer>
  </main>
</body>
</html>
"""


def render_svg(assessment: dict[str, Any]) -> str:
    source_map = {source["name"]: source for source in assessment.get("sources", [])}
    ai = _combined_ai_metrics(source_map)
    git = source_map.get("git", {}).get("metrics", {})
    width = 1200
    height = 1500
    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
        "<title>TalentAIQ Lite 人才画像（证据导向·面试准备专用）</title>",
        '<defs><filter id="softShadow" x="-4%" y="-4%" width="108%" height="112%"><feDropShadow dx="0" dy="3" stdDeviation="4" flood-color="#0f172a" flood-opacity="0.10"/></filter></defs>',
        f'<rect width="{width}" height="{height}" fill="#f5f7fb"/>',
        f'<rect x="0" y="0" width="{width}" height="118" fill="#071428"/>',
        '<text x="40" y="52" font-family="Arial, sans-serif" font-size="34" font-weight="800" fill="#ffffff">TalentAIQ Lite 面试画像</text>',
        '<text x="40" y="84" font-family="Arial, sans-serif" font-size="17" font-weight="700" fill="#dbeafe">证据导向 · 人工面试准备专用 · 不排名 · 不淘汰 · 不推荐录用</text>',
        f'<text x="1160" y="54" font-family="Arial, sans-serif" font-size="14" fill="#cbd5e1" text-anchor="end">Candidate: {escape(str(assessment["candidate_label"]))}</text>',
        f'<text x="1160" y="82" font-family="Arial, sans-serif" font-size="14" fill="#cbd5e1" text-anchor="end">Generated: {escape(str(assessment["generated_at"])[:19].replace("T", " "))} UTC</text>',
    ]
    elements.append(_svg_text(40, 154, "数据源", 18, "#0b3a78", weight=800))
    elements.extend(_svg_source_summary_cards(source_map))
    elements.append(_svg_text(40, 456, "六个能力维度", 22, "#0b1f44", weight=800))
    elements.extend(_svg_clean_dimension_cards(assessment, ai, git, source_map))
    elements.extend(_svg_clean_bottom_panels(assessment, source_map, ai, git))
    elements.append(
        _svg_text(
            40,
            1470,
            "注意：本报告基于本地可用数据生成，数据缺失不代表候选人无相关能力。所有结论必须通过面试或补充材料验证。",
            13,
            "#24324a",
        )
    )
    elements.append("</svg>")
    return "\n".join(elements)


def _svg_source_summary_cards(source_map: dict[str, dict[str, Any]]) -> list[str]:
    elements: list[str] = []
    for index, row in enumerate(_svg_source_rows(source_map)):
        col = index % 2
        line = index // 2
        x = 40 + col * 580
        y = 174 + line * 88
        w = 540
        color = row["accent"]
        elements.append(_svg_panel(x, y, w, 72))
        elements.append(_svg_text(x + 20, y + 30, row["label"], 15, "#0b1f44", weight=800))
        elements.append(_svg_small_badge(x + 20, y + 42, row["status"], color))
        elements.append(_svg_text(x + w - 20, y + 53, str(row["count"]), 24, "#111827", weight=800, anchor="end"))
    return elements


def _svg_clean_dimension_cards(
    assessment: dict[str, Any],
    ai: dict[str, Any],
    git: dict[str, Any],
    source_map: dict[str, dict[str, Any]],
) -> list[str]:
    project = source_map.get("project_traces", {}).get("metrics", {})
    project_workflow = _project_workflow_trace_count(project)
    project_delivery = _project_delivery_trace_count(project)
    families_count = len(ai.get("tool_families") or {})
    if source_map.get("git", {}).get("status") in {"available", "partial"}:
        families_count += 1
    if int(project.get("trace_items") or 0):
        families_count += 1
    cards = [
        {
            "id": "ai_tool_fluency",
            "title": "1. AI 工具熟练度",
            "metrics": [("工具事件", int(ai.get("tool_events") or 0)), ("工具家族", len(ai.get("tool_families") or {}))],
            "claim": "本地记录显示存在持续 AI coding 工具调用行为。",
            "focus": "追问如何分配 AI 与人工边界，以及如何复核 AI 输出。",
        },
        {
            "id": "task_decomposition",
            "title": "2. 任务拆解",
            "metrics": [("计划信号", int(ai.get("planning_signals") or 0)), ("Git 提交", int(git.get("commits") or 0))],
            "claim": "可见任务规划、todo 或拆解相关信号。",
            "focus": "追问如何拆目标、定验收标准、安排迭代顺序。",
        },
        {
            "id": "context_management",
            "title": "3. 上下文管理",
            "metrics": [("上下文信号", int(ai.get("context_signals") or 0)), ("长上下文", int(ai.get("long_context_records") or 0))],
            "claim": "可见摘要、续接、记忆或长任务上下文信号。",
            "focus": "追问如何保存约束、历史决策和未完成事项。",
        },
        {
            "id": "multi_tool_orchestration",
            "title": "4. 多工具编排",
            "metrics": [("工具/数据源", families_count)],
            "claim": "工作流涉及 AI 工具、本地工程痕迹或 Git 等多类信号。",
            "focus": "追问不同工具各自负责什么，哪些步骤必须人工确认。",
        },
        {
            "id": "ai_workflow_building",
            "title": "5. AI 工作流建设",
            "metrics": [("工作流信号", int(ai.get("workflow_signals") or 0) + project_workflow)],
            "claim": "可见脚本、CI、MCP、agent、prompt 或 skill 等工程化痕迹。",
            "focus": "追问是否沉淀过可复用流程，以及如何从失败案例改进。",
        },
        {
            "id": "engineering_delivery_linkage",
            "title": "6. 工程交付关联",
            "metrics": [("AI 记录", int(ai.get("records") or 0)), ("Git 提交", int(git.get("commits") or 0)), ("工程痕迹", project_delivery)],
            "claim": "可见 AI 使用和本地工程痕迹，但交付质量仍需代码/PR 级验证。",
            "focus": "追问一个真实提交或 PR，说明 AI 参与、人工修改和测试方式。",
        },
    ]
    dimension_map = {dimension["id"]: dimension for dimension in assessment.get("dimensions", [])}
    elements: list[str] = []
    for index, card in enumerate(cards):
        row = index // 2
        col = index % 2
        x = 40 + col * 580
        y = 482 + row * 150
        level = dimension_map.get(card["id"], {}).get("evidence_level", "missing")
        elements.extend(_svg_clean_dimension_card(x, y, 540, 126, card, level))
    return elements


def _svg_clean_dimension_card(x: int, y: int, w: int, h: int, card: dict[str, Any], level: str) -> list[str]:
    color = _level_color(level)
    elements = [
        _svg_panel(x, y, w, h),
        _svg_text(x + 22, y + 32, card["title"], 18, "#111827", weight=800),
        _svg_small_badge(x + w - 118, y + 16, level, color),
    ]
    metric_x = x + 22
    for label, value in card["metrics"][:3]:
        value_text = str(value)
        label_offset = 120 if len(value_text) >= 5 else 92 if len(value_text) >= 4 else 66
        elements.append(_svg_text(metric_x, y + 65, value_text, 23, "#050816", weight=800))
        elements.append(_svg_text(metric_x + label_offset, y + 64, label, 12, "#526074", weight=700))
        metric_x += 170
    elements.extend(_svg_multiline(x + 22, y + 91, card["claim"], 52, 17, 1, size=13, color="#17233a"))
    elements.extend(_svg_multiline(x + 22, y + 112, card["focus"], 54, 16, 1, size=12, color="#0f5132"))
    return elements


def _svg_clean_bottom_panels(
    assessment: dict[str, Any],
    source_map: dict[str, dict[str, Any]],
    ai: dict[str, Any],
    git: dict[str, Any],
) -> list[str]:
    has_ai = int(ai.get("records") or 0) > 0
    has_delivery = int(git.get("commits") or 0) > 0
    overall = _overall_judgement(has_ai, has_delivery, assessment).replace("\n\n", " ")
    integrity = _data_integrity_judgement(has_ai, has_delivery, source_map)
    return [
        _svg_panel(40, 970, 1120, 205),
        _svg_text(64, 1006, "总体判断（非评分）", 18, "#0b1f44", weight=800),
        *_svg_multiline(64, 1040, overall, 72, 21, 5, size=14, color="#17233a"),
        _svg_text(64, 1144, "边界：仅用于人工面试准备；limited / inferred 只能触发追问，不能作为事实结论。", 13, "#526074"),
        _svg_panel(40, 1208, 1120, 205),
        _svg_text(64, 1244, "面试使用建议", 18, "#0b1f44", weight=800),
        *_svg_multiline(64, 1278, integrity, 72, 21, 5, size=14, color="#17233a"),
        _svg_text(64, 1382, "建议流程：选真实任务，展示 prompt、AI 输出、人工修改、测试方式和一次 AI 出错修正。", 13, "#0f5132"),
    ]


def _svg_left_column(source_map: dict[str, dict[str, Any]]) -> list[str]:
    rows = _svg_source_rows(source_map)
    elements = [
        _svg_panel(32, 150, 400, 330),
        _svg_text(56, 184, "数据源概览", 18, "#0b3a78", weight=800),
        '<line x1="56" y1="207" x2="408" y2="207" stroke="#d7dee8"/>',
    ]
    for index, row in enumerate(rows):
        y = 222 + index * 50
        elements.extend(
            [
                f'<rect x="56" y="{y}" width="352" height="44" rx="8" fill="#ffffff" stroke="#d7dee8"/>',
                _svg_status_icon(70, y + 10, row["accent"]),
                _svg_text(104, y + 29, row["label"], 14, "#0b1f44", weight=700),
                _svg_small_badge(250, y + 10, row["status"], row["accent"]),
                _svg_text(394, y + 29, str(row["count"]), 14, "#111827", anchor="end", weight=700),
            ]
        )
    elements.extend(
        [
            _svg_panel(32, 505, 400, 205),
            _svg_text(56, 540, "数据解读", 18, "#0b3a78", weight=800),
            *_svg_multiline(
                56,
                574,
                _data_integrity_judgement(
                    has_ai=_source_records(source_map, "codex") + _source_records(source_map, "claude") > 0,
                    has_delivery=int(source_map.get("git", {}).get("metrics", {}).get("commits") or 0) > 0,
                    source_map=source_map,
                ),
                30,
                20,
                6,
                color="#17233a",
                size=14,
            ),
            _svg_panel(32, 735, 400, 190),
            _svg_text(56, 770, "证据等级说明", 18, "#0b3a78", weight=800),
            _svg_legend_row(56, 804, "observed", "直接可观察证据，可作为面试追问依据", "#16753b"),
            _svg_legend_row(56, 840, "limited", "证据不足，必须重点验证", "#c46d07"),
            _svg_legend_row(56, 876, "inferred", "间接信号推断，仅作假设", "#1f5fbf"),
            _svg_legend_row(56, 912, "missing", "当前未发现证据，不代表无能力", "#64748b"),
        ]
    )
    return elements


def _svg_source_rows(source_map: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    git = source_map.get("git", {})
    git_metrics = git.get("metrics", {})
    project = source_map.get("project_traces", {})
    project_metrics = project.get("metrics", {})
    git_commits = int(git_metrics.get("commits") or 0)
    git_repos = int(git_metrics.get("repos_analyzed") or 0)
    git_status = "available/empty" if git_repos and not git_commits else git.get("status", "missing")
    return [
        {
            "label": "Codex 本地记录",
            "status": source_map.get("codex", {}).get("status", "missing"),
            "count": _source_records(source_map, "codex"),
            "accent": "#1f5fbf" if _source_records(source_map, "codex") else "#64748b",
        },
        {
            "label": "Claude 本地记录",
            "status": source_map.get("claude", {}).get("status", "missing"),
            "count": _source_records(source_map, "claude"),
            "accent": "#a73b16" if source_map.get("claude", {}).get("status") == "missing" else "#1f5fbf",
        },
        {
            "label": "Git 提交记录",
            "status": git_status,
            "count": git_commits,
            "accent": "#c46d07" if git_status == "available/empty" else "#16753b",
        },
        {
            "label": "本地工程痕迹",
            "status": project.get("status", "missing"),
            "count": int(project_metrics.get("trace_items") or 0),
            "accent": "#16753b" if int(project_metrics.get("trace_items") or 0) else "#64748b",
        },
        {
            "label": "GitHub 远程数据",
            "status": source_map.get("github", {}).get("status", "missing"),
            "count": _source_records(source_map, "github"),
            "accent": "#64748b",
        },
    ]


def _svg_dimension_cards(assessment: dict[str, Any], ai: dict[str, Any], git: dict[str, Any]) -> list[str]:
    source_map = {source["name"]: source for source in assessment.get("sources", [])}
    project = source_map.get("project_traces", {}).get("metrics", {})
    project_workflow = _project_workflow_trace_count(project)
    project_delivery = _project_delivery_trace_count(project)
    cards = [
        {
            "id": "ai_tool_fluency",
            "title": "1. AI 工具熟练度",
            "values": [(str(int(ai.get("tool_events") or 0)), "工具事件"), (str(len(ai.get("tool_families") or {})), "工具家族数")],
            "insight": f"检测到大量 AI 工具调用，覆盖 {_format_tool_families(ai.get('tool_families') or {})} 等工具家族，显示持续使用行为。",
            "focus": "如何分配 AI 与人工的边界？如何复核 AI 输出？",
            "chips": [],
        },
        {
            "id": "task_decomposition",
            "title": "2. 任务拆解能力",
            "values": [(str(int(ai.get("planning_signals") or 0)), "计划/任务拆解信号"), (str(int(git.get("commits") or 0)), "Git 提交数")],
            "insight": "存在大量计划、todo、任务拆解行为，说明有任务规划和迭代意识。",
            "focus": "如何拆目标？如何定义验收标准和迭代顺序？",
            "chips": [],
        },
        {
            "id": "context_management",
            "title": "3. 上下文管理能力",
            "values": [(str(int(ai.get("context_signals") or 0)), "上下文相关信号"), (str(int(ai.get("long_context_records") or 0)), "长上下文记录")],
            "insight": "存在大量上下文、记忆、摘要、续接记录，包含长上下文任务管理行为。",
            "focus": "长任务中如何保持约束、历史决策不丢失？",
            "chips": [],
        },
        {
            "id": "multi_tool_orchestration",
            "title": "4. 多工具编排能力",
            "values": [(str(len(ai.get("tool_families") or {}) + 1), "工具/数据源家族")],
            "insight": "工作流涉及多工具协同（AI 工具、终端、Git、搜索等），显示跨工具解决问题的能力。",
            "focus": "请举例说明一个跨工具协作完成的任务。",
            "chips": list((ai.get("tool_families") or {}).keys())[:6],
        },
        {
            "id": "ai_workflow_building",
            "title": "5. AI 工作流建设能力",
            "values": [(str(int(ai.get("workflow_signals") or 0) + project_workflow), "工作流/工程资产信号")],
            "insight": "存在脚本、CI、测试、MCP、agent、prompt、Skill 或自动化等工程化沉淀痕迹。",
            "focus": "是否沉淀过可复用的流程？如何改进失败案例？",
            "chips": ["scripts", "CI", "tests", "MCP", "agent", "Skill"],
        },
        {
            "id": "engineering_delivery_linkage",
            "title": "6. 工程交付关联能力",
            "values": [
                (str(int(ai.get("records") or 0)), "AI 工具记录"),
                (str(int(git.get("commits") or 0)), "Git 提交数"),
                (str(int(git.get("files_touched_by_commits") or 0) + project_delivery), "交付痕迹数"),
            ],
            "insight": "可见 AI 使用记录和本地工程痕迹，但缺少 Git 提交、PR 和代码 diff 级证据，工程交付能力仍需验证。",
            "focus": "请提供一个真实提交或 PR，说明 AI 如何参与。",
            "chips": [],
        },
    ]
    dimension_map = {dimension["id"]: dimension for dimension in assessment.get("dimensions", [])}
    elements: list[str] = []
    for index, card in enumerate(cards):
        row = index // 2
        col = index % 2
        x = 472 + col * 526
        y = 190 + row * 315
        dimension = dimension_map.get(card["id"], {})
        level = dimension.get("evidence_level", "missing")
        elements.extend(_svg_dimension_card(x, y, 500, 292, card, level))
    return elements


def _svg_dimension_card(x: int, y: int, w: int, h: int, card: dict[str, Any], level: str) -> list[str]:
    color = _level_color(level)
    elements = [
        _svg_panel(x, y, w, h),
        _svg_text(x + 72, y + 38, card["title"], 19, "#111827", weight=800),
        _svg_small_badge(x + w - 124, y + 20, level, color),
        f'<rect x="{x + 24}" y="{y + 62}" width="56" height="56" rx="12" fill="#eef6ff" stroke="{color}" stroke-width="1.5"/>',
        _svg_text(x + 52, y + 98, _card_icon(card["id"]), 29, color, anchor="middle", weight=800),
    ]
    value_start_x = x + 132
    for idx, (value, label) in enumerate(card["values"][:3]):
        vx = value_start_x + idx * 118
        elements.append(_svg_text(vx, y + 93, value, 30, "#050816", weight=800, anchor="middle"))
        elements.append(_svg_text(vx, y + 123, label, 13, "#26344d", anchor="middle"))
    if card.get("chips"):
        chip_x = x + 24
        for chip in card["chips"][:6]:
            chip_width = 56 if len(chip) < 6 else 76
            elements.append(f'<rect x="{chip_x}" y="{y + 135}" width="{chip_width}" height="24" rx="6" fill="#ffffff" stroke="#cbd5e1"/>')
            elements.append(_svg_text(chip_x + chip_width / 2, y + 151, _chip_label(str(chip)), 10, "#0f172a", anchor="middle", weight=700))
            chip_x += chip_width + 8
    separator_y = y + 148 if not card.get("chips") else y + 172
    elements.append(f'<line x1="{x}" y1="{separator_y}" x2="{x + w}" y2="{separator_y}" stroke="#dfe5ee"/>')
    elements.append(_svg_text(x + 24, separator_y + 32, "关键洞察", 13, "#0b1f44", weight=800))
    elements.extend(_svg_multiline(x + 24, separator_y + 56, card["insight"], 51, 18, 3, size=13, color="#17233a"))
    focus_y = y + h - 38
    elements.append(f'<line x1="{x}" y1="{focus_y - 23}" x2="{x + w}" y2="{focus_y - 23}" stroke="#dfe5ee"/>')
    elements.append(_svg_text(x + 24, focus_y, "面试重点", 13, color, weight=800))
    elements.extend(_svg_multiline(x + 98, focus_y, card["focus"], 38, 17, 2, size=12, color="#17233a"))
    return elements


def _svg_bottom_panels(
    assessment: dict[str, Any],
    source_map: dict[str, dict[str, Any]],
    ai: dict[str, Any],
    git: dict[str, Any],
    github: dict[str, Any],
) -> list[str]:
    has_ai = int(ai.get("records") or 0) > 0
    has_delivery = int(git.get("commits") or 0) > 0
    overall = _overall_judgement(has_ai, has_delivery, assessment).replace("\n\n", " ")
    delivery_level = "中" if has_delivery else "低"
    delivery_text = "中（可追问交付关联）" if has_delivery else "低（limited）"
    return [
        _svg_panel(32, 1145, 400, 180),
        _svg_text(56, 1180, "使用边界", 18, "#0b3a78", weight=800),
        *_svg_check_lines(
            58,
            1214,
            [
                "本报告仅用于人工面试准备，不能用于自动排名、自动淘汰或推荐录用。",
                "observed / inferred / limited 均需通过面试或补充材料验证。",
                "不得依据年龄、性别、婚育、民族、宗教、残障等受保护属性提问或评价。",
            ],
        ),
        _svg_panel(472, 1145, 500, 180),
        _svg_text(496, 1180, "总体判断（非评分）", 18, "#0b1f44", weight=800),
        *_svg_multiline(496, 1214, overall, 52, 20, 4, size=14, color="#17233a"),
        _svg_text(496, 1300, "工程交付证据充分度", 12, "#0b1f44", weight=800),
        '<rect x="662" y="1293" width="250" height="8" rx="4" fill="#cbd5e1"/>',
        '<rect x="662" y="1293" width="70" height="8" rx="4" fill="#b5401d"/>',
        '<rect x="732" y="1293" width="84" height="8" rx="4" fill="#d98a21"/>',
        '<rect x="816" y="1293" width="96" height="8" rx="4" fill="#2b8a3e"/>',
        f'<circle cx="{732 if delivery_level == "低" else 816}" cy="1297" r="8" fill="#ffffff" stroke="#d98a21" stroke-width="3"/>',
        _svg_text(662, 1320, "低", 11, "#17233a"),
        _svg_text(902, 1320, "高", 11, "#17233a"),
        _svg_text(786, 1321, f"当前：{delivery_text}", 12, "#17233a", anchor="middle"),
        _svg_panel(998, 1145, 500, 180),
        _svg_text(1022, 1180, "建议面试流程", 18, "#0b1f44", weight=800),
        *_svg_numbered_lines(
            1024,
            1212,
            [
                "请候选人选择一个真实项目或任务作为案例。",
                "要求展示关键 prompt、AI 输出、人工修改点与最终代码/PR。",
                "要求说明测试策略与验证方式。",
                "要求复盘一次 AI 生成错误的案例及修正过程。",
                "关注候选人对工程质量、风险、边界的理解。",
                "可安排现场编码或需求变更应对，验证实际工程能力。",
            ],
        ),
    ]


def _svg_panel(x: int, y: int, width: int, height: int) -> str:
    return (
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="8" '
        'fill="#ffffff" stroke="#d7dee8" filter="url(#softShadow)"/>'
    )


def _svg_text(
    x: float,
    y: float,
    text: str,
    size: int,
    color: str,
    *,
    weight: int | str = 400,
    anchor: str = "start",
) -> str:
    return (
        f'<text x="{x}" y="{y}" font-family="Arial, sans-serif" font-size="{size}" '
        f'font-weight="{weight}" fill="{color}" text-anchor="{anchor}">{escape(str(text))}</text>'
    )


def _svg_multiline(
    x: int,
    y: int,
    text: str,
    width: int,
    line_height: int,
    max_lines: int,
    *,
    size: int,
    color: str,
) -> list[str]:
    lines = _wrap_svg_text(text, width=width, max_lines=max_lines)
    return [_svg_text(x, y + idx * line_height, line, size, color) for idx, line in enumerate(lines)]


def _svg_badge(x: int, y: int, width: int, height: int, title: str, subtitle: str, color: str) -> str:
    return (
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="8" fill="#071428" stroke="{color}" stroke-width="1.5"/>'
        f'<text x="{x + width / 2}" y="{y + 26}" font-family="Arial, sans-serif" font-size="13" font-weight="800" fill="{color}" text-anchor="middle">{escape(title)}</text>'
        f'<text x="{x + width / 2}" y="{y + 46}" font-family="Arial, sans-serif" font-size="13" font-weight="700" fill="{color}" text-anchor="middle">{escape(subtitle)}</text>'
    )


def _svg_small_badge(x: int, y: int, text: str, color: str) -> str:
    label = str(text)
    width = max(68, min(104, 12 * len(label)))
    return (
        f'<rect x="{x}" y="{y}" width="{width}" height="24" rx="5" fill="{color}"/>'
        f'<text x="{x + width / 2}" y="{y + 16}" font-family="Arial, sans-serif" font-size="11" font-weight="800" fill="#ffffff" text-anchor="middle">{escape(label)}</text>'
    )


def _svg_status_icon(x: int, y: int, color: str) -> str:
    return (
        f'<rect x="{x}" y="{y}" width="24" height="24" rx="5" fill="#f8fafc" stroke="{color}"/>'
        f'<circle cx="{x + 12}" cy="{y + 12}" r="5" fill="none" stroke="{color}" stroke-width="2"/>'
        f'<path d="M{x + 12} {y + 7} L{x + 12} {y + 17} M{x + 7} {y + 12} L{x + 17} {y + 12}" stroke="{color}" stroke-width="1.6" stroke-linecap="round"/>'
    )


def _svg_legend_row(x: int, y: int, level: str, text: str, color: str) -> str:
    return (
        _svg_small_badge(x, y - 18, level, color)
        + _svg_text(x + 118, y, text, 13, "#17233a")
    )


def _svg_check_lines(x: int, y: int, lines: list[str]) -> list[str]:
    elements: list[str] = []
    for idx, line in enumerate(lines):
        ly = y + idx * 42
        elements.append(f'<circle cx="{x + 5}" cy="{ly - 5}" r="5" fill="none" stroke="#0b1f44" stroke-width="1.6"/>')
        elements.append(f'<path d="M{x + 2} {ly - 5} L{x + 5} {ly - 2} L{x + 10} {ly - 8}" fill="none" stroke="#0b1f44" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>')
        elements.extend(_svg_multiline(x + 20, ly, line, 38, 17, 2, size=13, color="#17233a"))
    return elements


def _svg_numbered_lines(x: int, y: int, lines: list[str]) -> list[str]:
    elements: list[str] = []
    for idx, line in enumerate(lines, 1):
        ly = y + (idx - 1) * 24
        elements.append(f'<circle cx="{x + 8}" cy="{ly - 5}" r="7" fill="#eef2f7" stroke="#cbd5e1"/>')
        elements.append(_svg_text(x + 8, ly - 1, str(idx), 10, "#17233a", weight=800, anchor="middle"))
        elements.append(_svg_text(x + 26, ly, line, 12, "#17233a"))
    return elements


def _source_records(source_map: dict[str, dict[str, Any]], name: str) -> int:
    metrics = source_map.get(name, {}).get("metrics", {})
    if name == "git":
        return int(metrics.get("commits") or 0)
    if name == "project_traces":
        return int(metrics.get("trace_items") or 0)
    return int(metrics.get("records") or 0)


def _level_color(level: str) -> str:
    return {
        "observed": "#16753b",
        "limited": "#c46d07",
        "inferred": "#1f5fbf",
        "missing": "#64748b",
    }.get(level, "#64748b")


def _card_icon(card_id: str) -> str:
    return {
        "ai_tool_fluency": "AI",
        "task_decomposition": "✓",
        "context_management": "□",
        "multi_tool_orchestration": "⌘",
        "ai_workflow_building": "</>",
        "engineering_delivery_linkage": "▧",
    }.get(card_id, "•")


def _chip_label(value: str) -> str:
    return {
        "agent_orchestration": "agent",
        "search_read": "search",
        "external_context": "context",
        "other_tool": "other",
    }.get(value, value.replace("_", "-"))


def _poster_model(assessment: dict[str, Any]) -> dict[str, Any]:
    source_map = {source["name"]: source for source in assessment.get("sources", [])}
    ai = _combined_ai_metrics(source_map)
    git = source_map.get("git", {}).get("metrics", {})
    github = source_map.get("github", {}).get("metrics", {})
    token_usage = ai["token_usage"]
    total_tokens = int(token_usage.get("total_tokens") or 0)
    cached_tokens = int(token_usage.get("cached_tokens") or 0)
    input_tokens = int(token_usage.get("input_tokens") or 0)
    cache_base = max(input_tokens - cached_tokens, 0)
    cache_ratio = cached_tokens / cache_base if cached_tokens and cache_base else None
    repos = int(git.get("repos_analyzed") or 0)
    language_count = len(git.get("extensions_touched") or {})
    stars = int(github.get("stars") or 0)
    github_available = source_map.get("github", {}).get("status") == "available"
    git_available = source_map.get("git", {}).get("status") in {"available", "partial"}
    cards = [
        {
            "label": "Active Days",
            "value": _missing_or_number(ai["active_days"] + int(git.get("active_days") or 0)),
            "note": "AI logs and local Git activity days.",
            "level": "observed" if ai["active_days"] or git.get("active_days") else "missing",
        },
        {
            "label": "Local Commits",
            "value": str(int(git.get("commits") or 0)) if git_available else "--",
            "note": "Parsed from local Git history.",
            "level": "observed" if git_available else "missing",
        },
        {
            "label": "Tokens Through",
            "value": _format_compact(total_tokens) if total_tokens else "--",
            "note": "Observed token counters from local AI logs when present.",
            "level": "observed" if total_tokens else "missing",
        },
        {
            "label": "Cache Leverage",
            "value": f"1:{cache_ratio:.1f}" if cache_ratio else "--",
            "note": "Cached token leverage when local logs expose cache counters.",
            "level": "observed" if cache_ratio else "missing",
        },
        {
            "label": "GitHub Stars",
            "value": str(stars) if github_available else "--",
            "note": "Only shown from explicit GitHub input or enabled API data.",
            "level": "observed" if github_available else "missing",
        },
        {
            "label": "Repos · Langs",
            "value": f"{repos} · {language_count}" if repos else "--",
            "note": "Local repositories analyzed and touched extension families.",
            "level": "observed" if repos else "missing",
        },
    ]
    return {
        "headline": _poster_headline(assessment),
        "cards": cards,
        "timeline": _timeline_model(source_map),
        "slash_commands": _counter_items(ai["slash_commands"], empty="No slash commands observed"),
        "tool_families": _counter_items(ai["tool_families"], empty="No tool events observed"),
        "dimensions": [
            {
                "title": dimension["title"],
                "level": dimension["evidence_level"],
            }
            for dimension in assessment.get("dimensions", [])
        ],
        "sources": [
            {"name": source["name"], "status": source.get("status", "missing")}
            for source in assessment.get("sources", [])
        ],
    }


def _combined_ai_metrics(source_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    combined = {
        "active_days": 0,
        "records": 0,
        "tool_events": 0,
        "planning_signals": 0,
        "context_signals": 0,
        "workflow_signals": 0,
        "long_context_records": 0,
        "tool_families": {},
        "slash_commands": {},
        "token_usage": {},
    }
    for name in ("claude", "codex"):
        metrics = source_map.get(name, {}).get("metrics", {})
        combined["active_days"] += int(metrics.get("active_days") or 0)
        combined["records"] += int(metrics.get("records") or 0)
        combined["tool_events"] += int(metrics.get("tool_events") or 0)
        combined["planning_signals"] += int(metrics.get("planning_signals") or 0)
        combined["context_signals"] += int(metrics.get("context_signals") or 0)
        combined["workflow_signals"] += int(metrics.get("workflow_signals") or 0)
        combined["long_context_records"] += int(metrics.get("long_context_records") or 0)
        _merge_counts(combined["tool_families"], metrics.get("tool_families") or {})
        _merge_counts(combined["slash_commands"], metrics.get("slash_commands") or {})
        _merge_counts(combined["token_usage"], metrics.get("token_usage") or {})
    return combined


def _merge_counts(target: dict[str, int], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if isinstance(value, (int, float)):
            target[str(key)] = target.get(str(key), 0) + int(value)


def _poster_card(card: dict[str, str]) -> str:
    return f"""
      <article class="metric">
        <div class="label">{escape(card["label"])}</div>
        <div class="value">{escape(str(card["value"]))}</div>
        <div class="note"><span class="chip chip-{escape(card["level"])}">{escape(card["level"])}</span> {escape(card["note"])}</div>
      </article>"""


def _timeline_model(source_map: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for name in ("codex", "claude"):
        source = source_map.get(name, {})
        metrics = source.get("metrics", {})
        if metrics.get("first_seen_at"):
            items.append(
                {
                    "date": _format_month(str(metrics["first_seen_at"])),
                    "event": f"{name.title()} local evidence starts · {source.get('status')}",
                }
            )
    git = source_map.get("git", {}).get("metrics", {})
    for window in git.get("date_windows") or []:
        if window.get("first_commit_at"):
            items.append(
                {
                    "date": _format_month(str(window["first_commit_at"])),
                    "event": "Local Git delivery evidence starts",
                }
            )
            break
    if source_map.get("github", {}).get("status") == "available":
        items.append({"date": "GitHub", "event": "Optional GitHub evidence available"})
    if not items:
        items = [
            {"date": "Now", "event": "Candidate authorization captured"},
            {"date": "Missing", "event": "No local AI or Git evidence available"},
        ]
    while len(items) < 4:
        missing_source = next(
            (
                source["name"]
                for source in source_map.values()
                if source.get("status") in {"missing", "skipped"}
            ),
            "source",
        )
        items.append({"date": "Open", "event": f"{missing_source.title()} evidence gap to validate"})
    return items[:4]


def _counter_items(counter: dict[str, Any], empty: str) -> list[dict[str, str]]:
    if not counter:
        return [{"name": empty, "value": "missing"}]
    ordered = sorted(counter.items(), key=lambda item: int(item[1]), reverse=True)[:5]
    return [{"name": str(name), "value": str(int(value))} for name, value in ordered]


def _leader_item(item: dict[str, str]) -> str:
    return f'<div class="leader"><strong>{escape(item["name"])}</strong><span>{escape(item["value"])}</span></div>'


def _timeline_item(item: dict[str, str]) -> str:
    return f"""
        <div class="milestone">
          <div class="date">{escape(item["date"])}</div>
          <div class="event">{escape(item["event"])}</div>
        </div>"""


def _dimension_pill(item: dict[str, str]) -> str:
    return f"""
        <div class="dimension">
          <div class="dimension-title">{escape(item["title"])}</div>
          <div class="dimension-level">{escape(item["level"])}</div>
        </div>"""


def _poster_headline(assessment: dict[str, Any]) -> str:
    observed = sum(1 for dimension in assessment.get("dimensions", []) if dimension.get("evidence_level") == "observed")
    inferred = sum(1 for dimension in assessment.get("dimensions", []) if dimension.get("evidence_level") == "inferred")
    return f"{observed} observed dimensions · {inferred} inferred dimensions · human review required"


def _missing_or_number(value: int) -> str:
    return str(value) if value else "--"


def _format_compact(value: int) -> str:
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return str(value)


def _format_month(value: str) -> str:
    if len(value) >= 7 and value[4] == "-":
        return value[:7]
    return value[:10] if len(value) >= 10 else value


def _wrap_svg_text(text: str, width: int, max_lines: int) -> list[str]:
    if not text:
        return [""]
    chunks = _wrap_visual_text(text, width)
    if len(chunks) <= max_lines:
        return chunks
    return chunks[: max_lines - 1] + [chunks[max_lines - 1][: max(0, width - 1)] + "..."]


def _wrap_visual_text(text: str, width: int) -> list[str]:
    normalized = " ".join(str(text).split())
    lines: list[str] = []
    current = ""
    current_width = 0.0
    for char in normalized:
        char_width = 0.55 if ord(char) < 128 else 1.0
        if current and current_width + char_width > width:
            lines.append(current.rstrip())
            current = char
            current_width = char_width
        else:
            current += char
            current_width += char_width
    if current:
        lines.append(current.rstrip())
    return lines or [normalized]
