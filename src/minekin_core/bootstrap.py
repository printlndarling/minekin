"""Process bootstrap and CLI exit-code mapping."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from minekin_core.adapters.evidence.trace import replay_sealed_bundle
from minekin_core.adapters.launcher.artifacts import STORE_DIRECTORY, ArtifactStore
from minekin_core.adapters.launcher.fetch import ArtifactFetcher
from minekin_core.adapters.launcher.launch_plan import build_launch_plan
from minekin_core.adapters.launcher.provision import (
    missing_artifacts,
    plan_fetch_set,
    provision_bundle,
    require_reviewed_plan,
    reviewed_entry,
)
from minekin_core.adapters.system.clock import SystemClock
from minekin_core.application.autonomous_play import (
    DEFAULT_STEP_BUDGET,
    MAX_STEP_BUDGET,
    AutonomousAsk,
)
from minekin_core.application.player_mind import SKILL_OFFER
from minekin_core.application.skill_plan import (
    SkillPlan,
    SkillPlanError,
    parse_skill_plan,
)
from minekin_core.cli.auto_session import (
    AutoBundleDecision,
    prepare_auto_bundle_start,
    require_spendable_budget,
)
from minekin_core.cli.doctor import diagnose
from minekin_core.cli.evidence import verify_run
from minekin_core.cli.init import initialise_identity
from minekin_core.cli.parser import parse_args
from minekin_core.cli.persona import persona_report
from minekin_core.cli.rename import RENAME_NOTICE, rename_identity, show_identity
from minekin_core.cli.server_probe import probe_exit_ok, run_probe
from minekin_core.cli.session import (
    DEFAULT_CONNECTION_TIMEOUT_S,
    DEFAULT_HANDSHAKE_TIMEOUT_S,
    DEFAULT_SKILL_STEP_TIMEOUT_S,
    run_root,
    select_kin,
    start_and_supervise,
    stop_session,
)
from minekin_core.cli.session_runtime import SessionOutcome, SessionRun
from minekin_core.cli.status import ObservedState, read_status
from minekin_core.config import (
    configured_persona_seed,
    configured_username,
    data_root,
    forwarded_environment,
    java_executable,
    kin_selector,
    load_local_environment,
)
from minekin_core.domain.errors import (
    ErrorCategory,
    ExitCode,
    MinekinError,
    Retryability,
    fail_closed,
)
from minekin_core.domain.ids import KinId, SessionId
from minekin_core.domain.model_access import model_config
from minekin_core.domain.operator_config import (
    apply_operator_config,
    config_path,
    load_operator_config,
)

# A run that ended because the client left is the command succeeding; anything
# else is why it did not.
_OUTCOME_EXIT_CODES: dict[SessionOutcome, ExitCode] = {
    SessionOutcome.CLIENT_EXITED: ExitCode.OK,
    # A stop we honored and released over a live channel: the run ended as asked, so
    # it is the command succeeding — not the IPC-protocol fault that a genuine bridge
    # loss carries. Reporting it as 14 would call a normal stop a contract break.
    SessionOutcome.STOPPED_ON_REQUEST: ExitCode.OK,
    SessionOutcome.BRIDGE_LOST: ExitCode.IPC_PROTOCOL,
    SessionOutcome.HANDSHAKE_FAILED: ExitCode.IPC_PROTOCOL,
    SessionOutcome.HANDSHAKE_TIMEOUT: ExitCode.TIMEOUT,
}


def _exit_code_for(run: SessionRun) -> ExitCode:
    return _OUTCOME_EXIT_CODES[run.outcome]


def _command_name(args: argparse.Namespace) -> str:
    parts = [str(args.command)]
    for attribute in (
        "bundle_command",
        "session_command",
        "server_command",
        "evidence_command",
        "identity_command",
    ):
        value = getattr(args, attribute, None)
        if value is not None:
            parts.append(str(value))
    return " ".join(parts)


def _emit(value: object, stream: TextIO) -> None:
    print(json.dumps(value, sort_keys=True), file=stream)


def _install_store_root(explicit: str | None) -> Path:
    """The store `session start` will read, unless one is named outright.

    One store root per Kin, because that is where the plan's store paths live
    today; an install into a different root would fill a cache nothing reads.
    """

    if explicit is not None:
        return Path(explicit).resolve()
    root = data_root()
    return run_root(root, select_kin(root, kin_selector())) / STORE_DIRECTORY


def _target_kin(root: Path, kin_id_arg: str | None) -> KinId:
    """The Kin an identity command acts on: named outright, or this root's only Kin."""

    if kin_id_arg is not None:
        try:
            return KinId(str(kin_id_arg))
        except ValueError as error:
            raise MinekinError(
                "cli",
                "identity",
                ErrorCategory.CONFIG,
                Retryability.OPERATOR_ACTION,
                f"--kin-id is not a usable identifier: {error}",
            ) from error
    return select_kin(root, kin_selector())


