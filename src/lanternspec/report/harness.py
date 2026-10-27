"""Pick the AI work mode for the project size — harness · loop · graph (08 · BU-04 · BU-05).

| mode | when | lantern.yaml |
|---|---|---|
| harness (small loops) | small project · no acceptance tests yet | build.loop: off |
| loop (big loop)       | automated acceptance tests exist (build.test), success rate visible | build.loop: on · build.loop_limit |
| graph (parallel)      | several independent work items · many [P] tasks | (lantern work start · sub-agents) |

The suggestion is computed from facts (code size, works, tasks, run history); applying it is the
person's choice (`--apply`). `code_lines` is also the code size that picks the design principles (I-05).
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from typing import Any

from ..core.project import Project, git_out, read
from ..core.taskfile import TaskGraph, parse_tasks
from . import evaluate


@dataclass
class Suggestion:
    mode: str
    reasons: list[str] = field(default_factory=list)
    settings: dict[str, Any] = field(default_factory=dict)
    facts: dict[str, Any] = field(default_factory=dict)


CODE_SUFFIXES = (".py", ".ts", ".tsx", ".js", ".jsx", ".swift", ".kt", ".java", ".go", ".rs", ".rb", ".dart", ".vue", ".sql")
TEST_DIRS = {"test", "tests", "__tests__", "spec", "specs"}
TEST_NAMES = ("test_*", "*_test.*", "*.test.*", "*.spec.*", "*Tests.swift", "*Test.kt", "*Test.java")


def code_files(project: Project) -> list[str]:
    """Files git tracks that are neither documents nor AI-tool settings."""
    from .scan import is_doc_path

    return [f for f in git_out(["ls-files"], project.root).splitlines() if not is_doc_path(project, f)]


def code_lines(project: Project, tests: bool = True) -> int:
    """Count lines in code files (tracked by git, excluding documents and AI-tool settings).

    Args:
        project: The project.
        tests: Whether to count test files. The design-principle size (I-05) counts with False.

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
    files = code_files(project)
    loc = code_lines(project)
    works = project.work_dirs()
    tasks, parallel_ready = 0, 0
    for w in works:
        tf = w / "할 일.md"
        if tf.exists():
            ts = parse_tasks(read(tf))
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
    f = facts(project)
    reasons: list[str] = []
    if f["active_works"] >= 2 and (f["team"] or f["parallel_ready"] >= 2 or f["loc"] > 20000):
        reasons.append(
            f"진행 중 작업 {f['active_works']}개"
            + (" · 2인 이상" if f["team"] else "")
            + (f" · 지금 동시에 할 수 있는 [P] 할 일 {f['parallel_ready']}개" if f["parallel_ready"] else "")
        )
        reasons.append("서로 독립인 작업은 `lantern work start W-… W-…`로 worktree를 나눠 동시에 (설계 충돌은 미리 경고)")
        settings: dict[str, Any] = {"build.report_cycle": "criterion"}
        if f["has_test"]:
            settings.update({"build.loop": "on", "build.loop_limit": 3})
        return Suggestion("그래프 (병렬)", reasons, settings, f)
    if f["has_test"] and (f["skill_runs"] >= 5 and (f["clean_rate"] or 0) >= 70 or f["loc"] > 3000):
        reasons.append("수락 기준 테스트 명령이 있다 (build.test)")
        if f["skill_runs"]:
            reasons.append(f"지난 마무리 {f['skill_runs']}번 중 오류 없이 끝낸 비율 {f['clean_rate']}%")
        reasons.append("할 일을 다 끝낸 뒤 수락 기준 테스트가 통과할 때까지 작업 전체를 다시 돈다 (최대 build.loop_limit번)")
        return Suggestion("루프 (큰 반복)", reasons, {"build.loop": "on", "build.loop_limit": 3, "build.report_cycle": "work"}, f)
    reasons.append(f"코드 {f['loc']}줄 · 진행 중 작업 {f['active_works']}개 — 작은 프로젝트")
    if not f["has_test"]:
        reasons.append("수락 기준 → 자동 테스트가 아직 없다 (build.test) — 큰 루프는 테스트가 자리 잡은 뒤")
    reasons.append("할 일 하나 안에서 구현 → 테스트 → 고치기 최대 3번, 사람이 자주 본다")
    return Suggestion("하네스 (작은 반복)", reasons, {"build.loop": "off", "build.report_cycle": "criterion"}, f)
