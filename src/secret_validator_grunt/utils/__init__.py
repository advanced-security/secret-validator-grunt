"""Shared utility functions.

This subpackage provides common utility functions used across
the application with no dependencies on other subpackages.

Key modules:
    - parsing: Markdown and JSON parsing utilities
    - paths: Path safety and validation utilities
    - logging: Logging configuration
    - protocols: Protocol definitions for dependency injection
"""

from .parsing import (
    extract_json,
    strip_code_fences,
    parse_sections,
    extract_section,
    parse_table,
    extract_table_from_section,
    extract_bullets,
    normalize_heading,
)
from .paths import ensure_within
from .logging import configure_logging, get_logger
from .protocols import SessionProtocol, CopilotClientProtocol

__all__ = [
    # parsing
    "extract_json",
    "strip_code_fences",
    "parse_sections",
    "extract_section",
    "parse_table",
    "extract_table_from_section",
    "extract_bullets",
    "normalize_heading",
    # paths
    "ensure_within",
    # logging
    "configure_logging",
    "get_logger",
    # protocols
    "SessionProtocol",
    "CopilotClientProtocol",
]
