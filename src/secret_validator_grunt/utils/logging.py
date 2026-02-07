"""
Logging configuration module.

Provides centralized logging setup for the application with
configurable log levels and consistent formatting.
"""

from __future__ import annotations

import logging

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging(level: str = "info") -> None:
	"""
	Configure basic logging with level and format.

	Parameters:
		level: Log level string (e.g., "info", "debug", "warning").
	"""
	lvl = logging._nameToLevel.get(level.upper(), logging.INFO)
	logging.basicConfig(level=lvl, format=LOG_FORMAT)


def get_logger(name: str) -> logging.Logger:
	"""
	Get a logger for the specified module.

	Parameters:
		name: The logger name, typically __name__.

	Returns:
		Configured logger instance.
	"""
	return logging.getLogger(name)


__all__ = ["configure_logging", "get_logger"]
