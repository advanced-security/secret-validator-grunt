"""User interface components.

This subpackage provides terminal UI and output rendering
functionality for the secret validator.

Key modules:
    - tui: Rich-based terminal UI for progress display
    - streaming: Event stream handling and collection
    - reporting: Report rendering and persistence
"""

from secret_validator_grunt.ui.tui import TUI, RunDisplayState
from secret_validator_grunt.ui.streaming import (
    StreamCollector,
    ProgressCallback,
    fetch_last_assistant_message,
)
from secret_validator_grunt.ui.reporting import render_report_md, save_report_md

__all__ = [
    "TUI",
    "RunDisplayState",
    "StreamCollector",
    "ProgressCallback",
    "fetch_last_assistant_message",
    "render_report_md",
    "save_report_md",
]
