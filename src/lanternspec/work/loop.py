"""The facts of an automatic build loop: who may loop, where a loop started, each try at a criterion, what the loop changed.

A loop's results are measured by this module and written to the run log; the agent that builds never states them.
Later steps (wrap-up, the understanding-debt card, the retrospective) read these lines, not the setting in lantern.yaml,
which only says what the person wanted.

Responsibilities:
    - tell whether a work may loop: every acceptance criterion has a committed test, and a test command exists
    - start a loop: keep the settings, the content of the tests that judge it and the number of tests that ran before it
    - run one criterion's test (`build.test_one`, else the whole suite) and write the try
    - end a round: run the whole suite and say passed · failed · invalid
    - catch what makes a pass invalid: a linked test or a test settings file changed, or fewer tests ran
    - refuse more tries once the loop stopped, and a second loop for the same work unless the person says so
    - read back what the run log says about a work's loop

Not here:
    - the format of the run log lines → tools/runlog.py
    - suggesting how to build → report/build_mode.py
    - the commands → cli/work.py
"""

from __future__ import annotations

import hashlib
import re
import shlex
import subprocess
import uuid
from dataclasses import dataclass, field
from typing import Any

from ..core.messages import msg
from ..core.project import Project, git_out, read
from ..core.taskfile import Criterion, parse_criteria, parse_tasks
from . import stages

TEST_TIMEOUT = 900  # seconds one test command may run
TIMED_OUT, NOT_FOUND = 124, 127  # exit codes of a command that did not get to run its tests (shell conventions)
NOT_RUN = {TIMED_OUT, 126, NOT_FOUND}
MODE_LOOP, MODE_EACH = "loop", "each"  # the loop runs · the work goes on with a check after each task
PASS, FAIL, LIMIT = "pass", "fail", "limit"  # how a try ends (LIMIT: not run, the same criterion already failed too often)
PASSED, FAILED, INVALID = "passed", "failed", "invalid"  # how a round ends
TAIL_LINES = 15


@dataclass
class Eligibility:
    """Whether a work may build in a loop.

    Attributes:
        ok: Every criterion has a committed test and a test command exists.
        reasons: Why not, one line each in the project's language.
        missing: The criteria without a linked test.
        tests: Criterion → its test as written (`tests/test_login.py::test_wrong_password`).

    Example:
        >>> Eligibility(True, [], [], {"AC-1": "tests/test_a.py"}).ok
        True
    """

    ok: bool
    reasons: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    tests: dict[str, str] = field(default_factory=dict)


@dataclass
class Started:
    """What `start` decided.

    Attributes:
        run: The loop run's ID.
        mode: "loop" when the loop runs, "each" when the work goes on with a check after each task.
        reasons: Why the mode is "each", one line each.
        missing: The criteria without a linked test.
        tests_before: Tests that ran in the whole suite before the loop; None when the output did not say.

    Example:
        >>> Started("a1b2", "each", ["No test command"], [], None).mode
        'each'
    """

    run: str
    mode: str
    reasons: list[str]
    missing: list[str]
    tests_before: int | None


@dataclass
class Tried:
    """One try at one criterion.

    Attributes:
        ac: The criterion.
        attempt: Which try this is, from 1 (the last one made when the try was refused).
        result: "pass" · "fail" · "limit" (refused: it failed too often in a row).
        tail: The end of the test output.
        streak: Failures in a row, this one included; 0 when nothing is judged per criterion (no `build.test_one`).
        limit: How many in a row stop the loop.

    Example:
        >>> Tried("AC-1", 2, "fail", "", 2, 3).result
        'fail'
    """

    ac: str
    attempt: int
    result: str
    tail: str
    streak: int
    limit: int


@dataclass
class Finished:
    """How a round ended.

    Attributes:
        round: Which round of the loop this is, from 1.
        result: "passed" · "failed" · "invalid".
        unpassed: The criteria whose latest try in this run is not a pass.
        violations: What made the pass invalid: dicts of `kind` ("test" · "config" · "count") and `path`.
        tests_before: Tests that ran before the loop.
        tests_after: Tests that ran in this round's whole-suite run.
        tail: The end of the whole-suite output.
        stop: Whether the loop must stop here and hand the work to the person.

    Example:
        >>> Finished(1, "passed", [], [], 10, 12, "", False).stop
        False
    """

    round: int
    result: str
    unpassed: list[str]
    violations: list[dict[str, str]]
    tests_before: int | None
    tests_after: int | None
    tail: str
    stop: bool


