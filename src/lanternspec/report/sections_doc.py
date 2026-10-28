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
from ..core.messages import msg
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
        name = f"`## {title}`" + (msg(" (old names: {items})", items=", ".join(older)) if older else "")
        state = msg("not used") if n.is_unused(s.role) else msg("used")
        rows.append(f"| {docs} | {name} | {s.feature} | {state} | `{s.role}` |")
    return "\n".join(
        [
            msg("# 🔒 Protected Sections"),
            "",
            msg("> ⚙️ Generated — `lantern upgrade` · `lantern sections` · don't edit by hand."),
            "",
            f"> [!abstract] {n.marker('glance')}",
            msg(
                "> These are the sections lantern reads or writes. Templates and documents are yours to "
                "edit, but if you rename or delete one of these sections, the feature can't find it. Then "
                "`lantern check` asks whether you changed it on purpose and keeps working the way you "
                "answer."
            ),
            "",
            msg("| Document | Section | What it is for | This project | Key |"),
            "|---|---|---|---|---|",
            *rows,
            "",
            msg("## To change them"),
            msg(
                '- If you renamed it: `lantern sections rename <key> "new title"` — documents made with the old title are still recognized'
            ),
            msg("- To stop using the feature: `lantern sections off <key>` (to use it again, `lantern sections on <key>`)"),
            msg("- The answers are kept in `docs.sections` · `docs.unused_sections` of `lantern.yaml`"),
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
