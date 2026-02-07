"""File and resource loading utilities.

This subpackage handles loading various file types and resources
used throughout the application.

Key modules:
    - agents: Agent definition loading from markdown
    - prompts: Prompt template loading
    - templates: Report template loading
    - frontmatter: YAML frontmatter parsing
"""

from .frontmatter import split_frontmatter
from .agents import load_agent
from .prompts import load_prompt
from .templates import load_report_template

__all__ = [
    "split_frontmatter",
    "load_agent",
    "load_prompt",
    "load_report_template",
]
