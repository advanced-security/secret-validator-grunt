from pathlib import Path

import pytest

from secret_validator_grunt.models.run_params import RunParams


def test_run_params_valid():
	rp = RunParams(org_repo="org/repo", alert_id="1")
	assert rp.owner == "org"
	assert rp.repo == "repo"
	assert rp.org_repo_slug == Path("org/repo")
	assert rp.alert_id_slug == "1"
	assert rp.session_id_prefix.startswith("org_repo_1")


def test_run_params_invalid_org_repo():
	with pytest.raises(ValueError):
		RunParams(org_repo="../evil/repo", alert_id="1")


def test_run_params_invalid_alert_id():
	with pytest.raises(ValueError):
		RunParams(org_repo="org/repo", alert_id="../etc")


def test_run_params_positive_ints():
	with pytest.raises(ValueError):
		RunParams(org_repo="org/repo", alert_id="1", analyses=0)
