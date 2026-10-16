"""Filesystem checks for original evidence protection and rerun copies."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import json
import os
from pathlib import Path
import stat
import sys
from types import SimpleNamespace
from typing import Any

import pytest
from copilot.generated.session_events import SessionEventType

from secret_validator_grunt.core.challenge import (
    run_challenges,
    run_single_challenge,
)
from secret_validator_grunt.core.challenge_workspace import (
    changed_evidence,
    prepare_challenge_workspace,
)
from secret_validator_grunt.loaders.agents import load_agent
from secret_validator_grunt.models.challenge_result import ChallengeResult
from secret_validator_grunt.models.config import Config
from secret_validator_grunt.models.run_params import RunParams
from secret_validator_grunt.models.run_result import AgentRunResult


@pytest.fixture
def analysis_workspace(tmp_path: Path) -> Path:
	"""Create a small analyst workspace with a reusable executable script."""
	source = tmp_path / "analysis"
	for name in ("scripts", "logs", "artifacts", "repo"):
		(source / name).mkdir(parents=True)
	(source / "scripts" / "verify.py").write_text("print('verified')\n")
	(source / "scripts" / "verify.py").chmod(0o755)
	(source / "logs" / "verify.log").write_text("original stdout\n")
	(source / "artifacts" /
	 "verification.json").write_text('{"original":true}')
	(source / "report.md").write_text("Original report")
	(source / "repo" / "config.txt").write_text("repository context")
	return source


@pytest.mark.asyncio
async def test_copy_does_not_overwrite_originals(
        analysis_workspace: Path) -> None:
	"""The same output names in a rerun refer to independent writable files."""
	source = analysis_workspace
	ws = await prepare_challenge_workspace(source, source.parent)
	for relative in ("logs/verify.log", "artifacts/verification.json",
	                 "scripts/verify.py", "report.md"):
		original = source / relative
		copy = ws.working_directory / relative
		assert original.read_bytes() == copy.read_bytes()
		assert original.stat().st_ino != copy.stat().st_ino
		assert not original.stat().st_mode & 0o222
		assert copy.stat().st_mode & stat.S_IWUSR
		copy.write_text("rerun output")
	assert await changed_evidence(ws) == []
	assert (source / "scripts" / "verify.py").stat().st_mode & stat.S_IXUSR
	assert (ws.root / "evidence-manifest.json").is_file()


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation",
                         ["content", "delete", "add", "permissions"])
async def test_detects_original_evidence_changes(
    analysis_workspace: Path,
    mutation: str,
) -> None:
	"""A persistent change remains detectable even if write permissions return."""
	ws = await prepare_challenge_workspace(analysis_workspace,
	                                       analysis_workspace.parent)
	path = analysis_workspace / "artifacts" / "verification.json"
	if mutation == "content":
		path.chmod(0o644)
		path.write_text("changed")
		path.chmod(0o444)
	elif mutation == "permissions":
		path.chmod(0o644)
	else:
		path.parent.chmod(0o755)
		if mutation == "delete":
			path.unlink()
		else:
			path = path.parent / "added.json"
			path.write_text("added")
		path.parent.chmod(0o555)
	assert str(
	    path.relative_to(analysis_workspace)) in await changed_evidence(ws)


@pytest.mark.asyncio
async def test_runtime_directories_are_not_copied_or_locked(
    analysis_workspace: Path, ) -> None:
	"""Existing environments remain available without copying or chmodding them."""
	env = analysis_workspace / "scripts" / "venv"
	env.mkdir()
	(env / "pyvenv.cfg").write_text("home = /example\n")
	external = analysis_workspace.parent / "interpreter"
	external.write_text("not an evidence file")
	(env / "python").symlink_to(external)
	mode = external.stat().st_mode
	ws = await prepare_challenge_workspace(analysis_workspace,
	                                       analysis_workspace.parent)
	assert not (ws.working_directory / "scripts" / "venv").exists()
	assert external.stat().st_mode == mode
	assert env.stat().st_mode & stat.S_IWUSR
	assert await changed_evidence(ws) == []


@pytest.mark.asyncio
async def test_refuses_linked_evidence_without_touching_target(
    analysis_workspace: Path, ) -> None:
	"""A linked evidence file must not cause an external file to be locked."""
	external = analysis_workspace.parent / "external.log"
	external.write_text("outside")
	mode = external.stat().st_mode
	(analysis_workspace / "logs" / "linked.log").symlink_to(external)
	with pytest.raises(ValueError, match="Unsupported evidence entry"):
		await prepare_challenge_workspace(analysis_workspace,
		                                  analysis_workspace.parent)
	assert external.stat().st_mode == mode


@pytest.mark.asyncio
@pytest.mark.parametrize("absolute", [True, False])
async def test_repository_links_point_into_working_copy(
    analysis_workspace: Path,
    absolute: bool,
) -> None:
	"""Repository-local links never point back to writable original content."""
	repo = analysis_workspace / "repo"
	target = repo / "config.txt" if absolute else Path("config.txt")
	(repo / "linked.txt").symlink_to(target)
	ws = await prepare_challenge_workspace(analysis_workspace,
	                                       analysis_workspace.parent)
	link = ws.working_directory / "repo" / "linked.txt"
	assert link.resolve() == ws.working_directory / "repo" / "config.txt"
	link.write_text("rerun context")
	assert (repo / "config.txt").read_text() == "repository context"


@pytest.mark.asyncio
async def test_rejects_external_repository_links(
    analysis_workspace: Path, ) -> None:
	"""External links are not silently followed into the rerun workspace."""
	external = analysis_workspace.parent / "external"
	external.write_text("outside")
	mode = external.stat().st_mode
	(analysis_workspace / "repo" / "linked").symlink_to(external)
	with pytest.raises(ValueError, match="symlink escapes analysis"):
		await prepare_challenge_workspace(analysis_workspace,
		                                  analysis_workspace.parent)
	assert external.stat().st_mode == mode


@pytest.mark.asyncio
async def test_distinct_workspaces_and_invalid_sources(tmp_path: Path) -> None:
	"""Missing sources fail explicitly; repeated challenges never reuse outputs."""
	with pytest.raises(ValueError, match="not a real directory"):
		await prepare_challenge_workspace(tmp_path / "missing", tmp_path)
	source = tmp_path / "analysis"
	source.mkdir()
	with pytest.raises(ValueError, match="outside the analysis"):
		await prepare_challenge_workspace(source, source / "nested")
	first = await prepare_challenge_workspace(source, tmp_path)
	second = await prepare_challenge_workspace(source, tmp_path)
	assert first.root != second.root
	assert await changed_evidence(first) == []


class LocalSession:
	"""Exercise the real runner while replacing only the model transport."""

	def __init__(self, client: LocalClient, settings: dict[str, Any]) -> None:
		"""Retain the operation and event callback supplied to this session."""
		self.client = client
		self.settings = settings
		self.disconnected = False
		self.prompt = ""

	async def send_and_wait(self, prompt: str, *,
	                        timeout: float) -> SimpleNamespace:
		"""Perform the test operation and return a fixed model response."""
		self.prompt = prompt
		if self.client.operation:
			await self.client.operation(
			    Path(self.settings["working_directory"]))
		content = '{"verdict":"CONFIRMED","reasoning":"Matched the evidence"}'
		self.settings["on_event"](SimpleNamespace(
		    type=SessionEventType.ASSISTANT_MESSAGE,
		    data=SimpleNamespace(content=content),
		))
		return SimpleNamespace(data=SimpleNamespace(content=content))

	async def disconnect(self) -> None:
		"""Record shutdown before integrity checks run."""
		self.disconnected = True

	async def abort(self) -> None:
		"""Allow the runner's timeout path to complete."""

	async def get_events(self) -> list:
		"""No retained events exist beyond the callback used in this test."""
		return []


