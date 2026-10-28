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
from ..core.messages import msg
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
        return [
            Finding(
                "warn", rel, "ac-none", msg("No acceptance criteria (- [ ] AC-1 …)"), hint=msg("One per line in {name}", name=plan.name)
            )
        ]
    seen = set()
    for i, ac in enumerate(acs, start=1):
        line = ac.line_no + 1
        if ac.id in seen:
            out.append(Finding("error", rel, "ac-dup", msg("{id} number is duplicated", id=ac.id), line))
        seen.add(ac.id)
        if int(ac.id.split("-")[1]) != i:
            out.append(Finding("info", rel, "ac-order", msg("{id}: numbers are out of order (expected AC-{i})", id=ac.id, i=i), line))
        body = ac.text
        if "{{" in body:
            out.append(Finding("warn", rel, "ac-blank", msg("{id}: blanks remain", id=ac.id), line))
            continue
        if fmt == "gwt":
            if not re.search(rf"{action}\s*:", body) or not re.search(rf"{result_word}\s*:", body):
                out.append(
                    Finding(
                        "warn",
                        rel,
                        "ac-format",
                        msg(
                            "{id}: not in the {situation} · {action} · {result_word} form",
                            id=ac.id,
                            situation=situation,
                            action=action,
                            result_word=result_word,
                        ),
                        line,
                        msg(
                            "e.g. AC-1 Situation: on the sign-in screen · Action: pressing the Google button · Result: "
                            "home opens within 2 seconds"
                        ),
                    )
                )
            result = re.split(rf"{result_word}\s*:", body, maxsplit=1)[-1]
        else:
            if n.acceptance("simple_mark") not in body:
                out.append(Finding("warn", rel, "ac-format", msg("{id}: not in the 'when … then …' form", id=ac.id), line))
            result = body.split(n.acceptance("simple_mark"), 1)[-1]
        for word in n.acceptance("vague"):
            if word in body:
                out.append(
                    Finding(
                        "warn",
                        rel,
                        "ac-vague",
                        msg("{id}: hard-to-check word '{strip}'", id=ac.id, strip=word.strip()),
                        line,
                        msg('Replace it with a number · something visible · a state ("fast" → "within 2 seconds")'),
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
                        msg("{id}: the result can be read several ways ('{strip}')", id=ac.id, strip=word.strip()),
                        line,
                        msg("Split it into two criteria"),
                    )
                )
                break
        if len(result.strip()) < 4:
            out.append(Finding("warn", rel, "ac-result", msg("{id}: the result is too short", id=ac.id), line))
    # screen work under ui_reference=required needs a "matches the mockup" criterion
    if project.profile.get("plan.ui_reference") == "required" and meta.get("ui") is True:
        if not any(n.acceptance("mockup") in ac.text.lower() for ac in acs):
            out.append(
                Finding(
                    "warn",
                    rel,
                    "ac-mockup",
                    msg("A screen work without a 'the screen matches the mockup' acceptance criterion"),
                    hint=msg("e.g. AC-n Result: the screen matches the mockup screens/sign-in.png"),
                )
            )
        if not has_mockup(plan.parent, n):
            out.append(
                Finding(
                    "warn",
                    rel,
                    "mockup-missing",
                    msg("No screen mockup (an image · HTML under the screens folder)"),
                    hint=msg("Export it as HTML from Claude Design and put it in the screens folder"),
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
            raise ValueError(msg("Work {work_id} not found", work_id=work_id))
        plan = project.doc_path(w, "plan")
        if plan.exists():
            out += check_criteria(project, plan)
    return out