@dataclass
class Standing:
    """What the run log says about a work's latest loop.

    Attributes:
        run: The loop run's ID.
        mode: "loop" or "each".
        attempts: How many tries the run holds.
        last_result: How the latest round ended ("passed" · "failed" · "invalid"); "" when no round ended.
        violations: What changed under the loop's tests or test settings, measured now.
        starts: How many times a loop was started for the work.

    Example:
        >>> Standing("a1b2", "loop", 3, "passed", []).attempts
        3
    """

    run: str
    mode: str
    attempts: int
    last_result: str
    violations: list[dict[str, str]]
    starts: int = 1


def unlinked(criteria: list[Criterion]) -> list[str]:
    r"""List the acceptance criteria that have no linked test.

    Args:
        criteria: The criteria of a plan, read with the project's names.

    Returns:
        The IDs, in file order.

    Example:
        >>> from lanternspec.core.names import load
        >>> text = "- [ ] AC-1 하나 [테스트:: tests/a.py]\n- [ ] AC-2 둘"
        >>> unlinked(parse_criteria(text, load("ko")))
        ['AC-2']
    """
    return [c.id for c in criteria if not c.test_file]


def count_tests(output: str) -> int | None:
    r"""Count the tests a test run executed, from the end of its output.

    Reads the summaries of pytest, jest, vitest and unittest (the last one printed). A test tool it cannot read
    gives None, and the check on the number of tests is skipped.

    Args:
        output: What the test command printed.

    Returns:
        The number of tests that ran (passed · failed · errors); None when the output does not say.

    Example:
        >>> count_tests("== 3 failed, 12 passed, 2 skipped in 1.52s ==")
        15
        >>> count_tests("Ran 2 tests in 0.1s\n== 1 passed in 0.30s ==")
        1
        >>> count_tests("Tests:       1 failed, 4 passed, 5 total")
        5
        >>> count_tests("Ran 7 tests in 0.002s")
        7
        >>> count_tests("all fine") is None
        True
    """
    for line in reversed(output.splitlines()):  # pytest: the last line that ends with the run time
        if re.search(r"\bin [\d.]+s\b", line) and re.search(r"\d+ (passed|failed|errors?)\b", line):
            return sum(int(n) for n, _ in re.findall(r"(\d+) (passed|failed|errors?)\b", line))
    for pattern in (r"Tests:\s+.*?(\d+) total", r"^\s*Tests\s+.*\((\d+)\)\s*$", r"Ran (\d+) tests?"):  # jest · vitest · unittest
        if found := re.findall(pattern, output, re.MULTILINE):
            return int(found[-1])
    return None


def command_for(template: str, test: str) -> str:
    """Put a test into the one-test command.

    Args:
        template: `build.test_one`, e.g. "uv run pytest {test}".
        test: The test as written in the criterion; quoted so a path with spaces stays one word.

    Returns:
        The shell command.

    Example:
        >>> command_for("uv run pytest {test}", "tests/test a.py::test_ok")
        "uv run pytest 'tests/test a.py::test_ok'"
    """
    return template.replace("{test}", shlex.quote(test))


def file_hashes(project: Project, patterns: list[str]) -> dict[str, str]:
    """Fingerprint the files the patterns match, so a later look can tell what was edited, made, moved or deleted.

    Args:
        project: The project.
        patterns: Paths or glob patterns relative to the project root (`pytest.ini`, `tests/**/conftest.py`).

    Returns:
        Path → the SHA-1 of its content; only files that exist.

    Example:
        >>> file_hashes(project, ["pytest.ini"])  # doctest: +SKIP
        {'pytest.ini': '5a1f…'}
    """
    out: dict[str, str] = {}
    for pattern in patterns:
        for path in project.root.glob(pattern):
            if path.is_file():
                out[path.relative_to(project.root).as_posix()] = hashlib.sha1(path.read_bytes()).hexdigest()
    return out


