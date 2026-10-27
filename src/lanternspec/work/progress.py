"""Save progress into a document's "지금 상황" section just before the conversation is compacted.

Responsibilities:
    - overwrite "지금 상황" of each active work's `기록.md` with the current state (progress · next · blocked · open questions)
    - move what it replaced into "지난 기록" so nothing is lost
    - without any `기록.md`, write to `4. 운영 기록/세션/<date>.md`
    - read "지금 상황" back so it can be put back after compaction

Not here:
    - deciding when to save → tools/agent_hooks.py (pre-compact · session-start)
    - picking the next task → work/tasks.py (next_task)
"""

from __future__ import annotations

import re
from pathlib import Path

from ..core import frontmatter
from ..core.project import Project, now_minute, read, today, work_id_of, write
from ..core.taskfile import UNKNOWN, parse_tasks
from .scaffold import create_from_template
from .tasks import next_task

NOW = "지금 상황"
HISTORY = "지난 기록"
SESSION_TEMPLATE = "세션 기록"


def section_body(text: str, heading: str) -> str:
    r"""Return the content of a `## heading` section (without `> [!guide]` lines).

    Args:
        text: The whole document.
        heading: The section name after `## `.

    Returns:
        The section content; an empty string if there is no such section.

    Example:
        >>> section_body("## 지금 상황\n> [!guide] 덮어쓴다\n\n- 진행: A\n\n## 증거\n", "지금 상황")
        '- 진행: A'
    """
    m = _section(text, heading)
    if m is None:
        return ""
    lines = [l for l in m.group(2).split("\n") if not l.startswith("> [!guide]")]
    return "\n".join(lines).strip()


def replace_section(text: str, heading: str, body: str) -> tuple[str, str]:
    r"""Replace the content of a `## heading` section, keeping its guide lines.

    Args:
        text: The whole document.
        heading: The section name after `## `.
        body: New content.

    Returns:
        (new document, previous content). Without the section, one is added at the end and the previous content is empty.

    Example:
        >>> new, old = replace_section("## 지금 상황\n> [!guide] 덮어쓴다\n\n- 진행: A\n\n## 증거\n", "지금 상황", "- 진행: B")
        >>> old
        '- 진행: A'
        >>> print(new, end="")
        ## 지금 상황
        > [!guide] 덮어쓴다
        <BLANKLINE>
        - 진행: B
        <BLANKLINE>
        ## 증거
    """
    m = _section(text, heading)
    if m is None:
        return text.rstrip() + f"\n\n## {heading}\n{body}\n", ""
    guides = [l for l in m.group(2).split("\n") if l.startswith("> [!guide]")]
    old = section_body(text, heading)
    block = "\n".join(guides) + ("\n\n" if guides else "") + body.strip() + "\n\n"
    return text[: m.start(2)] + block + text[m.end(2) :], old


def append_history(text: str, stamp: str, old: str) -> str:
    r"""Append replaced "지금 상황" content, with a timestamp, to the end of "지난 기록".

    Args:
        text: The whole document.
        stamp: Timestamp, e.g. "2026-10-27 14:05".
        old: The replaced content.

    Returns:
        The document with one more entry in "지난 기록"; the section is added at the end if missing.

    Example:
        >>> print(append_history("## 지난 기록\n> [!guide] 쌓는다\n", "2026-10-27 14:05", "- 진행: A"), end="")
        ## 지난 기록
        > [!guide] 쌓는다
        <BLANKLINE>
        - 2026-10-27 14:05
          - 진행: A
    """
    entry = f"- {stamp}\n" + "\n".join(f"  {l}" for l in old.split("\n") if l.strip()) + "\n"
    m = _section(text, HISTORY)
    if m is None:
        return text.rstrip() + f"\n\n## {HISTORY}\n{entry}"
    body = m.group(2).rstrip("\n")
    return text[: m.start(2)] + body + "\n\n" + entry + ("\n" if text[m.end(2) :] else "") + text[m.end(2) :]


