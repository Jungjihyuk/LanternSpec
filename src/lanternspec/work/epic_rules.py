"""`lantern check --epic` — acceptance-criteria rule check (/l-plan step 5).

Two questions per criterion: does it mean one thing? can it be checked?

Not here:
    - the format checks of documents → check/check_docs.py
"""

from __future__ import annotations

import re
from pathlib import Path

from ..check.check_docs import Finding
from ..core import frontmatter
from ..core.names import Names
from ..core.project import Project, read
from ..core.taskfile import parse_criteria


def check_criteria(project: Project, plan: Path) -> list[Finding]:
    """Check the acceptance criteria of one plan.

    Numbers must be unique and in order, blanks filled, the format match `plan.ac_format`,
    and the result must be checkable (no vague words) and mean one thing (no "또는").
    Screen work under `plan.ui_reference: required` also needs a mockup and a "matches the mockup" criterion.

    Args:
        project: The project.
        plan: A work's `기획.md`.

    Returns:
        The findings; empty when every criterion passes.

    Example:
        >>> [f.message for f in check_criteria(project, plan)]  # doctest: +SKIP
        ["AC-1: 확인하기 어려운 말 '빠르게'"]
    """
    rel = project.rel(plan)
    text = read(plan)
    meta = frontmatter.parse(text).meta
    fmt = project.profile.get("plan.ac_format") or "gwt"
    acs = parse_criteria(text)
    n = project.names
    situation, action, result_word = n.acceptance("situation"), n.acceptance("action"), n.acceptance("result")
    out: list[Finding] = []
    if not acs:
        return [Finding("warn", rel, "ac-none", "수락 기준(- [ ] AC-1 …)이 없습니다", hint=f"{plan.name}에 한 줄에 하나씩")]
    seen = set()
    for i, ac in enumerate(acs, start=1):
        line = ac.line_no + 1
        if ac.id in seen:
            out.append(Finding("error", rel, "ac-dup", f"{ac.id} 번호가 겹칩니다", line))
        seen.add(ac.id)
        if int(ac.id.split("-")[1]) != i:
            out.append(Finding("info", rel, "ac-order", f"{ac.id}: 번호가 순서대로가 아닙니다 (기대 AC-{i})", line))
        body = ac.text
        if "{{" in body:
            out.append(Finding("warn", rel, "ac-blank", f"{ac.id}: 빈칸이 남아 있습니다", line))
            continue
        if fmt == "gwt":
            if not re.search(rf"{action}\s*:", body) or not re.search(rf"{result_word}\s*:", body):
                out.append(
                    Finding(
                        "warn",
                        rel,
                        "ac-format",
                        f"{ac.id}: {situation} · {action} · {result_word} 형식이 아닙니다",
                        line,
                        "예: AC-1 상황: 로그인 화면에서 · 행동: 카카오 버튼을 누르면 · 결과: 2초 안에 홈이 열린다",
                    )
                )
            result = re.split(rf"{result_word}\s*:", body, maxsplit=1)[-1]
        else:
            if n.acceptance("simple_mark") not in body:
                out.append(Finding("warn", rel, "ac-format", f"{ac.id}: '~하면 ~된다' 형식이 아닙니다", line))
            result = body.split(n.acceptance("simple_mark"), 1)[-1]
        for word in n.acceptance("vague"):
            if word in body:
                out.append(
                    Finding(
                        "warn",
                        rel,
                        "ac-vague",
                        f"{ac.id}: 확인하기 어려운 말 '{word.strip()}'",
                        line,
                        '숫자 · 화면에 보이는 것 · 상태로 바꾸세요 ("빠르게" → "2초 안에")',
                    )
                )
                break
        for word in n.acceptance("ambiguous"):
            if word in f" {result} ":
                out.append(
                    Finding(
                        "warn",
                        rel,
                        "ac-ambiguous",
                        f"{ac.id}: 결과가 여러 뜻으로 읽힙니다 ('{word.strip()}')",
                        line,
                        "기준을 둘로 나누세요",
                    )
                )
                break
        if len(result.strip()) < 4:
            out.append(Finding("warn", rel, "ac-result", f"{ac.id}: 결과가 너무 짧습니다", line))
    # screen work under ui_reference=required needs a "matches the mockup" criterion
    if project.profile.get("plan.ui_reference") == "required" and meta.get("ui") is True:
        if not any("시안" in ac.text for ac in acs):
            out.append(
                Finding(
                    "warn",
                    rel,
                    "ac-mockup",
                    "화면 작업인데 '화면이 시안과 같다' 수락 기준이 없습니다",
                    hint="예: AC-n 결과: 화면이 화면/로그인.png 시안과 같다",
                )
            )
        if not has_mockup(plan.parent, n):
            out.append(
                Finding(
                    "warn",
                    rel,
                    "mockup-missing",
                    "화면 시안이 없습니다 (화면/ 아래 이미지 · HTML)",
                    hint="Claude Design에서 HTML로 내보내 화면/에 두세요",
                )
            )
    return out


MOCKUP_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".html", ".htm", ".pdf"}


def has_mockup(work_dir: Path, names: Names) -> bool:
    """Tell whether a work folder has a screen mockup (an image, HTML or PDF in its mockup folder, `화면/`).

    Args:
        work_dir: The work folder.
        names: The project's names (the mockup folder's name).

    Returns:
        True when at least one mockup file exists.

    Example:
        >>> from lanternspec.core.names import load
        >>> has_mockup(Path("no-such-work"), load("ko"))
        False
    """
    d = work_dir / names.folder("screens")
    return d.exists() and any(p.suffix.lower() in MOCKUP_EXT for p in d.rglob("*") if p.is_file())


def run(project: Project, work_id: str | None = None) -> list[Finding]:
    """Check the acceptance criteria of one work or of every work in progress.

    Args:
        project: The project.
        work_id: Only this work; every work in progress when None.

    Returns:
        The findings of all checked plans.

    Raises:
        ValueError: work_id is given but the work does not exist.

    Example:
        >>> run(project, "W-012")  # doctest: +SKIP
        []
    """
    out: list[Finding] = []
    works = [project.find_work(work_id)] if work_id else project.work_dirs()
    for w in works:
        if w is None:
            raise ValueError(f"작업 {work_id}를 찾지 못했습니다")
        plan = project.doc_path(w, "plan")
        if plan.exists():
            out += check_criteria(project, plan)
    return out
