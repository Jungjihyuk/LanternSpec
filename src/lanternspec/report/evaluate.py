"""📊 AI work evaluation — "which setup helped the outcome?" (what the run log is for).

Reads `.lantern/runs.jsonl` (turn records from agent hooks, skill records from `lantern close`)
and the work folders, then compares configurations (model · skill · profile settings) by
cost (duration, tool calls) and outcome (check errors left at close, tasks done, size estimates).

Not here:
    - writing the run log → tools/runlog.py
"""

from __future__ import annotations

import datetime as _dt
import json
from collections import defaultdict
from statistics import mean, median
from typing import Any

from ..core.project import Project, read
from ..core.taskfile import parse_tasks

CONFIG_KEYS = [
    "design.approval",
    "build.report_cycle",
    "build.merge_approval",
    "build.loop",
    "plan.max_questions",
    "learn.detect",
    "idea.capture",
]


def config_snapshot(project: Project) -> dict[str, Any]:
    """Take the profile settings that a run record keeps, so runs can be compared by configuration.

    Args:
        project: The project.

    Returns:
        Setting key → value for each key in CONFIG_KEYS.

    Example:
        >>> config_snapshot(project)["build.loop"]  # doctest: +SKIP
        'off'
    """
    return {k: project.profile.get(k) for k in CONFIG_KEYS}


def load_runs(project: Project) -> list[dict[str, Any]]:
    """Read the run log; broken lines are skipped.

    Args:
        project: The project.

    Returns:
        One record per line; empty when there is no log.

    Example:
        >>> load_runs(project)[0]["kind"]  # doctest: +SKIP
        'turn'
    """
    p = project.state / "runs.jsonl"
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _dt_of(s: str | None) -> _dt.datetime | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M"):
        try:
            d = _dt.datetime.strptime(s, fmt)
            return d.replace(tzinfo=None)
        except ValueError:
            continue
    try:
        return _dt.datetime.fromisoformat(s).replace(tzinfo=None)
    except ValueError:
        return None


def _minutes(rec: dict[str, Any]) -> float | None:
    a, b = _dt_of(rec.get("start")), _dt_of(rec.get("end"))
    if a and b and b >= a:
        return (b - a).total_seconds() / 60
    return None


def task_durations(project: Project) -> dict[str, list[float]]:
    """Measure actual hours per size from `[시작:: …]` → `[완료:: …]` of finished tasks.

    Also used by `lantern task estimate`.

    Args:
        project: The project.

    Returns:
        Size (S · M · L, or "?") → hours of each finished task.

    Example:
        >>> task_durations(project)["S"]  # doctest: +SKIP
        [1.5, 2.0]
    """
    out: dict[str, list[float]] = defaultdict(list)
    for w in project.work_dirs(include_archive=True):
        tf = w / "할 일.md"
        if not tf.exists():
            continue
        for t in parse_tasks(read(tf)):
            a, b = _dt_of(t.started), _dt_of(t.finished)
            if t.done and a and b and b > a:
                out[t.size or "?"].append((b - a).total_seconds() / 3600)
    return out


