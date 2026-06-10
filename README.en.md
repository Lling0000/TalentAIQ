# TalentAIQ Lite

[中文](./README.md) | **English** · [GitHub](https://github.com/Lling0000/TalentAIQ) · [Issues](https://github.com/Lling0000/TalentAIQ/issues)

![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Local First](https://img.shields.io/badge/local--first-yes-brightgreen)
![No Ranking](https://img.shields.io/badge/no--ranking-no--rejection-orange)

TalentAIQ Lite is a local-first, candidate-authorized, redaction-by-default evidence generator for AI coding interviews.

It reads candidate-authorized local Codex records, Claude Code records, local Git data, and local project traces, then generates an interview-ready evidence packet: Markdown, structured JSON, interview follow-up questions, a privacy checklist, an HTML poster, and an SVG interview profile.

It is not a screening engine, ranking system, rejection system, or hiring recommendation system. TalentAIQ Lite only organizes observable evidence, missing evidence, and human interview follow-up questions.

## Why It Exists

AI coding is now part of real engineering work, but "used AI a lot" is not the same as "can ship reliable software." Interviewers need evidence they can inspect and verify:

- Did the candidate use AI coding tools repeatedly, or only once?
- Are there signals of task decomposition, context management, and multi-tool orchestration?
- Did the candidate turn AI usage into scripts, tests, CI, prompts, skills, or reusable workflow assets?
- Can the AI usage be connected to Git commits, PRs, code diffs, tests, or delivery artifacts?
- Which claims are only interview leads that require human validation?

TalentAIQ Lite answers with an evidence summary and follow-up questions, not with scores.

## What It Does / Never Does

| Does | Never does |
| --- | --- |
| Reads candidate-authorized local AI coding records | Reads unauthorized local data |
| Aggregates Codex, Claude, local Git, project traces, and optional GitHub data | Emits raw prompts, completions, secrets, or full local paths |
| Generates Markdown, JSON, questions, privacy checklist, HTML poster, and SVG profile | Ranks candidates, rejects candidates, or recommends hiring |
| Marks every conclusion as `observed`, `limited`, `inferred`, or `missing` | Turns missing data into ability claims |
| Prepares interview follow-up material for humans | Replaces code review, technical interviews, or human judgment |

## Workflow

```text
candidate authorization
  -> read local Codex / Claude / Git / project_traces
  -> redact by default and keep aggregate evidence
  -> organize conclusions across six evidence dimensions
  -> emit Markdown, JSON, questions, privacy checklist, HTML poster, and SVG
  -> validate findings in a human interview, code walkthrough, or live task
```

## 30-Second Quick Start

The current version has no third-party Python runtime dependencies:

```bash
git clone https://github.com/Lling0000/TalentAIQ.git
cd TalentAIQ
python3 -m talentaiq.cli --authorize --repo . --output-dir reports/self-check
```

Expected output:

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

Expected artifact tree:

```text
reports/self-check/
├── talentaiq_report.md
├── talentaiq_report.json
├── interview_questions.md
├── privacy_checklist.md
├── poster.html
└── interview_profile.svg
```

`reports/` is ignored by Git by default so local candidate evidence is not pushed accidentally.

To install the CLI entry point locally:

```bash
python3 -m pip install -e .
talentaiq --authorize --repo . --output-dir reports/self-check
```

## Output Artifacts

| File | Purpose |
| --- | --- |
| `talentaiq_report.md` | Chinese-first AI coding evidence summary for interview preparation |
| `talentaiq_report.json` | Full structured result for integrations or custom rendering |
| `interview_questions.md` | Follow-up questions organized by the six evidence dimensions |
| `privacy_checklist.md` | Candidate authorization, redaction, source status, and usage boundary checklist |
| `poster.html` | Recommended visual entry point for the AI-native work profile |
| `interview_profile.svg` | SVG interview profile for documents or interview prep packets |

## Data Sources

| Source | Default input | Support level | Missing-source behavior | Privacy handling |
| --- | --- | --- | --- | --- |
| Codex local records | `~/.codex/sessions/**/*.jsonl` | MVP supported | `missing` | Counts records, tool events, task/context/workflow signals |
| Claude Code local records | `~/.claude/projects/**/*.jsonl` | MVP supported | `missing` | Does not emit raw prompts or completions |
| Local Git | `--repo`, default current repo | MVP supported | `missing` or `available but empty` | Does not emit raw commit subjects, remote URLs, or author emails |
| Project traces | README, docs, tests, scripts, CI, package, MCP, agent config, prompt, skill | Supported | `missing` | Nested under `project_traces`; emits category counts only |
| GitHub | `--github-json` or explicit `--enable-github` | Optional | `skipped` by default | No remote PR or issue lookup unless explicitly enabled |

CI, tests, package manager, MCP, agent config, prompt, and skill signals are child metrics under `project_traces`; they are not top-level sources. `project_traces` can support interview questions about workflow assets, but it does not replace commit, PR, diff, or test evidence.

## Evidence Model

TalentAIQ Lite always organizes the report around six dimensions:

| Dimension | What it asks |
| --- | --- |
| AI tool fluency | Is there sustained AI coding usage and evidence of multiple tool-event families? |
| Task decomposition | Are there planning, todo, task breakdown, or iteration-control signals? |
| Context management | Are there summary, memory, continuation, or long-context signals? |
| Multi-tool orchestration | Does the workflow span AI tools, shell, search/read, edit, local Git, and project files? |
| AI workflow building | Are there scripts, CI, MCP, agent config, prompts, skills, or other reusable assets? |
| Engineering delivery linkage | Can AI usage be connected to commits, PRs, diffs, tests, or delivery artifacts? |

Every conclusion includes an evidence level:

| Level | Meaning | Use |
| --- | --- | --- |
| `observed` | Directly visible evidence | Can support interview follow-up |
| `limited` | Partial signal, key evidence missing | Must be validated |
| `inferred` | Indirect signal | Hypothesis only |
| `missing` | No accessible evidence | Do not draw a negative conclusion |

## Privacy And Safety Boundaries

TalentAIQ Lite keeps aggregate evidence by default, not raw conversations:

- It does not emit raw prompts, completions, or full tool arguments.
- It does not emit secrets, tokens, private keys, emails, or full local absolute paths.
- It does not query GitHub unless a local JSON export is supplied or `--enable-github` is explicitly set.
- It does not treat `limited` or `inferred` as facts.
- It must not be used for protected-attribute screening or evaluation.

The redactor removes common secret and PII patterns, but TalentAIQ Lite is not a formal DLP or security audit system. Organizations should run their own review before production use.

## When Not To Use It

Do not use TalentAIQ Lite for:

- Automatic candidate ranking.
- Automatic rejection.
- Hiring recommendations.
- Replacing code review or technical interviews.
- Reading local AI coding records without candidate authorization.
- Treating missing data as proof that a candidate lacks an ability.

## Development

```bash
python3 -m unittest discover -s tests
python3 -m compileall talentaiq tests setup.py
python3 -m talentaiq.cli --authorize --candidate-label self-check --repo . --output-dir reports/self-check
```

Before publishing, scan for accidental secrets outside ignored reports:

```bash
rg -n "sk-[A-Za-z0-9_-]{20,}|gh[opusr]_[A-Za-z0-9_]{20,}|github_pat_|BEGIN [A-Z ]*PRIVATE KEY" . --glob '!reports/**' --glob '!.git/**'
```

## Roadmap

- Support more local AI coding tools.
- Add deeper Git diff, test, and CI evidence linkage.
- Add configurable interview templates for organizations.
- Add stricter local privacy auditing before export.
- Add sample datasets and richer demo reports.

## License

MIT
