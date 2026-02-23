"""
Tests for challenge-related models and config.

Tests the ChallengeResult model, config fields, and integration
with AgentRunResult and RunOutcome.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from secret_validator_grunt.models.challenge_result import (
	ChallengeResult,
	VALID_CHALLENGE_VERDICTS,
)
from secret_validator_grunt.models.run_result import AgentRunResult
from secret_validator_grunt.models.run_outcome import RunOutcome
from secret_validator_grunt.models.judge_result import JudgeResult, JudgeScore
from secret_validator_grunt.models.config import Config


class TestChallengeResultModel:
	"""Tests for ChallengeResult model construction and validation."""

	def test_minimal_construction(self):
		"""ChallengeResult can be constructed with just verdict."""
		cr = ChallengeResult(verdict="CONFIRMED")
		assert cr.verdict == "CONFIRMED"
		assert cr.reasoning == ""
		assert cr.evidence_gaps == []
		assert cr.verification_reproduced is None
		assert cr.verification_result is None
		assert cr.contradicting_evidence == []

	def test_full_construction(self):
		"""ChallengeResult can be constructed with all fields."""
		cr = ChallengeResult(
			verdict="REFUTED",
			reasoning="Secret was rotated 2 days ago",
			evidence_gaps=["no rotation check", "accepted alert validity"],
			verification_reproduced=True,
			verification_result="401 Unauthorized",
			contradicting_evidence=["API returned expired error"],
		)
		assert cr.verdict == "REFUTED"
		assert cr.reasoning == "Secret was rotated 2 days ago"
		assert len(cr.evidence_gaps) == 2
		assert cr.verification_reproduced is True
		assert cr.verification_result == "401 Unauthorized"
		assert len(cr.contradicting_evidence) == 1

	def test_all_valid_verdicts(self):
		"""All valid verdict values are accepted."""
		for verdict in VALID_CHALLENGE_VERDICTS:
			cr = ChallengeResult(verdict=verdict)
			assert cr.verdict == verdict

	def test_verdict_normalization_lowercase(self):
		"""Lowercase verdicts are normalized to uppercase."""
		cr = ChallengeResult(verdict="confirmed")
		assert cr.verdict == "CONFIRMED"

	def test_verdict_normalization_mixed_case(self):
		"""Mixed case verdicts are normalized to uppercase."""
		cr = ChallengeResult(verdict="InSuFfIcIeNt_EvIdEnCe")
		assert cr.verdict == "INSUFFICIENT_EVIDENCE"

	def test_verdict_normalization_whitespace(self):
		"""Whitespace around verdict is trimmed."""
		cr = ChallengeResult(verdict="  REFUTED  ")
		assert cr.verdict == "REFUTED"

	def test_invalid_verdict_raises(self):
		"""Invalid verdict values raise ValidationError."""
		with pytest.raises(ValidationError) as exc_info:
			ChallengeResult(verdict="INVALID")
		assert "verdict must be one of" in str(exc_info.value)

	def test_invalid_verdict_typo(self):
		"""Common typos in verdict raise ValidationError."""
		with pytest.raises(ValidationError):
			ChallengeResult(verdict="CONFIRM")  # missing 'ED'

	def test_verdict_empty_string_raises(self):
		"""Empty string verdict raises ValidationError."""
		with pytest.raises(ValidationError):
			ChallengeResult(verdict="")

	def test_serialization_roundtrip(self):
		"""ChallengeResult can be serialized and deserialized."""
		original = ChallengeResult(
			verdict="REFUTED",
			reasoning="Test reasoning",
			evidence_gaps=["gap1", "gap2"],
			verification_reproduced=False,
			verification_result="connection refused",
			contradicting_evidence=["evidence1"],
		)
		json_data = original.model_dump()
		restored = ChallengeResult(**json_data)
		assert restored.verdict == original.verdict
		assert restored.reasoning == original.reasoning
		assert restored.evidence_gaps == original.evidence_gaps
		assert restored.verification_reproduced == original.verification_reproduced
		assert restored.verification_result == original.verification_result
		assert restored.contradicting_evidence == original.contradicting_evidence


class TestValidChallengeVerdicts:
	"""Tests for VALID_CHALLENGE_VERDICTS constant."""

	def test_is_frozenset(self):
		"""VALID_CHALLENGE_VERDICTS is a frozenset (immutable)."""
		assert isinstance(VALID_CHALLENGE_VERDICTS, frozenset)

	def test_contains_expected_values(self):
		"""VALID_CHALLENGE_VERDICTS contains expected values."""
		expected = {"CONFIRMED", "REFUTED", "INSUFFICIENT_EVIDENCE"}
		assert VALID_CHALLENGE_VERDICTS == expected


class TestAgentRunResultWithChallenge:
	"""Tests for AgentRunResult with challenge_result field."""

	def test_default_challenge_result_is_none(self):
		"""challenge_result defaults to None."""
		result = AgentRunResult(run_id="0", progress_log=[])
		assert result.challenge_result is None

	def test_with_challenge_result(self):
		"""AgentRunResult can store challenge_result."""
		cr = ChallengeResult(
			verdict="CONFIRMED",
			reasoning="Evidence verified",
		)
		result = AgentRunResult(
			run_id="0",
			progress_log=[],
			challenge_result=cr,
		)
		assert result.challenge_result is not None
		assert result.challenge_result.verdict == "CONFIRMED"

	def test_model_copy_with_challenge_update(self):
		"""model_copy can update challenge_result."""
		result = AgentRunResult(run_id="0", progress_log=[])
		assert result.challenge_result is None

		cr = ChallengeResult(verdict="REFUTED", reasoning="Test")
		updated = result.model_copy(update={"challenge_result": cr})
		assert updated.challenge_result is not None
		assert updated.challenge_result.verdict == "REFUTED"
		# Original unchanged
		assert result.challenge_result is None


class TestRunOutcomeWithChallenge:
	"""Tests for RunOutcome with challenge_results field."""

	def test_default_challenge_results_is_empty(self):
		"""challenge_results defaults to empty list."""
		outcome = RunOutcome(
			judge_result=JudgeResult(
				winner_index=0,
				scores=[JudgeScore(report_index=0, score=8)],
			),
			analysis_results=[AgentRunResult(run_id="0", progress_log=[])],
		)
		assert outcome.challenge_results == []

	def test_with_challenge_results(self):
		"""RunOutcome can store challenge_results."""
		cr0 = ChallengeResult(verdict="CONFIRMED")
		cr1 = ChallengeResult(verdict="REFUTED")
		outcome = RunOutcome(
			judge_result=JudgeResult(
				winner_index=0,
				scores=[
					JudgeScore(report_index=0, score=8),
					JudgeScore(report_index=1, score=6),
				],
			),
			analysis_results=[
				AgentRunResult(run_id="0", progress_log=[]),
				AgentRunResult(run_id="1", progress_log=[]),
			],
			challenge_results=[cr0, cr1],
		)
		assert len(outcome.challenge_results) == 2
		assert outcome.challenge_results[0].verdict == "CONFIRMED"
		assert outcome.challenge_results[1].verdict == "REFUTED"


class TestChallengerConfig:
	"""Tests for challenger-related config fields."""

	def test_challenger_agent_file_default(self):
		"""challenger_agent_file has expected default."""
		config = Config()
		assert config.challenger_agent_file == "agents/challenger.agent.md"

	def test_challenger_agent_file_custom(self):
		"""challenger_agent_file can be customized."""
		config = Config(CHALLENGER_AGENT_FILE="custom/agent.md")
		assert config.challenger_agent_file == "custom/agent.md"

	def test_challenger_timeout_seconds_default(self):
		"""challenger_timeout_seconds defaults to 300."""
		config = Config()
		assert config.challenger_timeout_seconds == 300

	def test_challenger_timeout_seconds_custom(self):
		"""challenger_timeout_seconds can be customized."""
		config = Config(CHALLENGER_TIMEOUT_SECONDS=600)
		assert config.challenger_timeout_seconds == 600

	def test_challenger_timeout_seconds_positive_validation(self):
		"""challenger_timeout_seconds must be positive."""
		with pytest.raises(ValidationError) as exc_info:
			Config(CHALLENGER_TIMEOUT_SECONDS=0)
		assert "challenger_timeout_seconds must be > 0" in str(exc_info.value)

	def test_challenger_timeout_seconds_negative_validation(self):
		"""challenger_timeout_seconds must be positive (negative)."""
		with pytest.raises(ValidationError):
			Config(CHALLENGER_TIMEOUT_SECONDS=-100)

	def test_challenger_skill_directories_default_empty(self):
		"""challenger_skill_directories defaults to empty list."""
		config = Config()
		assert config.challenger_skill_directories == []

	def test_challenger_skill_directories_comma_string(self):
		"""challenger_skill_directories parses comma-separated string."""
		# Use paths that don't exist to test parsing (filtered later)
		config = Config(
			CHALLENGER_SKILL_DIRECTORIES="/nonexistent/a,/nonexistent/b"
		)
		# After filter_existing, both are removed
		assert config.challenger_skill_directories == []

	def test_challenger_skill_directories_list(self, tmp_path):
		"""challenger_skill_directories accepts list."""
		d1 = tmp_path / "skill1"
		d1.mkdir()
		d2 = tmp_path / "skill2"
		d2.mkdir()
		config = Config(
			CHALLENGER_SKILL_DIRECTORIES=[str(d1), str(d2)]
		)
		assert len(config.challenger_skill_directories) == 2
		assert str(d1) in config.challenger_skill_directories
		assert str(d2) in config.challenger_skill_directories

	def test_challenger_skill_directories_filters_nonexistent(self, tmp_path):
		"""challenger_skill_directories filters nonexistent directories."""
		d1 = tmp_path / "exists"
		d1.mkdir()
		config = Config(
			CHALLENGER_SKILL_DIRECTORIES=[str(d1), "/nonexistent/path"]
		)
		assert config.challenger_skill_directories == [str(d1)]


class TestChallengeResultEdgeCases:
	"""Edge case tests for ChallengeResult."""

	def test_empty_lists(self):
		"""Empty lists are valid for list fields."""
		cr = ChallengeResult(
			verdict="CONFIRMED",
			evidence_gaps=[],
			contradicting_evidence=[],
		)
		assert cr.evidence_gaps == []
		assert cr.contradicting_evidence == []

	def test_none_verification_fields(self):
		"""None is valid for optional verification fields."""
		cr = ChallengeResult(
			verdict="INSUFFICIENT_EVIDENCE",
			verification_reproduced=None,
			verification_result=None,
		)
		assert cr.verification_reproduced is None
		assert cr.verification_result is None

	def test_long_reasoning(self):
		"""Long reasoning strings are accepted."""
		long_reasoning = "A" * 10000
		cr = ChallengeResult(
			verdict="REFUTED",
			reasoning=long_reasoning,
		)
		assert len(cr.reasoning) == 10000

	def test_special_chars_in_evidence(self):
		"""Special characters in evidence are preserved."""
		evidence = ["path/to/file.py:42", "```code```", "émoji 🔐"]
		cr = ChallengeResult(
			verdict="REFUTED",
			contradicting_evidence=evidence,
		)
		assert cr.contradicting_evidence == evidence


class TestChallengerAgentLoading:
	"""Tests for loading the challenger agent definition."""

	def test_agent_file_exists(self):
		"""Challenger agent file exists."""
		from pathlib import Path
		agent_path = (
			Path(__file__).parent.parent /
			"src/secret_validator_grunt/agents/challenger.agent.md"
		)
		assert agent_path.exists()

	def test_agent_loads_correctly(self):
		"""Challenger agent can be loaded and parsed."""
		from secret_validator_grunt.loaders.agents import load_agent
		agent = load_agent("agents/challenger.agent.md")
		assert agent.name == "secret-validator-challenger"
		assert agent.model  # model is set

	def test_agent_has_expected_tools(self):
		"""Challenger agent has expected tools."""
		from secret_validator_grunt.loaders.agents import load_agent
		agent = load_agent("agents/challenger.agent.md")
		expected_tools = [
			"view", "read", "grep", "bash",
			"gh_secret_scanning_alert",
			"validate_secret",
			"skill",
		]
		for tool in expected_tools:
			assert tool in agent.tools, f"Missing tool: {tool}"

	def test_agent_no_write_tools(self):
		"""Challenger agent should not have write tools."""
		from secret_validator_grunt.loaders.agents import load_agent
		agent = load_agent("agents/challenger.agent.md")
		forbidden_tools = ["edit", "write_bash"]
		for tool in forbidden_tools:
			assert tool not in agent.tools, f"Should not have: {tool}"


class TestChallengePromptLoading:
	"""Tests for loading the challenge prompt template."""

	def test_prompt_file_exists(self):
		"""Challenge prompt file exists."""
		from pathlib import Path
		prompt_path = (
			Path(__file__).parent.parent /
			"src/secret_validator_grunt/prompts/challenge_task.md"
		)
		assert prompt_path.exists()

	def test_prompt_loads_correctly(self):
		"""Challenge prompt can be loaded."""
		from secret_validator_grunt.loaders.prompts import load_prompt
		prompt = load_prompt("challenge_task.md")
		assert prompt is not None
		assert len(prompt) > 100

	def test_prompt_has_placeholders(self):
		"""Challenge prompt has required placeholders."""
		from secret_validator_grunt.loaders.prompts import load_prompt
		prompt = load_prompt("challenge_task.md")
		assert "{{report_markdown}}" in prompt
		assert "{{workspace_path}}" in prompt

	def test_prompt_has_json_format(self):
		"""Challenge prompt specifies JSON output format."""
		from secret_validator_grunt.loaders.prompts import load_prompt
		prompt = load_prompt("challenge_task.md")
		assert "```json" in prompt
		assert '"verdict"' in prompt


class TestChallengerSkills:
	"""Tests for challenger skills."""

	def test_challenger_skills_directory_exists(self):
		"""Challenger skills directory exists."""
		from pathlib import Path
		skills_dir = (
			Path(__file__).parent.parent /
			"src/secret_validator_grunt/skills/challenger"
		)
		assert skills_dir.exists()
		assert skills_dir.is_dir()

	def test_secret_verification_methodology_exists(self):
		"""secret-verification-methodology skill exists."""
		from pathlib import Path
		skill_path = (
			Path(__file__).parent.parent /
			"src/secret_validator_grunt/skills/challenger/"
			"secret-verification-methodology/SKILL.md"
		)
		assert skill_path.exists()

	def test_rotation_revocation_skill_exists(self):
		"""rotation-and-revocation-analysis skill exists."""
		from pathlib import Path
		skill_path = (
			Path(__file__).parent.parent /
			"src/secret_validator_grunt/skills/challenger/"
			"rotation-and-revocation-analysis/SKILL.md"
		)
		assert skill_path.exists()

	def test_false_indicator_skill_exists(self):
		"""false-indicator-recognition skill exists."""
		from pathlib import Path
		skill_path = (
			Path(__file__).parent.parent /
			"src/secret_validator_grunt/skills/challenger/"
			"false-indicator-recognition/SKILL.md"
		)
		assert skill_path.exists()

	def test_skill_has_frontmatter(self):
		"""Challenger skills have proper YAML frontmatter."""
		from pathlib import Path
		from secret_validator_grunt.loaders.frontmatter import split_frontmatter
		skill_path = (
			Path(__file__).parent.parent /
			"src/secret_validator_grunt/skills/challenger/"
			"secret-verification-methodology/SKILL.md"
		)
		content = skill_path.read_text()
		frontmatter, _ = split_frontmatter(content)
		assert frontmatter is not None
		assert frontmatter.get("name") == "secret-verification-methodology"
		assert frontmatter.get("agent") == "challenger"
		assert frontmatter.get("required") is True


# =============================================================================
# Phase 3 Tests: Challenge Runner Functions
# =============================================================================


class TestBuildChallengePrompt:
	"""Tests for build_challenge_prompt function."""

	def test_both_placeholders_substituted(self):
		"""Both report and workspace placeholders are replaced."""
		from secret_validator_grunt.core.challenge import build_challenge_prompt
		from secret_validator_grunt.models.run_params import RunParams

		template = "Report:\n{{report_markdown}}\n\nWorkspace:\n{{workspace_path}}"
		rp = RunParams(org_repo="org/repo", alert_id="123")
		result = build_challenge_prompt(
			report_markdown="# My Report",
			workspace_path="/tmp/ws",
			prompt_template=template,
			run_params=rp,
		)
		assert "{{report_markdown}}" not in result
		assert "{{workspace_path}}" not in result
		assert "# My Report" in result
		assert "/tmp/ws" in result

	def test_none_workspace_handled(self):
		"""None workspace produces fallback text."""
		from secret_validator_grunt.core.challenge import build_challenge_prompt
		from secret_validator_grunt.models.run_params import RunParams

		template = "Workspace: {{workspace_path}}"
		rp = RunParams(org_repo="org/repo", alert_id="123")
		result = build_challenge_prompt(
			report_markdown="report",
			workspace_path=None,
			prompt_template=template,
			run_params=rp,
		)
		assert "(no workspace available)" in result

	def test_empty_report_handled(self):
		"""Empty report markdown is allowed."""
		from secret_validator_grunt.core.challenge import build_challenge_prompt
		from secret_validator_grunt.models.run_params import RunParams

		template = "Report: {{report_markdown}}"
		rp = RunParams(org_repo="org/repo", alert_id="123")
		result = build_challenge_prompt(
			report_markdown="",
			workspace_path="/ws",
			prompt_template=template,
			run_params=rp,
		)
		assert result == "Report: "


class TestParseChallengeResult:
	"""Tests for parse_challenge_result function."""

	def test_valid_json(self):
		"""Valid JSON is parsed correctly."""
		from secret_validator_grunt.core.challenge import parse_challenge_result

		raw = '{"verdict": "CONFIRMED", "reasoning": "Test passed"}'
		result = parse_challenge_result(raw)
		assert result.verdict == "CONFIRMED"
		assert result.reasoning == "Test passed"

	def test_fenced_json(self):
		"""JSON in fenced block is extracted."""
		from secret_validator_grunt.core.challenge import parse_challenge_result

		raw = """Here is my analysis:
