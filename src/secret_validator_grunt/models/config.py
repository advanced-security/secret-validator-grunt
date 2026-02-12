from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_core.core_schema import ValidationInfo
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv


def load_env(env_file: str | Path | None = None) -> None:
	"""Load environment variables from an `.env` file if present."""
	env_path = Path(env_file) if env_file else Path(".env")
	if env_path.exists():
		load_dotenv(env_path)


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
	validate_secret_timeout_seconds: int = Field(
	    30,
	    alias="VALIDATE_SECRET_TIMEOUT_SECONDS",
	    description="Timeout in seconds for network-based secret validators",
	)
	skill_directories: Any = Field(
	    default_factory=list,
	    alias="SKILL_DIRECTORIES",
	    description="Additional skill directories for Copilot",
	)
	disabled_skills: Any = Field(
	    default_factory=list,
	    alias="DISABLED_SKILLS",
	    description="Skill names to disable for Copilot sessions",
	)

	@field_validator("skill_directories", mode="before")
	@classmethod
	def split_skill_dirs(cls, v: Any) -> list[str]:
		"""Normalize skill directories to a list regardless of input format."""
		if v is None or v == "":
			return []
		if isinstance(v, list):
			return v
		if isinstance(v, tuple):
			return list(v)
		# fallback: comma-separated string
		return [p.strip() for p in str(v).split(",") if p.strip()]

	@field_validator("skill_directories", mode="after")
	@classmethod
	def filter_existing_skill_dirs(cls, v: list[str]) -> list[str]:
		"""Filter to existing directories only."""
		return [p for p in v if Path(p).exists()]

	@field_validator("disabled_skills", mode="before")
	@classmethod
	def split_disabled_skills(cls, v: Any) -> list[str]:
		"""Normalize disabled skills to a list regardless of input format."""
		if v is None or v == "":
			return []
		if isinstance(v, list):
			return v
		if isinstance(v, tuple):
			return list(v)
		# fallback: comma-separated string
		return [p.strip() for p in str(v).split(",") if p.strip()]

	@field_validator("analysis_count", "analysis_timeout_seconds",
	                 "judge_timeout_seconds", "poll_interval_seconds",
	                 "max_parallel_sessions",
	                 "validate_secret_timeout_seconds")
	@classmethod
	def validate_positive(cls, v: Any, info: "ValidationInfo") -> Any:
		if v is None:
			return v
		try:
			if int(v) <= 0:
				raise ValueError(f"{info.field_name} must be > 0")
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
