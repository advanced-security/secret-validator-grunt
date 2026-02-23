"""Tests for build_analysis_prompt function."""


class TestBuildAnalysisPrompt:
	"""Tests for build_analysis_prompt template variable substitution."""

	def test_all_placeholders_substituted(self):
		"""All template placeholders are replaced with values."""
		from secret_validator_grunt.core.analysis import build_analysis_prompt

		template = (
			"Workspace: {{workspace_path}}\n"
			"Repository: {{org_repo}}\n"
			"Alert: {{alert_id}}"
		)
		result = build_analysis_prompt(
			prompt_template=template,
			workspace_path="/tmp/workspace",
			org_repo="owner/repo",
			alert_id="12345",
		)
		assert "{{workspace_path}}" not in result
		assert "{{org_repo}}" not in result
		assert "{{alert_id}}" not in result
		assert "/tmp/workspace" in result
		assert "owner/repo" in result
		assert "12345" in result

	def test_workspace_path_multiple_occurrences(self):
		"""Workspace path is substituted in all occurrences."""
		from secret_validator_grunt.core.analysis import build_analysis_prompt

		template = (
			"Main: {{workspace_path}}\n"
			"Scripts: {{workspace_path}}/scripts/\n"
			"Logs: {{workspace_path}}/logs/"
		)
		result = build_analysis_prompt(
			prompt_template=template,
			workspace_path="/analysis/run-123",
			org_repo="org/repo",
			alert_id="1",
		)
		assert result.count("/analysis/run-123") == 3
		assert "{{workspace_path}}" not in result

	def test_report_template_appended(self):
		"""Report template is appended with markdown fence."""
		from secret_validator_grunt.core.analysis import build_analysis_prompt

		result = build_analysis_prompt(
			prompt_template="Base prompt: {{org_repo}}",
			workspace_path="/ws",
			org_repo="org/repo",
			alert_id="1",
			report_template="# Report Template\n\n## Section",
		)
		assert "Report template you must use:" in result
		assert "```markdown" in result
		assert "# Report Template" in result
		assert "## Section" in result

	def test_skill_manifest_appended(self):
		"""Skill manifest context is appended when provided."""
		from secret_validator_grunt.core.analysis import build_analysis_prompt

		result = build_analysis_prompt(
			prompt_template="Base: {{workspace_path}}",
			workspace_path="/ws",
			org_repo="org/repo",
			alert_id="1",
			skill_manifest_context="## Available Skills\n\n- skill_one\n- skill_two",
		)
		assert "## Available Skills" in result
		assert "skill_one" in result

	def test_no_optional_parts(self):
		"""Prompt works without report template or skill manifest."""
		from secret_validator_grunt.core.analysis import build_analysis_prompt

		result = build_analysis_prompt(
			prompt_template="Analyze {{org_repo}} alert {{alert_id}}",
			workspace_path="/ws",
			org_repo="acme/app",
			alert_id="42",
		)
		assert result == "Analyze acme/app alert 42"

	def test_all_parts_combined(self):
		"""All parts are combined with double newline separators."""
		from secret_validator_grunt.core.analysis import build_analysis_prompt

		result = build_analysis_prompt(
			prompt_template="Prompt",
			workspace_path="/ws",
			org_repo="o/r",
			alert_id="1",
			skill_manifest_context="Skills",
			report_template="Template",
		)
		# Parts should be separated by \n\n
		assert "Prompt\n\n" in result
		assert "\n\nSkills\n\n" in result
		assert "```markdown\nTemplate\n```" in result