def _identity_rename(args: argparse.Namespace, *, stdout: TextIO, stderr: TextIO) -> int:
    """Rename a stopped Kin's identity, behind confirmation and a live-session guard.

    Both gates come before anything is written. Without `--confirm` the command is
    a request that has not yet accepted the UUID consequence, so it answers with
    the consequence and changes nothing. A Kin whose session the host can see
    running is refused outright — a rename landing under a live client would
    strand that client on an identity the ledger no longer holds.
    """

    root = data_root()
    kin_id = _target_kin(root, args.kin_id)

    if not args.confirm:
        _emit(
            {
                "schema_version": 1,
                "command": "identity rename",
                "status": "confirmation_required",
                "kin_id": str(kin_id),
                "reason": "RENAME_NOT_CONFIRMED",
                "message": RENAME_NOTICE,
            },
            stderr,
        )
        return int(ExitCode.USAGE)

    observed = read_status(root, kin_selector=str(kin_id))
    if observed.state is not ObservedState.IDLE:
        _emit(
            {
                "schema_version": 1,
                "command": "identity rename",
                "status": "refused",
                "kin_id": str(kin_id),
                "reason": "SESSION_NOT_STOPPED",
                "state": observed.state.value,
                "message": "this Kin's session is not stopped; stop it before renaming so "
                "no live client is left on an identity the ledger no longer holds",
            },
            stderr,
        )
        return int(ExitCode.CONTROL_SAFETY)

    report = rename_identity(
        kin_id,
        root=root,
        username=str(args.username),
        expected_revision=(None if args.expected_revision is None else int(args.expected_revision)),
    )
    _emit(report.as_dict(), stdout)
    return int(ExitCode.OK)


def _skill_plan_inputs(args: argparse.Namespace) -> tuple[SkillPlan | None, float]:
    """Read `--skill-plan` and `--skill-step-seconds` into the session's two arguments.

    The file is opened here, at the edge, and an unusable one is refused here: a
    plan is an operator's document and a typo in it is theirs to fix, so the
    answer has to come back before a client is started for it. The parse's own
    words are kept, because they already name which entry and which field.
    """

    path = args.skill_plan
    plan = None
    if path is not None:
        try:
            document = json.loads(Path(path).read_text(encoding="utf-8"))
            plan = parse_skill_plan(document, source=str(path))
        except (OSError, ValueError, SkillPlanError) as error:
            raise MinekinError(
                "cli",
                "session start",
                ErrorCategory.CONFIG,
                Retryability.OPERATOR_ACTION,
                f"--skill-plan is not a usable plan: {error}",
            ) from error
    step_seconds = (
        DEFAULT_SKILL_STEP_TIMEOUT_S
        if args.skill_step_seconds is None
        else float(args.skill_step_seconds)
    )
    return plan, step_seconds


def _autonomous_ask(args: argparse.Namespace, skill_step_seconds: float) -> AutonomousAsk | None:
    """Read `--autonomous` into the ask that replaces a plan.

    The offered set is the shipped one rather than something an operator re-picks
    per run: what this flag bounds is how many times the Kin may change its mind,
    not which skills exist, and an offer the lease never covered would be refused
    mid-run by the arbiter.

    The model configuration is read here, before the run resolves anything, and
    left unread otherwise. A half-entered provider is the operator's to fix, and a
    run that finds out only after it has launched a client has spent a world to
    say what an environment variable already did.
    """

    if args.autonomous_steps is not None and not args.autonomous:
        raise MinekinError(
            "cli",
            "session start",
            ErrorCategory.CONFIG,
            Retryability.OPERATOR_ACTION,
            "--autonomous-steps is only meaningful with --autonomous",
        )
    if not args.autonomous:
        return None
    steps = DEFAULT_STEP_BUDGET if args.autonomous_steps is None else int(args.autonomous_steps)
    if not 1 <= steps <= MAX_STEP_BUDGET:
        # The same refusal the session's own guard gives, made here as well so the
        # ask that is built is always one a lease can keep; a soak that outlasts
        # several compressed day cycles is still a number the operator names.
        raise MinekinError(
            "cli",
            "session start",
            ErrorCategory.CONFIG,
            Retryability.OPERATOR_ACTION,
            f"--autonomous-steps must be between 1 and {MAX_STEP_BUDGET}",
        )
    config = model_config()
    return AutonomousAsk(
        skills=SKILL_OFFER,
        step_budget=steps,
        step_seconds=skill_step_seconds,
        decision_seconds=config.timeout_ms / 1000.0 if config.enabled else 0.0,
    )


