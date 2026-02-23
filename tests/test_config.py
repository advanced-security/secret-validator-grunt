import pytest

from secret_validator_grunt.models.config import Config


def test_analysis_skill_directories_parsing(tmp_path):
	dirs = [tmp_path / n for n in ("a", "b", "c")]
	for d in dirs:
		d.mkdir()
	cfg = Config(ANALYSIS_SKILL_DIRECTORIES=",".join(str(d) for d in dirs))
	assert cfg.analysis_skill_directories == [str(d) for d in dirs]


def test_timeouts_defaults():
	cfg = Config()
	assert cfg.analysis_timeout_seconds == 1800
	assert cfg.judge_timeout_seconds == 300


def test_disabled_skills_parsing():
	cfg = Config(DISABLED_SKILLS="a,b , c ")
	assert cfg.disabled_skills == ["a", "b", "c"]


def test_cli_url_passthrough():
	cfg = Config(COPILOT_CLI_URL="localhost:5554")
	assert cfg.cli_url == "localhost:5554"


def test_cli_url_port_only_passthrough():
	cfg = Config(COPILOT_CLI_URL="5554")
	assert cfg.cli_url == "5554"


def test_cli_url_any_scheme_allowed():
	cfg = Config(COPILOT_CLI_URL="ftp://x")
	assert cfg.cli_url == "ftp://x"


def test_cli_url_https_host_port():
	cfg = Config(COPILOT_CLI_URL="https://127.0.0.1:5554")
	assert cfg.cli_url == "https://127.0.0.1:5554"


def test_max_parallel_sessions():
	cfg = Config(MAX_PARALLEL_SESSIONS=2)
	assert cfg.max_parallel_sessions == 2


def test_native_mode_no_cli_url():
	"""Config works without cli_url (native stdio mode)."""
	cfg = Config()
	assert cfg.cli_url is None
	assert cfg.use_native_cli is True


def test_external_mode_with_cli_url():
	"""Config with cli_url set uses external server mode."""
	cfg = Config(COPILOT_CLI_URL="localhost:8080")
	assert cfg.cli_url == "localhost:8080"
	assert cfg.use_native_cli is False


def test_native_mode_with_github_token():
	"""Native mode works with github_token for auth."""
	cfg = Config(GITHUB_TOKEN="ghp_test123")
	assert cfg.use_native_cli is True
	assert cfg.github_token == "ghp_test123"


def test_validate_secret_timeout_default():
	"""Default validate_secret_timeout_seconds is 30."""
	cfg = Config()
	assert cfg.validate_secret_timeout_seconds == 30


def test_validate_secret_timeout_custom():
	"""validate_secret_timeout_seconds can be overridden."""
	cfg = Config(VALIDATE_SECRET_TIMEOUT_SECONDS=60)
	assert cfg.validate_secret_timeout_seconds == 60


def test_validate_secret_timeout_rejects_zero():
	"""validate_secret_timeout_seconds must be > 0."""
	with pytest.raises(ValueError):
		Config(VALIDATE_SECRET_TIMEOUT_SECONDS=0)


# ── apply_overrides ──────────────────────────────────────────────────


def test_apply_overrides_all_fields():
	"""apply_overrides sets every overridable field from RunParams."""
	from secret_validator_grunt.models.run_params import RunParams

	cfg = Config()
	rp = RunParams(
	    org_repo="o/r",
	    alert_id="1",
	    analyses=7,
	    timeout=999,
	    judge_timeout=42,
	    stream_verbose=True,
	    show_usage=True,
	)
	cfg.apply_overrides(rp)
	assert cfg.analysis_count == 7
	assert cfg.analysis_timeout_seconds == 999
	assert cfg.judge_timeout_seconds == 42
	assert cfg.stream_verbose is True
	assert cfg.show_usage is True


def test_apply_overrides_none_preserves_defaults():
	"""apply_overrides skips None fields, keeping env/default values."""
	from secret_validator_grunt.models.run_params import RunParams

	cfg = Config(ANALYSIS_COUNT=5)
	rp = RunParams(org_repo="o/r", alert_id="1")  # all overrides None
	cfg.apply_overrides(rp)
	assert cfg.analysis_count == 5  # unchanged
	assert cfg.analysis_timeout_seconds == 1800  # default preserved


def test_apply_overrides_partial():
	"""apply_overrides handles a mix of set and None fields."""
	from secret_validator_grunt.models.run_params import RunParams

	cfg = Config()
	rp = RunParams(org_repo="o/r", alert_id="1", analyses=10)
	cfg.apply_overrides(rp)
	assert cfg.analysis_count == 10
	assert cfg.stream_verbose is False  # default preserved
