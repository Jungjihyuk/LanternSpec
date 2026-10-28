"""Build the protected-sections page (`0. 템플릿/_meta/보호 칸.md`): which sections lantern uses, and this project's choices.

Templates and documents carry no marks; this page is where a person (or the AI working on templates)
looks up which sections lantern reads or writes before changing a template.

Not here:
    - the list of protected sections → resources/names.yaml (sections)
    - asking about a missing section → check/check_docs.py
"""

from __future__ import annotations

from pathlib import Path

from ..core import frontmatter
from ..core.project import Project, read, today, write


def page_path(project: Project) -> Path:
    """Return where the protected-sections page lives.

    Args:
        project: The project.

    Returns:
        `docs/0. 템플릿/_meta/보호 칸.md`.

    Example:
        >>> page_path(project).name  # doctest: +SKIP
        '보호 칸.md'
    """
    return project.templates_dir / "_meta" / project.names.file("sections_page")


def render(project: Project) -> str:
    """Render the page body: one row per protected section, grouped by document.

    Args:
        project: The project.

    Returns:
        Markdown body (without frontmatter).

    Example:
        >>> render(project).splitlines()[0]  # doctest: +SKIP
        '# 🔒 보호 칸'
    """
    n = project.names
    rows = []
    for s in n.sections():
        docs = ", ".join(f"`{n.file(d)}`" for d in s.docs)
        title = n.title(s.role)
        older = [t for t in n.titles(s.role) if t != title]
        name = f"`## {title}`" + (f" (예전 이름: {', '.join(older)})" if older else "")
        state = "쓰지 않음" if n.is_unused(s.role) else "사용"
        rows.append(f"| {docs} | {name} | {s.feature} | {state} | `{s.role}` |")
    return "\n".join(
        [
            "# 🔒 보호 칸",
            "",
            "> ⚙️ 자동 생성 — `lantern upgrade` · `lantern sections` · 손으로 고치지 마세요.",
            "",
            f"> [!abstract] {n.marker('glance')}",
            "> lantern이 읽거나 써 넣는 칸입니다. 템플릿과 문서는 자유롭게 고쳐도 되지만, 이 칸의 제목을 바꾸거나 지우면 "
            "그 기능이 이 칸을 찾지 못합니다. 그때는 `lantern check`가 일부러 바꾼 것인지 묻고, 답한 대로 계속 동작합니다.",
            "",
            "| 문서 | 칸 | 이 칸으로 하는 일 | 이 프로젝트 | 키 |",
            "|---|---|---|---|---|",
            *rows,
            "",
            "## 바꾸고 싶을 때",
            '- 제목을 바꿨다면: `lantern sections rename <키> "새 제목"` — 예전 제목으로 만든 문서도 계속 알아본다',
            "- 이 기능을 쓰지 않으려면: `lantern sections off <키>` (다시 쓰려면 `lantern sections on <키>`)",
            "- 답은 `lantern.yaml`의 `docs.sections` · `docs.unused_sections`에 남는다",
            "",
        ]
    )


def write_page(project: Project) -> Path | None:
    """Write the page when the template folder exists, skipping the write when nothing changed.

    Args:
        project: The project.

    Returns:
        The page when it was written; None when skipped (no template folder, or unchanged).

    Example:
        >>> write_page(project)  # doctest: +SKIP
        PosixPath('…/0. 템플릿/_meta/보호 칸.md')
    """
    if not project.templates_dir.exists():
        return None
    path = page_path(project)
    body = render(project)
    if path.exists() and frontmatter.parse(read(path)).body.strip() == body.strip():
        return None
    meta = {"id": "META-sections", "type": "report", "generated": True, "updated": today()}
    write(path, frontmatter.render(meta, body))
    return path
