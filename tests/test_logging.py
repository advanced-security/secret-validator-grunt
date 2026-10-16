"""Tests for the logging module — token sanitization."""

from __future__ import annotations

import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from io import StringIO

import pytest
from rich.console import Console
from rich.logging import RichHandler

from secret_validator_grunt.utils.logging import (
    sanitize_text,
    TokenSanitizingFilter,
    configure_logging,
)


@contextmanager
def isolated_root_logger() -> Iterator[logging.Logger]:
	"""Isolate logging setup and restore pytest's handlers afterward."""
	root = logging.getLogger()
	previous_level = root.level
	previous_handlers, previous_filters = root.handlers, root.filters
	root.handlers, root.filters = [], []
	try:
		yield root
	finally:
		for handler in root.handlers:
			handler.close()
		root.handlers, root.filters = previous_handlers, previous_filters
		root.setLevel(previous_level)


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
		text = ("clone failed: https://x-access-token:secret@host.com/r.git "
		        "returned 128")
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
		text = ("https://u:tok1@a.com and https://v:tok2@b.com")
		result = sanitize_text(text)
		assert "tok1" not in result
		assert "tok2" not in result
		assert result.count("***") == 2

	def test_empty_string(self) -> None:
		"""Empty string returns empty."""
		assert sanitize_text("") == ""

	def test_masks_different_token_types(self) -> None:
		"""GitHub API and Copilot tokens in separate URLs are both masked."""
		text = (
		    "clone: https://x-access-token:ghp_api_token@github.com/o/r.git "
		    "copilot: https://x-access-token:gho_copilot_token@github.com/o/r.git"
		)
		result = sanitize_text(text)
		assert "ghp_api_token" not in result
		assert "gho_copilot_token" not in result
		assert result.count("***") == 2


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
		    "error: https://u:ghp_secret@host.com/r.git")
		f.filter(record)
		assert "ghp_secret" not in record.msg
		assert "***" in record.msg

	def test_sanitizes_tuple_args(self) -> None:
		"""Token in tuple args is masked."""
		f = TokenSanitizingFilter()
		record = self._make_record(
		    "clone output: %s",
		    ("https://u:tok@host.com/r.git", ),
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
		record = self._make_record("rc=%d", (128, ))
		f.filter(record)
		assert record.args == (128, )

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
		    f for f in root.filters if not isinstance(f, TokenSanitizingFilter)
		]
		configure_logging("warning")
		count = sum(1 for f in root.filters
		            if isinstance(f, TokenSanitizingFilter))
		assert count == 1

	def test_no_duplicate_on_repeated_calls(self) -> None:
		"""Calling configure_logging twice doesn't add duplicate filters."""
		root = logging.getLogger()
		root.filters = [
		    f for f in root.filters if not isinstance(f, TokenSanitizingFilter)
		]
		configure_logging("info")
		configure_logging("info")
		count = sum(1 for f in root.filters
		            if isinstance(f, TokenSanitizingFilter))
		assert count == 1


