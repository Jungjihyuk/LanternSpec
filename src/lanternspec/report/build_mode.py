"""Suggest how to build, one axis at a time: loop scope, task delegation and parallel works.

| axis | choices | where it is set |
|---|---|---|
| loop scope | check each task · loop automatically until the acceptance tests pass | lantern.yaml build.loop (`--apply`) |
| task delegation | one at a time · hand [P] tasks to sub-agents | /l-build, when the tool has sub-agents |
| parallel works | one at a time · several works in worktrees | /l-parallel → lantern work start |

The suggestion is computed from facts (code size, works, tasks, run history); applying it is the
person's choice (`--apply`, loop scope only). `code_lines` is also the code size that picks the design principles.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from typing import Any

from ..core.messages import msg
from ..core.project import Project, git_out, read, work_id_of
from ..core.taskfile import TaskGraph, parse_tasks
from . import evaluate


@dataclass
class Axis:
    """The suggestion for one axis.

    Attributes:
        name: The axis, e.g. "반복 범위".
        choice: What is suggested, e.g. "할 일마다 확인".
        reasons: Why, one line each.

    Example:
        >>> Axis("반복 범위", "할 일마다 확인").choice
        '할 일마다 확인'
    """

    name: str
    choice: str
    reasons: list[str] = field(default_factory=list)


@dataclass
class Suggestion:
    """A suggestion for every axis.

    Attributes:
        axes: One entry per axis, in order (loop scope, task delegation, parallel works).
        settings: lantern.yaml values for the loop scope (applied only with `--apply`).
        facts: The facts the suggestion was computed from (see facts).

    Example:
        >>> Suggestion([Axis("반복 범위", "할 일마다 확인")], {"build.loop": "off"}).settings
        {'build.loop': 'off'}
    """

    axes: list[Axis]
    settings: dict[str, Any] = field(default_factory=dict)
    facts: dict[str, Any] = field(default_factory=dict)


CODE_SUFFIXES = (".py", ".ts", ".tsx", ".js", ".jsx", ".swift", ".kt", ".java", ".go", ".rs", ".rb", ".dart", ".vue", ".sql")
TEST_DIRS = {"test", "tests", "__tests__", "spec", "specs"}
TEST_NAMES = ("test_*", "*_test.*", "*.test.*", "*.spec.*", "*Tests.swift", "*Test.kt", "*Test.java")


def code_files(project: Project) -> list[str]:
    """List the files git tracks that are neither documents nor AI-tool settings.

    Args:
        project: The project.

    Returns:
        Paths relative to the project root.

    Example:
        >>> code_files(project)[:2]  # doctest: +SKIP
        ['src/app.py', 'tests/test_app.py']
    """
    from .scan import is_doc_path

    return [f for f in git_out(["ls-files"], project.root).splitlines() if not is_doc_path(project, f)]


def code_lines(project: Project, tests: bool = True) -> int:
    """Count lines in code files (tracked by git, excluding documents and AI-tool settings).

    Args:
        project: The project.
        tests: Whether to count test files. The design-principle size counts with False.

    Returns:
        Line count. With very many files, only the first 4000 are counted.

    Example:
        >>> code_lines(project, tests=False)  # doctest: +SKIP
        8123
    """
    loc = 0
    for f in code_files(project)[:4000]:
        p = project.root / f
        if p.suffix not in CODE_SUFFIXES or (not tests and _is_test(f)):
            continue
        try:
            loc += p.read_text(encoding="utf-8", errors="ignore").count("\n")
        except OSError:
            pass
    return loc


def _is_test(rel: str) -> bool:
    parts = rel.split("/")
    return bool(TEST_DIRS & set(parts[:-1])) or any(fnmatch.fnmatch(parts[-1], pat) for pat in TEST_NAMES)


def facts(project: Project) -> dict[str, Any]:
    """Collect the facts a build-mode suggestion looks at.

    Args:
        project: The project.

    Returns:
        code_files, loc, active_works, waiting_works (works in progress not running in a worktree),
        tasks, parallel_ready ([P] tasks that can start now), team, has_test, skill_runs and
        clean_rate (percent of skill closes without errors, or None).

    Example:
        >>> facts(project)["active_works"]  # doctest: +SKIP
        1
    """
    files = code_files(project)
    loc = code_lines(project)
    works = project.work_dirs()
    tasks, parallel_ready = 0, 0
    for w in works:
        tf = project.doc_path(w, "tasks")
        if tf.exists():
            ts = parse_tasks(read(tf), project.names)
            tasks += len(ts)
            g = TaskGraph(ts)
            parallel_ready += sum(1 for t in ts if t.parallel and g.blocked_reason(t) is None)
    from ..work.branches import running_works

    running = set(running_works(project))
    s = evaluate.summary(project)
    close_runs = [v for v in s["close_quality"].values() if v["n"]]
    clean = round(sum(v["clean_rate"] * v["n"] for v in close_runs) / sum(v["n"] for v in close_runs)) if close_runs else None
    return {
        "code_files": len(files),
        "loc": loc,
        "active_works": len(works),
        "waiting_works": [wid for w in works if (wid := work_id_of(w)) and wid not in running],
        "tasks": tasks,
        "parallel_ready": parallel_ready,
        "team": project.profile.team,
        "has_test": bool(project.profile.get("build.test")),
        "skill_runs": s["skill_runs"],
        "clean_rate": clean,
    }


def suggest(project: Project) -> Suggestion:
    """Suggest each axis from the project's facts.

    Loop scope: loop automatically when acceptance tests exist and wrap-ups are mostly clean (or the
    code is past 3000 lines); check each task otherwise. Task delegation: worth it with two or more
    [P] tasks ready. Parallel works: worth checking with two or more works waiting and a team or a
    large codebase.

    Args:
        project: The project.

    Returns:
        The suggestion.

    Example:
        >>> [a.choice for a in suggest(project).axes]  # doctest: +SKIP
        ['할 일마다 확인', '지금은 필요 없음', '하나씩']
    """
    f = facts(project)
    if f["has_test"] and (f["skill_runs"] >= 5 and (f["clean_rate"] or 0) >= 70 or f["loc"] > 3000):
        why = [msg("There is an acceptance-test command (build.test)")]
        if f["skill_runs"]:
            why.append(
                msg(
                    "{clean_rate}% of the last {skill_runs} wrap-ups finished without errors",
                    skill_runs=f["skill_runs"],
                    clean_rate=f["clean_rate"],
                )
            )
        why.append(msg("After all tasks are done, rerun the whole work until the acceptance tests pass (up to build.loop_limit times)"))
        loop = Axis(msg("Loop scope"), msg("Loop automatically"), why)
        settings: dict[str, Any] = {"build.loop": "on", "build.loop_limit": 3, "build.report_cycle": "work"}
    else:
        why = [msg("{loc} lines of code · {active_works} works in progress", loc=f["loc"], active_works=f["active_works"])]
        if not f["has_test"]:
            why.append(msg("No automatic tests for the acceptance criteria yet (build.test) — loop automatically once they are in place"))
        why.append(msg("Within one task, build → test → fix up to 3 times; the person checks often"))
        loop = Axis(msg("Loop scope"), msg("Check each task"), why)
        settings = {"build.loop": "off", "build.report_cycle": "criterion"}
    if f["parallel_ready"] >= 2:
        delegate = Axis(
            msg("Task delegation"),
            msg("Worth it"),
            [msg("{parallel_ready} [P] tasks can run at once now — /l-build hands them to sub-agents", parallel_ready=f["parallel_ready"])],
        )
    else:
        delegate = Axis(
            msg("Task delegation"), msg("Not needed now"), [msg("{parallel_ready} [P] tasks ready now", parallel_ready=f["parallel_ready"])]
        )
    waiting = f["waiting_works"]
    if len(waiting) >= 2 and (f["team"] or f["loc"] > 20000 or f["parallel_ready"] >= 2):
        parallel = Axis(
            msg("Parallel works"),
            msg("Worth checking"),
            [msg("{count} works waiting — check them first with /l-parallel {ids}", count=len(waiting), ids=" ".join(waiting))],
        )
    else:
        parallel = Axis(msg("Parallel works"), msg("One at a time"), [msg("{count} works waiting", count=len(waiting))])
    return Suggestion([loop, delegate, parallel], settings, f)
