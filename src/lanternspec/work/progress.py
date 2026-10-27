"""대화가 압축되기 직전, 진행 상황을 문서의 "지금 상황" 칸에 저장한다.

책임:
    - 진행 중 작업의 `기록.md` "지금 상황"을 지금 상태(진행 · 다음 · 막힌 것 · 열린 질문)로 덮어쓰기
    - 덮어쓰기 전의 내용을 "지난 기록"으로 옮겨 잃지 않기
    - `기록.md`가 있는 작업이 없으면 `4. 운영 기록/세션/날짜.md`에 남기기
    - 압축 뒤 다시 넣어 줄 수 있게 "지금 상황" 칸 읽기

하지 않는 일:
    - 언제 저장할지 정하기 → tools/agent_hooks.py (pre-compact · session-start)
    - 다음 할 일 고르기 → work/tasks.py (next_task)
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
    r"""`## 제목` 칸의 내용을 돌려준다 (작성 안내 `> [!guide]` 줄은 뺀다).

    Args:
        text: 문서 전체 글.
        heading: `## ` 뒤의 칸 이름.

    Returns:
        칸의 내용. 칸이 없으면 빈 문자열.

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
    r"""`## 제목` 칸의 내용을 바꾼다. 작성 안내 줄은 그대로 둔다.

    Args:
        text: 문서 전체 글.
        heading: `## ` 뒤의 칸 이름.
        body: 새 내용.

    Returns:
        (바꾼 문서 글, 바꾸기 전 내용). 칸이 없으면 문서 끝에 칸을 만들고 바꾸기 전 내용은 빈 문자열.

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
    r"""밀려난 "지금 상황" 내용을 "지난 기록" 칸 끝에 시각과 함께 쌓는다.

    Args:
        text: 문서 전체 글.
        stamp: 기록 시각. 예: "2026-10-27 14:05".
        old: 밀려난 내용.

    Returns:
        "지난 기록"에 한 덩어리를 더한 문서 글. 칸이 없으면 문서 끝에 만든다.

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
    """작업 하나의 지금 상태를 "지금 상황" 칸 모양(3~4줄)으로 만든다.

    Args:
        project: 프로젝트.
        work: 작업 폴더.

    Returns:
        `- 진행:` · `- 다음:` · (있으면) `- 막힌 것:` · `- 열린 질문:` 줄.

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
    from ..report.status import open_unknowns  # 작성 안내 속 언급은 빼고 센다

    folder = project.docs_rel(work)
    unknowns = sum(n for doc, n in open_unknowns(project) if doc.startswith(folder + "/"))
    if unknowns:
        lines.append(f"- 열린 질문: {UNKNOWN} {unknowns}개")
    return "\n".join(lines)


def save_before_compact(project: Project) -> dict[Path, str]:
    """진행 상황을 문서에 저장하고, 문서마다 덮어쓰기 전의 "지금 상황"을 돌려준다.

    `기록.md`가 있는 진행 중 작업마다 "지금 상황"을 덮어쓴다. 그런 작업이 없으면
    `4. 운영 기록/세션/날짜.md`(그날 하나)에 진행 중 작업 전체의 상태를 남긴다.
    덮어쓰기 전의 내용은 "지난 기록"으로 옮긴다.

    Args:
        project: 프로젝트.

    Returns:
        저장한 문서 경로 → 덮어쓰기 전에 적혀 있던 "지금 상황" (비어 있었거나 빈칸뿐이면 빈 문자열).
        압축 뒤에 이 옛 내용(사람 · AI가 적어 둔 맥락)도 함께 다시 넣어 줄 수 있다.

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
    """한 문서의 "지금 상황"을 덮어쓰고, 의미 있던 옛 내용은 "지난 기록"으로 옮긴 뒤 그 옛 내용을 돌려준다."""
    text, old = replace_section(read(path), NOW, body)
    old = "\n".join(l for l in old.split("\n") if l.strip() and "{{" not in l)  # 채우지 않은 빈칸 줄은 버린다
    meaningful = bool(old) and old.strip() != body.strip()
    if meaningful:
        text = append_history(text, stamp, old)
    write(path, frontmatter.set_fields(text, {}))
    return old if meaningful else ""


def _section(text: str, heading: str) -> re.Match[str] | None:
    """`## 제목` 줄과 그 칸의 내용(다음 `## ` · 템플릿 전용 표시 전까지)을 찾는다."""
    return re.search(rf"^(## {re.escape(heading)}[ \t]*\n)(.*?)(?=^## |^<!-- lantern:template-only -->|\Z)", text, re.M | re.S)
