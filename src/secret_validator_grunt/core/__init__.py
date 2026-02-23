"""Core business logic for secret validation.

This subpackage contains the main orchestration and execution logic
for running validation analyses and judging results.

Key modules:
    - runner: Main orchestration via run_all()
    - analysis: Individual analysis session execution
    - judge: Judge session for selecting best report
    - challenge: Adversarial challenge runner
    - skills: Unified skill discovery interface
"""

from secret_validator_grunt.core.runner import run_all
from secret_validator_grunt.core.analysis import run_analysis
from secret_validator_grunt.core.judge import run_judge
from secret_validator_grunt.core.challenge import run_challenges
from secret_validator_grunt.core.skills import (
    VALID_AGENT_TYPES,
    discover_skill_directories,
    discover_skill_directories_for_agent,
    discover_challenger_skill_directories,
    discover_skills,
    discover_hidden_skills,
    build_skill_manifest,
    format_manifest_for_context,
)

__all__ = [
    # runner
    "run_all",
    # analysis
    "run_analysis",
    # judge
    "run_judge",
    # challenge
    "run_challenges",
    # skills
    "VALID_AGENT_TYPES",
    "discover_skill_directories",
    "discover_skill_directories_for_agent",
    "discover_challenger_skill_directories",
    "discover_skills",
    "discover_hidden_skills",
    "build_skill_manifest",
    "format_manifest_for_context",
]