class LocalClient:
	"""Create offline sessions that can execute a bounded local fixture."""

	def __init__(
	    self,
	    operation: Callable[[Path], Awaitable[None]] | None = None,
	) -> None:
		"""Accept an optional operation performed instead of model inference."""
		self.operation = operation
		self.sessions: list[LocalSession] = []

	async def create_session(self, **settings: Any) -> LocalSession:
		"""Capture the real session configuration without launching a CLI."""
		session = LocalSession(self, settings)
		self.sessions.append(session)
		return session


async def _challenge(source: Path, client: LocalClient) -> ChallengeResult:
	"""Challenge a fixture through the production runner."""
	return await run_single_challenge(
	    client,
	    Config(SHOW_USAGE=True),
	    load_agent("agents/challenger.agent.md"),
	    AgentRunResult(run_id="0", workspace=str(source),
	                   raw_markdown="Report"),
	    RunParams(org_repo="org/repo", alert_id="1"),
	    0,
	    alert_dir=source.parent,
	)


@pytest.mark.asyncio
async def test_real_rerun_retains_separate_evidence(
        analysis_workspace: Path) -> None:
	"""A real subprocess overwrites the copy's artifact, never the analyst's."""
	script = analysis_workspace / "scripts" / "verify.py"
	script.write_text(
	    "from pathlib import Path\n"
	    "root = Path(__file__).resolve().parents[1]\n"
	    "(root / 'artifacts' / 'verification.json').write_text('rerun artifact')\n"
	    "print('real rerun stdout')\n")
	original_script = script.read_bytes()

	async def execute(working: Path) -> None:
		"""Run only this local, network-free verification fixture."""
		process = await asyncio.create_subprocess_exec(
		    sys.executable, str(working / "scripts" / "verify.py"),
		    cwd=working, stdout=asyncio.subprocess.PIPE,
		    stderr=asyncio.subprocess.STDOUT)
		stdout, _ = await process.communicate()
		assert process.returncode == 0
		(working / "logs" / "rerun.log").write_bytes(stdout)

	client = LocalClient(execute)
	result = await _challenge(analysis_workspace, client)
	root = Path(result.workspace)
	assert result.verdict == "CONFIRMED"
	assert root.parent == analysis_workspace.parent / "challenges"
	assert client.sessions[0].disconnected
	assert script.read_bytes() == original_script
	assert (analysis_workspace / "artifacts" /
	        "verification.json").read_text() == '{"original":true}'
	assert (root / "work" / "artifacts" /
	        "verification.json").read_text() == "rerun artifact"
	assert (root / "work" / "logs" /
	        "rerun.log").read_text() == "real rerun stdout\n"
	assert (root / "stream.log").is_file()
	saved = json.loads((root / "result.json").read_text())
	assert saved["verdict"] == "CONFIRMED"
	assert saved["workspace"] == str(root)
	assert saved["usage"] is not None
	assert "{{workspace_path}}" not in client.sessions[0].prompt
	assert "{{challenge_workspace_path}}" not in client.sessions[0].prompt


