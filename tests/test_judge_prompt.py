from secret_validator_grunt.utils.parsing import extract_json
from secret_validator_grunt.core.judge import (
	_format_skill_usage_summary,
	_format_eval_annotation,
	_format_challenge_annotation,
	_format_reports,
)
from secret_validator_grunt.models.run_result import AgentRunResult
from secret_validator_grunt.models.skill_usage import SkillUsageStats
from secret_validator_grunt.models.eval_result import (
	EvalCheck,
	EvalResult,
)

JUDGE_RESPONSE = """
Sure.
```json
{
  "winner_index": 0,
  "scores": [ { "report_index": 0, "score": 8.5, "rationale": "good" } ],
  "rationale": "Report 0 has best evidence",
  "verdict": "Report 0 is best"
}
```
"""


def test_extract_json_from_judge_response():
	got = extract_json(JUDGE_RESPONSE)
	assert got["winner_index"] == 0
	assert got["scores"][0]["score"] == 8.5


def test_extract_json_balanced_without_fence():
	text = "Assistant: sure {\"winner_index\":1,\"scores\":[]} trailing"
	got = extract_json(text)
	assert got["winner_index"] == 1
	assert got["scores"] == []


def test_format_skill_usage_summary_with_full_data():
	"""Skill usage summary should include compliance metrics."""
	skill_usage = SkillUsageStats(
	    available_skills=["a", "b", "c"],
	    required_skills=["a", "b"],
	    loaded_skills=["a", "c"],
	)
	result = AgentRunResult(
	    run_id="0",
	    raw_markdown="# Report\nContent",
	    progress_log=[],
	    skill_usage=skill_usage,
	)
	summary = _format_skill_usage_summary(result)

	assert "### Methodology Compliance" in summary
	assert "2/3" in summary  # Skills loaded
	assert "1/2" in summary  # Required loaded
	assert "50%" in summary  # Compliance score
	assert "Required Skills Loaded:** a" in summary
	assert "Required Skills Skipped:** b" in summary


def test_format_skill_usage_summary_no_data():
	"""Skill usage summary should be empty when no data available."""
	result = AgentRunResult(
	    run_id="0",
	    raw_markdown="# Report",
	    progress_log=[],
	    skill_usage=None,
	)
	summary = _format_skill_usage_summary(result)
	assert summary == ""


def test_format_reports_includes_skill_usage():
	"""_format_reports should include skill usage summary for each report."""
	results = [
	    AgentRunResult(
	        run_id="0",
	        raw_markdown="# Report 0",
	        progress_log=[],
	        skill_usage=SkillUsageStats(
	            available_skills=["a", "b"],
	            required_skills=["a"],
	            loaded_skills=["a"],
	        ),
	    ),
	    AgentRunResult(
	        run_id="1",
	        raw_markdown="# Report 1",
	        progress_log=[],
	        skill_usage=SkillUsageStats(
	            available_skills=["a", "b"],
	            required_skills=["a"],
	            loaded_skills=[],  # Didn't load required skill
	        ),
	    ),
	]
	blob = _format_reports(results)

	assert "REPORT 0:" in blob
	assert "REPORT 1:" in blob
	# Report 0 should show 100% compliance
	assert "100%" in blob
	# Report 1 should show 0% compliance
	assert "0%" in blob


def test_format_eval_annotation_no_data():
	"""Eval annotation is empty when no eval result present."""
	result = AgentRunResult(
		run_id="0",
		raw_markdown="# Report",
		progress_log=[],
		eval_result=None,
	)
	assert _format_eval_annotation(result) == ""


def test_format_eval_annotation_all_passed():
	"""Eval annotation shows passed status when all checks pass."""
	result = AgentRunResult(
		run_id="0",
		raw_markdown="# Report",
		progress_log=[],
		eval_result=EvalResult(
			report_id="0",
			checks=[
				EvalCheck(
					name="valid_verdict",
					passed=True,
					message="Verdict: TRUE_POSITIVE",
				),
				EvalCheck(
					name="metadata_complete",
					passed=True,
					message="All metadata fields populated",
				),
			],
		),
	)
	annotation = _format_eval_annotation(result)
	assert "--- EVAL CHECK RESULT ---" in annotation
	assert "Passed: True" in annotation
	assert "Score: 100%" in annotation
	assert "Failed checks:" not in annotation
	assert "--- END EVAL ---" in annotation


