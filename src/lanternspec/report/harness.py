"""Pick the AI work mode for the project size — harness · loop · graph.

| mode | when | lantern.yaml |
|---|---|---|
| harness (small loops) | small project · no acceptance tests yet | build.loop: off |
| loop (big loop)       | automated acceptance tests exist (build.test), success rate visible | build.loop: on · build.loop_limit |
| graph (parallel)      | several independent work items · many [P] tasks | (lantern work start · sub-agents) |

The suggestion is computed from facts (code size, works, tasks, run history); applying it is the
person's choice (`--apply`). `code_lines` is also the code size that picks the design principles.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from typing import Any

from ..core.messages import msg
from ..core.project import Project, git_out, read
from ..core.taskfile import TaskGraph, parse_tasks
from . import evaluate


@dataclass
class Suggestion:
    """A suggested work mode.

    Attributes:
        mode: The mode's display name, e.g. "하네스 (작은 반복)".
        reasons: Why, one line each.
        settings: lantern.yaml values that put the mode in place (applied only with `--apply`).
        facts: The facts the suggestion was computed from (see facts).

    Example:
        >>> Suggestion("하네스 (작은 반복)", settings={"build.loop": "off"}).settings
        {'build.loop': 'off'}
    """

    mode: str
    reasons: list[str] = field(default_factory=list)
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
    """Collect the facts a work-mode suggestion looks at.

    Args:
        project: The project.

    Returns:
        code_files, loc, active_works, tasks, parallel_ready ([P] tasks that can start now),
        team, has_test, skill_runs and clean_rate (percent of skill closes without errors, or None).

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
    s = evaluate.summary(project)
    close_runs = [v for v in s["close_quality"].values() if v["n"]]
    clean = round(sum(v["clean_rate"] * v["n"] for v in close_runs) / sum(v["n"] for v in close_runs)) if close_runs else None
    return {
        "code_files": len(files),
        "loc": loc,
        "active_works": len(works),
        "tasks": tasks,
        "parallel_ready": parallel_ready,
        "team": project.profile.team,
        "has_test": bool(project.profile.get("build.test")),
        "skill_runs": s["skill_runs"],
        "clean_rate": clean,
    }


def suggest(project: Project) -> Suggestion:
    """Suggest a work mode from the project's facts.

    Graph when two or more works run alongside a team, parallel tasks or a large codebase;
    loop when acceptance tests exist and closes are mostly clean (or the code is past 3000 lines);
    harness otherwise.

    Args:
        project: The project.

    Returns:
        The suggestion.

    Example:
        >>> suggest(project).mode  # doctest: +SKIP
        '하네스 (작은 반복)'
    """
    f = facts(project)
    reasons: list[str] = []
    if f["active_works"] >= 2 and (f["team"] or f["parallel_ready"] >= 2 or f["loc"] > 20000):
        reasons.append(
            msg("{active_works} works in progress", active_works=f["active_works"])
            + (msg(" · 2 or more people") if f["team"] else "")
            + (msg(" · {parallel_ready} [P] tasks can run at once now", parallel_ready=f["parallel_ready"]) if f["parallel_ready"] else "")
        )
        reasons.append(
            msg(
                "Run independent works at once in separate worktrees with `lantern work start W-… W-…` "
                "(design conflicts are warned about first)"
            )
        )
        settings: dict[str, Any] = {"build.report_cycle": "criterion"}
        if f["has_test"]:
            settings.update({"build.loop": "on", "build.loop_limit": 3})
        return Suggestion(msg("Graph (parallel)"), reasons, settings, f)
    if f["has_test"] and (f["skill_runs"] >= 5 and (f["clean_rate"] or 0) >= 70 or f["loc"] > 3000):
        reasons.append(msg("There is an acceptance-test command (build.test)"))
        if f["skill_runs"]:
            reasons.append(
                msg(
                    "{clean_rate}% of the last {skill_runs} wrap-ups finished without errors",
                    skill_runs=f["skill_runs"],
                    clean_rate=f["clean_rate"],
                )
            )
        reasons.append(msg("After all tasks are done, rerun the whole work until the acceptance tests pass (up to build.loop_limit times)"))
        return Suggestion(msg("Loop (big loop)"), reasons, {"build.loop": "on", "build.loop_limit": 3, "build.report_cycle": "work"}, f)
    reasons.append(
        msg("{loc} lines of code · {active_works} works in progress — a small project", loc=f["loc"], active_works=f["active_works"])
    )
    if not f["has_test"]:
        reasons.append(msg("No automatic tests for the acceptance criteria yet (build.test) — the big loop comes once tests are in place"))
    reasons.append(msg("Within one task, build → test → fix up to 3 times; the person checks often"))
    return Suggestion(msg("Harness (small loop)"), reasons, {"build.loop": "off", "build.report_cycle": "criterion"}, f)