def _boot_mode_line(decision: AutoBundleDecision) -> str:
    """One stderr line naming what kind of start this was, from the fetch counts.

    A cold first prepare and a warm cache reuse look identical from outside while the
    store is being filled; naming the mode turns a silent multi-minute download into
    feedback the operator can read, without collapsing the two into one acceptance.
    """

    if decision.boot_mode == "cache_hit":
        return (
            f"client ready from cache: reused {decision.reused} of {decision.fetch_set} artifacts"
        )
    return (
        f"first prepare: fetched {decision.installed}, reused {decision.reused} "
        f"of {decision.fetch_set} artifacts ({decision.boot_mode})"
    )


def _session_start_auto(args: argparse.Namespace, *, stdout: TextIO, stderr: TextIO) -> int:
    """`session start --auto-bundle`: resolve the target, then launch what it resolved to.

    The deciding itself lives in `cli.auto_session` so every refusal is reachable without
    a JVM. What is added here is only the hand-off: the recipe the reviewed registry named
    takes the place of the one the operator typed, and the launch is the same
    `start_and_supervise` call the explicit `--profile` path makes.
    """

    if args.server_profile is None:
        # The freeze answers this with `USAGE` rather than a configuration error, and
        # the difference is real: no input document is wrong, the operator simply did
        # not say which world to resolve a bundle against. `ErrorCategory` has no
        # `USAGE` member, so the refusal is a printed document plus the exit code,
        # the way a command that is not implemented answers.
        _emit(
            {
                "schema_version": 1,
                "status": "usage",
                "command": "session start --auto-bundle",
                "message": "an automatic bundle start needs --server-profile: with no "
                "target there is no observation to resolve a bundle from",
            },
            stderr,
        )
        return int(ExitCode.USAGE)
    root = data_root()
    selector = kin_selector()

    def progress(done: int, total: int) -> None:
        # stdout stays one document. A fill of thousands of artifacts is long enough to
        # be worth reading while it happens, and the session's own report still comes
        # back at the end unchanged.
        if done == total or done % 100 == 0:
            print(f"fetching {done}/{total}", file=stderr, flush=True)

    # Read before the fetch: an unusable plan should not be discovered after
    # thousands of artifacts have already been pulled down for a run that cannot
    # start.
    skill_plan, skill_step_seconds = _skill_plan_inputs(args)
    autonomous = _autonomous_ask(args, skill_step_seconds)
    decision = prepare_auto_bundle_start(
        registry_path=Path(args.auto_bundle),
        server_profile=Path(args.server_profile),
        run_root=run_root(root, select_kin(root, selector)),
        max_bytes=None if args.max_bytes is None else int(args.max_bytes),
        on_progress=progress,
    )
    # The fetch lines above say how much was downloaded; this says what kind of start
    # it was, so a long first prepare is not read as a hang and a warm one is not read
    # as a fresh download. stdout still carries only the one final document.
    print(_boot_mode_line(decision), file=stderr, flush=True)
    launch, session_run = asyncio.run(
        start_and_supervise(
            root=root,
            profile=decision.recipe,
            java_executable=java_executable(),
            session_id=SessionId.new().value,
            generation=1,
            kin_selector=selector,
            forward_environment=forwarded_environment(),
            server_profile=Path(args.server_profile),
            handshake_timeout=(
                DEFAULT_HANDSHAKE_TIMEOUT_S
                if args.handshake_timeout_seconds is None
                else float(args.handshake_timeout_seconds)
            ),
            connection_timeout=(
                DEFAULT_CONNECTION_TIMEOUT_S
                if args.connection_timeout_seconds is None
                else float(args.connection_timeout_seconds)
            ),
            hold_forward=(
                None if args.hold_forward_seconds is None else float(args.hold_forward_seconds)
            ),
            hold_use=(None if args.hold_use_seconds is None else float(args.hold_use_seconds)),
            hold_strafe=(None if args.hold_strafe is None else float(args.hold_strafe)),
            hold_jump=bool(args.hold_jump),
            hold_sneak=bool(args.hold_sneak),
            hold_at=str(args.hold_at),
            look_yaw_degrees=(
                None if args.look_yaw_degrees is None else float(args.look_yaw_degrees)
            ),
            look_pitch_degrees=(
                None if args.look_pitch_degrees is None else float(args.look_pitch_degrees)
            ),
            world_save=(None if args.world_save is None else Path(args.world_save)),
            world_name=(None if args.world_name is None else str(args.world_name)),
            identity_candidate=(
                None if args.identity_candidate is None else str(args.identity_candidate)
            ),
            open_lan=bool(args.open_lan),
            open_lan_port=int(args.open_lan_port),
            skill_plan=skill_plan,
            skill_step_seconds=skill_step_seconds,
            autonomous=autonomous,
        )
    )
    _emit(
        {**launch.as_dict(), "auto_bundle": decision.as_document(), "run": session_run.as_dict()},
        stdout,
    )
    return int(_exit_code_for(session_run))