def describe(violation: dict[str, str]) -> str:
    """Say in words what made a pass invalid.

    Args:
        violation: One of Finished.violations.

    Returns:
        A line in the project's language.

    Example:
        >>> describe({"kind": "config", "path": "pytest.ini"})  # doctest: +SKIP
        'A test settings file changed: pytest.ini'
    """
    if violation["kind"] == "test":
        return msg("A linked test changed: {path}", path=violation["path"])
    if violation["kind"] == "config":
        return msg("A test settings file changed: {path}", path=violation["path"])
    return msg("Fewer tests ran than before the loop: {path}", path=violation["path"])


# --------------------------------------------------------------------------- reading the work and the run log


def _plan_text(project: Project, work_id: str) -> str:
    folder = project.find_work(work_id, include_archive=False)
    if folder is None:
        raise ValueError(msg("Work in progress {work_id} not found", work_id=work_id))
    plan = project.doc_path(folder, "plan")
    return read(plan) if plan.exists() else ""


def _lines(project: Project, work_id: str) -> list[dict[str, Any]]:
    from ..report.evaluate import load_runs

    return [r for r in load_runs(project) if r.get("kind") in ("loop", "attempt") and r.get("work") == work_id]


def last_start(project: Project, work_id: str) -> dict[str, Any] | None:
    """Find the latest loop start line of a work.

    Args:
        project: The project.
        work_id: E.g. "W-012".

    Returns:
        The start line; None when no loop was started for the work.

    Example:
        >>> last_start(project, "W-012")["mode"]  # doctest: +SKIP
        'loop'
    """
    starts = [r for r in _lines(project, work_id) if r.get("event") == "start"]
    return starts[-1] if starts else None


def _run_lines(project: Project, start: dict[str, Any]) -> list[dict[str, Any]]:
    return [r for r in _lines(project, start["work"]) if r.get("run") == start["run"] and r.get("event") != "start"]


def _stopped(lines: list[dict[str, Any]]) -> bool:
    """Whether the run was told to stop: a round that ended invalid or at its limit, or a criterion at its limit."""
    return any(r.get("stop") or r.get("result") == LIMIT for r in lines)


def _active(project: Project, work_id: str) -> dict[str, Any]:
    start = last_start(project, work_id)
    if start is None or start.get("mode") != MODE_LOOP:
        raise ValueError(msg("No loop is running for {work_id} — run `lantern loop start {work_id}` first", work_id=work_id))
    if _stopped(_run_lines(project, start)):
        raise ValueError(
            msg(
                "The loop for {work_id} has stopped — hand it to the person (another loop needs `lantern loop start {work_id} --again`)",
                work_id=work_id,
            )
        )
    return start


def _latest(lines: list[dict[str, Any]]) -> dict[str, str]:
    """Criterion → the result of its latest try that actually ran."""
    out: dict[str, str] = {}
    for r in lines:
        if r.get("kind") == "attempt" and r.get("result") != LIMIT:
            out[r["ac"]] = r["result"]
    return out


def _streak(tries: list[dict[str, Any]]) -> int:
    n = 0
    for r in reversed([x for x in tries if x.get("result") != LIMIT]):
        if r["result"] != FAIL:
            break
        n += 1
    return n


def standing(project: Project, work_id: str) -> Standing | None:
    """Read how a work's latest loop stands, measuring what changed under its tests now.

    Args:
        project: The project.
        work_id: E.g. "W-012".

    Returns:
        The standing; None when no loop was started for the work.

    Example:
        >>> standing(project, "W-012").last_result  # doctest: +SKIP
        'passed'
    """
    start = last_start(project, work_id)
    if start is None:
        return None
    lines = _run_lines(project, start)
    ends = [r for r in lines if r.get("event") == "end"]
    starts = sum(1 for r in _lines(project, work_id) if r.get("event") == "start" and r.get("mode") == MODE_LOOP)
    return Standing(
        run=start["run"],
        mode=start.get("mode", ""),
        attempts=sum(1 for r in lines if r.get("kind") == "attempt"),
        last_result=ends[-1]["result"] if ends else "",
        violations=changed(project, start) if start.get("mode") == MODE_LOOP else [],
        starts=starts,
    )


