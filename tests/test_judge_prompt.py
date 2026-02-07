from secret_validator_grunt.utils.parsing import extract_json
from secret_validator_grunt.core.judge import _format_skill_usage_summary, _format_reports
from secret_validator_grunt.models.run_result import AgentRunResult
from secret_validator_grunt.models.skill_usage import SkillUsageStats

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
