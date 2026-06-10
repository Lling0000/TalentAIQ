# TalentAIQ Lite

**中文** | [English](./README.en.md) · [GitHub](https://github.com/Lling0000/TalentAIQ) · [Issues](https://github.com/Lling0000/TalentAIQ/issues)

![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Local First](https://img.shields.io/badge/local--first-yes-brightgreen)
![No Ranking](https://img.shields.io/badge/no--ranking-no--rejection-orange)

本地优先、候选人授权、默认脱敏的 AI coding 能力证据生成器。

TalentAIQ Lite 读取候选人本机可访问的 Codex、Claude Code、本地 Git 和本地工程痕迹，生成一份面向人工技术面试的证据包：Markdown 报告、结构化 JSON、面试追问题、隐私清单、HTML 画报和 SVG 面试画像。

它不是自动筛选系统，也不是录用建议系统。它不做候选人排名、不自动淘汰、不推荐录用，只把“看到了什么证据、缺了什么证据、面试应该追问什么”整理出来。

## 为什么需要它

AI coding 已经进入真实开发流程，但“用了很多 AI”并不等于“工程能力强”。面试官真正需要的是可验证的证据线索：

- 候选人是否高频使用 AI coding 工具？
- 是否有任务拆解、上下文管理、多工具编排的痕迹？
- 是否把 AI 工作流沉淀成脚本、测试、CI、prompt 或 skill？
- AI 使用是否真的转化成 Git commit、PR、代码 diff 或测试结果？
- 哪些结论只是线索，必须在面试中继续验证？

TalentAIQ Lite 的答案不是评分，而是一份证据摘要和追问清单。

## 它做什么 / 绝不做什么

| 做什么 | 绝不做什么 |
| --- | --- |
| 读取候选人授权的本地 AI coding 记录 | 不读取未授权数据 |
| 聚合 Codex、Claude、本地 Git、本地工程痕迹和可选 GitHub 数据 | 不输出原始 prompt、completion、secret 或完整本地路径 |
| 生成 Markdown、JSON、追问题、隐私清单、HTML 画报、SVG 画像 | 不做自动排名、自动淘汰、自动推荐录用 |
| 给每条结论标记 `observed` / `limited` / `inferred` / `missing` | 不把缺失数据编造成能力判断 |
| 帮面试官准备人工追问 | 不替代代码审查、技术面试或人工判断 |

## 工作流

```text
候选人授权
  -> 读取本地 Codex / Claude / Git / project_traces
  -> 默认脱敏，只保留聚合证据和类别指标
  -> 按六个维度生成 observed / limited / inferred / missing 结论
  -> 输出报告、JSON、追问题、隐私清单、HTML 画报和 SVG 画像
  -> 由面试官在人工面试、代码讲解或现场任务中验证
```

## 30 秒快速开始

当前版本不依赖第三方 Python 包。克隆仓库后即可运行：

```bash
git clone https://github.com/Lling0000/TalentAIQ.git
cd TalentAIQ
python3 -m talentaiq.cli --authorize --repo . --output-dir reports/self-check
```

你会看到类似输出：

```text
TalentAIQ Lite generated evidence artifacts:
- json: reports/self-check/talentaiq_report.json
- markdown: reports/self-check/talentaiq_report.md
- questions: reports/self-check/interview_questions.md
- privacy: reports/self-check/privacy_checklist.md
- poster_html: reports/self-check/poster.html
- svg: reports/self-check/interview_profile.svg
Boundary: evidence only; no ranking, rejection, or hiring recommendation.
```

输出目录会是这个形状：

```text
reports/self-check/
├── talentaiq_report.md
├── talentaiq_report.json
├── interview_questions.md
├── privacy_checklist.md
├── poster.html
└── interview_profile.svg
```

打开推荐入口：

```bash
open reports/self-check/poster.html
open reports/self-check/talentaiq_report.md
```

`reports/` 默认被 `.gitignore` 忽略，避免把本地候选人证据包误推到远程仓库。

如果希望安装命令行入口，也可以在仓库内执行：

```bash
python3 -m pip install -e .
talentaiq --authorize --repo . --output-dir reports/self-check
```

## 输出产物

| 文件 | 用途 |
| --- | --- |
| `talentaiq_report.md` | 中文优先的 AI coding 证据摘要，适合面试前阅读 |
| `talentaiq_report.json` | 完整结构化结果，可用于后续系统集成或二次渲染 |
| `interview_questions.md` | 按六个维度生成的面试追问题 |
| `privacy_checklist.md` | 候选人授权、脱敏、数据源状态和风险边界清单 |
| `poster.html` | 推荐查看入口，画报式 AI-native 工作画像页面 |
| `interview_profile.svg` | 可嵌入文档或面试材料的 SVG 面试画像 |

## 示例摘要

报告会把事实、限制和追问分开：

```md
## 4.4 工程交付关联

**证据等级：`limited`**

当前证据能说明存在 AI coding 使用记录和部分工程结构痕迹，
但不能充分证明这些 AI 使用已经转化为真实、可审查、可交付的工程成果。

面试中应要求候选人提供至少一个真实 commit、PR、项目交付物或代码 diff。
```

这类文字由当前运行的 JSON metrics 动态生成，不会把某一次 self-check 的数字硬编码进 README 或报告模板。

## 数据源

| 数据源 | 默认输入 | 支持级别 | 缺失时行为 | 隐私处理 |
| --- | --- | --- | --- | --- |
| Codex 本地记录 | `~/.codex/sessions/**/*.jsonl` | MVP 支持 | 标记为 `missing` | 只统计记录数、工具事件、任务/上下文/工作流信号 |
| Claude Code 本地记录 | `~/.claude/projects/**/*.jsonl` | MVP 支持 | 标记为 `missing` | 不输出原始 prompt 或 completion |
| 本地 Git | `--repo` 指定路径，默认当前仓库 | MVP 支持 | 标记为 `missing` 或 `available but empty` | 不输出原始 commit subject、远程 URL、作者邮箱 |
| 本地工程痕迹 | README、docs、tests、scripts、CI、package、MCP、agent config、prompt、skill | 支持 | 标记为 `missing` | 作为 `project_traces` 子类指标，只输出类别计数 |
| GitHub | `--github-json` 或显式 `--enable-github` | 可选 | 默认 `skipped` | 不自动访问远程仓库或 PR 数据 |

注意：CI、test、package manager、MCP、agent config、prompt、skill 都是 `project_traces` 下面的子类指标，不会被拆成顶层数据源。

`project_traces` 的作用是补充“项目结构里是否存在工程化痕迹”，例如测试目录、CI 配置、package manifest、MCP 配置、agent 配置、prompt 或 skill 文件。它只能说明“看到了这些类别”，不能代替 commit、PR、diff 或测试结果。

## 六个证据维度

TalentAIQ Lite 固定围绕六个维度组织报告：

| 维度 | 关注问题 |
| --- | --- |
| AI 工具熟练度 | 是否存在持续 AI coding 工具使用和多类工具事件 |
| 任务拆解 | 是否存在 planning、todo、任务拆解或迭代控制信号 |
| 上下文管理 | 是否存在 summary、memory、continuation、long-context 等信号 |
| 多工具编排 | 是否跨 AI 工具、shell、搜索读取、编辑、本地 Git、工程文件协同 |
| AI 工作流建设 | 是否沉淀 scripts、CI、MCP、agent config、prompt、skill 等工程化痕迹 |
| 工程交付关联 | AI 使用是否能和 Git commit、PR、代码 diff、测试结果形成可审查关联 |

## 证据等级

| 等级 | 含义 | 使用方式 |
| --- | --- | --- |
| `observed` | 有直接可观察信号 | 可以作为面试追问依据 |
| `limited` | 有部分信号，但关键证据不足 | 只能作为重点验证点 |
| `inferred` | 基于间接信号推断 | 只能作为假设，不能当作事实 |
| `missing` | 当前数据源未发现证据 | 不能反推出候选人没有该能力 |

## 常用命令

单仓库生成报告：

```bash
python3 -m talentaiq.cli --authorize --repo . --output-dir reports/self-check
```

多仓库生成报告：

```bash
python3 -m talentaiq.cli \
  --authorize \
  --candidate-label candidate-2026-001 \
  --repo /path/to/project-a \
  --repo /path/to/project-b \
  --output-dir reports/candidate-2026-001
```

指定本地 AI 工具目录：

```bash
python3 -m talentaiq.cli \
  --authorize \
  --codex-dir ~/.codex \
  --claude-dir ~/.claude \
  --repo . \
  --output-dir reports/self-check
```

读取本地 GitHub JSON 导出：

```bash
python3 -m talentaiq.cli \
  --authorize \
  --repo . \
  --github-json ./github-export.json \
  --output-dir reports/with-github-json
```

显式允许 GitHub CLI 查询：

```bash
python3 -m talentaiq.cli \
  --authorize \
  --repo . \
  --enable-github \
  --github-user octocat \
  --output-dir reports/with-gh-api
```

## 隐私与安全边界

TalentAIQ Lite 默认只保留聚合证据，不保留原始对话内容：

- 不输出原始 prompt、completion、工具参数全文。
- 不输出 secret、token、私钥、邮箱或完整本地绝对路径。
- 不自动读取 GitHub，除非传入本地 JSON 或显式开启 `--enable-github`。
- 不把 `limited` 或 `inferred` 当作事实结论。
- 不依据年龄、性别、婚育、民族、宗教、残障等受保护属性进行提问、评价或筛选。

本工具会尽力通过模式匹配移除常见 secret，但它不是正式 DLP 或安全审计系统。正式使用前仍应做组织内安全审查。

## 什么时候不该用

不要把 TalentAIQ Lite 用在这些场景：

- 自动候选人排名。
- 自动淘汰候选人。
- 自动推荐录用。
- 替代代码审查或技术面试。
- 在候选人未授权时读取本地 AI coding 记录。
- 把缺失数据解释为“候选人没有能力”。

## 开发与验证

运行测试：

```bash
python3 -m unittest discover -s tests
```

运行编译检查：

```bash
python3 -m compileall talentaiq tests setup.py
```

生成本地 self-check 报告：

```bash
python3 -m talentaiq.cli --authorize --candidate-label self-check --repo . --output-dir reports/self-check
```

发布前建议做一次敏感信息扫描：

```bash
rg -n "sk-[A-Za-z0-9_-]{20,}|gh[opusr]_[A-Za-z0-9_]{20,}|github_pat_|BEGIN [A-Z ]*PRIVATE KEY" . --glob '!reports/**' --glob '!.git/**'
```

## 路线图

- 支持更多 AI coding 工具本地记录。
- 增加更细粒度的 Git diff / test / CI 证据关联。
- 增加可配置的证据维度和组织内面试模板。
- 增加更严格的本地隐私审计和输出前检查。
- 增加示例数据集和更完整的 demo 报告。

## License

MIT