def built_by_loop(project: Project, work_id: str) -> bool:
    """Tell whether a work was built by a loop: one ran and tried at least one criterion.

    Args:
        project: The project.
        work_id: E.g. "W-012".

    Returns:
        True when the run log holds a loop start for the work and a try after it.

    Example:
        >>> built_by_loop(project, "W-012")  # doctest: +SKIP
        True
    """
    s = standing(project, work_id)
    return s is not None and s.mode == MODE_LOOP and s.attempts > 0


def doubts(project: Project, work_id: str) -> list[str]:
    """Say where a work's loop record and the settings disagree, or where the loop's pass does not hold.

    Args:
        project: The project.
        work_id: E.g. "W-012".

    Returns:
        Warning lines in the project's language; empty when the work needs none. Without a loop record, only
        `build.loop: on` is a doubt — a work built with a check after each task is fine.

    Example:
        >>> doubts(project, "W-012")  # doctest: +SKIP
        ['⚠ The loop never ended a round']
    """
    now = standing(project, work_id)
    if now is None:
        return (
            [msg("⚠ build.loop is on but the run log has no loop for {work_id}", work_id=work_id)]
            if project.profile.get("build.loop") == "on"
            else []
        )
    if now.mode != MODE_LOOP:
        return []
    out = [msg("⚠ {line}", line=describe(v)) for v in now.violations]
    if now.starts > 1:
        out.append(
            msg("⚠ A loop was started {n} times for this work — each restart forgets the failures and limits before it", n=now.starts)
        )
    if not now.attempts:
        out.append(msg("⚠ The loop started but no criterion was tried"))
    if now.last_result != PASSED:
        out.append(msg("⚠ The loop's last round did not pass ({result})", result=now.last_result or msg("no round ended")))
    return out


# --------------------------------------------------------------------------- may it loop, and what did it change


def eligibility(project: Project, work_id: str) -> Eligibility:
    """Tell whether a work may build in a loop.

    A loop is allowed only when a test command exists and every acceptance criterion links a test that git
    tracks and has no uncommitted change — so the tests that judge the loop are fixed before it starts.

    Args:
        project: The project.
        work_id: E.g. "W-012".

    Returns:
        The verdict, with the reasons and the criteria that miss a test.

    Raises:
        ValueError: The work is not in progress.

    Example:
        >>> eligibility(project, "W-012").missing  # doctest: +SKIP
        ['AC-2']
    """
    criteria = parse_criteria(_plan_text(project, work_id), project.names)
    reasons: list[str] = []
    if not criteria:
        reasons.append(msg("The plan has no acceptance criteria"))
    missing = unlinked(criteria)
    if missing:
        reasons.append(msg("No test is linked to {ids}", ids=", ".join(missing)))
    if not project.profile.get("build.test"):
        reasons.append(msg("There is no test command (build.test)"))
    for c in criteria:
        if not c.test_file:
            continue
        if not git_out(["ls-files", "--", c.test_file], project.root):
            reasons.append(msg("{ac}: the test file {file} is not committed", ac=c.id, file=c.test_file))
        elif git_out(["status", "--porcelain", "--", c.test_file], project.root):
            reasons.append(msg("{ac}: the test file {file} has uncommitted changes", ac=c.id, file=c.test_file))
    return Eligibility(not reasons, reasons, missing, {c.id: c.test for c in criteria if c.test})


def changed(project: Project, start: dict[str, Any]) -> list[dict[str, str]]:
    """List what changed since the loop started in the tests that judge it.

    Compares the content of the linked test files and of the files `build.test_config` matches (a new or a
    moved one included) with what the start line fingerprinted. It needs no git, so a git failure cannot
    let a change through. New tests in new files are fine.

    Args:
        project: The project.
        start: The loop's start line.

    Returns:
        One dict per change: `kind` ("test" or "config") and `path`.

    Example:
        >>> changed(project, last_start(project, "W-012"))  # doctest: +SKIP
        [{'kind': 'test', 'path': 'tests/test_login.py'}]
    """
    files = start.get("files") or {}
    settings = start.get("settings") or {}
    out: list[dict[str, str]] = []
    for kind, then, patterns in (
        ("test", files.get("tests") or {}, list(files.get("tests") or {})),
        ("config", files.get("config") or {}, settings.get("test_config") or []),
    ):
        now = file_hashes(project, patterns)
        out += [{"kind": kind, "path": path} for path in sorted(then.keys() | now.keys()) if then.get(path) != now.get(path)]
    return out


