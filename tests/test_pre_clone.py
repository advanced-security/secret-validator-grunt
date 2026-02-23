"""Tests for pre-clone repo optimization in runner."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from secret_validator_grunt.core.runner import (
	pre_clone_repo,
)


class TestPreCloneRepo:
	"""Tests for pre_clone_repo async helper."""

	@pytest.mark.asyncio
	async def test_returns_none_on_clone_failure(self, tmp_path):
		"""Returns None when git clone fails."""
		target = tmp_path / "target"
		target.mkdir()

		mock_proc = AsyncMock()
		mock_proc.returncode = 128
		mock_proc.communicate = AsyncMock(
			return_value=(b"", b"fatal: repo not found"),
		)

		with patch(
			"asyncio.create_subprocess_exec",
			return_value=mock_proc,
		):
			result = await pre_clone_repo(
				"org/repo", target, github_token=None,
			)

		assert result is None
		# Should clean up failed directory
		assert not (target / "_shared_repo").exists()

	@pytest.mark.asyncio
	async def test_returns_path_on_success(self, tmp_path):
		"""Returns repo path when git clone succeeds."""
		target = tmp_path / "target"
		target.mkdir()
		repo_dir = target / "_shared_repo"

		mock_proc = AsyncMock()
		mock_proc.returncode = 0
		mock_proc.communicate = AsyncMock(
			return_value=(b"", b""),
		)

		with patch(
			"asyncio.create_subprocess_exec",
			return_value=mock_proc,
		):
			result = await pre_clone_repo(
				"org/repo", target, github_token="ghp_test",
			)

		assert result == repo_dir

	@pytest.mark.asyncio
	async def test_skips_if_already_exists(self, tmp_path):
		"""Returns existing path without cloning again."""
		target = tmp_path / "target"
		target.mkdir()
		repo_dir = target / "_shared_repo"
		repo_dir.mkdir()

		with patch(
			"asyncio.create_subprocess_exec",
		) as mock_exec:
			result = await pre_clone_repo(
				"org/repo", target, github_token=None,
			)
			mock_exec.assert_not_called()

		assert result == repo_dir

	@pytest.mark.asyncio
	async def test_returns_none_on_exception(self, tmp_path):
		"""Returns None when subprocess raises exception."""
		target = tmp_path / "target"
		target.mkdir()

		with patch(
			"asyncio.create_subprocess_exec",
			side_effect=OSError("git not found"),
		):
			result = await pre_clone_repo(
				"org/repo", target, github_token=None,
			)

		assert result is None

	@pytest.mark.asyncio
	async def test_uses_token_in_url(self, tmp_path):
		"""Token is included in clone URL for private repos."""
		target = tmp_path / "target"
		target.mkdir()

		mock_proc = AsyncMock()
		mock_proc.returncode = 0
		mock_proc.communicate = AsyncMock(
			return_value=(b"", b""),
		)

		with patch(
			"asyncio.create_subprocess_exec",
			return_value=mock_proc,
		) as mock_exec:
			await pre_clone_repo(
				"org/repo", target, github_token="ghp_abc123",
			)

		call_args = mock_exec.call_args
		# The clone URL should contain the token
		args = call_args[0]
		clone_url = args[3]  # git, clone, --depth=1, URL, .
		assert "ghp_abc123" in clone_url
		assert "org/repo" in clone_url

	@pytest.mark.asyncio
	async def test_no_token_public_url(self, tmp_path):
		"""No token produces a plain HTTPS URL."""
		target = tmp_path / "target"
		target.mkdir()

		mock_proc = AsyncMock()
		mock_proc.returncode = 0
		mock_proc.communicate = AsyncMock(
			return_value=(b"", b""),
		)

		with patch(
			"asyncio.create_subprocess_exec",
			return_value=mock_proc,
		) as mock_exec:
			await pre_clone_repo(
				"org/repo", target, github_token=None,
			)

		call_args = mock_exec.call_args
		args = call_args[0]
		clone_url = args[3]
		assert "x-access-token" not in clone_url
		assert clone_url == "https://github.com/org/repo.git"
