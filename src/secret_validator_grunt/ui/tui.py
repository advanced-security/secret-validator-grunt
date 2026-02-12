"""
Terminal UI for run progress visualization.

Provides a Rich-based TUI for displaying parallel analysis runs
and their progress in real-time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from collections import deque

from rich.console import Console, Group
from rich.live import Live
from rich.table import Table
from rich.text import Text
from rich import box

_MAX_MESSAGES = 8


@dataclass
class RunDisplayState:
	"""State for a single run row in the TUI."""

	run_id: str
	status: str = "pending"  # pending|running|completed|failed
	workspace: str | None = None
	messages: deque[str] = field(
	    default_factory=lambda: deque(maxlen=_MAX_MESSAGES))
	# Outcome fields from analysis
	verdict: str | None = None
	confidence: str | None = None
	risk_level: str | None = None
	key_finding: str | None = None

	def add_message(self, msg: str) -> None:
		"""Add a message to the scrolling log."""
		self.messages.append(msg)

	def render_cell(self, org_repo: str | None = None,
	                alert_id: str | None = None) -> Text:
		"""Render cell content for display."""
		text = Text()
		text.append(f"status: {self.status}\n", style="bold")

		if org_repo:
			text.append(f"repo: {org_repo}\n", style="magenta")
		if alert_id:
			text.append(f"alert: {alert_id}\n", style="magenta")
		if self.workspace:
			text.append(f"ws: {self.workspace}\n", style="dim")

		# Show outcome if available
		if self.verdict:
			style = "green" if "FALSE" in self.verdict.upper() else "red"
			text.append(f"verdict: {self.verdict}\n", style=style)
		if self.confidence:
			text.append(f"confidence: {self.confidence}\n", style="cyan")
		if self.risk_level:
			text.append(f"risk: {self.risk_level}\n", style="yellow")
		if self.key_finding:
			# Truncate key finding to fit display
			kf = self.key_finding[:80] + "..." if len(
			    self.key_finding) > 80 else self.key_finding
			text.append(f"finding: {kf}\n", style="white")

		for msg in self.messages:
			clean = msg.strip()
			if "error" in clean.lower() or "failed" in clean.lower():
				text.append(f"• {clean}\n", style="red")
			elif clean.startswith("analysis_") or clean.startswith("judge_"):
				text.append(f"• {clean}\n", style="green")
			else:
				text.append(f"• {clean}\n", style="dim")

		return text


class TUI:
	"""
	Rich-based TUI for streaming run progress.
	
	Uses Rich's Live display with auto-refresh to update in place.
	"""

	def __init__(self, analysis_count: int, show_usage: bool = False,
	             org_repo: str | None = None, alert_id: str | None = None,
	             console: Console | None = None):
		self.console = console or Console()
		self.analysis_count = analysis_count
		self.show_usage = show_usage
		self.org_repo = org_repo
		self.alert_id = alert_id
		self.states: dict[str, RunDisplayState] = {
		    str(i): RunDisplayState(run_id=str(i))
		    for i in range(analysis_count)
		}
		self.states["judge"] = RunDisplayState(run_id="judge")
		self.live: Live | None = None

	def _build_table(self) -> Group:
		"""Build the display tables."""
		# Analysis table
		runs_table = Table(box=box.ROUNDED, expand=True, show_header=True)
		for i in range(self.analysis_count):
			runs_table.add_column(f"Analysis {i}", min_width=30)

		cells = [
		    self.states[str(i)].render_cell(self.org_repo, self.alert_id)
		    for i in range(self.analysis_count)
		]
		runs_table.add_row(*cells)

		# Judge table
		judge_table = Table(box=box.ROUNDED, expand=True, show_header=True)
		judge_table.add_column("Judge", min_width=30)
		judge_table.add_row(self.states["judge"].render_cell(
		    self.org_repo, self.alert_id))

		return Group(runs_table, judge_table)

	def __enter__(self):
		"""Start the Live display."""
		self.live = Live(
		    self._build_table(),
		    console=self.console,
		    refresh_per_second=4,
		)
		self.live.start()
		return self

	def __exit__(self, exc_type, exc, tb):
		"""Stop the Live display."""
		if self.live:
			self.live.stop()

	def update(self, run_id: str, msg: str) -> None:
		"""Update state for a run and refresh display."""
		state = self.states.get(run_id)
		if not state:
			return

		# Update status based on message
		if msg.startswith("analysis_started"):
			state.status = "running"
		elif msg.startswith("analysis_completed"):
			state.status = "completed"
		elif msg.startswith("judge_started"):
			state.status = "running"
		elif msg.startswith("judge_completed"):
			state.status = "completed"
		elif msg.startswith("judge_failed") or "error" in msg.lower(
		) or msg.startswith("timeout"):
			state.status = "failed"

		# Capture workspace
		if msg.startswith("workspace:"):
			state.workspace = msg.split(":", 1)[1].strip()
		else:
			state.add_message(msg)

		# Refresh the live display
		if self.live:
			self.live.update(self._build_table())

	def refresh(self):
		"""Force a display refresh."""
		if self.live:
			self.live.update(self._build_table())

	def finalize(self):
		"""Stop the live display."""
		if self.live:
			self.live.stop()

	def _render_usage_table(self, analysis_results: list,
	                        judge_result) -> Table:
		"""Render token usage statistics table."""
		from secret_validator_grunt.models.usage import (UsageStats, aggregate,
		                                                 format_duration)

		table = Table(show_header=True, expand=True, box=box.ROUNDED)
		table.add_column("Run")
		table.add_column("In")
		table.add_column("Out")
		table.add_column("Requests")
		table.add_column("Duration")

		def fmt_usage(u: UsageStats) -> tuple[str, str, str, str]:
			return (
			    f"{u.input_tokens:g}",
			    f"{u.output_tokens:g}",
			    f"{u.cost:g}" if u.cost else "0",
			    format_duration(u.duration),
			)

		for res in analysis_results:
			u = res.usage
			if u:
				inp, out, cost, dur = fmt_usage(u)
				table.add_row(f"run {res.run_id}", inp, out, cost, dur)

		ju = judge_result.usage if judge_result else None
		if ju:
			inp, out, cost, dur = fmt_usage(ju)
			table.add_row("judge", inp, out, cost, dur)

		# Totals
		all_usages = [r.usage for r in analysis_results]
		if ju:
			all_usages.append(ju)
		all_usages = [u for u in all_usages if u]
		if all_usages:
			t = aggregate(all_usages)
			table.add_row(
			    "total",
			    f"{t.input_tokens:g}",
			    f"{t.output_tokens:g}",
			    f"{t.cost:g}" if t.cost else "0",
			    format_duration(t.duration),
			    style="bold",
			)
		return table

	def _render_skill_usage_table(self, analysis_results: list) -> Table:
		"""
		Render skill usage statistics table.

		Parameters:
			analysis_results: List of agent run results with skill usage.

		Returns:
			Rich Table with skill usage statistics.
		"""
		table = Table(show_header=True, expand=True, box=box.ROUNDED)
		table.add_column("Run")
		table.add_column("Skills Loaded")
		table.add_column("By Phase")
		table.add_column("Required")
		table.add_column("Compliance")

		for res in analysis_results:
			su = res.skill_usage
			if su:
				loaded_count = len(su.loaded_skills)
				available_count = len(su.available_skills)
				required_count = len(su.required_skills)
				loaded_required = len(
				    set(su.loaded_skills) & set(su.required_skills))

				# Build phase breakdown string
				available_by_phase = su.available_by_phase()
				loaded_by_phase = su.loaded_by_phase()
				phase_parts = []
				for phase in sorted(available_by_phase.keys()):
					avail = len(available_by_phase[phase])
					loaded = len(loaded_by_phase.get(phase, []))
					phase_parts.append(f"{phase}: {loaded}/{avail}")
				phase_str = "  ".join(phase_parts) if phase_parts else "-"

				compliance = su.compliance_score
				compliance_style = "green" if compliance == 100 else (
				    "yellow" if compliance >= 50 else "red")

				table.add_row(
				    f"run {res.run_id}",
				    f"{loaded_count}/{available_count}",
				    phase_str,
				    f"{loaded_required}/{required_count}",
				    Text(f"{compliance:.0f}%", style=compliance_style),
				)
			else:
				table.add_row(f"run {res.run_id}", "-", "-", "-", "-")

		return table

	def _render_tool_usage_table(self, analysis_results: list) -> Table:
		"""
		Render tool usage statistics table.

		Parameters:
			analysis_results: List of agent run results with tool usage.

		Returns:
			Rich Table with tool call statistics.
		"""
		table = Table(show_header=True, expand=True, box=box.ROUNDED)
		table.add_column("Run")
		table.add_column("Total")
		table.add_column("Success")
		table.add_column("Failed")
		table.add_column("Rate")
		table.add_column("Top Tools")

		for res in analysis_results:
			tu = res.tool_usage
			if tu:
				rate = tu.success_rate
				rate_style = "green" if rate == 100 else (
				    "yellow" if rate >= 80 else "red")

				top = tu.top_tools(limit=5)
				top_str = " ".join(
				    f"{t.tool_name}({t.total})" for t in top
				) if top else "-"

				table.add_row(
				    f"run {res.run_id}",
				    str(tu.total_calls),
				    str(tu.successful_calls),
				    str(tu.failed_calls),
				    Text(f"{rate:.0f}%", style=rate_style),
				    top_str,
				)
			else:
				table.add_row(
				    f"run {res.run_id}", "-", "-", "-", "-", "-",
				)

		return table

	def update_outcome(self, run_id: str, verdict: str | None = None,
	                   confidence: str | None = None,
	                   risk_level: str | None = None,
	                   key_finding: str | None = None) -> None:
		"""Update outcome information for a run."""
		state = self.states.get(run_id)
		if not state:
			return
		if verdict:
			state.verdict = verdict
		if confidence:
			state.confidence = confidence
		if risk_level:
			state.risk_level = risk_level
		if key_finding:
			state.key_finding = key_finding
		if self.live:
			self.live.update(self._build_table())

	def print_summary(self, winner_index: int, analysis_results: list,
	                  output_dir: Path, judge_result=None):
		"""Print final summary after runs complete."""
		from secret_validator_grunt.models.summary import build_summary_data

		self.finalize()
		self.console.print()

		data = build_summary_data(
			winner_index, analysis_results, output_dir,
			judge_result=judge_result, show_usage=self.show_usage,
		)
		self._render_summary(data, analysis_results, judge_result)

	def _render_summary(self, data, analysis_results: list,
	                    judge_result=None):
		"""Render the summary to console using pre-extracted data.

		Parameters:
			data: SummaryData model with all display values.
			analysis_results: Original results (needed for usage tables).
			judge_result: Original judge result (needed for usage table).
		"""
		# Winner table
		if data.winner:
			result_table = Table(
			    title="Winner Report",
			    box=box.ROUNDED,
			    show_header=False,
			    expand=True,
			    title_style="bold cyan",
			)
			result_table.add_column("Field", style="bold")
			result_table.add_column("Value")

			w = data.winner
			if w.verdict:
				style = "green" if "FALSE" in w.verdict.upper() else "red"
				result_table.add_row("Verdict", Text(w.verdict, style=style))
			if w.confidence:
				result_table.add_row("Confidence", w.confidence)
			if w.risk_level:
				result_table.add_row("Risk Level", w.risk_level)
			if w.secret_type:
				result_table.add_row("Secret Type", w.secret_type)
			if w.key_finding:
				result_table.add_row("Key Finding", w.key_finding)
			if w.workspace:
				result_table.add_row("Workspace", w.workspace)
			if w.final_report_path:
				result_table.add_row("Final Report", w.final_report_path)

			self.console.print(result_table)

		# Judge table
		if data.judge and (data.judge.rationale or data.judge.verdict):
			judge_table = Table(
			    title="Judge Decision",
			    box=box.ROUNDED,
			    show_header=False,
			    expand=True,
			    title_style="bold yellow",
			)
			judge_table.add_column("Field", style="bold")
			judge_table.add_column("Value")
			judge_table.add_row("Winner", f"Report {data.judge.winner_index}")
			if data.judge.rationale:
				judge_table.add_row("Rationale", data.judge.rationale)
			if data.judge.verdict:
				judge_table.add_row("Verdict", data.judge.verdict)
			self.console.print(judge_table)

		# Workspaces summary
		self.console.print("\n[dim]All workspaces:[/dim]")
		for entry in data.workspaces:
			label = "Judge" if entry.run_id == "judge" else f"Run {entry.run_id}"
			self.console.print(f"  {label}: {entry.workspace}")

		if data.show_usage and judge_result is not None:
			self.console.print("\n[bold]Usage[/bold]")
			self.console.print(
			    self._render_usage_table(analysis_results, judge_result))

		if data.show_usage:
			if data.has_skill_usage:
				self.console.print("\n[bold]Skill Usage[/bold]")
				self.console.print(
				    self._render_skill_usage_table(analysis_results),
				)

			if data.has_tool_usage:
				self.console.print("\n[bold]Tool Usage[/bold]")
				self.console.print(
				    self._render_tool_usage_table(analysis_results),
				)


__all__ = ["TUI", "RunDisplayState"]
