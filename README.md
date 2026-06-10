# TalentAIQ Lite

TalentAIQ Lite 是一个本地优先、候选人授权、默认脱敏的 AI-native 候选人能力证据生成器。它读取候选人本机可访问的 AI coding 工具记录、本地 Git 数据，以及可选 GitHub 数据，生成面试前的证据材料。

它不是自动筛选系统，也不是录用建议系统。TalentAIQ Lite 不做候选人排名、不自动淘汰、不推荐录用，只把可验证证据、缺失证据和建议追问整理出来。

## MVP 支持范围

- Claude Code 本地记录：默认读取 `~/.claude/projects/**/*.jsonl`
- Codex 本地记录：默认读取 `~/.codex/sessions/**/*.jsonl`
- 本地 Git：默认读取当前仓库，也可以用 `--repo` 指定多个仓库
- 本地工程痕迹：扫描 README、docs、tests、test reports、scripts、CI、package manager、lockfiles、MCP、agent config、prompt、skill 等类别指标
- 可选 GitHub：读取本地 JSON 导出，或在显式开启后用 `gh api` 做有限查询
- 默认脱敏：secret、token、邮箱、本机 home path、带敏感 query 的 URL 会被替换
- 优雅降级：Claude、Codex、GitHub 或 Git 数据缺失时不会编造结论，而是标记为 `missing` / `skipped` / `partial`

## 输出产物

运行后会在输出目录生成：

- `talentaiq_report.md`：面试可读 Markdown 报告
- `talentaiq_report.json`：结构化 JSON
- `interview_questions.md`：按证据缺口组织的面试追问题
- `privacy_checklist.md`：候选人授权、数据源、脱敏和安全边界清单
- `poster.html`：画报式 AI-native 工作画像页面，包含大数字指标、时间线、Top slash 命令和六维证据概览
- `interview_profile.svg`：面试画像 SVG，不含分数和排名

报告固定围绕六个维度组织：

1. AI 工具熟练度
2. 任务拆解
3. 上下文管理
4. 多工具编排
5. AI 工作流建设
6. 工程交付关联

每条结论都带 `evidence_level`：

- `observed`：本地记录或 Git 数据直接可见
- `inferred`：由多个可观察信号组合推断，必须面试复核
- `limited`：证据稀疏，只能作为追问线索
- `missing`：没有可访问证据，不能下结论

## 快速开始

```bash
python3 -m talentaiq.cli --authorize --repo . --output-dir reports
```

指定候选人标签和本地工具目录：

```bash
python3 -m talentaiq.cli \
  --authorize \
  --candidate-label "candidate-2026-001" \
  --repo /path/to/project-a \
  --repo /path/to/project-b \
  --codex-dir ~/.codex \
  --claude-dir ~/.claude \
  --output-dir reports/candidate-2026-001
```

读取本地 GitHub JSON 导出：

```bash
python3 -m talentaiq.cli \
  --authorize \
  --repo . \
  --github-json ./github-export.json \
  --output-dir reports
```

显式允许使用 GitHub CLI 查询公开/授权数据：

```bash
python3 -m talentaiq.cli \
  --authorize \
  --repo . \
  --enable-github \
  --github-user octocat \
  --output-dir reports
```

没有 `--authorize` 时程序会拒绝运行，因为本工具的前提是候选人授权。

## 隐私与安全边界

TalentAIQ Lite 默认不输出原始 prompt、completion、完整命令参数、secret 或 token。采集器只保留聚合信号、工具类型、文件数量、提交数量、工程痕迹类别、状态和脱敏后的路径。CI、test、package manager、MCP、agent config、prompt、skill 都作为 `project_traces` 的子类指标，不会拆成一堆顶层数据源。输出中的隐私清单会说明扫描了哪些数据源、哪些数据源缺失、发生了多少次脱敏替换。

本工具会尽力通过模式匹配移除常见 secret，但不能替代正式 DLP 或安全审计。面试官使用报告时必须保留人工复核，不得把 `observed` 或 `inferred` 误用为自动招聘结论。

## 开发与验证

```bash
python3 -m unittest discover -s tests
python3 -m talentaiq.cli --authorize --repo . --output-dir reports/self-check
```

## English Summary

TalentAIQ Lite is a local-first, candidate-authorized, redaction-by-default evidence generator for AI-native engineering interviews. It reads Claude Code, Codex, local Git, and optional GitHub data, then emits Markdown, JSON, interview questions, a privacy checklist, and an SVG interview profile. It never ranks candidates, rejects candidates, or recommends hiring.