def test_format_eval_annotation_with_failures():
	"""Eval annotation lists failed checks with severity."""
	result = AgentRunResult(
		run_id="0",
		raw_markdown="# Report",
		progress_log=[],
		eval_result=EvalResult(
			report_id="0",
			checks=[
				EvalCheck(
					name="has_required_sections",
					passed=False,
					message="Missing sections: Locations",
					severity="error",
				),
				EvalCheck(
					name="has_code_evidence",
					passed=False,
					message="No file paths or code snippets",
					severity="warning",
				),
				EvalCheck(
					name="valid_verdict",
					passed=True,
					message="Verdict: TRUE_POSITIVE",
				),
			],
		),
	)
	annotation = _format_eval_annotation(result)
	assert "Passed: False" in annotation
	assert "Failed checks:" in annotation
	assert "[error] has_required_sections" in annotation
	assert "Missing sections: Locations" in annotation
	assert "[warning] has_code_evidence" in annotation


def test_format_reports_includes_eval_annotation():
	"""_format_reports includes eval annotation in judge blob."""
	results = [
		AgentRunResult(
			run_id="0",
			raw_markdown="# Report 0",
			progress_log=[],
			eval_result=EvalResult(
				report_id="0",
				checks=[
					EvalCheck(
						name="valid_verdict",
						passed=True,
						message="OK",
					),
				],
			),
		),
	]
	blob = _format_reports(results)
	assert "REPORT 0:" in blob
	assert "--- EVAL CHECK RESULT ---" in blob
	assert "--- END EVAL ---" in blob


def test_format_reports_no_eval_no_annotation():
	"""_format_reports omits eval block when no eval result."""
	results = [
		AgentRunResult(
			run_id="0",
			raw_markdown="# Report 0",
			progress_log=[],
			eval_result=None,
		),
	]
	blob = _format_reports(results)
	assert "REPORT 0:" in blob
	assert "--- EVAL CHECK RESULT ---" not in blob


def test_format_challenge_annotation_no_data():
	"""Empty string when no challenge result."""
	result = AgentRunResult(
		run_id="0",
		raw_markdown="# Report",
		progress_log=[],
		challenge_result=None,
	)
	assert _format_challenge_annotation(result) == ""


def test_format_challenge_annotation_confirmed():
	"""Challenge annotation shows verdict and reasoning."""
	from secret_validator_grunt.models.challenge_result import (
		ChallengeResult,
	)

	result = AgentRunResult(
		run_id="0",
		raw_markdown="# Report",
		progress_log=[],
		challenge_result=ChallengeResult(
			verdict="CONFIRMED",
			reasoning="Verified via API call",
		),
	)
	annotation = _format_challenge_annotation(result)
	assert "--- ADVERSARIAL CHALLENGE RESULT ---" in annotation
	assert "Challenge Verdict: CONFIRMED" in annotation
	assert "Verified via API call" in annotation
	assert "--- END CHALLENGE ---" in annotation
	assert "Evidence Gaps:" not in annotation
	assert "Contradicting Evidence:" not in annotation


def test_format_challenge_annotation_with_gaps():
	"""Challenge annotation includes evidence gaps."""
	from secret_validator_grunt.models.challenge_result import (
		ChallengeResult,
	)

	result = AgentRunResult(
		run_id="0",
		raw_markdown="# Report",
		progress_log=[],
		challenge_result=ChallengeResult(
			verdict="REFUTED",
			reasoning="Missing evidence",
			evidence_gaps=["No API logs", "No rotation"],
		),
	)
	annotation = _format_challenge_annotation(result)
	assert "Evidence Gaps: No API logs, No rotation" in annotation


def test_format_challenge_annotation_with_contradictions():
	"""Challenge annotation includes contradicting evidence."""
	from secret_validator_grunt.models.challenge_result import (
		ChallengeResult,
	)

	result = AgentRunResult(
		run_id="0",
		raw_markdown="# Report",
		progress_log=[],
		challenge_result=ChallengeResult(
			verdict="REFUTED",
			reasoning="Found revoked key",
			contradicting_evidence=["Key rotated 2023-01-01"],
		),
	)
	annotation = _format_challenge_annotation(result)
	assert "Contradicting Evidence: Key rotated 2023-01-01" in annotation


def test_format_reports_eval_and_challenge_together():
	"""Both eval and challenge blocks appear in report blob."""
	from secret_validator_grunt.models.challenge_result import (
		ChallengeResult,
	)

	results = [
		AgentRunResult(
			run_id="0",
			raw_markdown="# Report 0",
			progress_log=[],
			eval_result=EvalResult(
				report_id="0",
				checks=[
					EvalCheck(
						name="valid_verdict",
						passed=True,
						message="OK",
					),
				],
			),
			challenge_result=ChallengeResult(
				verdict="CONFIRMED",
				reasoning="Verified",
			),
		),
	]
	blob = _format_reports(results)
	assert "--- EVAL CHECK RESULT ---" in blob
	assert "--- ADVERSARIAL CHALLENGE RESULT ---" in blob
	# Eval appears before challenge
	eval_pos = blob.index("--- EVAL CHECK RESULT ---")
	challenge_pos = blob.index(
		"--- ADVERSARIAL CHALLENGE RESULT ---"
	)
	assert eval_pos < challenge_pos