def work_state(project: Project, work: Path) -> str:
    """Describe one work item's current state in "지금 상황" form (3–4 lines).

    Args:
        project: The project.
        work: The work folder.

    Returns:
        `- 진행:` · `- 다음:` lines, plus `- 막힌 것:` · `- 열린 질문:` when there are any.

    Example:
        >>> print(work_state(project, work))  # doctest: +SKIP
        - 진행: 구현 · 할 일 1/3 · 하는 중 W-001-T02
        - 다음: W-001-T03 저장 버튼
    """
    wid = work_id_of(work)
    stage = str(frontmatter.parse(read(work / "기획.md")).meta.get("status") or "") if (work / "기획.md").exists() else ""
    tasks = parse_tasks(read(work / "할 일.md")) if (work / "할 일.md").exists() else []
    doing = [t.id for t in tasks if not t.done and t.attrs.get("시작")]
    progress = [stage] if stage else []
    if tasks:
        progress.append(f"할 일 {sum(t.done for t in tasks)}/{len(tasks)}")
    if doing:
        progress.append("하는 중 " + ", ".join(doing))
    lines = [f"- 진행: {' · '.join(progress) or '시작 전'}"]
    nxt = next_task(project, wid)
    if nxt.task:
        lines.append(f"- 다음: {nxt.task.id} {nxt.task.title}" + (" (하는 중)" if nxt.task.id in doing else ""))
    elif nxt.all_done:
        lines.append("- 다음: 모든 할 일 완료 — 현재 상태 반영")
    else:
        lines.append("- 다음: 정해진 할 일 없음")
    if nxt.skipped:
        lines.append("- 막힌 것: " + " · ".join(f"{tid} ({why})" for tid, why in nxt.skipped[:3]))
    from ..report.status import open_unknowns  # mentions inside guide text don't count

    folder = project.docs_rel(work)
    unknowns = sum(n for doc, n in open_unknowns(project) if doc.startswith(folder + "/"))
    if unknowns:
        lines.append(f"- 열린 질문: {UNKNOWN} {unknowns}개")
    return "\n".join(lines)


def save_before_compact(project: Project) -> dict[Path, str]:
    """Save progress into documents and return each document's previous "지금 상황".

    Overwrites "지금 상황" of every active work item that has a `기록.md`. Without any, the state of
    all active work goes to `4. 운영 기록/세션/<date>.md` (one per day).
    Previous content moves to "지난 기록".

    Args:
        project: The project.

    Returns:
        Saved document path → the "지금 상황" it held before (empty when it was empty or only blanks).
        This earlier context (written by a person or the AI) can be put back after compaction too.

    Example:
        >>> {project.rel(p): old for p, old in save_before_compact(project).items()}  # doctest: +SKIP
        {'docs/2. 작업/W-001 로그인/기록.md': '- 진행: 로그인 버튼 붙이는 중'}
    """
    stamp = now_minute()
    records = [w / "기록.md" for w in project.work_dirs() if (w / "기록.md").exists()]
    if records:
        return {rec: _overwrite_now(rec, work_state(project, rec.parent), stamp) for rec in records}
    session = project.folder("sessions") / f"{today()}.md"
    if not session.exists():
        create_from_template(project, SESSION_TEMPLATE, session, {"id": f"SESSION-{today()}"})
    states = [f"**{work_id_of(w)}**\n{work_state(project, w)}" for w in project.work_dirs()]
    return {session: _overwrite_now(session, "\n\n".join(states) or "- 진행 중 작업 없음", stamp)}


def _overwrite_now(path: Path, body: str, stamp: str) -> str:
    """Overwrite one document's "지금 상황", move meaningful old content to "지난 기록", and return it."""
    text, old = replace_section(read(path), NOW, body)
    old = "\n".join(l for l in old.split("\n") if l.strip() and "{{" not in l)  # drop unfilled {{blank}} lines
    meaningful = bool(old) and old.strip() != body.strip()
    if meaningful:
        text = append_history(text, stamp, old)
    write(path, frontmatter.set_fields(text, {}))
    return old if meaningful else ""


def _section(text: str, heading: str) -> re.Match[str] | None:
    """Find a `## heading` line and its content (up to the next `## ` or the template-only mark)."""
    return re.search(rf"^(## {re.escape(heading)}[ \t]*\n)(.*?)(?=^## |^<!-- lantern:template-only -->|\Z)", text, re.M | re.S)