@pytest.mark.asyncio
async def test_modified_original_cannot_be_confirmed(
        analysis_workspace: Path) -> None:
	"""Host integrity checks override a model's confirmation after mutation."""

	async def mutate(working: Path) -> None:
		"""Simulate a same-user writer changing a protected fixture."""
		path = analysis_workspace / "artifacts" / "verification.json"
		path.chmod(0o644)
		path.write_text("modified original")
		path.chmod(0o444)

	result = await _challenge(analysis_workspace, LocalClient(mutate))
	assert result.verdict == "INSUFFICIENT_EVIDENCE"
	assert "artifacts/verification.json" in result.reasoning
	saved = json.loads((Path(result.workspace) / "result.json").read_text())
	assert saved["verdict"] == "INSUFFICIENT_EVIDENCE"
	assert saved["evidence_gaps"]


@pytest.mark.asyncio
@pytest.mark.parametrize("failure",
                         [RuntimeError, TimeoutError, asyncio.CancelledError])
async def test_session_failure_still_finalizes_evidence(
    analysis_workspace: Path,
    failure: type[BaseException],
) -> None:
	"""Session errors and cancellation cannot leave a confirmed result behind."""

	async def fail(working: Path) -> None:
		"""Stop the fake session without modifying any evidence."""
		raise failure("fixture failure")

	client = LocalClient(fail)
	if failure is asyncio.CancelledError:
		with pytest.raises(asyncio.CancelledError):
			await _challenge(analysis_workspace, client)
	else:
		result = await _challenge(analysis_workspace, client)
		assert result.verdict == "INSUFFICIENT_EVIDENCE"
	assert client.sessions[0].disconnected
	working = Path(client.sessions[0].settings["working_directory"])
	saved = json.loads((working.parent / "result.json").read_text())
	assert saved["verdict"] == "INSUFFICIENT_EVIDENCE"


@pytest.mark.asyncio
async def test_missing_workspace_does_not_start_session(
        tmp_path: Path) -> None:
	"""The runner must not fall back to executing in an unprotected directory."""
	client = LocalClient()
	result = await _challenge(tmp_path / "missing", client)
	assert result.verdict == "INSUFFICIENT_EVIDENCE"
	assert "not a real directory" in result.reasoning
	assert client.sessions == []


