"""
Logging configuration module.

Provides centralized logging setup for the application with
configurable log levels and consistent formatting.
"""

from __future__ import annotations

import logging
import re

from rich.console import Console
from rich.logging import RichHandler

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"

# Pattern to match tokens embedded in git clone URLs
# e.g. https://x-access-token:ghp_abc123@github.com/...
_TOKEN_RE = re.compile(
    r"(https?://[^:]+:)[^@]+(@)",
    re.IGNORECASE,
)


def sanitize_text(text: str) -> str:
	"""Mask embedded credentials in text.

	Replaces tokens in git-style URLs
	(``https://user:TOKEN@host``) with ``***``.

	Parameters:
		text: Raw text that may contain token-embedded URLs.

	Returns:
		Text with tokens replaced by ``***``.
	"""
	return _TOKEN_RE.sub(r"\1***\2", text)


class TokenSanitizingFilter(logging.Filter):
	"""Logging filter that redacts credentials from log records.

	Applied to the configured handler so child loggers are also
	sanitized without call-site awareness.
	"""

	def filter(self, record: logging.LogRecord) -> bool:
		"""Sanitize the log record message and args."""
		if isinstance(record.msg, str):
			record.msg = sanitize_text(record.msg)
		if record.args:
			if isinstance(record.args, dict):
				record.args = {
				    k: sanitize_text(str(v)) if isinstance(v, str) else v
				    for k, v in record.args.items()
				}
			elif isinstance(record.args, tuple):
				record.args = tuple(
				    sanitize_text(str(a)) if isinstance(a, str) else a
				    for a in record.args)
		return True


def configure_logging(level: str = "info",
                      console: Console | None = None) -> None:
	"""
	Configure basic logging with level, format, and token sanitization.

	Use the live display's console when provided so log messages clear
	and redraw the display instead of writing through it.

	Parameters:
		level: Log level string (e.g., "info", "debug", "warning").
		console: Shared Rich console, or None for standard stderr logging.
	"""
	lvl = logging._nameToLevel.get(level.upper(), logging.INFO)
	handler = (RichHandler(console=console, show_time=False, show_level=False,
	                       show_path=False)
	           if console is not None else logging.StreamHandler())
	handler.addFilter(TokenSanitizingFilter())
	logging.basicConfig(level=lvl, format=LOG_FORMAT, handlers=[handler])
	root = logging.getLogger()
	# Avoid adding duplicate filters on repeated calls
	if not any(isinstance(f, TokenSanitizingFilter) for f in root.filters):
		root.addFilter(TokenSanitizingFilter())


def get_logger(name: str) -> logging.Logger:
	"""
	Get a logger for the specified module.

	Parameters:
		name: The logger name, typically __name__.

	Returns:
		Configured logger instance.
	"""
	return logging.getLogger(name)


__all__ = [
    "configure_logging",
    "get_logger",
    "sanitize_text",
    "TokenSanitizingFilter",
]
