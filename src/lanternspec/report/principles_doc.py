"""개발 원칙 문서(`규칙 · 결정 기록/개발 원칙.md`)를 기준표에서 만든다 — AGENTS.md에 넣은 핵심의 자세한 설명.

책임:
    - 고른 설계 원칙 · 작업 방식 · 코드 컨벤션을 설명 · 이유 · 지키는 법과 함께 한 문서로 쓰기

하지 않는 일:
    - 무엇을 고를지 정하기 → core/principles.py (select)
    - AGENTS.md의 짧은 요약 → tools/rules.py (principles_section)
"""

from __future__ import annotations

from pathlib import Path

from ..core import frontmatter, principles
from ..core.project import Project, read, today, write

DOC_NAME = "개발 원칙.md"


def doc_path(project: Project) -> Path:
    """개발 원칙 문서의 경로를 돌려준다.

    Args:
        project: 프로젝트.

    Returns:
        `docs/3. 현재 상태/규칙 · 결정 기록/개발 원칙.md`.

    Example:
        >>> project.rel(doc_path(project))  # doctest: +SKIP
        'docs/3. 현재 상태/규칙 · 결정 기록/개발 원칙.md'
    """
    return project.folder("rules") / DOC_NAME


def render(sel: principles.Selection, profile_language: str = "ko") -> str:
    r"""고른 결과를 개발 원칙 문서의 본문(frontmatter 없이)으로 만든다.

    Args:
        sel: 고른 원칙 · 작업 방식 · 컨벤션.
        profile_language: 문서 주석에 쓸 말 (lantern.yaml project.language).

    Returns:
        Markdown 본문.

    Example:
        >>> from lanternspec.core.profile import DEFAULTS, Profile
        >>> data = {**DEFAULTS, "project": {**DEFAULTS["project"], "kind": "cli"}}
        >>> print(render(principles.select(Profile(data))).split("\n")[0])
        # 🧭 개발 원칙
    """
    t = principles.table()
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
        lines += [f"| {principles.ROLE_LABEL.get(role, '패키지')} | {name} | {cmd} |" for role, (name, cmd) in c.tools.items()]
        lines += ["", "| 항목 | 규칙 |", "|---|---|"]
        lines += [f"| {principles.RULE_LABEL[k]} | {v} |" for k, v in c.rules.items()]
        lang = c.language if c.language != "typescript" else "ts"
        lines += [
            "",
            f"문서 주석: {c.docs_style} · {principles.DOC_LANGUAGE.get(profile_language, profile_language)}",
            "",
            f"```{lang}",
            c.example.rstrip(),
            "```",
        ]
    return "\n".join(lines) + "\n"


def write_doc(project: Project) -> Path | None:
    """개발 원칙 문서를 (다시) 쓴다. 내용이 그대로면 쓰지 않는다 (upgrade마다 바뀐 파일이 생기지 않게).

    Args:
        project: 프로젝트. lantern.yaml에 project.kind가 있어야 쓴다.

    Returns:
        쓴 문서 경로. project.kind가 없거나 docs/가 아직 없거나 내용이 그대로면 None.

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
    body = render(sel, str(project.profile.get("project.language") or "ko"))
    if path.exists() and frontmatter.parse(read(path)).body.strip() == body.strip():
        return None
    write(path, frontmatter.render(meta, body))
    return path
