"""Runtime configuration loaded from environment variables.

Provides the ``Config`` class backed by ``pydantic-settings``
which loads values from environment variables and ``.env``
files.  Field aliases match the env-var names and **must**
be used when constructing ``Config`` in code or tests.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import AliasChoices, Field, field_validator
from pydantic_core.core_schema import ValidationInfo
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv


def load_env(env_file: str | Path | None = None) -> None:
	"""Load environment variables from an `.env` file if present."""
	env_path = Path(env_file) if env_file else Path(".env")
	if env_path.exists():
		load_dotenv(env_path)


def _split_comma_list(value: Any) -> list[str]:
	"""Normalize a comma-separated string or collection to a list.

	Accepts ``None``, an empty string, a list, a tuple, or a
	comma-separated string and always returns ``list[str]``.
	"""
	if value is None or value == "":
		return []
	if isinstance(value, list):
		return value
	if isinstance(value, tuple):
		return list(value)
	return [p.strip() for p in str(value).split(",") if p.strip()]


def _filter_existing_dirs(dirs: list[str]) -> list[str]:
	"""Filter a list of directory paths to only those that exist."""
	return [p for p in dirs if Path(p).exists()]


class Config(BaseSettings):
	"""Runtime configuration loaded from environment variables."""

	model_config = SettingsConfigDict(env_prefix="", case_sensitive=False)

	cli_url: str | None = Field(
	    default=None,
	    alias="COPILOT_CLI_URL",
	    description=
	    "External Copilot CLI server URL. If unset, spawns native CLI via stdio.",
	)
	model: str = Field(
	    "Claude Sonnet 4.5",
	    alias="COPILOT_MODEL",
	    description="Default model name",
	)
	analysis_count: int = Field(
	    3,
	    alias="ANALYSIS_COUNT",
	    description="Number of analyses to run concurrently",
	)
	analysis_timeout_seconds: int = Field(
	    1800,
	    alias="ANALYSIS_TIMEOUT_SECONDS",
	    description="Analysis timeout in seconds",
	)
	judge_timeout_seconds: int = Field(
	    300,
	    alias="JUDGE_TIMEOUT_SECONDS",
	    description="Judge timeout in seconds",
	)
	max_parallel_sessions: int | None = Field(
	    default=None,
	    alias="MAX_PARALLEL_SESSIONS",
	    description="Maximum parallel sessions (default=analysis_count)",
	)
	stream_verbose: bool = Field(False, alias="STREAM_VERBOSE",
	                             description="Stream deltas to console")
	agent_file: str = Field(
	    "agents/secret_validator.agent.md",
	    alias="AGENT_FILE",
	    description="Path to validator agent definition",
	)
	judge_agent_file: str = Field(
	    "agents/judge.agent.md",
	    alias="JUDGE_AGENT_FILE",
	    description="Path to judge agent definition",
	)
	report_template_file: str = Field(
	    "templates/report.md",
	    alias="REPORT_TEMPLATE_FILE",
	    description="Default report template path",
	)
	poll_interval_seconds: int = Field(
	    5,
	    alias="POLL_INTERVAL_SECONDS",
	    description="Polling interval in seconds",
	)
	output_dir: str = Field("analysis", alias="OUTPUT_DIR",
	                        description="Base output directory")
	log_level: str = Field("info", alias="LOG_LEVEL",
	                       description="Log level for Copilot client")
	show_usage: bool = Field(
	    False,
	    alias="SHOW_USAGE",
	    description="Show token/cost usage metrics in TUI and summary",
	)
	github_token: str | None = Field(
	    default=None,
	    alias="GITHUB_TOKEN",
	    description="GitHub token for secret scanning API access",
	)
	max_continuation_attempts: int = Field(
	    2,
	    alias="MAX_CONTINUATION_ATTEMPTS",
	    description=("Maximum continuation prompts to send when the model "
	                 "terminates early with an empty response"),
	)
	min_response_length: int = Field(
	    500,
	    alias="MIN_RESPONSE_LENGTH",
	    description=(
	        "Minimum character length to consider a response valid. "
	        "Responses shorter than this trigger a continuation prompt."),
	)
	validate_secret_timeout_seconds: int = Field(
	    30,
	    alias="VALIDATE_SECRET_TIMEOUT_SECONDS",
	    description="Timeout in seconds for network-based secret validators",
	)
	analysis_skill_directories: Any = Field(
	    default_factory=list,
	    validation_alias=AliasChoices(
	        "ANALYSIS_SKILL_DIRECTORIES",
	        "SKILL_DIRECTORIES",
	    ),
	    description="Additional skill directories for analysis agent",
	)
	disabled_skills: Any = Field(
	    default_factory=list,
	    alias="DISABLED_SKILLS",
	    description="Skill names to disable for Copilot sessions",
	)
	challenger_agent_file: str = Field(
	    "agents/challenger.agent.md",
	    alias="CHALLENGER_AGENT_FILE",
	    description="Path to challenger agent definition",
	)
	challenger_timeout_seconds: int = Field(
	    300,
	    alias="CHALLENGER_TIMEOUT_SECONDS",
	    description="Challenger session timeout in seconds",
	)
	challenger_skill_directories: Any = Field(
	    default_factory=list,
	    alias="CHALLENGER_SKILL_DIRECTORIES",
	    description="Additional skill directories for challenger agent",
	)

	@field_validator("analysis_skill_directories", mode="before")
	@classmethod
	def split_skill_dirs(cls, v: Any) -> list[str]:
		"""Normalize skill directories to a list regardless of input format."""
		return _split_comma_list(v)

	@field_validator("analysis_skill_directories", mode="after")
	@classmethod
	def filter_existing_skill_dirs(cls, v: list[str]) -> list[str]:
		"""Filter to existing directories only."""
		return _filter_existing_dirs(v)

	@field_validator("disabled_skills", mode="before")
	@classmethod
	def split_disabled_skills(cls, v: Any) -> list[str]:
		"""Normalize disabled skills to a list regardless of input format."""
		return _split_comma_list(v)

	@field_validator("challenger_skill_directories", mode="before")
	@classmethod
	def split_challenger_skill_dirs(cls, v: Any) -> list[str]:
		"""Normalize challenger skill directories to a list."""
		return _split_comma_list(v)

	@field_validator("challenger_skill_directories", mode="after")
	@classmethod
	def filter_existing_challenger_skill_dirs(cls, v: list[str]) -> list[str]:
		"""Filter to existing directories only."""
		return _filter_existing_dirs(v)

	@field_validator(
	    "analysis_count",
	    "analysis_timeout_seconds",
	    "judge_timeout_seconds",
	    "poll_interval_seconds",
	    "max_parallel_sessions",
	    "validate_secret_timeout_seconds",
	    "challenger_timeout_seconds",
	)
	@classmethod
	def validate_positive(cls, v: Any, info: "ValidationInfo") -> Any:
		"""Reject zero and negative values."""
		if v is None:
			return v
		try:
			if int(v) <= 0:
				raise ValueError(f"{info.field_name} must be > 0")
		except Exception:
			raise
		return v

	@field_validator(
	    "max_continuation_attempts",
	    "min_response_length",
	)
	@classmethod
	def validate_non_negative(
	    cls,
	    v: Any,
	    info: "ValidationInfo",
	) -> Any:
		"""Allow zero (disabled) but reject negative values."""
		if v is None:
			return v
		try:
			if int(v) < 0:
				raise ValueError(f"{info.field_name} must be >= 0")
		except Exception:
			raise
		return v

	@property
	def use_native_cli(self) -> bool:
		"""Return True when using native stdio mode (no external server)."""
		return not self.cli_url

	@property
	def output_path(self) -> Path:
		"""Return output_dir as Path."""
		return Path(self.output_dir)

	def apply_overrides(self, run_params: "RunParams") -> None:
		"""Apply CLI overrides from RunParams onto this config.

		Only non-None fields in run_params are applied, preserving
		environment-based defaults for anything the user didn't explicitly set.

		Parameters:
			run_params: Validated run parameters with optional overrides.
		"""
		_OVERRIDES: list[tuple[str, str]] = [
		    ("analyses", "analysis_count"),
		    ("timeout", "analysis_timeout_seconds"),
		    ("judge_timeout", "judge_timeout_seconds"),
		    ("stream_verbose", "stream_verbose"),
		    ("show_usage", "show_usage"),
		]
		for param_field, config_field in _OVERRIDES:
			value = getattr(run_params, param_field)
			if value is not None:
				setattr(self, config_field, value)


__all__ = ["Config", "load_env"]