class TestConsoleLogging:
	"""Logging shares the live console without changing message semantics."""

	def test_uses_shared_console(self) -> None:
		"""A supplied console receives the existing timestamped log format."""
		output = StringIO()
		console = Console(file=output, width=200)
		with isolated_root_logger() as root:
			configure_logging(console=console)
			handler = root.handlers[0]
			assert isinstance(handler, RichHandler)
			assert handler.console is console
			logging.getLogger("test.display").info("pre-clone completed")
		assert "INFO test.display: pre-clone completed" in output.getvalue()

	def test_sanitizes_child_logger_arguments(self) -> None:
		"""Propagated records are sanitized at the Rich handler."""
		output = StringIO()
		url = "https://x-access-token:example-token@github.com/org/repo.git"
		with isolated_root_logger():
			configure_logging(console=Console(file=output, width=200))
			logging.getLogger("test.display").warning("clone failed: %s", url)
		assert "example-token" not in output.getvalue()
		assert "x-access-token:***@github.com" in output.getvalue()
		assert "WARNING test.display: clone failed:" in output.getvalue()

	def test_default_logging_uses_stderr(
	    self,
	    monkeypatch: pytest.MonkeyPatch,
	) -> None:
		"""Callers without a console retain standard stderr logging."""
		output = StringIO()
		monkeypatch.setattr("sys.stderr", output)
		with isolated_root_logger() as root:
			configure_logging()
			logging.getLogger("test.display").info("plain output")
			assert root.handlers[0].stream is output
		assert "INFO test.display: plain output" in output.getvalue()
		assert "\x1b" not in output.getvalue()

	def test_repeated_configuration_keeps_one_handler(self) -> None:
		"""Repeated configuration does not duplicate console output."""
		output = StringIO()
		console = Console(file=output, width=200)
		with isolated_root_logger() as root:
			configure_logging(console=console)
			configure_logging(console=console)
			logging.getLogger("test.display").info("one message")
			assert len(root.handlers) == 1
		assert output.getvalue().count("one message") == 1

	@pytest.mark.parametrize("fail", [False, True])
	def test_cli_shares_console_and_cleans_up(
	    self,
	    monkeypatch: pytest.MonkeyPatch,
	    fail: bool,
	) -> None:
		"""The real CLI shares one console and stops Live on either outcome."""
		from secret_validator_grunt import main
		from secret_validator_grunt.models.config import Config
		from secret_validator_grunt.models.judge_result import JudgeResult
		from secret_validator_grunt.models.run_outcome import RunOutcome
		from secret_validator_grunt.models.run_params import RunParams
		from secret_validator_grunt.models.run_result import AgentRunResult
		from secret_validator_grunt.ui.streaming import ProgressCallback

		output = StringIO()
		console = Console(file=output, width=200)
		monkeypatch.setattr(main, "Console", lambda: console)
		monkeypatch.setattr(main, "load_env", lambda: None)
		monkeypatch.setattr(main, "Config",
		                    lambda: Config(_env_file=None, ANALYSIS_COUNT=1))

		async def fake_run_all(
		    config: Config,
		    run_params: RunParams,
		    progress_cb: ProgressCallback | None = None,
		) -> RunOutcome:
			assert console._live_stack
			handler = logging.getLogger().handlers[0]
			assert isinstance(handler, RichHandler)
			assert handler.console is console
			logging.getLogger("test.display").info("synthetic runner")
			assert progress_cb is not None
			progress_cb("0", "analysis_started")
			if fail:
				raise RuntimeError("synthetic failure")
			progress_cb("0", "analysis_completed")
			return RunOutcome(
			    analysis_results=[AgentRunResult(run_id="0", progress_log=[])],
			    judge_result=JudgeResult(winner_index=0, scores=[]),
			)

		monkeypatch.setattr(main, "run_all", fake_run_all)
		with isolated_root_logger():
			if fail:
				with pytest.raises(RuntimeError, match="synthetic failure"):
					main.run_impl("example/repo", "2")
			else:
				main.run_impl("example/repo", "2")
				assert output.getvalue().count("Winner Report") == 1
		assert output.getvalue().count("synthetic runner") == 1
		assert not console._live_stack

	@pytest.mark.parametrize("width,height", [(80, 24), (120, 40), (200, 50)])
	def test_log_clears_and_redraws_live_panels(
	    self,
	    monkeypatch: pytest.MonkeyPatch,
	    width: int,
	    height: int,
	) -> None:
		"""A log clears every visible panel line before redrawing progress."""
		from functools import partial
		from rich.live import Live
		from secret_validator_grunt.ui.tui import TUI

		# Refresh explicitly so background ticks cannot race the assertions.
		monkeypatch.setattr("secret_validator_grunt.ui.tui.Live",
		                    partial(Live, auto_refresh=False))
		output = StringIO()
		console = Console(file=output, force_terminal=True, color_system=None,
		                  width=width, height=height)
		stdout, stderr = sys.stdout, sys.stderr
		with isolated_root_logger():
			configure_logging(console=console)
			with TUI(3, org_repo="example/repo", alert_id="2",
			         console=console) as ui:
				ui.update("0", "analysis_started")
				for index in range(8):
					ui.update("0", f"assistant: inspecting repository {index}")
				assert ui.live is not None
				ui.live.refresh()
				frame_height = min(
				    height,
				    len(
				        console.render_lines(ui._build_table(),
				                             console.options, pad=False)),
				)
				start = output.tell()
				logging.getLogger("test.display").info("redraw-check")
				written = output.getvalue()[start:]
				before, marker, after = written.partition("redraw-check")
				assert marker
				assert before.count("\x1b[2K") == frame_height
				assert "Analysis 0" in after
				assert "status: running" in after
		assert sys.stdout is stdout
		assert sys.stderr is stderr

	def test_redirected_output_has_one_final_panel_snapshot(self) -> None:
		"""Piped output includes logs and final panels without cursor codes."""
		from secret_validator_grunt.ui.tui import TUI

		output = StringIO()
		console = Console(file=output, force_terminal=False, width=120)
		with isolated_root_logger():
			configure_logging(console=console)
			with TUI(2, console=console) as ui:
				ui.update("0", "analysis_started")
				logging.getLogger("test.display").info("redirected-check")
				ui.update("0", "analysis_completed")
		text = output.getvalue()
		assert "\x1b" not in text
		assert text.count("redirected-check") == 1
		assert text.count("Analysis 0") == 1
		assert text.count("Challenger 0") == 1
		assert text.count("Judge") == 1
		assert "status: completed" in text
