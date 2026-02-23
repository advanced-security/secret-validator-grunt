"""
Secret Validator Grunt models.

This subpackage contains Pydantic models for configuration, reports,
run parameters, and other data structures used throughout the application.

Key models:
    - Config: Application configuration loaded from environment
    - RunParams: Parameters for a validation run
    - Report: Parsed validation report
    - AgentConfig: Agent definition loaded from markdown files
    - SkillInfo: Metadata for a single skill
    - SkillManifest: Complete manifest of discovered skills
"""

from .usage import UsageStats
from .config import Config, load_env
from .agent_config import AgentConfig
from .report import Report, ReportScore
from .run_result import AgentRunResult
from .judge_result import JudgeResult, JudgeScore
from .run_outcome import RunOutcome
from .run_params import RunParams
from .skill import SkillInfo, SkillManifest
from .skill_usage import SkillLoadStatus, SkillLoadEvent, SkillUsageStats
from .tool_usage import ToolCallEvent, ToolCallSummary, ToolUsageStats
from .eval_result import EvalCheck, EvalResult
from .summary import (
    SummaryData,
    WinnerInfo,
    JudgeInfo,
    WorkspaceEntry,
    build_summary_data,
)
from .challenge_result import ChallengeResult, VALID_CHALLENGE_VERDICTS

__all__ = [
    "UsageStats",
    "Config",
    "load_env",
    "AgentConfig",
    "Report",
    "ReportScore",
    "AgentRunResult",
    "JudgeResult",
    "JudgeScore",
    "RunOutcome",
    "RunParams",
    "SkillInfo",
    "SkillManifest",
    "SkillLoadStatus",
    "SkillLoadEvent",
    "SkillUsageStats",
    "ToolCallEvent",
    "ToolCallSummary",
    "ToolUsageStats",
    "EvalCheck",
    "EvalResult",
    "SummaryData",
    "WinnerInfo",
    "JudgeInfo",
    "WorkspaceEntry",
    "build_summary_data",
    "ChallengeResult",
    "VALID_CHALLENGE_VERDICTS",
]
