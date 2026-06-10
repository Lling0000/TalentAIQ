from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

from talentaiq.core import RunConfig, run_assessment


class TalentAIQTests(unittest.TestCase):
    def test_generates_all_outputs_with_redaction_and_evidence_levels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_dir = root / "codex"
            claude_dir = root / "claude"
            repo = root / "repo"
            out = root / "out"
            (codex_dir / "sessions").mkdir(parents=True)
            (claude_dir / "projects" / "sample").mkdir(parents=True)
            secret = "sk-ant-" + "a" * 40
            (codex_dir / "sessions" / "one.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps({"role": "user", "content": f"plan this task with credential marker {secret}"}),
                        json.dumps({"type": "function_call", "name": "functions.update_plan"}),
                        json.dumps({"type": "function_call", "name": "functions.exec_command"}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (claude_dir / "projects" / "sample" / "one.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "type": "assistant",
                                "message": {
                                    "content": [
                                        {"type": "tool_use", "name": "TodoWrite"},
                                        {"type": "tool_use", "name": "Bash"},
                                        {"type": "tool_use", "name": "Edit"},
                                    ]
                                },
                            }
                        ),
                        json.dumps({"role": "user", "content": "context summary workflow script"}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            self._init_git_repo(repo)

            assessment = run_assessment(
                RunConfig(
                    candidate_label="candidate-test",
                    repos=[str(repo)],
                    output_dir=str(out),
                    codex_dir=str(codex_dir),
                    claude_dir=str(claude_dir),
                    authorized=True,
                )
            )

            expected_files = {
                "talentaiq_report.md",
                "talentaiq_report.json",
                "interview_questions.md",
                "privacy_checklist.md",
                "poster.html",
                "interview_profile.svg",
            }
            self.assertEqual(expected_files, {path.name for path in out.iterdir()})

            combined_output = "\n".join(path.read_text(encoding="utf-8") for path in out.iterdir())
            self.assertNotIn(secret, combined_output)
            self.assertIn("[REDACTED", combined_output)
            self.assertIn("AI 工具熟练度", combined_output)
            self.assertIn("工程交付关联", combined_output)
            self.assertIn("Active Days", combined_output)
            self.assertIn("Top Slash 命令", combined_output)
            markdown = (out / "talentaiq_report.md").read_text(encoding="utf-8")
            self.assertIn("# TalentAIQ Lite · AI Coding 证据摘要", markdown)
            self.assertIn("## 1. 生成对象", markdown)
            self.assertIn("## 2. 数据源概览", markdown)
            self.assertIn("本地工程痕迹", markdown)
            self.assertIn("## 3. 证据等级说明", markdown)
            self.assertIn("## 4. 核心证据摘要", markdown)
            self.assertIn("## 5. 六个面试验证维度", markdown)
            self.assertIn("## 6. 面试官使用建议", markdown)
            self.assertIn("## 7. 禁用用途", markdown)
            self.assertIn("## 8. 最终一句话摘要", markdown)
            svg = (out / "interview_profile.svg").read_text(encoding="utf-8")
            self.assertIn("本地工程痕迹", svg)
            ET.fromstring(svg)

            report = json.loads((out / "talentaiq_report.json").read_text(encoding="utf-8"))
            source_names = [source["name"] for source in report["sources"]]
            self.assertEqual(["claude", "codex", "git", "project_traces", "github"], source_names)
            self.assertTrue(
                {
                    "ci",
                    "test",
                    "tests",
                    "package_manager",
                    "package",
                    "mcp",
                    "agent_config",
                    "prompt",
                    "skill",
                }.isdisjoint(source_names)
            )
            self.assertEqual(6, len(report["dimensions"]))
            for dimension in report["dimensions"]:
                self.assertIn(dimension["evidence_level"], {"observed", "inferred", "limited", "missing"})
                self.assertTrue(dimension["conclusions"])
                for conclusion in dimension["conclusions"]:
                    self.assertIn(conclusion["evidence_level"], {"observed", "inferred", "limited", "missing"})
            self.assertTrue(report["assessment_boundaries"]["no_auto_ranking"])
            self.assertTrue(report["assessment_boundaries"]["no_auto_rejection"])
            self.assertTrue(report["assessment_boundaries"]["no_hiring_recommendation"])
            self.assertEqual("poster.html", report["artifacts"]["poster_html"])
            self.assertIn("output_paths", assessment)

    def test_graceful_degradation_for_missing_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "out"
            assessment = run_assessment(
                RunConfig(
                    candidate_label="candidate-missing",
                    repos=[str(root / "not-a-repo")],
                    output_dir=str(out),
                    codex_dir=str(root / "missing-codex"),
                    claude_dir=str(root / "missing-claude"),
                    authorized=True,
                )
            )
            statuses = {source["name"]: source["status"] for source in assessment["sources"]}
            self.assertEqual("missing", statuses["claude"])
            self.assertEqual("missing", statuses["codex"])
            self.assertEqual("missing", statuses["git"])
            self.assertEqual("missing", statuses["project_traces"])
            self.assertEqual("skipped", statuses["github"])
            report = json.loads((out / "talentaiq_report.json").read_text(encoding="utf-8"))
            self.assertTrue(all(dimension["evidence_level"] in {"limited", "missing"} for dimension in report["dimensions"]))
            poster = (out / "poster.html").read_text(encoding="utf-8")
            self.assertIn("--", poster)
            self.assertIn("missing", poster)

    def test_project_traces_are_nested_metrics_and_do_not_leak_file_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            out = root / "out"
            repo.mkdir()
            fake_secret = "sk-" + "b" * 40
            fake_local_path = str(repo / "private" / "candidate.py")
            self._write_project_trace_fixtures(repo, fake_secret, fake_local_path)

            run_assessment(
                RunConfig(
                    candidate_label="candidate-project-traces",
                    repos=[str(repo)],
                    output_dir=str(out),
                    codex_dir=str(root / "missing-codex"),
                    claude_dir=str(root / "missing-claude"),
                    authorized=True,
                )
            )

            report = json.loads((out / "talentaiq_report.json").read_text(encoding="utf-8"))
            source_names = [source["name"] for source in report["sources"]]
            self.assertEqual(["claude", "codex", "git", "project_traces", "github"], source_names)
            self.assertTrue(
                {
                    "ci",
                    "test",
                    "tests",
                    "package_manager",
                    "package",
                    "mcp",
                    "agent_config",
                    "prompt",
                    "skill",
                }.isdisjoint(source_names)
            )

            project = next(source for source in report["sources"] if source["name"] == "project_traces")
            metrics = project["metrics"]
            self.assertEqual("available", project["status"])
            self.assertGreaterEqual(metrics["readme_files"], 1)
            self.assertGreaterEqual(metrics["test_dirs"], 1)
            self.assertGreaterEqual(metrics["test_reports"], 1)
            self.assertGreaterEqual(metrics["scripts"], 1)
            self.assertGreaterEqual(metrics["ci_configs"], 1)
            self.assertGreaterEqual(metrics["package_manifests"], 1)
            self.assertGreaterEqual(metrics["lockfiles"], 1)
            self.assertGreaterEqual(metrics["mcp_config_files"], 1)
            self.assertGreaterEqual(metrics["agent_config_files"], 2)
            self.assertGreaterEqual(metrics["prompt_files"], 1)
            self.assertGreaterEqual(metrics["skill_files"], 1)
            self.assertGreaterEqual(metrics["trace_items"], 11)
            self.assertNotIn("prompt_or_skill_files", metrics)
            self.assertFalse(project["privacy"]["raw_file_contents_included"])
            self.assertFalse(project["privacy"]["raw_paths_included"])
            self.assertFalse(project["privacy"]["raw_prompt_text_included"])

            refs = {
                ref
                for dimension in report["dimensions"]
                for ref in dimension.get("evidence_refs", [])
            }
            self.assertIn("project_traces.workflow_artifacts", refs)
            self.assertIn("project_traces.delivery_artifacts", refs)
            workflow_observations = "\n".join(
                "\n".join(dimension.get("observations", []))
                for dimension in report["dimensions"]
            )
            self.assertNotIn("Repository artifact signals", workflow_observations)

            combined_output = "\n".join(path.read_text(encoding="utf-8") for path in out.iterdir())
            self.assertIn("本地工程痕迹", combined_output)
            self.assertIn("source_project_traces", combined_output)
            self.assertNotIn(fake_secret, combined_output)
            self.assertNotIn(fake_local_path, combined_output)
            self.assertNotIn("raw prompt fixture must not leak", combined_output)

    def test_authorization_required(self) -> None:
        with self.assertRaises(PermissionError):
            run_assessment(RunConfig(authorized=False))

    def test_ai_jsonl_limits_are_configurable_and_zero_disables_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_dir = root / "codex"
            repo = root / "repo"
            out_limited = root / "out-limited"
            out_unlimited = root / "out-unlimited"
            (codex_dir / "sessions").mkdir(parents=True)
            (codex_dir / "sessions" / "one.jsonl").write_text(
                "\n".join(json.dumps({"role": "user", "content": f"record {idx}"}) for idx in range(3)) + "\n",
                encoding="utf-8",
            )
            self._init_git_repo(repo)

            limited = run_assessment(
                RunConfig(
                    repos=[str(repo)],
                    output_dir=str(out_limited),
                    codex_dir=str(codex_dir),
                    claude_dir=str(root / "missing-claude"),
                    max_ai_jsonl_records=2,
                    authorized=True,
                )
            )
            limited_codex = next(source for source in limited["sources"] if source["name"] == "codex")
            self.assertEqual(2, limited_codex["metrics"]["records"])
            self.assertIsNone(limited_codex["metrics"]["max_jsonl_files"])
            self.assertEqual(2, limited_codex["metrics"]["max_jsonl_records"])

            unlimited = run_assessment(
                RunConfig(
                    repos=[str(repo)],
                    output_dir=str(out_unlimited),
                    codex_dir=str(codex_dir),
                    claude_dir=str(root / "missing-claude"),
                    max_ai_jsonl_records=None,
                    authorized=True,
                )
            )
            unlimited_codex = next(source for source in unlimited["sources"] if source["name"] == "codex")
            self.assertEqual(3, unlimited_codex["metrics"]["records"])
            self.assertIsNone(unlimited_codex["metrics"]["max_jsonl_records"])

    @staticmethod
    def _init_git_repo(repo: Path) -> None:
        repo.mkdir()
        subprocess.run(["git", "-C", str(repo), "init"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "TalentAIQ Test"], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
        (repo / "README.md").write_text("# sample\n", encoding="utf-8")
        (repo / "scripts").mkdir()
        (repo / "scripts" / "check.sh").write_text("echo ok\n", encoding="utf-8")
        (repo / "tests").mkdir()
        (repo / "tests" / "test_sample.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "initial"], check=True, capture_output=True)

    @staticmethod
    def _write_project_trace_fixtures(repo: Path, fake_secret: str, fake_local_path: str) -> None:
        (repo / "README.md").write_text("# sample\n", encoding="utf-8")
        (repo / "docs").mkdir()
        (repo / "docs" / "overview.md").write_text("docs\n", encoding="utf-8")
        (repo / "tests").mkdir()
        (repo / "tests" / "test_sample.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
        (repo / "coverage.xml").write_text("<coverage />\n", encoding="utf-8")
        (repo / "scripts").mkdir()
        (repo / "scripts" / "check.sh").write_text("echo ok\n", encoding="utf-8")
        (repo / ".github" / "workflows").mkdir(parents=True)
        (repo / ".github" / "workflows" / "ci.yml").write_text("name: ci\n", encoding="utf-8")
        (repo / "package.json").write_text('{"scripts":{"test":"pytest"}}\n', encoding="utf-8")
        (repo / "package-lock.json").write_text('{"lockfileVersion":3}\n', encoding="utf-8")
        (repo / ".mcp.json").write_text(
            json.dumps({"api_key": fake_secret, "path": fake_local_path}),
            encoding="utf-8",
        )
        (repo / "AGENTS.md").write_text(
            f"agent config with {fake_secret} and {fake_local_path}\n",
            encoding="utf-8",
        )
        (repo / "agents").mkdir()
        (repo / "agents" / "openai.yaml").write_text("agent: local\n", encoding="utf-8")
        (repo / "prompts").mkdir()
        (repo / "prompts" / "review.md").write_text(
            f"raw prompt fixture must not leak {fake_secret} {fake_local_path}\n",
            encoding="utf-8",
        )
        (repo / "skills" / "demo").mkdir(parents=True)
        (repo / "skills" / "demo" / "SKILL.md").write_text(
            f"# Skill\nsecret {fake_secret}\npath {fake_local_path}\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