def _bundle_install(args: argparse.Namespace, *, stdout: TextIO, stderr: TextIO) -> int:
    """Fetch one reviewed tested entry into the store, under an explicit budget."""

    # The same named budget rule the automatic start answers under, before this entry
    # reads the registry or rebuilds a plan: a non-positive number is refused by name,
    # not by the installer's invariant crashing the CLI (A2 §3.2 N2).
    require_spendable_budget(int(args.max_bytes), operation="bundle install")
    entry = reviewed_entry(Path(args.registry), str(args.bundle_id))
    root = _install_store_root(args.store)
    store = ArtifactStore(root)
    plan = require_reviewed_plan(entry)
    artifacts = plan_fetch_set(plan)
    missing = missing_artifacts(plan, store)

    # The job is reported before it is paid for, and the same document comes back
    # either way, so a refusal names the plan it was refusing.
    summary: dict[str, object] = {
        "schema_version": 1,
        "command": _command_name(args),
        "bundle_id": entry.bundle_id,
        "store": str(root),
        "plan_sha256": plan["plan_sha256"],
        "artifacts": len(artifacts),
        "missing": len(missing),
        "missing_bytes": sum(artifact.size for artifact in missing),
        "max_bytes": int(args.max_bytes),
        "jobs": int(args.jobs),
    }
    if args.dry_run:
        _emit({**summary, "status": "planned"}, stdout)
        return int(ExitCode.OK)

    quiet = bool(args.quiet)

    def progress(done: int, total: int) -> None:
        # stdout stays one document; a run of thousands of artifacts is long
        # enough that it has to be legible while it happens.
        if not quiet and (done == total or done % 100 == 0):
            print(f"fetching {done}/{total}", file=stderr, flush=True)

    report = provision_bundle(
        plan,
        store,
        fetcher=ArtifactFetcher(store, jobs=int(args.jobs)),
        max_bytes=int(args.max_bytes),
        on_progress=progress,
    )
    _emit({**summary, **report.as_dict()}, stdout)
    return int(ExitCode.OK if report.complete else ExitCode.SUPPLY_CHAIN)


