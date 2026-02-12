# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- `Config.apply_overrides()` method for clean CLI→config mapping
- `SummaryData` model separating data extraction from TUI rendering
- Shared session utilities (`core/session.py`) deduplicating analysis/judge lifecycle
- `resolve_asset_path()` for package-relative asset resolution
- PEP 561 `py.typed` marker for downstream type checking
- Debug logging with `exc_info=True` for all silenced exceptions
- `@lru_cache` on `_import_registry()` for deterministic import caching
- `PrivateAttr` for `ToolUsageStats._pending` (Pydantic v2 compliant)

### Changed
- `RunOutcome` converted from `@dataclass` to Pydantic `BaseModel`
- All typing imports modernized: `List`→`list`, `Dict`→`dict`, `Optional[X]`→`X | None`
- `getattr()` overuse on typed models replaced with proper null checks
- `run_analysis()` decomposed into `_setup_workspace`, `_build_session_config`, `_persist_diagnostics`
- `print_summary()` split into `build_summary_data()` (pure) + `_render_summary()` (Rich)
- Config defaults now use package-relative paths (work with pip install)
- Deferred imports in `analysis.py` moved to module level

### Fixed
- Agent/template paths now resolve correctly when installed via pip
- Stray `from typing import Iterable` mid-file in `usage.py` moved to top
- Module docstring ordering in `agent_config.py` (before `__future__` import)