# --------------------------------------------------------------------------- the loop


def _run(project: Project, cmd: str) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, shell=True, cwd=str(project.root), capture_output=True, text=True, timeout=TEST_TIMEOUT)
    except subprocess.TimeoutExpired:
        return TIMED_OUT, msg("Timed out after {seconds} seconds", seconds=TEST_TIMEOUT)
    return r.returncode, r.stdout + r.stderr


def _tail(output: str) -> str:
    return "\n".join(output.strip().split("\n")[-TAIL_LINES:])


def start(project: Project, work_id: str, again: bool = False) -> Started:
    """Start a loop for a work, or decide that it goes on with a check after each task.

    Needs `build.loop: on`. When the work may loop, runs the whole suite once to count its tests, then writes a
    `start` line with the settings, the base commit, the linked tests and the test settings files — later rounds
    read that line, not lantern.yaml. When it may not, or the suite does not run, the line says mode "each".
    A work whose loop already started cannot start another unless the person says so (`again`): a restart
    forgets the failures, the limits and the tests fingerprinted before.

    Args:
        project: The project.
        work_id: E.g. "W-012".
        again: The person said to start another loop for the work.

    Returns:
        What was decided.

    Raises:
        ValueError: `build.loop` is off, the work is not in progress, or a loop already started and `again` is not set.

    Example:
        >>> start(project, "W-012").mode  # doctest: +SKIP
        'loop'
    """
    from ..tools import runlog

    if project.profile.get("build.loop") != "on":
        raise ValueError(msg("build.loop is off, so no loop starts (lantern build-mode suggest)"))
    previous = last_start(project, work_id)
    if previous is not None and previous.get("mode") == MODE_LOOP and not again:
        raise ValueError(
            msg(
                "A loop already started for {work_id} — another needs the person's say: `lantern loop start {work_id} --again`",
                work_id=work_id,
            )
        )
    elig = eligibility(project, work_id)
    reasons, before, mode = list(elig.reasons), None, MODE_LOOP if elig.ok else MODE_EACH
    settings = {
        "test": project.profile.get("build.test") or "",
        "test_one": project.profile.get("build.test_one") or "",
        "loop_limit": project.profile.get("build.loop_limit"),
        "same_ac_limit": project.profile.get("build.same_ac_limit"),
        "test_config": [str(f) for f in project.profile.get("build.test_config") or []],
    }
    if elig.ok:
        code, out = _run(project, settings["test"])
        if code in NOT_RUN:
            mode, reasons = MODE_EACH, [msg("`{cmd}` did not run (exit {code})", cmd=settings["test"], code=code)]
        before = count_tests(out)
    run = uuid.uuid4().hex[:8]
    files = {
        "tests": file_hashes(project, sorted({test.split("::", 1)[0].strip() for test in elig.tests.values()})),
        "config": file_hashes(project, settings["test_config"]),
    }
    runlog.loop_event(
        project,
        "start",
        run,
        work_id,
        mode=mode,
        reasons=reasons,
        base=git_out(["rev-parse", "HEAD"], project.root),
        settings=settings,
        tests=elig.tests,
        files=files,
        tests_before=before,
        again=again,
    )
    return Started(run, mode, reasons, elig.missing, before)


def _task_of(project: Project, work_id: str, ac: str) -> str:
    folder = project.find_work(work_id, include_archive=False)
    path = project.doc_path(folder, "tasks") if folder else None
    tasks = [t for t in parse_tasks(read(path), project.names) if ac in t.criteria] if path and path.exists() else []
    return next((t.id for t in tasks if not t.done), tasks[0].id if tasks else "")


