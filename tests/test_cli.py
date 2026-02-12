import sys
from secret_validator_grunt.main import entrypoint


def _make_fake_run_impl():
	"""Return a (fake_run_impl, seen_dict) pair for monkeypatching."""
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

	return fake_run_impl, seen


def test_cli_entrypoint_defaults_to_run(monkeypatch):
	fake_run_impl, seen = _make_fake_run_impl()
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


def test_cli_entrypoint_strips_run_prefix(monkeypatch):
	"""'run org/repo 1' is equivalent to 'org/repo 1'."""
	fake_run_impl, seen = _make_fake_run_impl()
	monkeypatch.setattr("secret_validator_grunt.main.run_impl", fake_run_impl)
	entrypoint(["run", "myorg/myrepo", "42"], standalone_mode=False)
	assert seen["org_repo"] == "myorg/myrepo"
	assert seen["alert_id"] == "42"


def test_cli_entrypoint_help_does_not_crash(monkeypatch):
	"""--help should exit cleanly (SystemExit with code 0)."""
	import pytest

	with pytest.raises(SystemExit) as exc_info:
		entrypoint(["--help"], standalone_mode=True)
	assert exc_info.value.code == 0


def test_cli_entrypoint_explicit_run_with_options(monkeypatch):
	"""'run org/repo 1 --show-usage' routes correctly."""
	fake_run_impl, seen = _make_fake_run_impl()
	monkeypatch.setattr("secret_validator_grunt.main.run_impl", fake_run_impl)
	entrypoint(
	    ["run", "myorg/myrepo", "99", "--show-usage"],
	    standalone_mode=False,
	)
	assert seen["org_repo"] == "myorg/myrepo"
	assert seen["alert_id"] == "99"
	assert seen["show_usage"] is True
