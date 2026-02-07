import pytest
from pathlib import Path

from secret_validator_grunt.utils.paths import ensure_within


def test_ensure_within(tmp_path):
	base = tmp_path / "base"
	child = base / "a" / "b"
	# path may not exist; ensure_within should still allow
	assert ensure_within(base, child) == child


def test_ensure_within_raises(tmp_path):
	base = tmp_path / "base"
	outside = tmp_path.parent / "other"
	with pytest.raises(ValueError):
		ensure_within(base, outside)