```json
{"verdict": "REFUTED", "reasoning": "No evidence"}
```
Done."""
		result = parse_challenge_result(raw)
		assert result.verdict == "REFUTED"
		assert result.reasoning == "No evidence"

	def test_prose_plus_json(self):
		"""Prose before JSON is handled."""
		from secret_validator_grunt.core.challenge import parse_challenge_result

		raw = """I analyzed the report.
{"verdict": "REFUTED", "reasoning": "Key was rotated"}"""
		result = parse_challenge_result(raw)
		assert result.verdict == "REFUTED"
		assert result.reasoning == "Key was rotated"

	def test_empty_string(self):
		"""Empty string returns INSUFFICIENT_EVIDENCE."""
		from secret_validator_grunt.core.challenge import parse_challenge_result

		result = parse_challenge_result("")
		assert result.verdict == "INSUFFICIENT_EVIDENCE"
		assert "Failed to parse" in result.reasoning

	def test_garbage_input(self):
		"""Garbage returns INSUFFICIENT_EVIDENCE."""
		from secret_validator_grunt.core.challenge import parse_challenge_result

		result = parse_challenge_result("not json at all")
		assert result.verdict == "INSUFFICIENT_EVIDENCE"

	def test_invalid_verdict_normalized(self):
		"""Invalid verdict is normalized to INSUFFICIENT_EVIDENCE."""
		from secret_validator_grunt.core.challenge import parse_challenge_result

		raw = '{"verdict": "MAYBE", "reasoning": "unsure"}'
		result = parse_challenge_result(raw)
		assert result.verdict == "INSUFFICIENT_EVIDENCE"

	def test_partial_fields(self):
		"""Missing optional fields get defaults."""
		from secret_validator_grunt.core.challenge import parse_challenge_result

		raw = '{"verdict": "CONFIRMED"}'
		result = parse_challenge_result(raw)
		assert result.verdict == "CONFIRMED"
		assert result.reasoning == ""
		assert result.evidence_gaps == []
		assert result.contradicting_evidence == []

	def test_all_fields_populated(self):
		"""All fields are populated from JSON."""
		from secret_validator_grunt.core.challenge import parse_challenge_result

		raw = '''{"verdict": "REFUTED",
			"reasoning": "Could not reproduce",
			"evidence_gaps": ["Missing API logs"],
			"verification_reproduced": false,
			"verification_result": "Connection refused",
			"contradicting_evidence": ["Revoked key found"]}'''
		result = parse_challenge_result(raw)
		assert result.verdict == "REFUTED"
		assert result.reasoning == "Could not reproduce"
		assert result.evidence_gaps == ["Missing API logs"]
		assert result.verification_reproduced is False
		assert result.verification_result == "Connection refused"
		assert result.contradicting_evidence == ["Revoked key found"]

	def test_lowercase_verdict_normalized(self):
		"""Lowercase verdict is uppercased."""
		from secret_validator_grunt.core.challenge import parse_challenge_result

		raw = '{"verdict": "confirmed"}'
		result = parse_challenge_result(raw)
		assert result.verdict == "CONFIRMED"


class TestChallengerSkillManifestAlignment:
	"""Tests that challenger skill manifest follows the same approach as analysis.

	The challenger must:
	- Build skill_manifest_context unconditionally (no ``if skills`` guard)
	- Pass skill_manifest to StreamCollector unconditionally
	- Discover and pass disabled_skills the same way analysis does
	- Honour the ``required`` flag on individual skills
	"""

	def test_required_flag_flows_through_manifest(self):
		"""Required flag from SKILL.md frontmatter appears in formatted context."""
		from secret_validator_grunt.core.skills import (
			discover_challenger_skill_directories,
			build_skill_manifest,
			format_manifest_for_context,
		)

		skill_dirs = discover_challenger_skill_directories()
		manifest = build_skill_manifest(skill_dirs)
		context = format_manifest_for_context(manifest)

		# Required skills show the REQUIRED marker
		assert "REQUIRED" in context

	def test_required_skills_marked_in_formatted_context(self):
		"""Each skill with required=True gets **⚠️ REQUIRED** in the formatted context."""
		from secret_validator_grunt.core.skills import (
			discover_challenger_skill_directories,
			build_skill_manifest,
			format_manifest_for_context,
		)

		skill_dirs = discover_challenger_skill_directories()
		manifest = build_skill_manifest(skill_dirs)
		context = format_manifest_for_context(manifest)

		# Count required skills in manifest
		required_skills = [s for s in manifest.skills if s.required]
		assert len(required_skills) >= 2  # verification + rotation

		# Each required skill's name appears with REQUIRED marker
		for skill in required_skills:
			assert skill.name in context

	def test_non_required_skill_omits_required_marker(self):
		"""Skills with required=False do NOT get the REQUIRED marker."""
		from secret_validator_grunt.core.skills import (
			discover_challenger_skill_directories,
			build_skill_manifest,
			format_manifest_for_context,
		)

		skill_dirs = discover_challenger_skill_directories()
		manifest = build_skill_manifest(skill_dirs)
		context = format_manifest_for_context(manifest)

		non_required = [s for s in manifest.skills if not s.required]
		assert len(non_required) >= 1  # false-indicator-recognition

		for skill in non_required:
			# Find the line for this skill
			for line in context.splitlines():
				if skill.name in line:
					assert "REQUIRED" not in line, (
						f"Non-required skill {skill.name!r} should not "
						f"have REQUIRED marker"
					)

	def test_manifest_context_unconditional(self):
		"""format_manifest_for_context always returns a string, even with empty manifest."""
		from secret_validator_grunt.core.skills import (
			build_skill_manifest,
			format_manifest_for_context,
		)

		# Empty manifest still produces a valid context string
		manifest = build_skill_manifest([])
		context = format_manifest_for_context(manifest)
		assert isinstance(context, str)
		assert "Available Skills" in context

	def test_disabled_skills_from_challenger_directory(self):
		"""discover_hidden_skills produces a list (possibly empty) for challenger dir."""
		from secret_validator_grunt.core.skills import (
			discover_hidden_skills,
			CHALLENGER_SKILLS_DIRECTORY,
		)

		hidden = discover_hidden_skills(CHALLENGER_SKILLS_DIRECTORY)
		assert isinstance(hidden, list)

	def test_challenger_imports_discover_hidden_skills(self):
		"""challenge.py imports discover_all_disabled_skills and CHALLENGER_SKILLS_DIRECTORY."""
		import inspect
		import secret_validator_grunt.core.challenge as mod

		source = inspect.getsource(mod)
		assert "discover_all_disabled_skills" in source
		assert "CHALLENGER_SKILLS_DIRECTORY" in source

	def test_challenger_passes_disabled_skills_to_session(self):
		"""Challenger session config includes disabled_skills kwarg."""
		import inspect
		import secret_validator_grunt.core.challenge as mod

		source = inspect.getsource(mod.run_single_challenge)
		# After refactor to build_session_config(), disabled_skills
		# is passed as a keyword argument rather than a dict key.
		assert "disabled_skills=" in source

	def test_challenger_passes_disabled_skills_to_collector(self):
		"""StreamCollector in challenger receives disabled_skills kwarg."""
		import inspect
		import secret_validator_grunt.core.challenge as mod

		source = inspect.getsource(mod.run_single_challenge)
		assert "disabled_skills=disabled_skills" in source

	def test_challenger_no_conditional_manifest_guard(self):
		"""Challenger does not use 'if skill_manifest.skills' guard on context."""
		import inspect
		import secret_validator_grunt.core.challenge as mod

		source = inspect.getsource(mod.run_single_challenge)
		# Should NOT have the conditional pattern
		assert "if skill_manifest.skills else None" not in source


class TestDiscoverChallengerSkillDirectories:
	"""Tests for discover_challenger_skill_directories function."""

	def test_default_directory_exists(self):
		"""Default challenger skills directory exists and is returned."""
		from secret_validator_grunt.core.skills import (
			discover_challenger_skill_directories,
			CHALLENGER_SKILLS_DIRECTORY,
		)
		assert CHALLENGER_SKILLS_DIRECTORY.exists()
		dirs = discover_challenger_skill_directories()
		assert len(dirs) >= 1
		assert str(CHALLENGER_SKILLS_DIRECTORY.resolve()) in dirs

	def test_additional_dirs_included(self, tmp_path):
		"""Additional directories are included."""
		from secret_validator_grunt.core.skills import discover_challenger_skill_directories

		extra = tmp_path / "extra-skills"
		extra.mkdir()
		dirs = discover_challenger_skill_directories([str(extra)])
		assert str(extra.resolve()) in dirs

	def test_nonexistent_dirs_filtered(self):
		"""Non-existent directories are filtered out."""
		from secret_validator_grunt.core.skills import discover_challenger_skill_directories

		dirs = discover_challenger_skill_directories(["/nonexistent/path/skills"])
		# Should only have default, not the nonexistent path
		assert "/nonexistent/path/skills" not in dirs

	def test_empty_additional_dirs(self):
		"""Empty additional dirs list is handled."""
		from secret_validator_grunt.core.skills import discover_challenger_skill_directories

		dirs = discover_challenger_skill_directories([])
		assert len(dirs) >= 1  # At least default

	def test_none_additional_dirs(self):
		"""None additional dirs is handled."""
		from secret_validator_grunt.core.skills import discover_challenger_skill_directories

		dirs = discover_challenger_skill_directories(None)
		assert len(dirs) >= 1


class TestChallengerSkillDirectoryConstant:
	"""Tests for CHALLENGER_SKILLS_DIRECTORY constant."""

	def test_points_to_correct_location(self):
		"""Constant points to skills/challenger directory."""
		from secret_validator_grunt.core.skills import CHALLENGER_SKILLS_DIRECTORY

		assert CHALLENGER_SKILLS_DIRECTORY.name == "challenger"
		assert CHALLENGER_SKILLS_DIRECTORY.parent.name == "skills"

	def test_contains_skill_files(self):
		"""Directory contains expected skill files."""
		from secret_validator_grunt.core.skills import CHALLENGER_SKILLS_DIRECTORY

		skill_dirs = list(CHALLENGER_SKILLS_DIRECTORY.iterdir())
		assert len(skill_dirs) >= 3
		names = [d.name for d in skill_dirs]
		assert "secret-verification-methodology" in names


# =============================================================================
# Phase 4 Tests: Runner + Judge Integration
# =============================================================================


class TestFormatReportsWithChallenge:
	"""Tests for _format_reports with challenge annotations."""

	def test_no_challenge_results_unchanged(self):
		"""Reports without challenge results format normally."""
		from secret_validator_grunt.core.judge import _format_reports
		from secret_validator_grunt.models.run_result import AgentRunResult

		results = [
			AgentRunResult(
				run_id="0",
				raw_markdown="# Report 0\nContent here",
				progress_log=[],
			),
			AgentRunResult(
				run_id="1",
				raw_markdown="# Report 1\nMore content",
				progress_log=[],
			),
		]
		output = _format_reports(results)
		assert "REPORT 0:" in output
		assert "REPORT 1:" in output
		assert "--- ADVERSARIAL CHALLENGE RESULT ---" not in output

	def test_with_challenge_results_annotated(self):
		"""Reports with challenge results include annotations."""
		from secret_validator_grunt.core.judge import _format_reports
		from secret_validator_grunt.models.run_result import AgentRunResult
		from secret_validator_grunt.models.challenge_result import ChallengeResult

		results = [
			AgentRunResult(
				run_id="0",
				raw_markdown="# Report 0",
				progress_log=[],
				challenge_result=ChallengeResult(
					verdict="CONFIRMED",
					reasoning="Verified via API call",
					evidence_gaps=[],
				),
			),
		]
		output = _format_reports(results)
		assert "--- ADVERSARIAL CHALLENGE RESULT ---" in output
		assert "Challenge Verdict: CONFIRMED" in output
		assert "Verified via API call" in output
		assert "--- END CHALLENGE ---" in output

	def test_with_challenge_evidence_gaps(self):
		"""Challenge annotations include evidence gaps when present."""
		from secret_validator_grunt.core.judge import _format_reports
		from secret_validator_grunt.models.run_result import AgentRunResult
		from secret_validator_grunt.models.challenge_result import ChallengeResult

		results = [
			AgentRunResult(
				run_id="0",
				raw_markdown="# Report 0",
				progress_log=[],
				challenge_result=ChallengeResult(
					verdict="REFUTED",
					reasoning="Missing evidence",
					evidence_gaps=["No API logs", "No rotation check"],
				),
			),
		]
		output = _format_reports(results)
		assert "Evidence Gaps: No API logs, No rotation check" in output

	def test_with_contradicting_evidence(self):
		"""Challenge annotations include contradicting evidence when present."""
		from secret_validator_grunt.core.judge import _format_reports
		from secret_validator_grunt.models.run_result import AgentRunResult
		from secret_validator_grunt.models.challenge_result import ChallengeResult

		results = [
			AgentRunResult(
				run_id="0",
				raw_markdown="# Report 0",
				progress_log=[],
				challenge_result=ChallengeResult(
					verdict="REFUTED",
					reasoning="Found revoked key",
					contradicting_evidence=["Key rotated 2023-01-01"],
				),
			),
		]
		output = _format_reports(results)
		assert "Contradicting Evidence: Key rotated 2023-01-01" in output

	def test_mixed_results(self):
		"""Mixed results with some challenged and some not."""
		from secret_validator_grunt.core.judge import _format_reports
		from secret_validator_grunt.models.run_result import AgentRunResult
		from secret_validator_grunt.models.challenge_result import ChallengeResult

		results = [
			AgentRunResult(
				run_id="0",
				raw_markdown="# Report 0",
				progress_log=[],
				challenge_result=ChallengeResult(
					verdict="CONFIRMED",
					reasoning="Verified",
				),
			),
			AgentRunResult(
				run_id="1",
				raw_markdown="# Report 1",
				progress_log=[],
				# No challenge_result
			),
		]
		output = _format_reports(results)
		# First report has challenge
		assert "REPORT 0:" in output
		assert "Challenge Verdict: CONFIRMED" in output
		# Second report does not
		assert "REPORT 1:" in output
		# Only one challenge block
		assert output.count("--- ADVERSARIAL CHALLENGE RESULT ---") == 1


class TestRunnerChallengeIntegration:
	"""Tests for runner challenge integration behavior."""

	def test_runner_imports_challenge(self):
		"""Runner imports run_challenges without error."""
		from secret_validator_grunt.core.runner import run_all
		from secret_validator_grunt.core.challenge import run_challenges

		# Just verify imports work
		assert run_all is not None
		assert run_challenges is not None


# =============================================================================
# Phase 5: TUI Integration Tests
# =============================================================================


class TestTUIRunDisplayStateChallenge:
	"""Tests for RunDisplayState challenge_verdict field."""

	def test_challenge_verdict_field_exists(self):
		"""RunDisplayState has challenge_verdict field."""
		from secret_validator_grunt.ui.tui import RunDisplayState

		state = RunDisplayState(run_id="0")
		assert hasattr(state, "challenge_verdict")
		assert state.challenge_verdict is None

	def test_challenge_verdict_can_be_set(self):
		"""challenge_verdict can be set to valid values."""
		from secret_validator_grunt.ui.tui import RunDisplayState

		for verdict in ["CONFIRMED", "REFUTED", "INSUFFICIENT_EVIDENCE"]:
			state = RunDisplayState(run_id="0", challenge_verdict=verdict)
			assert state.challenge_verdict == verdict

	def test_render_cell_without_challenge(self):
		"""render_cell works without challenge_verdict."""
		from secret_validator_grunt.ui.tui import RunDisplayState

		state = RunDisplayState(run_id="0", status="completed")
		cell = state.render_cell()
		# Should not contain challenge line
		assert "challenge:" not in cell.plain

	def test_render_cell_with_confirmed_verdict(self):
		"""render_cell shows CONFIRMED verdict in red."""
		from secret_validator_grunt.ui.tui import RunDisplayState

		state = RunDisplayState(
			run_id="0",
			status="completed",
			challenge_verdict="CONFIRMED"
		)
		cell = state.render_cell()
		assert "challenge: CONFIRMED" in cell.plain

	def test_render_cell_with_refuted_verdict(self):
		"""render_cell shows REFUTED verdict in green."""
		from secret_validator_grunt.ui.tui import RunDisplayState

		state = RunDisplayState(
			run_id="0",
			status="completed",
			challenge_verdict="REFUTED"
		)
		cell = state.render_cell()
		assert "challenge: REFUTED" in cell.plain

	def test_render_cell_with_insufficient_evidence(self):
		"""render_cell shows INSUFFICIENT_EVIDENCE verdict in yellow."""
		from secret_validator_grunt.ui.tui import RunDisplayState

		state = RunDisplayState(
			run_id="0",
			status="completed",
			challenge_verdict="INSUFFICIENT_EVIDENCE"
		)
		cell = state.render_cell()
		assert "challenge: INSUFFICIENT_EVIDENCE" in cell.plain


# =============================================================================
# Phase 6: Stream Log Path Tests
# =============================================================================


class TestChallengerStreamLogPath:
	"""Tests for challenger stream log being written to alert_dir."""

	def test_run_challenges_accepts_alert_dir(self):
		"""run_challenges signature accepts alert_dir parameter."""
		import inspect
		from secret_validator_grunt.core.challenge import run_challenges

		sig = inspect.signature(run_challenges)
		assert "alert_dir" in sig.parameters

	def test_run_single_challenge_accepts_alert_dir(self):
		"""run_single_challenge signature accepts alert_dir parameter."""
		import inspect
		from secret_validator_grunt.core.challenge import run_single_challenge

		sig = inspect.signature(run_single_challenge)
		assert "alert_dir" in sig.parameters

	def test_stream_log_path_uses_alert_dir(self, tmp_path):
		"""When alert_dir is provided, stream_log_path targets alert_dir."""
		from pathlib import Path
		from secret_validator_grunt.models.run_params import RunParams

		alert_dir = tmp_path / "org" / "repo" / "alert-1"
		alert_dir.mkdir(parents=True)

		rp = RunParams(org_repo="org/repo", alert_id="1")
		org_repo_slug = rp.org_repo.replace("/", "_")
		expected_name = f"challenge-0-{org_repo_slug}-{rp.alert_id}.stream.log"
		expected_path = alert_dir / expected_name

		# Verify the naming pattern
		assert expected_path.name == "challenge-0-org_repo-1.stream.log"
		assert expected_path.parent == alert_dir

	def test_stream_log_path_per_index(self, tmp_path):
		"""Each challenge index gets its own stream log file."""
		from secret_validator_grunt.models.run_params import RunParams

		alert_dir = tmp_path / "test"
		alert_dir.mkdir()

		rp = RunParams(org_repo="acme/app", alert_id="42")
		org_repo_slug = rp.org_repo.replace("/", "_")

		names = [
			f"challenge-{i}-{org_repo_slug}-{rp.alert_id}.stream.log"
			for i in range(3)
		]
		assert names == [
			"challenge-0-acme_app-42.stream.log",
			"challenge-1-acme_app-42.stream.log",
			"challenge-2-acme_app-42.stream.log",
		]


class TestBuildChallengePromptSkillManifest:
	"""Tests for skill manifest context in build_challenge_prompt."""

	def test_skill_manifest_appended(self):
		"""Skill manifest context is appended to the prompt."""
		from secret_validator_grunt.core.challenge import build_challenge_prompt
		from secret_validator_grunt.models.run_params import RunParams

		template = "Report: {{report_markdown}}\nWorkspace: {{workspace_path}}"
		rp = RunParams(org_repo="org/repo", alert_id="1")
		result = build_challenge_prompt(
			report_markdown="# Report",
			workspace_path="/ws",
			prompt_template=template,
			run_params=rp,
			skill_manifest_context="## Available Skills\n\n- skill_a\n- skill_b",
		)
		assert "## Available Skills" in result
		assert "skill_a" in result
		assert "skill_b" in result

	def test_none_skill_manifest_excluded(self):
		"""None skill_manifest_context doesn't add extra content."""
		from secret_validator_grunt.core.challenge import build_challenge_prompt
		from secret_validator_grunt.models.run_params import RunParams

		template = "Report: {{report_markdown}}"
		rp = RunParams(org_repo="org/repo", alert_id="1")
		result = build_challenge_prompt(
			report_markdown="# Report",
			workspace_path="/ws",
			prompt_template=template,
			run_params=rp,
			skill_manifest_context=None,
		)
		assert result == "Report: # Report"

	def test_skill_manifest_separated_by_double_newline(self):
		"""Skill manifest is joined with double newline separator."""
		from secret_validator_grunt.core.challenge import build_challenge_prompt
		from secret_validator_grunt.models.run_params import RunParams

		template = "Base prompt"
		rp = RunParams(org_repo="org/repo", alert_id="1")
		result = build_challenge_prompt(
			report_markdown="",
			workspace_path="/ws",
			prompt_template=template,
			run_params=rp,
			skill_manifest_context="Skills here",
		)
		assert "\n\n" in result
		assert "Base prompt\n\nSkills here" in result


