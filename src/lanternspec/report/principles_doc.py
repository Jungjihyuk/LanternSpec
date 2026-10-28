"""Build the design-principles document (`규칙 · 결정 기록/개발 원칙.md`) from the tables — the details behind the AGENTS.md essentials.

Responsibilities:
    - write the chosen design principles, ways of working and code conventions, with reasons and how to follow them, in one document

Not here:
    - deciding what to choose → core/principles.py (select)
    - the short AGENTS.md summary → tools/rules.py (principles_section)
"""

from __future__ import annotations

from pathlib import Path

from ..core import frontmatter, principles
from ..core.project import Project, read, today, write


def doc_path(project: Project) -> Path:
    """Return the path of the design-principles document.

    Args:
        project: The project.

    Returns:
        `docs/3. 현재 상태/규칙 · 결정 기록/개발 원칙.md`.

    Example:
        >>> project.rel(doc_path(project))  # doctest: +SKIP
        'docs/3. 현재 상태/규칙 · 결정 기록/개발 원칙.md'
    """
    return project.folder("rules") / project.names.file("principles")


def render(sel: principles.Selection, profile_language: str = "ko") -> str:
    r"""Render a selection as the body of the design-principles document (without frontmatter).

    Args:
        sel: The chosen principles, ways of working and conventions.
        profile_language: Language for doc comments (lantern.yaml project.comment_language, else language).

    Returns:
        Markdown body.

    Example:
        >>> from lanternspec.core.profile import DEFAULTS, Profile
        >>> data = {**DEFAULTS, "project": {**DEFAULTS["project"], "kind": "cli"}}
        >>> print(render(principles.select(Profile(data))).split("\n")[0])
        # 🧭 개발 원칙
    """
    t = principles.table(sel.locale)
    names = t["levels"]
    lines = [
        "# 🧭 개발 원칙",
        "",
        "> ⚙️ 자동 생성 — `lantern upgrade` · 손으로 고치지 마세요.",
        "> 바꾸려면 lantern.yaml의 project.kind · external · code_size · languages를 고치고 `lantern upgrade`.",
        "> 이 프로젝트만의 규칙은 AGENTS.md의 LanternSpec 블록 밖에 적는다.",
        "",
        "> [!abstract] 한눈에 보기",
        f"> {sel.summary()}" + (" · " + " · ".join(c.label for c in sel.conventions) if sel.conventions else ""),
        f"> {t['priority']}",
        "",
        "## 설계 원칙",
        "| 원칙 | 단계 | 왜 |",
        "|---|---|---|",
    ]
    lines += [f"| {p.name} | {names[p.level]} | {p.reason} |" for p in sel.principles]
    for p in sel.principles:
        if p.level == "skip":
            continue
        lines += ["", f"### {p.name} — {names[p.level]}", p.explain, ""]
        lines += [f"- {r}" for r in p.rules]
        if p.note:
            lines.append(f"- {p.note}")
    skipped = sel.at("skip")
    if skipped:
        lines += [
            "",
            f"> {names['skip']}: " + " · ".join(p.name for p in skipped) + " — 이 종류 · 규모에서는 넣지 않는다.",
        ]
    lines += ["", "## 작업 방식 (늘)"]
    for name, rules in sel.always:
        lines += ["", f"### {name}"] + [f"- {r}" for r in rules]
    for c in sel.conventions:
        lines += ["", f"## 코드 컨벤션 — {c.label}", "| 할 일 | 도구 | 기본 명령 |", "|---|---|---|"]
        lines += [f"| {principles.role_label(role, sel.locale)} | {name} | {cmd} |" for role, (name, cmd) in c.tools.items()]
        lines += ["", "| 항목 | 규칙 |", "|---|---|"]
        lines += [f"| {principles.rule_label(k, sel.locale)} | {v} |" for k, v in c.rules.items()]
        lang = c.language if c.language != "typescript" else "ts"
        lines += [
            "",
            f"문서 주석: {c.docs_style} · {principles.comment_languages(sel.locale).get(profile_language, profile_language)}",
            "",
            f"```{lang}",
            c.example.rstrip(),
            "```",
        ]
    return "\n".join(lines) + "\n"


def write_doc(project: Project) -> Path | None:
    """(Re)write the design-principles document; skip when unchanged (so upgrades do not leave changed files).

    Args:
        project: The project. Nothing is written without project.kind in lantern.yaml.

    Returns:
        Path written; None without project.kind or docs/, or when unchanged.

    Example:
        >>> project.rel(write_doc(project))  # doctest: +SKIP
        'docs/3. 현재 상태/규칙 · 결정 기록/개발 원칙.md'
    """
    sel = principles.select(project.profile)
    if sel is None or not project.docs.exists():
        return None
    meta = {
        "id": "PRINCIPLES",
        "type": "report",
        "status": project.enums.value("current_status", "active"),
        "generated": True,
        "updated": today(),
        "kind": sel.kind,
        "code_size": sel.code,
    }
    path = doc_path(project)
    body = render(sel, project.profile.comment_language)
    if path.exists() and frontmatter.parse(read(path)).body.strip() == body.strip():
        return None
    write(path, frontmatter.render(meta, body))
    return path