def summary(project: Project) -> dict[str, Any]:
    """Summarize the run log and task times.

    Args:
        project: The project.

    Returns:
        turns, skill_runs, by_skill and by_model (count, median minutes, average tool calls),
        close_quality and by_config (count, percent closed without errors, average warnings),
        and task_hours (size → count and median hours).

    Example:
        >>> summary(project)["skill_runs"]  # doctest: +SKIP
        12
    """
    runs = load_runs(project)
    turns = [r for r in runs if r.get("kind") == "turn"]
    skills = [r for r in runs if r.get("kind") == "skill"]
    by_skill: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in turns:
        by_skill[str(r.get("skill") or "(스킬 없음)")].append(r)
    by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in turns:
        by_model[str(r.get("model") or "?")].append(r)
    closes: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in skills:
        closes[str(r.get("skill"))].append(r)
    by_config: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in skills:
        if r.get("config"):
            by_config[json.dumps(r["config"], ensure_ascii=False, sort_keys=True)].append(r)

    def agg(items: list[dict[str, Any]]) -> dict[str, Any]:
        mins = [m for m in (_minutes(r) for r in items) if m is not None]
        calls = [int(r.get("tool_calls") or 0) for r in items]
        return {
            "n": len(items),
            "median_min": round(median(mins), 1) if mins else None,
            "avg_tools": round(float(mean(calls)), 1) if calls else None,
        }

    def quality(items: list[dict[str, Any]]) -> dict[str, Any]:
        errs = [int((r.get("check") or {}).get("error", 0)) for r in items]
        warns = [int((r.get("check") or {}).get("warn", 0)) for r in items]
        clean = sum(1 for e in errs if e == 0)
        return {
            "n": len(items),
            "clean_rate": round(100 * clean / len(items)) if items else None,
            "avg_warn": round(float(mean(warns)), 1) if warns else None,
        }

    durations = task_durations(project)
    return {
        "turns": len(turns),
        "skill_runs": len(skills),
        "by_skill": {k: agg(v) for k, v in sorted(by_skill.items())},
        "by_model": {k: agg(v) for k, v in sorted(by_model.items())},
        "close_quality": {k: quality(v) for k, v in sorted(closes.items())},
        "by_config": {k: quality(v) for k, v in by_config.items()},
        "task_hours": {k: {"n": len(v), "median_h": round(median(v), 2)} for k, v in sorted(durations.items())},
    }


def markdown(project: Project) -> str:
    """Write the evaluation as Markdown tables for the report.

    Args:
        project: The project.

    Returns:
        The tables; a short note when there is no run log yet.

    Example:
        >>> markdown(project).splitlines()[0]  # doctest: +SKIP
        '실행 기록: 대화 턴 40개 · 스킬 마무리 12개'
    """
    s = summary(project)
    if not s["turns"] and not s["skill_runs"]:
        return "_실행 기록이 아직 없습니다 (.lantern/runs.jsonl) — 스킬을 쓰면 쌓인다._"
    out = [f"실행 기록: 대화 턴 {s['turns']}개 · 스킬 마무리 {s['skill_runs']}개", ""]

    def table(title: str, head: tuple[str, ...], rows: list[tuple[Any, ...]]) -> None:
        if not rows:
            return
        out.extend([f"**{title}**", "", "| " + " | ".join(head) + " |", "|" + "---|" * len(head)])
        out.extend("| " + " | ".join("—" if v is None else str(v) for v in r) + " |" for r in rows)
        out.append("")

    table(
        "스킬별 비용",
        ("스킬", "턴", "중간 시간(분)", "평균 도구 호출"),
        [(k, v["n"], v["median_min"], v["avg_tools"]) for k, v in s["by_skill"].items()],
    )
    table(
        "모델별 비용",
        ("모델", "턴", "중간 시간(분)", "평균 도구 호출"),
        [(k, v["n"], v["median_min"], v["avg_tools"]) for k, v in s["by_model"].items()],
    )
    table(
        "마무리 품질 (close 때 양식 검사)",
        ("스킬", "실행", "오류 없이 끝낸 비율(%)", "평균 경고"),
        [(k, v["n"], v["clean_rate"], v["avg_warn"]) for k, v in s["close_quality"].items()],
    )
    if len(s["by_config"]) > 1:
        table(
            "구성별 결과 — 어떤 설정이 도움이 됐나",
            ("구성", "실행", "오류 없이 끝낸 비율(%)", "평균 경고"),
            [
                (", ".join(f"{k}={v}" for k, v in json.loads(c).items() if v is not None), v["n"], v["clean_rate"], v["avg_warn"])
                for c, v in s["by_config"].items()
            ],
        )
    table(
        "할 일 크기별 실제 시간",
        ("크기", "끝낸 할 일", "중간 시간(시간)"),
        [(k, v["n"], v["median_h"]) for k, v in s["task_hours"].items()],
    )
    return "\n".join(out).rstrip()