class TestChallengerEvidenceFocus:
	"""Tests that challenger instructions focus on evidence integrity, not verdict re-adjudication."""

	def test_agent_step5_is_evidence_quality(self):
		"""Step 5 in challenger agent focuses on evidence quality, not confidence scoring."""
		from secret_validator_grunt.loaders.agents import load_agent
		agent = load_agent("agents/challenger.agent.md")
		content = agent.prompt
		assert "Assess Evidence Quality" in content
		assert "Assess Confidence" not in content

	def test_agent_no_verdict_readjudication(self):
		"""Challenger agent does not tell agent to re-adjudicate verdicts."""
		from secret_validator_grunt.loaders.agents import load_agent
		agent = load_agent("agents/challenger.agent.md")
		content = agent.prompt
		# Should NOT contain verdict-level criteria
		assert "TRUE_POSITIVE requires at least one successful" not in content
		# Should contain evidence-focused language
		assert "verify the EVIDENCE" in content

	def test_agent_refuted_is_evidence_based(self):
		"""REFUTED verdict criteria is about fabricated/contradicted evidence."""
		from secret_validator_grunt.loaders.agents import load_agent
		agent = load_agent("agents/challenger.agent.md")
		content = agent.prompt
		# Should NOT contain verdict-level REFUTED criteria
		assert "secret is rotated but report says TRUE_POSITIVE" not in content
		# Should contain evidence-integrity REFUTED criteria
		assert "fabricated" in content.lower()

	def test_prompt_step6_is_evidence_quality(self):
		"""Step 6 in challenge prompt focuses on evidence quality."""
		from secret_validator_grunt.loaders.prompts import load_prompt
		prompt = load_prompt("challenge_task.md")
		assert "evidence quality" in prompt.lower()
		# Should NOT contain verdict-level criteria
		assert "TRUE_POSITIVE requires at least one successful" not in prompt

	def test_prompt_evidence_integrity_language(self):
		"""Challenge prompt uses evidence integrity language, not verdict critique."""
		from secret_validator_grunt.loaders.prompts import load_prompt
		prompt = load_prompt("challenge_task.md")
		assert "evidence integrity" in prompt.lower()
		assert "not to re-adjudicate the verdict" in prompt.lower()
