"""The AI retro: one line for each criterion (or check) that did not pass on the first try of a loop, and for what the AI got stuck on.

The facts of a line (time · work · tries · result · run) are written by code from the run log when a loop ends. The
judgment (weakness · remedy · hypothesis · suggestion) is filled by the AI through `lantern retro judge`, which only
accepts the values in enums.yaml, and a person confirms it. The file is one per month: `4. 운영 기록/AI 회고/YYYY-MM.md`.

    - 09:31 W-012 AC-2 [시도:: 3] [결과:: 통과] [약점:: 명세] [보완:: LanternSpec] [실행:: a1b2c3d4] 가설: … / 제안: … [확인:: ✅]

A stuck line is the AI's own note (`lantern retro note`), in any way of building: nothing measured it, so it has no tries or result.

    - 18:59 W-005 [막힘:: 자동 커밋 연결이 아니면 멈춘다] [할 일:: W-005-T02] [해결:: isolation_level=None] [실행:: n-1a2b3c4d]

Responsibilities:
    - work out the rows of a finished loop from its run-log lines (a pure function)
    - read and write the monthly file: rows under a date heading, and the summary section
    - write a line for what the AI got stuck on
    - judge · confirm a row, list the unconfirmed rows
    - find the values and fields of a row that the lists and names do not know

Not here:
    - the loop's facts and the run-log format → work/loop.py · tools/runlog.py
    - turning the problems into check findings → check/check_docs.py
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..core import sections
from ..core.enums import Enums
from ..core.messages import msg
from ..core.names import Names
from ..core.project import Project, now_iso, read, write
from ..core.taskfile import ATTR, find_task, parse_tasks
from ..work.scaffold import create_from_template

ROW = re.compile(r"^- (\d{2}:\d{2}) (W-\d{3,}) (.*)$")
DAY = re.compile(r"^## (\d{4}-\d{2}-\d{2})\s*$")
TARGET = re.compile(r"^(W-\d{3,})(-T\d{2,})?$")
MONTH_FILE = re.compile(r"^\d{4}-\d{2}\.md$")
CONFIRMED = "✅"


@dataclass
class Row:
    """One retro line.

    Attributes:
        date: The day it is under, "2026-11-20".
        time: "09:31".
        work: "W-012".
        key: The criterion ("AC-2"), or for a check the name of the check as written (`[검증:: 전체 테스트]`);
            for a stuck line the name of its field ("막힘").
        is_check: Whether the key is a check rather than a criterion.
        tries: How many tries (rounds, for a check) it took or were made; 0 for a stuck line.
        result: The result as written ("통과" · "중단"); "" for a stuck line.
        run: The loop run it came from; an ID of its own for a stuck line.
        weakness: Judgment: why the first try was blocked; "" until judged.
        remedy: Judgment: where fixing it helps.
        hypothesis: Judgment: the guess, one line.
        suggestion: Judgment: what to change, one line.
        confirmed: Whether a person confirmed the judgment.
        other: Fields on the line that this module does not know, kept as written.
        line: The 0-based line in the file; -1 for a row not in a file yet.
        stuck: What the AI got stuck on; "" when the line is not a stuck line.
        solved: How it got past it; "" when it did not, or not yet.
        task: The task it got stuck in ("W-005-T02"); "" when only the work is known.

    Example:
        >>> Row("2026-11-20", "09:31", "W-012", "AC-2", False, 3, "통과", "a1b2").confirmed
        False
    """

    date: str
    time: str
    work: str
    key: str
    is_check: bool
    tries: int
    result: str
    run: str
    weakness: str = ""
    remedy: str = ""
    hypothesis: str = ""
    suggestion: str = ""
    confirmed: bool = False
    other: list[str] = field(default_factory=list)
    line: int = -1
    stuck: str = ""
    solved: str = ""
    task: str = ""

    @property
    def judged(self) -> bool:
        """Whether the judgment fields are filled."""
        return bool(self.weakness and self.remedy and self.hypothesis)


def _clean(text: str, names: Names) -> str:
    """One line a row can hold: no line breaks, no brackets or ` / ` or label words (`가설:` · `제안:`) that would read back as a field."""
    text = text.replace("[", "(").replace("]", ")").replace(" / ", " · ")
    for label in (names.retro_attr("hypothesis"), names.retro_attr("suggestion")):
        text = text.replace(f"{label}:", f"{label} -")
    return re.sub(r"\s+", " ", text).strip()


def rows_from_run(lines: list[dict[str, Any]], enums: Enums) -> list[Row]:
    """Work out the retro rows of a loop run from its run-log lines.

    A criterion that passed on its first try leaves no row; one that passed later leaves a row with the number of
    tries; one that never passed leaves a stopped row. A round that failed on the whole suite, or that was
    invalid, leaves one row per kind. Nothing is made while the loop is still going, and nothing for criteria
    judged by the whole suite (no `build.test_one`): their tries say nothing about one criterion.

    Args:
        lines: The start line and the attempt and round lines of one run, in order (`loop.last_run`).
        enums: The project's lists (the result and check names).

    Returns:
        The rows, criteria first; empty when the loop has not ended.

    Example:
        >>> from lanternspec.core.enums import load
        >>> tries = [{"kind": "attempt", "ac": "AC-1", "result": "fail", "scope": "one", "at": "2026-11-20T09:31:00+09:00"},
        ...          {"kind": "attempt", "ac": "AC-1", "result": "pass", "scope": "one", "at": "2026-11-20T09:40:00+09:00"},
        ...          {"kind": "loop", "event": "end", "result": "passed", "at": "2026-11-20T09:41:00+09:00"}]
        >>> [(r.key, r.tries, r.result) for r in rows_from_run(tries, load())]
        [('AC-1', 2, '통과')]
    """
    from ..work.loop import FAILED, INVALID, LIMIT, PASS, PASSED, stopped

    body = [r for r in lines if r.get("event") != "start"]
    ends = [r for r in body if r.get("event") == "end"]
    if not body or not (stopped(body) or (ends and ends[-1].get("result") == PASSED)):
        return []
    work, run = str(lines[0].get("work") or ""), str(lines[0].get("run") or "")
    date = str(body[-1].get("at") or "")[:10]
    passed, stopped_ = enums.value("retro_result", "passed"), enums.value("retro_result", "stopped")
    rows: list[Row] = []
    by_ac: dict[str, list[dict[str, Any]]] = {}
    for r in body:
        if r.get("kind") == "attempt" and r.get("scope", "one") == "one" and r.get("result") != LIMIT:
            by_ac.setdefault(str(r["ac"]), []).append(r)
    for ac, tries in by_ac.items():
        done = tries[-1]["result"] == PASS
        if tries[0]["result"] == PASS and done:
            continue  # passed at once and stayed passed: nothing to look back on
        rows.append(Row(date, str(tries[0].get("at") or "")[11:16], work, ac, False, len(tries), passed if done else stopped_, run))
    for kind, result in (("suite", FAILED), ("invalid", INVALID)):
        bad = [i for i, e in enumerate(ends) if e.get("result") == result and (result == INVALID or e.get("exit"))]
        if not bad:
            continue
        later_pass = any(e.get("result") == PASSED for e in ends[bad[-1] + 1 :])  # the order of the rounds, not their clock
        tries = len(bad) + (1 if later_pass else 0)  # like a criterion: the try that passed is a try too
        rows.append(
            Row(
                date,
                str(ends[bad[0]].get("at") or "")[11:16],
                work,
                enums.value("retro_check", kind),
                True,
                tries,
                passed if later_pass else stopped_,
                run,
            )
        )
    return rows


def rows_from_review(rounds: list[Any], work: str, ended: bool, enums: Enums) -> list[Row]:
    """Work out the retro row of a work's review: one `[검증:: 검토]` row when a round found issues and the review is over.

    Args:
        rounds: The review rounds (`work.review.Round`), oldest first.
        work: The work, e.g. "W-012".
        ended: Whether the review is over (the last round found nothing, or no round remains).
        enums: The project's lists (the result and check names).

    Returns:
        The row, with the number of rounds as its tries and "통과" when the last round was clean, else "중단";
        empty when the review is not over or no round found an issue.

    Example:
        >>> from lanternspec.core.enums import load
        >>> from lanternspec.work.review import Round
        >>> found = Round(1, "2026-11-20T09:00:00+09:00", "m", 5, 2, 0, ["x"], "r1", "hook")
        >>> clean = Round(2, "2026-11-20T09:30:00+09:00", "m", 5, 0, 0, [], "r1", "hook")
        >>> done = [found, clean]
        >>> [(r.key, r.tries, r.result) for r in rows_from_review(done, "W-1", True, load())]
        [('검토', 2, '통과')]
    """
    first = next((r for r in rounds if r.issues), None)
    if not ended or first is None:
        return []
    result = "passed" if not rounds[-1].issues else "stopped"
    return [
        Row(
            first.at[:10],
            first.at[11:16],
            work,
            enums.value("retro_check", "review"),
            True,
            len(rounds),
            enums.value("retro_result", result),
            first.run,
        )
    ]


# --------------------------------------------------------------------------- reading and writing a line


def parse_row(line: str, date: str, names: Names, line_no: int = -1) -> Row | None:
    """Read one retro line.

    Args:
        line: A line of the file.
        date: The day heading it is under.
        names: The project's names (the field names).
        line_no: Its 0-based line in the file.

    Returns:
        The row; None when the line is not a row.

    Example:
        >>> from lanternspec.core.names import load
        >>> line = "- 09:31 W-012 AC-2 [시도:: 3] [결과:: 통과] [실행:: a1b2] 가설: 문구가 없었다 / 제안: 칸을 더한다"
        >>> row = parse_row(line, "2026-11-20", load("ko"))
        >>> (row.key, row.tries, row.result, row.hypothesis, row.suggestion)
        ('AC-2', 3, '통과', '문구가 없었다', '칸을 더한다')
    """
    m = ROW.match(line)
    if not m:
        return None
    rest = m.group(3)
    key = ""
    if ac := re.match(r"(AC-\d+)\s+(.*)$", rest):
        key, rest = ac.group(1), ac.group(2)
    fields: dict[str, str] = {}
    other: list[str] = []
    for name, value in ATTR.findall(rest):
        role = names.retro_attr_role(name.strip())
        if role in names.table["retro_attrs"] and role not in ("hypothesis", "suggestion"):
            fields[role] = value.strip()
        else:
            other.append(f"[{name.strip()}:: {value.strip()}]")
    text = ATTR.sub("", rest).strip()
    hyp, sug = re.escape(names.retro_attr("hypothesis")), re.escape(names.retro_attr("suggestion"))
    h = re.search(rf"{hyp}:\s*(.*?)\s*(?:/\s*{sug}:|$)", text)
    s = re.search(rf"{sug}:\s*(.*)$", text)
    is_check = not key and "check" in fields
    stuck = "" if key or is_check else fields.get("stuck", "")
    tries = fields.get("tries", "")
    return Row(
        date=date,
        time=m.group(1),
        work=m.group(2),
        key=key or fields.get("check", "") or (names.retro_attr("stuck") if stuck else ""),
        is_check=is_check,
        tries=int(tries) if tries.isdigit() else 0,
        result=fields.get("result", ""),
        run=fields.get("run", ""),
        stuck=stuck,
        solved=fields.get("solved", "") if stuck else "",
        task=fields.get("task", "") if stuck else "",
        weakness=fields.get("weakness", ""),
        remedy=fields.get("remedy", ""),
        hypothesis=h.group(1).strip() if h else "",
        suggestion=s.group(1).strip() if s else "",
        confirmed=fields.get("confirmed", "") == CONFIRMED,
        other=other,
        line=line_no,
    )


def render_row(row: Row, names: Names) -> str:
    """Write one retro line.

    Args:
        row: The row.
        names: The project's names (the field names).

    Returns:
        The line, in the order the facts, the judgment fields, the run, then the free text and the confirmation.

    Example:
        >>> from lanternspec.core.names import load
        >>> render_row(Row("2026-11-20", "09:31", "W-012", "AC-2", False, 3, "통과", "a1b2"), load("ko"))
        '- 09:31 W-012 AC-2 [시도:: 3] [결과:: 통과] [실행:: a1b2]'
    """
    a = names.retro_attr
    if row.stuck:
        fields = (("stuck", row.stuck), ("task", row.task), ("solved", row.solved))
        parts = [f"- {row.time} {row.work}", *(f"[{a(role)}:: {value}]" for role, value in fields if value)]
    else:
        parts = [f"- {row.time} {row.work}", f"[{a('check')}:: {row.key}]" if row.is_check else row.key]
        parts += [f"[{a('tries')}:: {row.tries}]", f"[{a('result')}:: {row.result}]"]
    if row.weakness:
        parts.append(f"[{a('weakness')}:: {row.weakness}]")
    if row.remedy:
        parts.append(f"[{a('remedy')}:: {row.remedy}]")
    parts.append(f"[{a('run')}:: {row.run}]")
    parts += row.other
    text = " ".join(parts)
    said = [f"{a(label)}: {value}" for label, value in (("hypothesis", row.hypothesis), ("suggestion", row.suggestion)) if value]
    if said:
        text += " " + " / ".join(said)
    if row.confirmed:
        text += f" [{a('confirmed')}:: {CONFIRMED}]"
    return text


def parse(text: str, names: Names) -> list[Row]:
    r"""Read every row of a monthly file, each with the day heading it is under.

    Args:
        text: The whole file.
        names: The project's names.

    Returns:
        The rows in file order.

    Example:
        >>> from lanternspec.core.names import load
        >>> parse("## 2026-11-20\n- 09:31 W-012 AC-2 [시도:: 3] [결과:: 통과] [실행:: a1b2]\n", load("ko"))[0].date
        '2026-11-20'
    """
    rows, date = [], ""
    for i, line in enumerate(text.split("\n")):
        if day := DAY.match(line):
            date = day.group(1)
        elif row := parse_row(line, date, names, i):
            rows.append(row)
    return rows


# --------------------------------------------------------------------------- the files


def _folder(project: Project) -> Path:
    return project.folder("retro")


def _file(project: Project, date: str) -> Path:
    return _folder(project) / f"{date[:7]}.md"


def all_rows(project: Project) -> list[tuple[Path, Row]]:
    """Read the rows of every monthly file, oldest month first.

    Args:
        project: The project.

    Returns:
        (file, row) pairs.

    Example:
        >>> [row.key for _, row in all_rows(project)]  # doctest: +SKIP
        ['AC-2']
    """
    folder = _folder(project)
    files = sorted(p for p in folder.iterdir() if MONTH_FILE.match(p.name)) if folder.exists() else []
    return [(p, row) for p in files for row in parse(read(p), project.names)]


def summary_lines(rows: list[Row], enums: Enums) -> list[str]:
    """Write the summary of a month: how many rows, confirmed, and the weaknesses and remedies counted.

    Args:
        rows: The month's rows.
        enums: The project's lists (the order of the weaknesses and remedies).

    Returns:
        The lines, each a list item.

    Example:
        >>> from lanternspec.core.enums import load
        >>> rows = [Row("2026-11-20", "09:31", "W-1", "AC-1", False, 2, "통과", "r", "명세", "LanternSpec", "가설", confirmed=True)]
        >>> len(summary_lines(rows, load()))  # the counts, then the weakness, then the remedy
        3
    """
    confirmed = sum(r.confirmed for r in rows)
    out = [
        msg(
            "- {rows} rows · {confirmed} confirmed · {pending} unconfirmed",
            rows=len(rows),
            confirmed=confirmed,
            pending=len(rows) - confirmed,
        )
    ]
    if todo := sum(not r.judged for r in rows):
        out.append(msg("- {count} rows not judged yet", count=todo))
    for label, attr, name in ((msg("Weaknesses"), "weakness", "retro_weakness"), (msg("Remedies"), "remedy", "retro_remedy")):
        known = enums.values(name)
        counts = {v: sum(getattr(r, attr) == v for r in rows) for v in known}
        counts.update({v: sum(getattr(r, attr) == v for r in rows) for v in {getattr(r, attr) for r in rows} - set(known) - {""}})
        items = [f"{v} {n}" for v, n in counts.items() if n]
        if items:
            out.append(f"- {label}: " + " · ".join(items))
    return out


def _rewrite_summary(project: Project, path: Path) -> None:
    text = read(path)
    rows = parse(text, project.names)
    done = (
        None
        if project.names.is_unused("retro_summary")
        else sections.replace(text, project.names.titles("retro_summary"), "\n".join(summary_lines(rows, project.enums)))
    )
    if done is not None and done[0] != text:
        write(path, done[0])


def _add_line(text: str, date: str, line: str) -> str:
    """Put a line at the end of a day's block, making the day heading when the day is new."""
    lines = text.rstrip("\n").split("\n")
    heading = next((i for i, l in enumerate(lines) if (m := DAY.match(l)) and m.group(1) == date), None)
    if heading is None:
        return "\n".join([*lines, "", f"## {date}", line]) + "\n"
    end = next((i for i in range(heading + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    while end > heading + 1 and not lines[end - 1].strip():
        end -= 1
    lines.insert(end, line)
    return "\n".join(lines) + "\n"


def record(project: Project, work_id: str) -> list[Row]:
    """Add the retro rows of a work's latest loop and of its review, once each has ended; rows already there are left alone.

    Args:
        project: The project.
        work_id: E.g. "W-012".

    Returns:
        The rows added; empty when the loop has not ended or every row is there already.

    Raises:
        ValueError: The work has neither a loop record nor a review.

    Example:
        >>> [r.key for r in record(project, "W-012")]  # doctest: +SKIP
        ['AC-2']
    """
    from ..work.loop import last_run
    from ..work.review import rounds, standing

    lines, reviewed = last_run(project, work_id), rounds(project, work_id)
    if not lines and not reviewed:
        raise ValueError(msg("The run log has no loop or review for {work_id}", work_id=work_id))
    over = standing(project, work_id) in ("clean", "limit")
    rows = (rows_from_run(lines, project.enums) if lines else []) + rows_from_review(reviewed, work_id, over, project.enums)
    have = {(r.run, r.key) for _, r in all_rows(project)}
    added = [r for r in rows if (r.run, r.key) not in have]
    for row in added:
        _append(project, row)
    return added


def note(project: Project, target: str, stuck: str, solved: str = "") -> Row:
    """Write one line for what the AI got stuck on while building, in any way of building (with or without a loop).

    The time, the work and the line's ID are written by code; the two texts are the AI's, so a person confirms the line
    like any other.

    Args:
        project: The project.
        target: The task ("W-005-T02") or the work ("W-005").
        stuck: What it got stuck on, one line.
        solved: How it got past it, one line; empty when it did not.

    Returns:
        The row as saved.

    Raises:
        ValueError: There is no such work or task, or `stuck` is empty.

    Example:
        >>> note(project, "W-005-T02", "자동 커밋 연결이 아니면 멈춘다", "isolation_level=None").stuck  # doctest: +SKIP
        '자동 커밋 연결이 아니면 멈춘다'
    """
    m = TARGET.match(target.strip().upper())
    folder = project.find_work(m.group(1)) if m else None
    if m is None or folder is None:
        raise ValueError(msg("No such work or task: {target}", target=target))
    work, task = m.group(1), m.group(0) if m.group(2) else ""
    tasks = project.doc_path(folder, "tasks")
    if task and (not tasks.exists() or find_task(parse_tasks(read(tasks), project.names), task) is None):
        raise ValueError(msg("No such work or task: {target}", target=target))
    said = _clean(stuck, project.names)
    if not said:
        raise ValueError(msg("Write what it got stuck on in one line (--stuck)"))
    now = now_iso()
    row = Row(
        date=now[:10],
        time=now[11:16],
        work=work,
        key=project.names.retro_attr("stuck"),
        is_check=False,
        tries=0,
        result="",
        run=f"n-{uuid.uuid4().hex[:8]}",
        stuck=said,
        solved=_clean(solved, project.names),
        task=task,
    )
    _append(project, row)
    return row


def _append(project: Project, row: Row) -> Path:
    """Put a row in the file of its month, making the file when it is new."""
    path = _file(project, row.date)
    if not path.exists():
        month = row.date[:7]
        create_from_template(project, project.names.doc("retro"), path, {"id": f"RETRO-{month}", "month": month})
    write(path, _add_line(read(path), row.date, render_row(row, project.names)))
    _rewrite_summary(project, path)
    return path


def _find(project: Project, run: str, key: str) -> tuple[Path, Row]:
    checks = project.enums["retro_check"]
    for path, row in all_rows(project):
        role = "stuck" if row.stuck else checks.role_of(row.key)
        if row.run == run and (key == row.key or key.upper() in (row.key, role.upper())):
            return path, row
    raise ValueError(msg("No retro row for run {run} · {key}", run=run, key=key))


def _save(project: Project, path: Path, row: Row) -> None:
    lines = read(path).split("\n")
    lines[row.line] = render_row(row, project.names)
    write(path, "\n".join(lines))
    _rewrite_summary(project, path)


def check_judgment(project: Project, weakness: str, remedy: str, hypothesis: str) -> None:
    """Refuse a judgment whose values are not in the lists, or whose hypothesis is empty.

    Args:
        project: The project.
        weakness: A value of `retro_weakness`.
        remedy: A value of `retro_remedy`.
        hypothesis: The guess, one line.

    Raises:
        ValueError: A value is not in its list, or the hypothesis is empty.

    Example:
        >>> check_judgment(project, "명세", "LanternSpec", "문구가 설계에 없었다")  # doctest: +SKIP
    """
    for name, value in (("retro_weakness", weakness), ("retro_remedy", remedy)):
        if value not in project.enums.values(name):
            raise ValueError(msg("'{value}' is not one of: {items}", value=value, items=" · ".join(project.enums.values(name))))
    if not hypothesis.strip():
        raise ValueError(msg("The hypothesis can't be empty — write the guess in one line"))


def judge(project: Project, run: str, key: str, weakness: str, remedy: str, hypothesis: str, suggestion: str = "") -> Row:
    """Fill the judgment of a row; only the values of the lists are accepted.

    Args:
        project: The project.
        run: The loop run (`[실행:: …]`).
        key: The criterion ("AC-2") or the check (its name or role, e.g. "suite").
        weakness: A value of `retro_weakness`.
        remedy: A value of `retro_remedy`.
        hypothesis: The guess, one line.
        suggestion: What to change, one line; may be empty.

    Returns:
        The row as saved.

    Raises:
        ValueError: The row does not exist, or a value is not in its list.

    Example:
        >>> judge(project, "a1b2", "AC-2", "명세", "LanternSpec", "문구가 설계에 없었다").weakness  # doctest: +SKIP
        '명세'
    """
    check_judgment(project, weakness, remedy, hypothesis)
    path, row = _find(project, run, key)
    row.weakness, row.remedy = weakness, remedy
    row.hypothesis, row.suggestion = _clean(hypothesis, project.names), _clean(suggestion, project.names)
    row.confirmed = False  # a changed judgment is for a person to confirm again
    _save(project, path, row)
    return row


def confirm(project: Project, run: str, key: str) -> Row:
    """Mark a row confirmed: a person looked at the judgment and agrees.

    Args:
        project: The project.
        run: The loop run.
        key: The criterion or the check.

    Returns:
        The row as saved.

    Raises:
        ValueError: The row does not exist, or has no judgment yet.

    Example:
        >>> confirm(project, "a1b2", "AC-2").confirmed  # doctest: +SKIP
        True
    """
    path, row = _find(project, run, key)
    if not row.judged:
        raise ValueError(msg("Judge {key} first (lantern retro judge)", key=row.key))
    row.confirmed = True
    _save(project, path, row)
    return row


def review(project: Project) -> list[tuple[Path, Row]]:
    """List the rows nobody has confirmed, and rewrite every month's summary (a confirmation typed by hand counts).

    Args:
        project: The project.

    Returns:
        The unconfirmed (file, row) pairs, oldest first.

    Example:
        >>> len(review(project))  # doctest: +SKIP
        3
    """
    pairs = all_rows(project)
    for path in {p for p, _ in pairs}:
        _rewrite_summary(project, path)
    return [(p, r) for p, r in pairs if not r.confirmed]


def problems(project: Project, text: str) -> list[tuple[int, str, str]]:
    """Find what a monthly file holds that the names and lists do not know.

    Args:
        project: The project.
        text: The whole file.

    Returns:
        (1-based line, code, message) for each problem: a value outside its list, a field nobody knows, or half a judgment.

    Example:
        >>> problems(project, text)  # doctest: +SKIP
        [(7, 'retro-value', "'약함'은(는) 약점 목록에 없습니다 …")]
    """
    out: list[tuple[int, str, str]] = []
    n, e = project.names, project.enums
    for row in parse(text, n):
        at = row.line + 1
        for attr, name, label in (
            (row.weakness, "retro_weakness", n.retro_attr("weakness")),
            (row.remedy, "retro_remedy", n.retro_attr("remedy")),
            (row.result, "retro_result", n.retro_attr("result")),
            (row.key if row.is_check else "", "retro_check", n.retro_attr("check")),
        ):
            if attr and attr not in e.values(name):
                out.append(
                    (
                        at,
                        "retro-value",
                        msg("'{value}' is not in the {label} list ({items})", value=attr, label=label, items=" · ".join(e.values(name))),
                    )
                )
        for field_text in row.other:
            out.append((at, "retro-field", msg("{field} is not a field of an AI retro row", field=field_text)))
        if bool(row.weakness) != bool(row.remedy):
            out.append((at, "retro-half", msg("{key}: the weakness and the remedy are filled together", key=row.key)))
    return out
