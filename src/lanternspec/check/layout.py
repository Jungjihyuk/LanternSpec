"""Put documents where the current names.yaml says they belong — from any older layout, with no per-version code.

Documents carry their identity in frontmatter (`id: CUR-deploy`, `id: ADR-004`), so where a document
*is* and where it *should be* can be compared at any time. When a folder or document name changes in
names.yaml, `lantern upgrade` shows what would move and `lantern upgrade --apply` moves it.

Responsibilities:
    - where each document should be: fixed-id documents through DOC_FOLDERS, numbered documents
      (ADR · idea · debt card · meeting) through their ID kind's folder
    - plan the moves, the `template:` values to update and the links to rewrite (nothing changes)
    - apply the plan: `git mv` (history continues), rewrite links, one commit

Not here:
    - where each kind of document lives → core/profile.py (DOC_FOLDERS) · core/new_id.py (KINDS) · names.yaml
    - running it as part of an upgrade → tools/install.py (upgrade)
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..core import frontmatter, state
from ..core.links import Resolver, iter_links
from ..core.messages import msg
from ..core.new_id import KINDS
from ..core.profile import DOC_FOLDERS, doc_place
from ..core.project import Project, git, git_out, move_path, nfc, read, write

SKIP_HOOKS = {"LANTERN_SKIP_HOOKS": "1"}  # our own git hooks would check the commit we make


class LayoutError(RuntimeError):
    """The documents can't be moved now; the message says why and what to do.

    Example:
        >>> str(LayoutError("변경 사항이 있습니다"))
        '변경 사항이 있습니다'
    """


@dataclass
class LayoutPlan:
    """What it takes to bring the documents to the current layout.

    Attributes:
        moves: (from, to) document paths.
        templates: (document, old value, new value) for a `template:` field that kept an old name.
        links: (document, link as written, new link) for links that would break after the moves.
        conflicts: Problems a person must settle (two documents with one id, a target already taken).
        renamed_templates: (old, new) names of the project's template copies whose base template was renamed.

    Example:
        >>> LayoutPlan().empty, LayoutPlan(conflicts=["…"]).empty
        (True, True)
    """

    moves: list[tuple[Path, Path]] = field(default_factory=list)
    templates: list[tuple[Path, str, str]] = field(default_factory=list)
    links: list[tuple[Path, str, str]] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    renamed_templates: list[tuple[str, str]] = field(default_factory=list)  # (old, new) template names, for the install record

    @property
    def empty(self) -> bool:
        """Whether nothing needs to change (conflicts alone change nothing)."""
        return not (self.moves or self.templates or self.links)


def fixed_places(project: Project) -> dict[str, tuple[str, str | None]]:
    """Map each fixed document id to where it belongs and the template name it should record.

    Ids come from the base templates (`id: CUR-deploy`) and, for generated documents, from the
    modules that write them.

    Args:
        project: The project.

    Returns:
        id → (path from the documents root, template name or None for generated documents).

    Example:
        >>> fixed_places(project)["CUR-deploy"]  # doctest: +SKIP
        ('3. 현재 상태/배포 · 운영/배포.md', '배포')
    """
    from ..learn.debt import STATUS_DOC_ID
    from ..report.principles_doc import DOC_ID as PRINCIPLES_ID
    from ..work.scaffold import base_template_text

    generated = {"principles": PRINCIPLES_ID, "debt-status": STATUS_DOC_ID}
    names = project.names
    out: dict[str, tuple[str, str | None]] = {}
    for key in DOC_FOLDERS:
        place = doc_place(names, key)
        if key in generated:
            out[generated[key]] = (place, None)
            continue
        template = names.doc(key.replace("-", "_"))
        try:
            doc_id = frontmatter.as_str(frontmatter.parse(base_template_text(template, project.profile.language)).meta.get("id"))
        except FileNotFoundError:
            continue
        if doc_id and "${" not in doc_id:
            out[doc_id] = (place, template)
    return out


def _kind_folder(project: Project, doc_id: str) -> Path | None:
    """The folder a numbered document (ADR-004 · IDEA-012 · D-007 · MTG-003) belongs in; None for other ids."""
    for kind, spec in KINDS.items():
        if kind != "work" and re.fullmatch(rf"{spec['prefix']}-\d+", doc_id):
            return project.folder(str(spec["folder"]))
    return None


def _documents(project: Project) -> list[Path]:
    """Every Markdown document a person or lantern wrote — not templates, legacy originals (the legacy map is ours) or hidden folders."""
    skip = {project.folder(k).resolve() for k in ("templates", "legacy")}
    legacy_map = (project.docs / doc_place(project.names, "legacy-map")).resolve()  # ours, though it sits with the originals
    out = []
    for p in sorted(project.docs.rglob("*.md")):
        rel = p.relative_to(project.docs).parts
        if any(part.startswith(".") for part in rel):
            continue
        if p.resolve() != legacy_map and any(s in p.resolve().parents for s in skip):
            continue
        out.append(p)
    return out


def plan(project: Project) -> LayoutPlan:
    """Compare where each document is with where the current layout puts it. Changes nothing.

    Args:
        project: The project.

    Returns:
        The moves, template values and links to change, and the conflicts to report.

    Example:
        >>> [(project.docs_rel(a), project.docs_rel(b)) for a, b in plan(project).moves]  # doctest: +SKIP
        [('3. 현재 상태/규칙 · 결정 기록/ADR-001 인증.md', '3. 현재 상태/결정 기록/ADR-001 인증.md')]
    """
    result = LayoutPlan()
    if not project.docs.exists():
        return result
    places = fixed_places(project)
    seen: dict[str, Path] = {}
    docs = _documents(project)
    for path in docs:
        meta = frontmatter.parse(read(path)).meta
        doc_id = frontmatter.as_str(meta.get("id"))
        if doc_id in places:
            place, template = places[doc_id]
            if doc_id in seen:
                result.conflicts.append(
                    msg(
                        "Two documents have id {id}: {a} · {b} — keep one",
                        id=doc_id,
                        a=project.docs_rel(seen[doc_id]),
                        b=project.docs_rel(path),
                    )
                )
                continue
            seen[doc_id] = path
            dest = project.docs / place
            old_template = frontmatter.as_str(meta.get("template"))
            if template and old_template and old_template != template:
                result.templates.append((path, old_template, template))
        elif (folder := _kind_folder(project, doc_id)) is not None:
            dest = folder / path.name
        else:
            continue
        if nfc(str(dest)) == nfc(str(path)):
            continue
        if dest.exists():
            result.conflicts.append(
                msg(
                    "{a} belongs at {b}, but a file is already there — merge them by hand",
                    a=project.docs_rel(path),
                    b=project.docs_rel(dest),
                )
            )
            continue
        result.moves.append((path, dest))
    _plan_template_copies(project, places, result)
    result.links = _link_changes(project, docs, dict(result.moves))
    return result


def _plan_template_copies(project: Project, places: dict[str, tuple[str, str | None]], result: LayoutPlan) -> None:
    """A template copy carries the same id as its documents: when its base template was renamed, rename the copy too."""
    if not project.templates_dir.exists():
        return
    for path in sorted(project.templates_dir.glob("*.md")):
        meta = frontmatter.parse(read(path)).meta
        template = places.get(frontmatter.as_str(meta.get("id")), ("", None))[1]
        if not template or nfc(path.stem) == nfc(template):
            continue
        dest = project.templates_dir / f"{template}.md"
        if dest.exists():
            result.conflicts.append(
                msg(
                    "{a} belongs at {b}, but a file is already there — merge them by hand",
                    a=project.docs_rel(path),
                    b=project.docs_rel(dest),
                )
            )
            continue
        result.moves.append((path, dest))
        result.renamed_templates.append((nfc(path.stem), template))
        if frontmatter.as_str(meta.get("template")) not in ("", template):
            result.templates.append((path, frontmatter.as_str(meta.get("template")), template))


def _link_changes(project: Project, docs: list[Path], moved: dict[Path, Path]) -> list[tuple[Path, str, str]]:
    """Find the links a move would break and how to write them after it."""
    if not moved:
        return []
    resolver = Resolver(project.docs)
    root = resolver.root
    moved_r = {a.resolve(): b for a, b in moved.items()}
    out = []
    for source in docs:
        new_source = moved_r.get(source.resolve(), source)
        for link in iter_links(read(source)):
            target = resolver.resolve(link, source)
            if target is None or target.resolve() == source.resolve():
                continue
            new_target = moved_r.get(target.resolve(), target)
            if link.kind == "wiki":
                if "/" not in link.target or (new_target == target and new_source == source):
                    continue  # a bare name still finds the file (Obsidian looks it up by name)
                rel = nfc(os.path.relpath(new_target.resolve(), root))
                new_text = rel if link.target.lower().endswith(".md") else rel.removesuffix(".md")
            else:
                new_text = nfc(os.path.relpath(new_target, new_source.parent))
            if nfc(new_text) == nfc(link.target) or link.target not in link.raw:
                continue
            out.append((source, link.raw, link.raw.replace(link.target, new_text, 1)))
    return out


def describe(project: Project, result: LayoutPlan) -> list[str]:
    """Write a plan for the user.

    Args:
        project: The project.
        result: The plan.

    Returns:
        Lines: moves, template values, links, conflicts.

    Example:
        >>> describe(project, LayoutPlan())  # doctest: +SKIP
        []
    """
    out = []
    if result.moves:
        out.append(msg("📦 {count} documents are not where the current layout puts them", count=len(result.moves)))
        out += [f"   {project.docs_rel(a)} → {project.docs_rel(b)}" for a, b in result.moves]
    if result.templates:
        out.append(msg("🏷 {count} documents record an old template name", count=len(result.templates)))
        out += [f"   {project.docs_rel(p)}: {a} → {b}" for p, a, b in result.templates]
    if result.links:
        sources = {p for p, _, _ in result.links}
        out.append(msg("🔗 {count} links to rewrite in {docs} documents", count=len(result.links), docs=len(sources)))
        out += [f"   {project.docs_rel(p)}: {a} → {b}" for p, a, b in result.links[:20]]
    if result.conflicts:
        out.append(msg("⚠ Left for you to settle:"))
        out += [f"   {c}" for c in result.conflicts]
    return out


def changed_documents(project: Project) -> list[str]:
    """List the uncommitted changes under the documents root (where the documents' git runs).

    Args:
        project: The project.

    Returns:
        One `git status --porcelain` line per changed file; empty outside git.

    Example:
        >>> changed_documents(project)  # doctest: +SKIP
        [' M 개발문서 MOC.md']
    """
    cwd = project.docs_git_cwd()
    if git(["rev-parse", "--git-dir"], cwd).returncode != 0:
        return []
    return [line for line in git_out(["status", "--porcelain", "--", str(project.docs)], cwd).splitlines() if line]


def apply(project: Project, result: LayoutPlan) -> list[str]:
    """Carry out a plan: rewrite links and template values, move with `git mv`, then commit once.

    The documents' git (the docs worktree in local mode) must have nothing staged and no changes
    under the documents root, so the commit holds only this change and one revert undoes it.

    Args:
        project: The project.
        result: The plan from plan().

    Returns:
        What was done.

    Raises:
        LayoutError: The documents have uncommitted changes, or have never been committed.

    Example:
        >>> apply(project, plan(project))  # doctest: +SKIP
        ['✔ 문서 5개를 옮겼습니다 (커밋 3f2a1c0)']
    """
    if result.empty:
        return []
    cwd = project.docs_git_cwd()
    in_git = git(["rev-parse", "--git-dir"], cwd).returncode == 0
    if in_git:
        if git(["rev-parse", "--verify", "-q", "HEAD"], cwd).returncode != 0:
            raise LayoutError(msg("The documents have never been committed — commit them once, then run lantern upgrade --apply again"))
        staged = git_out(["diff", "--cached", "--name-only"], cwd)
        if staged or changed_documents(project):
            raise LayoutError(msg("Commit or stash the changes in the documents first, then run lantern upgrade --apply again"))
    edits: dict[Path, str] = {}
    for path, old, new in result.links:
        text = edits.get(path, read(path))
        edits[path] = text.replace(old, new)
    for path, _, new in result.templates:
        edits[path] = frontmatter.set_fields(edits.get(path, read(path)), {"template": new}, touch=False)
    _rename_template_records(project, result, edits)
    for path, text in edits.items():
        write(path, text)
    old_dirs = set()
    for src, dest in result.moves:
        move_path(project, src, dest)
        old_dirs.add(src.parent)
    for d in sorted(old_dirs, key=lambda p: len(p.parts), reverse=True):  # leave no empty old folders behind
        while d != project.docs and d.exists() and not any(d.iterdir()):
            d.rmdir()
            d = d.parent
    out = [msg("✔ Moved {count} documents · rewrote {links} links", count=len(result.moves), links=len(result.links))]
    if in_git:
        git(["add", "-A", "--", str(project.docs)], cwd)
        r = git(["commit", "-q", "-m", msg("docs: move documents to the current layout [lantern]")], cwd, env=SKIP_HOOKS)
        if r.returncode == 0:
            out.append(msg("   one commit {sha} — git revert {sha} undoes it", sha=git_out(["rev-parse", "--short", "HEAD"], cwd)))
    return out


def _rename_template_records(project: Project, result: LayoutPlan, edits: dict[Path, str]) -> None:
    """Carry each renamed template copy's install record over; an unedited copy stays unedited, so upgrade refreshes it."""
    if not result.renamed_templates:
        return
    st = state.load(project)
    records = st.setdefault("templates", {})
    for old, new in result.renamed_templates:
        rec = records.pop(old, None)
        if rec is None:
            continue
        path = project.templates_dir / f"{old}.md"
        if path in edits and rec.get("sha256") == state.sha256_text(read(path)):
            rec["sha256"] = state.sha256_text(edits[path])
        records[new] = rec
    state.save(project, st)