def attempt(project: Project, work_id: str, ac: str, task: str = "") -> Tried:
    """Run one criterion's test and write the try; the result is the command's exit code, nothing else.

    A criterion that already failed `same_ac_limit` times in a row is not run again: the try is written as
    "limit", the loop has stopped, and every later try or round is refused. Without `build.test_one` the whole
    suite stands in and nothing is judged per criterion: a failing suite says nothing about this criterion
    (the others may not be built yet), so no failures are counted and no limit applies.

    Args:
        project: The project.
        work_id: E.g. "W-012".
        ac: The criterion, e.g. "AC-2".
        task: The task being built; the first unfinished task serving the criterion when empty.

    Returns:
        The try.

    Raises:
        ValueError: No loop is running for the work, it has stopped, or the criterion is not in it.

    Example:
        >>> attempt(project, "W-012", "AC-2").result  # doctest: +SKIP
        'pass'
    """
    from ..tools import runlog

    start_line = _active(project, work_id)
    ac = ac.upper()
    link = (start_line.get("tests") or {}).get(ac)
    if not link:
        raise ValueError(msg("{ac} has no linked test in this loop", ac=ac))
    settings = start_line["settings"]
    limit = int(settings.get("same_ac_limit") or 3)
    mine = [r for r in _run_lines(project, start_line) if r.get("kind") == "attempt" and r.get("ac") == ac]
    one = bool(settings.get("test_one"))
    streak = _streak(mine) if one else 0
    made = sum(1 for r in mine if r["result"] != LIMIT)
    task = task or _task_of(project, work_id, ac)
    understood = stages.understood(project, work_id)

    def write(n: int, result: str, failed: str, scope: str) -> None:
        runlog.loop_attempt(project, start_line["run"], task, ac, n, result, failed, understood, work_id, scope)

    if streak >= limit:
        if not mine or mine[-1]["result"] != LIMIT:
            write(made, LIMIT, link, "one")
        return Tried(ac, made, LIMIT, "", streak, limit)
    code, out = _run(project, command_for(settings["test_one"], link) if one else settings["test"])
    result = PASS if code == 0 else FAIL
    last = next((x for x in reversed(out.strip().splitlines()) if x.strip()), "")
    write(made + 1, result, "" if code == 0 else f"{link}: {last[:200]}", "one" if one else "all")
    return Tried(ac, made + 1, result, _tail(out), streak + 1 if one and code != 0 else 0, limit)


def finish(project: Project, work_id: str) -> Finished:
    """End a round: run the whole suite, check the criteria and what changed, and write the round.

    The round passes only when every criterion's latest try in this run passed (judged per criterion only with
    `build.test_one`), the whole suite passed, nothing changed under the loop's tests or test settings, and, when
    the suite passed, no fewer tests ran than before the loop (a failing run may stop early, so its count says
    nothing).

    Args:
        project: The project.
        work_id: E.g. "W-012".

    Returns:
        How the round ended and whether the loop must stop.

    Raises:
        ValueError: No loop is running for the work, or it has stopped.

    Example:
        >>> finish(project, "W-012").result  # doctest: +SKIP
        'passed'
    """
    from ..tools import runlog

    start_line = _active(project, work_id)
    settings = start_line["settings"]
    lines = _run_lines(project, start_line)
    latest = _latest(lines)
    judged_per_ac = bool(settings.get("test_one"))
    unpassed = [ac for ac in start_line.get("tests") or {} if judged_per_ac and latest.get(ac) != PASS]
    code, out = _run(project, settings["test"])
    after, before = count_tests(out), start_line.get("tests_before")
    violations = changed(project, start_line)
    if code == 0 and before is not None and after is not None and after < before:
        violations.append({"kind": "count", "path": f"{before} → {after}"})
    round_no = sum(1 for r in lines if r.get("event") == "end") + 1
    result = INVALID if violations else FAILED if code != 0 or unpassed else PASSED
    stop = result == INVALID or (result == FAILED and round_no >= int(settings.get("loop_limit") or 3))
    runlog.loop_event(
        project,
        "end",
        start_line["run"],
        work_id,
        round=round_no,
        result=result,
        unpassed=unpassed,
        violations=violations,
        tests_before=before,
        tests_after=after,
        exit=code,
        stop=stop,
    )
    return Finished(round_no, result, unpassed, violations, before, after, _tail(out), stop)