def run(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    """Parse and execute one CLI command.

    Commands that are frozen but not implemented fail before reading their path
    arguments or creating persistent state, and say so on stderr.
    """

    args = parse_args(argv)
    if args.command == "doctor":
        report = diagnose()
        _emit(report.as_dict(), stdout)
        return int(ExitCode.OK if report.ok else ExitCode.CONFIG)

    if args.command == "init":
        try:
            kin_id = KinId(str(args.kin_id))
        except ValueError as error:
            raise MinekinError(
                "cli",
                "init",
                ErrorCategory.CONFIG,
                Retryability.OPERATOR_ACTION,
                f"--kin-id is not a usable identifier: {error}",
            ) from error
        report = initialise_identity(
            kin_id,
            root=data_root(),
            username=configured_username(),
            clock=SystemClock(),
            persona_seed=configured_persona_seed(),
        )
        _emit(report.as_dict(), stdout)
        return int(ExitCode.OK)

    if args.command == "identity" and args.identity_command == "show":
        root = data_root()
        view = show_identity(root, _target_kin(root, args.kin_id))
        _emit(
            {"schema_version": 1, "command": "identity show", "status": "ok", **view.as_dict()},
            stdout,
        )
        return int(ExitCode.OK)

    if args.command == "identity" and args.identity_command == "rename":
        return _identity_rename(args, stdout=stdout, stderr=stderr)

    if args.command == "persona" and args.persona_command == "show":
        root = data_root()
        _emit(persona_report(root, _target_kin(root, args.kin_id)), stdout)
        return int(ExitCode.OK)

    if args.command == "session" and args.session_command == "start":
        if args.auto_bundle is not None:
            return _session_start_auto(args, stdout=stdout, stderr=stderr)
        if args.max_bytes is not None:
            # A2 §3.2 N2: beside `--profile` the budget used to be accepted and then
            # silently ignored, even though the help text says it belongs to
            # `--auto-bundle`. The two ways to say which client to run are exclusive,
            # so this is a request that named two entries: answer it as a usage
            # mistake, by name, before any profile is read and before a JVM exists.
            _emit(
                {
                    "schema_version": 1,
                    "status": "usage",
                    "command": "session start --profile",
                    "reason": "MAX_BYTES_WITHOUT_AUTO_BUNDLE",
                    "message": "--max-bytes only bounds what --auto-bundle may fetch; "
                    "with --profile the recipe is named outright and there is no "
                    "automatic fill to budget. The two entries exclude each other: to "
                    "run under a budget say `session start --auto-bundle <registry> "
                    "--max-bytes N`; to run the named recipe drop --max-bytes.",
                },
                stderr,
            )
            return int(ExitCode.USAGE)
        skill_plan, skill_step_seconds = _skill_plan_inputs(args)
        autonomous = _autonomous_ask(args, skill_step_seconds)
        launch, run = asyncio.run(
            start_and_supervise(
                root=data_root(),
                profile=Path(args.profile),
                java_executable=java_executable(),
                session_id=SessionId.new().value,
                generation=1,
                kin_selector=kin_selector(),
                # Resolved here, at the edge, the way the data root and Java
                # are: what the host is willing to lend the client is the
                # operator's environment, and the list of what may be lent is
                # the code's.
                forward_environment=forwarded_environment(),
                server_profile=(None if args.server_profile is None else Path(args.server_profile)),
                handshake_timeout=(
                    DEFAULT_HANDSHAKE_TIMEOUT_S
                    if args.handshake_timeout_seconds is None
                    else float(args.handshake_timeout_seconds)
                ),
                connection_timeout=(
                    DEFAULT_CONNECTION_TIMEOUT_S
                    if args.connection_timeout_seconds is None
                    else float(args.connection_timeout_seconds)
                ),
                hold_forward=(
                    None if args.hold_forward_seconds is None else float(args.hold_forward_seconds)
                ),
                hold_use=(None if args.hold_use_seconds is None else float(args.hold_use_seconds)),
                hold_strafe=(None if args.hold_strafe is None else float(args.hold_strafe)),
                hold_jump=bool(args.hold_jump),
                hold_sneak=bool(args.hold_sneak),
                hold_at=str(args.hold_at),
                look_yaw_degrees=(
                    None if args.look_yaw_degrees is None else float(args.look_yaw_degrees)
                ),
                look_pitch_degrees=(
                    None if args.look_pitch_degrees is None else float(args.look_pitch_degrees)
                ),
                world_save=(None if args.world_save is None else Path(args.world_save)),
                world_name=(None if args.world_name is None else str(args.world_name)),
                identity_candidate=(
                    None if args.identity_candidate is None else str(args.identity_candidate)
                ),
                open_lan=bool(args.open_lan),
                open_lan_port=int(args.open_lan_port),
                skill_plan=skill_plan,
                skill_step_seconds=skill_step_seconds,
                autonomous=autonomous,
            )
        )
        _emit({**launch.as_dict(), "run": run.as_dict()}, stdout)
        return int(_exit_code_for(run))

    if args.command == "session" and args.session_command == "status":
        report = read_status(data_root(), kin_selector=kin_selector())
        _emit(report.as_dict(), stdout)
        return int(ExitCode.OK)

    if args.command == "session" and args.session_command == "stop":
        stopped = stop_session(data_root(), kin_selector=kin_selector())
        _emit(stopped.as_dict(), stdout)
        return int(ExitCode.OK if stopped.outcome.complete else ExitCode.PROCESS)

    if args.command == "launch-plan":
        _emit(build_launch_plan(Path(args.profile)), stdout)
        return int(ExitCode.OK)

    if args.command == "bundle" and args.bundle_command == "verify":
        plan = build_launch_plan(Path(args.profile))
        _emit(
            {
                "schema_version": 1,
                "status": "valid_recipe",
                "launchable": plan["launchable"],
                "blockers": plan["blockers"],
                "plan_sha256": plan["plan_sha256"],
            },
            stdout,
        )
        return int(ExitCode.OK)

    if args.command == "bundle" and args.bundle_command == "install":
        return _bundle_install(args, stdout=stdout, stderr=stderr)

    if args.command == "server" and args.server_command == "probe":
        # A probe's answer is an observation, not a failure: an endpoint that
        # refused, timed out or contradicted itself still gets a document on
        # stdout. The exit code only says whether a version was actually read —
        # anything else is an admission problem a script branches on.
        observation = run_probe(
            Path(args.server_profile),
            timeout_s=float(args.timeout_seconds),
        )
        _emit({**observation.as_document(), "command": _command_name(args)}, stdout)
        return int(ExitCode.OK if probe_exit_ok(observation) else ExitCode.ADMISSION)

    if args.command == "evidence" and args.evidence_command == "verify":
        # Whether a bundle holds up is not a reason the command failed, so it
        # gets its own exit code rather than an error: the report on stdout is
        # the answer, and the code is what a script branches on.
        verification = verify_run(data_root(), args.run_id)
        _emit(verification.as_dict(), stdout)
        return int(ExitCode.OK if verification.verified else ExitCode.STORAGE)

    if args.command == "replay":
        # Which of the two rejections this was is the report's own answer: a bundle
        # whose bytes are not the ones that were sealed is a STORAGE problem, and a
        # bundle that holds up and records no session history is a SESSION one. The
        # exit code is the category, so a script can branch on it without reading the
        # document — and the reading itself is not this file's, it is the adapter's.
        replay = replay_sealed_bundle(Path(args.evidence_dir))
        _emit({**replay.as_dict(), "command": _command_name(args)}, stdout)
        return int(replay.exit_code)

    command = _command_name(args)
    _emit(
        {
            "schema_version": 1,
            "status": "not_implemented",
            "command": command,
            "message": "command is frozen but not implemented in W00",
        },
        stderr,
    )
    return int(ExitCode.USAGE)


def apply_persisted_config() -> None:
    """Fold the dashboard-saved settings into the environment before any reader sees it.

    The operator may have configured the model and the standing goal from the dashboard rather
    than the shell, and those live in `operator-config.json` under the data root. This is the one
    place that file is read into the running process, and it runs after `load_local_environment`
    so the precedence stays a single chain: a name the operator exported in the shell wins, then
    one the `.env` file carried, then one only the saved document holds. No data root or no
    document is simply nothing to fold in — not a fault — so a version query, or a machine with no
    `MINEKIN_HOME` yet, still runs. A document that exists but will not parse is a different
    thing: the operator saved settings they believe are live, so it raises rather than running on
    a guess. Only the applied *names* are known here and none are said aloud, because a name that
    went in is a value that can be printed.

    This folds in configuration only; it never starts, resumes or replays anything. A saved goal
    waits for an explicit `session start` just as a shell-exported one always has.
    """

    try:
        root = data_root()
    except MinekinError:
        return
    if not config_path(root).is_file():
        return
    apply_operator_config(load_operator_config(root))


def main(argv: Sequence[str] | None = None) -> int:
    try:
        # The operator's `.env` is read here and nowhere deeper: a command that
        # runs from the repository picks up the names it carries, while a caller
        # that hands `run` its own environment still sees exactly what it was
        # given. Which names went in is not said aloud, because a name that went
        # in is a value that can be printed.
        load_local_environment()
        apply_persisted_config()
        return run(argv)
    except KeyboardInterrupt:
        return int(ExitCode.INTERRUPTED)
    except SystemExit:
        raise
    except BaseException as error:
        converted = fail_closed(error, component="cli", operation="dispatch")
        _emit(converted.diagnostic(), sys.stderr)
        return int(converted.exit_code)