class TestBuildAnalysisPromptPreCloned:
	"""Tests for repo_pre_cloned parameter in build_analysis_prompt."""

	def test_pre_cloned_notice_appended(self):
		"""Pre-cloned notice is appended when repo_pre_cloned is True."""
		from secret_validator_grunt.core.analysis import build_analysis_prompt

		result = build_analysis_prompt(
			prompt_template="Base: {{workspace_path}}",
			workspace_path="/ws",
			org_repo="org/repo",
			alert_id="1",
			repo_pre_cloned=True,
		)
		assert "Pre-cloned Repository" in result
		assert "/ws/repo/" in result
		assert "Do NOT clone" in result

	def test_no_notice_when_not_pre_cloned(self):
		"""No pre-clone notice when repo_pre_cloned is False."""
		from secret_validator_grunt.core.analysis import build_analysis_prompt

		result = build_analysis_prompt(
			prompt_template="Base: {{workspace_path}}",
			workspace_path="/ws",
			org_repo="org/repo",
			alert_id="1",
			repo_pre_cloned=False,
		)
		assert "Pre-cloned Repository" not in result
		assert "Do NOT clone" not in result

	def test_default_is_not_pre_cloned(self):
		"""Default value of repo_pre_cloned is False."""
		from secret_validator_grunt.core.analysis import build_analysis_prompt

		result = build_analysis_prompt(
			prompt_template="Base: {{workspace_path}}",
			workspace_path="/ws",
			org_repo="org/repo",
			alert_id="1",
		)
		assert "Pre-cloned Repository" not in result

	def test_pre_cloned_with_all_parts(self):
		"""Pre-clone notice is included alongside skills and template."""
		from secret_validator_grunt.core.analysis import build_analysis_prompt

		result = build_analysis_prompt(
			prompt_template="Prompt",
			workspace_path="/ws",
			org_repo="o/r",
			alert_id="1",
			skill_manifest_context="Skills",
			report_template="Template",
			repo_pre_cloned=True,
		)
		assert "Pre-cloned Repository" in result
		assert "Skills" in result
		assert "Template" in result


class TestScriptExecutionInstructions:
	"""Tests that analysis instructions require actual script execution, not hand-written results."""

	def test_testing_skill_requires_bash_execution(self):
		"""Testing environment skill requires executing scripts via bash."""
		from pathlib import Path
		skill_path = (
			Path(__file__).parent.parent /
			"src/secret_validator_grunt/skills/analysis/1-initialization"
			"/testing-environment/SKILL.md"
		)
		content = skill_path.read_text()
		assert "MUST be executed via `bash`" in content

	def test_testing_skill_forbids_handwritten_results(self):
		"""Testing environment skill forbids writing results files by hand."""
		from pathlib import Path
		skill_path = (
			Path(__file__).parent.parent /
			"src/secret_validator_grunt/skills/analysis/1-initialization"
			"/testing-environment/SKILL.md"
		)
		content = skill_path.read_text()
		assert "FORBIDDEN" in content
		assert "Writing `test_results.json` or any results file by hand" in content

	def test_testing_skill_no_save_test_result_function(self):
		"""Testing environment skill no longer provides save_test_result() template."""
		from pathlib import Path
		skill_path = (
			Path(__file__).parent.parent /
			"src/secret_validator_grunt/skills/analysis/1-initialization"
			"/testing-environment/SKILL.md"
		)
		content = skill_path.read_text()
		assert "save_test_result" not in content

	def test_testing_skill_shows_tee_pattern(self):
		"""Testing environment skill shows stdout capture via tee."""
		from pathlib import Path
		skill_path = (
			Path(__file__).parent.parent /
			"src/secret_validator_grunt/skills/analysis/1-initialization"
			"/testing-environment/SKILL.md"
		)
		content = skill_path.read_text()
		assert "2>&1 | tee" in content

	def test_agent_step7_requires_execution(self):
		"""Agent methodology step 7 requires executing scripts and capturing output."""
		from secret_validator_grunt.loaders.agents import load_agent
		agent = load_agent("agents/secret_validator.agent.md")
		content = agent.prompt
		assert "MUST execute the script via `bash`" in content
		assert "NEVER write results files by hand" in content

	def test_prompt_logs_instruction_forbids_handwriting(self):
		"""Analysis prompt Logs instruction forbids hand-written results."""
		from secret_validator_grunt.loaders.prompts import load_prompt
		prompt = load_prompt("analysis_task.md")
		assert "NEVER write results files by hand" in prompt