@pytest.mark.asyncio
async def test_integrity_read_error_is_not_confirmation(
    analysis_workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""Unreadable evidence is an explicit failure, not a successful comparison."""

	async def unreadable(workspace: Any) -> list[str]:
		"""Simulate losing access after the session finishes."""
		raise PermissionError("fixture unreadable")

	monkeypatch.setattr(
	    "secret_validator_grunt.core.challenge.changed_evidence", unreadable)
	result = await _challenge(analysis_workspace, LocalClient())
	assert result.verdict == "INSUFFICIENT_EVIDENCE"
	assert "Cannot verify original evidence integrity" in result.reasoning


@pytest.mark.asyncio
async def test_parallel_challenges_have_distinct_outputs(
        analysis_workspace: Path) -> None:
	"""Parallel reruns cannot share artifact or stream-log paths."""

	async def write_output(working: Path) -> None:
		"""Write the same relative filename in each independent workspace."""
		(working / "artifacts" / "verification.json").write_text(str(working))

	client = LocalClient(write_output)
	results = await run_challenges(
	    client,
	    Config(ANALYSIS_COUNT=3, MAX_PARALLEL_SESSIONS=3),
	    load_agent("agents/challenger.agent.md"),
	    [
	        AgentRunResult(run_id=str(i), workspace=str(analysis_workspace),
	                       raw_markdown="Report") for i in range(3)
	    ],
	    RunParams(org_repo="org/repo", alert_id="1"),
	    alert_dir=analysis_workspace.parent,
	)
	assert len({r.workspace for r in results}) == 3
	for result in results:
		assert result.verdict == "CONFIRMED"
		root = Path(result.workspace)
		assert (root / "work" / "artifacts" /
		        "verification.json").read_text() == str(root / "work")
		assert (root / "stream.log").is_file()
	assert (analysis_workspace / "artifacts" /
	        "verification.json").read_text() == '{"original":true}'


@pytest.mark.asyncio
async def test_hardlinked_evidence_does_not_change_external_permissions(
    analysis_workspace: Path, ) -> None:
	"""Locking a shared inode would also chmod files outside this workspace."""
	external = analysis_workspace.parent / "external"
	external.write_text("outside")
	mode = external.stat().st_mode
	os.link(external, analysis_workspace / "logs" / "shared")
	with pytest.raises(ValueError, match="Hard-linked evidence"):
		await prepare_challenge_workspace(analysis_workspace,
		                                  analysis_workspace.parent)
	assert external.stat().st_mode == mode


@pytest.mark.asyncio
@pytest.mark.parametrize("ignored", [True, False])
async def test_lock_failure_prevents_session(
    analysis_workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
    ignored: bool,
) -> None:
	"""A filesystem that cannot enforce the requested mode must fail preparation."""
	original_chmod = Path.chmod

	def cannot_lock(path: Path, mode: int) -> None:
		"""Simulate unsupported permissions or a denied chmod."""
		if path == analysis_workspace / "scripts":
			if ignored:
				return
			raise PermissionError("fixture lock denied")
		original_chmod(path, mode)

	monkeypatch.setattr(Path, "chmod", cannot_lock)
	client = LocalClient()
	result = await _challenge(analysis_workspace, client)
	assert result.verdict == "INSUFFICIENT_EVIDENCE"
	assert client.sessions == []
	assert "read-only" in result.reasoning or "lock denied" in result.reasoning


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.name != "posix" or os.geteuid() == 0,
    reason="Read-only mode enforcement requires an unprivileged POSIX user",
)
async def test_absolute_output_is_blocked_until_copy_is_adapted(
    analysis_workspace: Path, ) -> None:
	"""An absolute original output path fails; adapting only the copy succeeds."""
	output = analysis_workspace / "artifacts" / "verification.json"
	script = analysis_workspace / "scripts" / "verify.py"
	text = ("from pathlib import Path\n"
	        f"Path({str(output)!r}).write_text('rerun')\n")
	script.write_text(text)
	ws = await prepare_challenge_workspace(analysis_workspace,
	                                       analysis_workspace.parent)
	copy = ws.working_directory / "scripts" / "verify.py"

	async def execute() -> tuple[int, bytes]:
		"""Capture a local fixture's actual exit code and output."""
		process = await asyncio.create_subprocess_exec(
		    sys.executable, str(copy), cwd=ws.working_directory,
		    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
		stdout, _ = await process.communicate()
		assert process.returncode is not None
		return process.returncode, stdout

	code, stdout = await execute()
	assert code != 0
	assert b"PermissionError" in stdout
	rerun_output = ws.working_directory / "artifacts" / "verification.json"
	copy.write_text(text.replace(str(output), str(rerun_output)))
	code, _ = await execute()
	assert code == 0
	assert rerun_output.read_text() == "rerun"
	assert script.read_text() == text
	assert output.read_text() == '{"original":true}'
	assert await changed_evidence(ws) == []


@pytest.mark.asyncio
async def test_persistence_failure_is_explicit(
        analysis_workspace: Path) -> None:
	"""An unwritable result destination must not return a successful verdict."""

	async def block_result(working: Path) -> None:
		"""Create an incompatible destination for the host result."""
		(working.parent / "result.json").mkdir()

	result = await _challenge(analysis_workspace, LocalClient(block_result))
	assert result.verdict == "INSUFFICIENT_EVIDENCE"
	assert "Cannot persist challenge result" in result.reasoning
