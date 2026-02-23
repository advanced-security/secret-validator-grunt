"""Tests for the logging module — token sanitization."""

from __future__ import annotations

import logging

import pytest

from secret_validator_grunt.utils.logging import (
	sanitize_text,
	TokenSanitizingFilter,
	configure_logging,
)


class TestSanitizeText:
	"""Tests for sanitize_text()."""

	def test_masks_token_in_clone_url(self) -> None:
		"""Token in https://user:TOKEN@host is replaced with ***."""
		url = "https://x-access-token:ghp_abc123@github.com/org/repo.git"
		result = sanitize_text(url)
		assert "ghp_abc123" not in result
		assert "***" in result
		assert "github.com/org/repo.git" in result

	def test_masks_token_in_surrounding_text(self) -> None:
		"""Token is masked even when URL is embedded in a sentence."""
		text = (
			"clone failed: https://x-access-token:secret@host.com/r.git "
			"returned 128"
		)
		result = sanitize_text(text)
		assert "secret" not in result
		assert "***" in result
		assert "returned 128" in result

	def test_no_change_without_token(self) -> None:
		"""Plain text without token URLs passes through unchanged."""
		text = "pre-clone completed for org/repo"
		assert sanitize_text(text) == text

	def test_no_change_for_public_url(self) -> None:
		"""Public https://host/repo URL without credentials is untouched."""
		text = "https://github.com/org/repo.git"
		assert sanitize_text(text) == text

	def test_masks_multiple_tokens(self) -> None:
		"""Multiple token URLs in one string are all masked."""
		text = (
			"https://u:tok1@a.com and https://v:tok2@b.com"
		)
		result = sanitize_text(text)
		assert "tok1" not in result
		assert "tok2" not in result
		assert result.count("***") == 2

	def test_empty_string(self) -> None:
		"""Empty string returns empty."""
		assert sanitize_text("") == ""


class TestTokenSanitizingFilter:
	"""Tests for the TokenSanitizingFilter logging.Filter."""

	def _make_record(
		self,
		msg: str,
		args: tuple | dict | None = None,
	) -> logging.LogRecord:
		"""Create a minimal LogRecord for testing."""
		record = logging.LogRecord(
			name="test",
			level=logging.WARNING,
			pathname="test.py",
			lineno=1,
			msg=msg,
			args=args,
			exc_info=None,
		)
		return record

	def test_sanitizes_msg(self) -> None:
		"""Token in record.msg is masked."""
		f = TokenSanitizingFilter()
		record = self._make_record(
			"error: https://u:ghp_secret@host.com/r.git"
		)
		f.filter(record)
		assert "ghp_secret" not in record.msg
		assert "***" in record.msg

	def test_sanitizes_tuple_args(self) -> None:
		"""Token in tuple args is masked."""
		f = TokenSanitizingFilter()
		record = self._make_record(
			"clone output: %s",
			("https://u:tok@host.com/r.git",),
		)
		f.filter(record)
		assert isinstance(record.args, tuple)
		assert "tok" not in record.args[0]

	def test_sanitizes_dict_args(self) -> None:
		"""Token in dict args is masked."""
		f = TokenSanitizingFilter()
		record = self._make_record("%(url)s failed")
		record.args = {"url": "https://u:tok@host.com/r.git"}
		f.filter(record)
		assert isinstance(record.args, dict)
		assert "tok" not in record.args["url"]

	def test_non_string_args_unchanged(self) -> None:
		"""Non-string args pass through without modification."""
		f = TokenSanitizingFilter()
		record = self._make_record("rc=%d", (128,))
		f.filter(record)
		assert record.args == (128,)

	def test_always_returns_true(self) -> None:
		"""Filter never suppresses records — always returns True."""
		f = TokenSanitizingFilter()
		record = self._make_record("any message")
		assert f.filter(record) is True

	def test_no_args(self) -> None:
		"""Record with no args doesn't raise."""
		f = TokenSanitizingFilter()
		record = self._make_record("plain message", None)
		assert f.filter(record) is True
		assert record.msg == "plain message"


class TestConfigureLoggingFilter:
	"""Tests that configure_logging installs the filter."""

	def test_filter_installed_once(self) -> None:
		"""configure_logging adds TokenSanitizingFilter to root logger."""
		root = logging.getLogger()
		# Remove any pre-existing filter from prior test runs
		root.filters = [
			f for f in root.filters
			if not isinstance(f, TokenSanitizingFilter)
		]
		configure_logging("warning")
		count = sum(
			1 for f in root.filters
			if isinstance(f, TokenSanitizingFilter)
		)
		assert count == 1

	def test_no_duplicate_on_repeated_calls(self) -> None:
		"""Calling configure_logging twice doesn't add duplicate filters."""
		root = logging.getLogger()
		root.filters = [
			f for f in root.filters
			if not isinstance(f, TokenSanitizingFilter)
		]
		configure_logging("info")
		configure_logging("info")
		count = sum(
			1 for f in root.filters
			if isinstance(f, TokenSanitizingFilter)
		)
		assert count == 1
