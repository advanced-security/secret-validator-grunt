from secret_validator_grunt.ui.reporting import render_report_md
from secret_validator_grunt.models.report import Report


def test_render_report_md():
	md = render_report_md(
	    Report(
	        alert_id="1",
	        repository="org/repo",
	        confidence_score=9,
	        confidence_label="High",
	    ))
	assert "Secret Validation Report" in md
	assert "org/repo" in md
