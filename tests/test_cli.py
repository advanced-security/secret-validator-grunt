import sys
from secret_validator_grunt.main import entrypoint


def test_cli_entrypoint_defaults_to_run(monkeypatch):
	seen = {}

	def fake_run_impl(
	    org_repo,
	    alert_id,
	    analyses=None,
	    timeout=None,
	    judge_timeout=None,
	    stream_verbose=None,
	    show_usage=None,
	):
		seen["org_repo"] = org_repo
		seen["alert_id"] = alert_id
		seen["analyses"] = analyses
		seen["timeout"] = timeout
		seen["judge_timeout"] = judge_timeout
		seen["stream_verbose"] = stream_verbose
		seen["show_usage"] = show_usage

	monkeypatch.setattr("secret_validator_grunt.main.run_impl", fake_run_impl)
	entrypoint(
	    [
	        "myorg/myrepo",
	        "123",
	        "--analyses",
	        "2",
	        "--timeout",
	        "10",
	        "--judge-timeout",
	        "20",
	        "--stream-verbose",
	    ],
	    standalone_mode=False,
	)
	assert seen["org_repo"] == "myorg/myrepo"
	assert seen["alert_id"] == "123"
	assert seen["analyses"] == 2
	assert seen["timeout"] == 10
	assert seen["judge_timeout"] == 20
	assert seen["stream_verbose"] is True
	assert seen["show_usage"] is False
