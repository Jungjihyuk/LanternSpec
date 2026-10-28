"""`lantern template …` — the scripted half of /l-template.

list · lint · level · bump · outdated · diff · new · usage · migrate

Responsibilities:
    - list the project's templates and compare them with the bundled base
    - lint a template's format; work out how big a change is and bump its version
    - find documents made from older template versions and migrate them, keeping every piece of content

Not here:
    - checking documents made from templates → check/check_docs.py
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..core import frontmatter, state, templating
from ..core.messages import msg
from ..core.project import Project, git, nfc, read, today, write
from ..work.scaffold import base_template_names, base_template_text, base_values, condition_context, template_version
from .check_docs import Finding, _active_doc, semver, version_gap

SYSTEM_KEYS = {
    "id",
    "name",
    "today",
    "work_id",
    "links",
    "project",
    "kind",
    "status",
    "variant",
    "owner",
    "aliases",
    "area",
    "auto",
    "raw",
    "note",
    "work",
    "session",
    "work_text",
    "profile_table",
    "members_table",
    "legacy_rows",
    "base",
}
_SYS_RE = re.compile(r"\$\{([a-z_]+(?:\.[a-z_]+)*)\}")


def template_path(project: Project, name: str) -> Path:
    """Find the project's template file by name.

    Args:
        project: The project.
        name: Template name.

    Returns:
        The file in `docs/0. 템플릿`.

    Raises:
        FileNotFoundError: The project has no template by that name.

    Example:
        >>> template_path(project, "기획").name  # doctest: +SKIP
        '기획.md'
    """
    p = project.templates_dir / f"{name}.md"
    if p.exists():
        return p
    for cand in project.templates_dir.glob("*.md"):
        if nfc(cand.stem) == nfc(name):
            return cand
    raise FileNotFoundError(
        msg("Template '{name}' is not in {rel} (lantern template list)", name=name, rel=project.rel(project.templates_dir))
    )


def names(project: Project) -> list[str]:
    """List the project's templates.

    Args:
        project: The project.

    Returns:
        Template names, sorted; empty when there is no template folder.

    Example:
        >>> names(project)[:2]  # doctest: +SKIP
        ['ADR', '기록']
    """
    if not project.templates_dir.exists():
        return []
    return sorted(nfc(p.stem) for p in project.templates_dir.glob("*.md"))


# --------------------------------------------------------------------------- list · diff


def list_rows(project: Project) -> list[str]:
    """Describe each template in one line: version, base or own, edited, newer base available.

    Args:
        project: The project.

    Returns:
        One line per template.

    Example:
        >>> list_rows(project)[0]  # doctest: +SKIP
        'ADR  v1.0.0  (기본 양식)'
    """
    st = state.load(project)
    language = project.profile.language
    base_names = set(base_template_names(language))
    rows = []
    for name in names(project):
        text = read(template_path(project, name))
        ver = template_version(text)
        info = st["templates"].get(name) or {}
        modified = info.get("sha256") and state.sha256_text(text) != info.get("sha256")
        base = ""
        if name in base_names:
            bv = template_version(base_template_text(name, language))
            if version_gap(info.get("based_on") or ver, bv):
                base = msg(" · base template {bv} is out", bv=bv)
        origin = msg("base template") if name in base_names else msg("custom template")
        rows.append(f"{name}  v{ver}  ({origin}{msg(', refined') if modified else ''}{base})")
    return rows


def diff_base(project: Project, name: str) -> str:
    """Show how the project's copy of a template differs from the bundled base.

    Args:
        project: The project.
        name: Template name.

    Returns:
        A unified diff; a "same as base" line when nothing differs.

    Raises:
        FileNotFoundError: The project or the package has no template by that name.

    Example:
        >>> diff_base(project, "기획")  # doctest: +SKIP
        '기본 양식과 같습니다'
    """
    mine = read(template_path(project, name)).splitlines(keepends=True)
    base = base_template_text(name, project.profile.language).splitlines(keepends=True)
    folder = project.names.folder("templates")
    out = "".join(difflib.unified_diff(base, mine, fromfile=msg("base template/{name}.md", name=name), tofile=f"{folder}/{name}.md"))
    return out or msg("Same as the base template")


# --------------------------------------------------------------------------- lint


def lint(project: Project, name: str) -> list[Finding]:
    """Check a template's own format.

    Common frontmatter, a 1.2.0-style version, a known type, allowed blank names, known `${…}` values,
    the at-a-glance box, the change log and its last version, and writing guides.

    Args:
        project: The project.
        name: Template name.

    Returns:
        The findings; empty when the template is in shape.

    Raises:
        FileNotFoundError: The project has no template by that name.

    Example:
        >>> lint(project, "기획")  # doctest: +SKIP
        []
    """
    p = template_path(project, name)
    rel = project.rel(p)
    text = read(p)
    out: list[Finding] = []
    doc = frontmatter.parse(text)
    if doc.error or not doc.has_frontmatter:
        return [Finding("error", rel, "frontmatter", doc.error or msg("No frontmatter"))]
    meta = doc.meta
    for key in ("id", "type", "status", "created", "updated", "links", "template", "template_version"):
        if key not in meta:
            out.append(Finding("error", rel, "common-fields", msg("Common frontmatter '{key}' is missing", key=key)))
    if meta.get("template") and nfc(str(meta["template"])) != nfc(p.stem):
        out.append(
            Finding(
                "warn",
                rel,
                "template-name",
                msg("template: '{template}' differs from the file name '{stem}'", template=meta["template"], stem=p.stem),
            )
        )
    if not re.match(r"^\d+\.\d+\.\d+$", frontmatter.as_str(meta.get("template_version"))):
        out.append(Finding("error", rel, "version", msg("template_version must look like 1.2.0")))
    if "based_on" not in meta:
        out.append(Finding("info", rel, "based-on", msg("No based_on (for a custom template, the same as template_version)")))
    enums = project.enums
    if meta.get("type") and str(meta["type"]) not in enums.values("doc_type"):
        out.append(Finding("error", rel, "enum", msg("type '{type}' is not in enums.yaml doc_type", type=meta["type"])))
    n = project.names
    mark = n.marker("required")
    for pname, _req, line in templating.placeholders(text, mark):
        base = templating.field_base_name(pname, mark).lower()
        if base in templating.FORBIDDEN_FIELD_NAMES:
            out.append(
                Finding(
                    "error",
                    rel,
                    "forbidden-name",
                    msg("The blank name '{pname}' can't be used (no date · time · title)", pname=pname),
                    line,
                )
            )
        if "|" in pname:
            out.append(Finding("error", rel, "pipe", msg("The blank name has '|' — mark required ones with '{mark}'", mark=mark), line))
    enum_keys = project.enums.context()  # ${work_status.plan} · ${debt_status.new.label} …
    for m in _SYS_RE.finditer(text):
        if m.group(1) not in SYSTEM_KEYS and m.group(1) not in enum_keys:
            out.append(Finding("warn", rel, "system-key", msg("A value the script doesn't know: ${{{group}}}", group=m.group(1))))
    glance, changelog = n.marker("glance"), n.marker("changelog")
    if not re.search(rf"^>\s*\[!abstract\][^\n]*{re.escape(glance)}\s*\n>\s*\S", text, re.M):
        out.append(Finding("warn", rel, "glance", msg("The '> [!abstract] {glance}' section at the top is missing", glance=glance)))
    if templating.TEMPLATE_ONLY not in text or f"## {changelog}" not in text:
        out.append(
            Finding(
                "warn",
                rel,
                "changelog",
                msg(
                    "{template_only} + '## {changelog}' at the bottom is missing",
                    template_only=templating.TEMPLATE_ONLY,
                    changelog=changelog,
                ),
            )
        )
    else:
        rows = re.findall(r"^\|\s*(\d+\.\d+\.\d+)\s*\|", text.split(templating.TEMPLATE_ONLY, 1)[1], re.M)
        if rows and rows[-1] != frontmatter.as_str(meta.get("template_version")):
            out.append(
                Finding(
                    "warn",
                    rel,
                    "changelog-version",
                    msg(
                        "{changelog} last version {rows} ≠ template_version {get}",
                        changelog=changelog,
                        rows=rows[-1],
                        get=meta.get("template_version"),
                    ),
                )
            )
    if "> [!guide]" not in text:
        out.append(Finding("info", rel, "guide", msg("No '> [!guide]' writing notes at all")))
    return out


# --------------------------------------------------------------------------- level · bump


def _norm_heading(h: str) -> str:
    h = re.sub(r"[^\w가-힣]+", "", nfc(h)).lower()
    return h


def structure(text: str, required: str) -> tuple[list[str], list[str]]:
    r"""Read a template's structure: its `## ` headings and its blank names.

    Args:
        text: Template text.
        required: The mark of a required blank, e.g. "(필수)".

    Returns:
        (headings, blank names without the required mark, in order without repeats).

    Example:
        >>> structure("## 목표\n{{목표 (필수)}}\n## 메모\n{{메모}} {{메모}}\n", "(필수)")
        (['목표', '메모'], ['목표', '메모'])
    """
    body = templating.strip_template_only(text)
    heads = [l[3:].strip() for l in body.split("\n") if l.startswith("## ")]
    fields = [templating.field_base_name(n, required) for n, _, _ in templating.placeholders(body, required)]
    return heads, list(dict.fromkeys(fields))


def change_level(old: str, new: str, required: str) -> str | None:
    r"""Work out how big a template change is.

    patch = only guides or wording changed · minor = blanks, sections or frontmatter keys added ·
    major = any of them removed or renamed.

    Args:
        old: The template before.
        new: The template after.
        required: The mark of a required blank, e.g. "(필수)".

    Returns:
        "patch", "minor" or "major"; None when nothing changed.

    Example:
        >>> change_level("## 목표\n{{목표}}\n", "## 목표\n{{목표}}\n## 메모\n{{메모}}\n", "(필수)")
        'minor'
        >>> change_level("## 목표\n{{목표}}\n", "## 목적\n{{목적}}\n", "(필수)")
        'major'
    """
    if templating.strip_template_only(old) == templating.strip_template_only(new):
        return None
    oh, of = structure(old, required)
    nh, nf = structure(new, required)
    removed = (set(of) - set(nf)) | (set(oh) - set(nh))
    added = (set(nf) - set(of)) | (set(nh) - set(oh))
    old_meta = set(frontmatter.parse(old).meta) - {"updated", "template_version"}
    new_meta = set(frontmatter.parse(new).meta) - {"updated", "template_version"}
    removed |= {f"frontmatter {k}" for k in old_meta - new_meta}
    added |= {f"frontmatter {k}" for k in new_meta - old_meta}
    if removed:
        return "major"
    if added:
        return "minor"
    return "patch"


def committed_text(project: Project, path: Path, rev: str = "HEAD") -> str | None:
    """Read a file as it was at a git revision.

    Args:
        project: The project.
        path: The file.
        rev: The revision.

    Returns:
        The file's text then; None when it was not committed or is outside the repository.

    Example:
        >>> committed_text(project, template_path(project, "기획"))[:3]  # doctest: +SKIP
        '---'
    """
    cwd = project.docs_git_cwd()
    try:
        rel = nfc(str(path.resolve().relative_to(cwd.resolve())))
    except ValueError:
        return None
    r = git(["show", f"{rev}:{rel}"], cwd)
    return r.stdout if r.returncode == 0 else None


def level(project: Project, name: str, rev: str = "HEAD") -> tuple[str | None, str]:
    """Work out how big the uncommitted change to a template is (against git, else the bundled base).

    Args:
        project: The project.
        name: Template name.
        rev: The revision to compare with.

    Returns:
        (change level or None, what it was compared with — or why it could not compare).

    Raises:
        FileNotFoundError: The project has no template by that name.

    Example:
        >>> level(project, "기획")  # doctest: +SKIP
        ('minor', 'git HEAD')
    """
    p = template_path(project, name)
    old = committed_text(project, p, rev)
    source = f"git {rev}"
    if old is None:
        language = project.profile.language
        if name in base_template_names(language):
            old, source = base_template_text(name, language), msg("base template")
        else:
            return None, msg("No earlier version to compare with (never committed)")
    return change_level(old, read(p), project.names.marker("required")), source


def bump_version(ver: str, lvl: str) -> str:
    """Raise a version by a change level.

    Args:
        ver: The current version.
        lvl: "major", "minor" or "patch".

    Returns:
        The new version.

    Example:
        >>> bump_version("1.2.3", "minor"), bump_version("1.2.3", "major"), bump_version("1.2.3", "patch")
        ('1.3.0', '2.0.0', '1.2.4')
    """
    a, b, c = semver(ver)
    if lvl == "major":
        return f"{a + 1}.0.0"
    if lvl == "minor":
        return f"{a}.{b + 1}.0"
    return f"{a}.{b}.{c + 1}"


def bump(project: Project, name: str, lvl: str, note: str) -> str:
    """Raise a template's version and add a row to its change log.

    Args:
        project: The project.
        name: Template name.
        lvl: "patch", "minor", "major", or "auto" to work it out from the change.
        note: What changed, in one line.

    Returns:
        "name: level → vX.Y.Z".

    Raises:
        FileNotFoundError: The project has no template by that name.
        ValueError: The level is unknown, or "auto" found no change.

    Example:
        >>> bump(project, "기획", "auto", "메모 칸 추가")  # doctest: +SKIP
        '기획: minor → v1.1.0'
    """
    p = template_path(project, name)
    text = read(p)
    if lvl == "auto":
        detected, _ = level(project, name)
        if detected is None:
            raise ValueError(msg("Nothing changed — the version stays"))
        lvl = detected
    if lvl not in ("patch", "minor", "major"):
        raise ValueError(msg("level is one of patch · minor · major · auto"))
    new_ver = bump_version(template_version(text), lvl)
    text = frontmatter.set_fields(text, {"template_version": new_ver}, touch=False)
    row = f"| {new_ver} | {today()} | {note} |"
    changelog = project.names.marker("changelog")
    if templating.TEMPLATE_ONLY in text and f"## {changelog}" in text:
        text = text.rstrip("\n") + "\n" + row + "\n"
    else:
        text = text.rstrip("\n") + msg(
            "\n\n{template_only}\n## {changelog}\n| Version | Date | What changed |\n|---|---|---|\n{row}\n",
            template_only=templating.TEMPLATE_ONLY,
            changelog=changelog,
            row=row,
        )
    write(p, text)
    return f"{name}: {lvl} → v{new_ver}"


# --------------------------------------------------------------------------- outdated · usage


@dataclass
class Outdated:
    """A document made from an older version of its template.

    Attributes:
        path: The document.
        template: Its template.
        have: The template version it was made from.
        current: The template's current version.
        gap: "major", "minor" or "patch".
        active: Whether the document is still in use (only those get migrate suggestions).

    Example:
        >>> [o.gap for o in outdated(project)]  # doctest: +SKIP
        ['minor']
    """

    path: Path
    template: str
    have: str
    current: str
    gap: str
    active: bool


def outdated(project: Project, name: str | None = None, include_inactive: bool = False) -> list[Outdated]:
    """Find documents made from older template versions.

    Args:
        project: The project.
        name: Only this template; all when None.
        include_inactive: Also list documents no longer in use.

    Returns:
        The outdated documents.

    Example:
        >>> outdated(project, "기획")[0].current  # doctest: +SKIP
        '1.1.0'
    """
    versions = {n: template_version(read(template_path(project, n))) for n in names(project)}
    out: list[Outdated] = []
    for p in project.iter_docs():
        meta = frontmatter.parse(read(p)).meta
        t = nfc(str(meta.get("template") or ""))
        if not t or t not in versions or (name and t != nfc(name)):
            continue
        gap = version_gap(meta.get("template_version"), versions[t])
        if not gap:
            continue
        active = _active_doc(project, p, meta)
        if active or include_inactive:
            out.append(Outdated(p, t, frontmatter.as_str(meta.get("template_version")), versions[t], gap, active))
    return out


def usage(project: Project, name: str) -> list[str]:
    """Show, per blank of a template, how many of its documents still leave it empty.

    Args:
        project: The project.
        name: Template name.

    Returns:
        A header line and one line per blank; blanks always left empty are marked as candidates to drop.

    Raises:
        FileNotFoundError: The project has no template by that name.

    Example:
        >>> usage(project, "기획")[1]  # doctest: +SKIP
        '  0/3  {{목표}}'
    """
    tmpl = read(template_path(project, name))
    mark = project.names.marker("required")
    _, fields = structure(tmpl, mark)
    docs = [p for p in project.iter_docs() if nfc(str(frontmatter.parse(read(p)).meta.get("template") or "")) == nfc(name)]
    if not docs:
        return [msg("No documents made from template '{name}' yet", name=name)]
    rows = [msg("{count} documents from template '{name}' — documents still empty in each section:", name=name, count=len(docs))]
    for f in fields:
        blank = sum(1 for p in docs if re.search(r"\{\{\s*" + re.escape(f) + rf"(\s*{re.escape(mark)})?\s*\}}\}}", read(p)))
        mark = msg("  ← always empty (a candidate to delete or to reword its guide)") if blank == len(docs) and len(docs) >= 2 else ""
        rows.append(f"  {blank}/{len(docs)}  {{{{{f}}}}}{mark}")
    return rows


# --------------------------------------------------------------------------- new (sample → template)


def skeleton_from(project: Project, name: str, source: Path) -> str:
    """Turn a sample document into a blank template skeleton.

    The title becomes `${name}`; sections and table headers stay; content becomes {{blanks}};
    code fences stay empty; a guide line is added under each section.

    Args:
        project: The project.
        name: The new template's name.
        source: The sample document.

    Returns:
        The template text, with frontmatter and a change log.

    Example:
        >>> skeleton_from(project, "회고", Path("sample.md")).splitlines()[11]  # doctest: +SKIP
        '# ${name}'
    """
    body = frontmatter.parse(read(source)).body
    n = project.names
    glance = n.marker("glance")
    out: list[str] = ["# ${name}", "", f"> [!abstract] {glance}", f"> {{{{{glance} {n.marker('required')}}}}}"]
    in_fence = False
    current: str | None = None
    filled = False  # the current section already got its blank
    table_state = ""  # "" | "header" | "body"
    for line in body.split("\n"):
        s = line.strip()
        if s.startswith("```"):
            in_fence = not in_fence
            out.append(line)  # keep the fence (mermaid · dbml spot), drop its content
            continue
        if in_fence:
            continue
        if s.startswith("# "):
            continue  # the title becomes ${name}
        m = re.match(r"^(#{2,4})\s+(.+)$", s)
        if m:
            current = re.sub(r"[{}|]", "", m.group(2)).strip()
            out += [
                "",
                f"{m.group(1)} {current}",
                msg("> [!guide] 🟦 Original section · one line on what goes in '{current}'", current=current),
                "",
            ]
            filled, table_state = False, ""
            continue
        if s.startswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if table_state == "":
                out.append("| " + " | ".join(re.sub(r"[{}]", "", c) for c in cells) + " |")
                table_state = "header"
            elif table_state == "header" and re.match(r"^\|[\s\-:|]+\|$", s):
                out.append(line)
            elif table_state == "header":
                out.append("| " + " | ".join("{{" + f"{current or msg('value')} {i + 1}" + "}}" for i in range(len(cells))) + " |")
                table_state = "body"
            continue
        table_state = ""
        if s and current and not filled and not s.startswith(">"):
            out.append(("- " if s.startswith(("- ", "* ", "1. ")) else "") + "{{" + current + "}}")
            filled = True
    meta = (
        "---\nid: ${id}\ntype: current\nstatus: ${current_status.active}\ncreated: ${today}\nupdated: ${today}\nlinks: []\n"
        f"template: {name}\ntemplate_version: 1.0.0\nbased_on: 1.0.0\n---\n"
    )
    tail = msg(
        "\n\n{template_only}\n## {marker}\n| Version | Date | What changed |\n|---|---|---|\n| 1.0.0 | "
        "{today} | Made from the draft {name} |\n",
        template_only=templating.TEMPLATE_ONLY,
        marker=n.marker("changelog"),
        today=today(),
        name=source.name,
    )
    return meta + re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip() + tail


# --------------------------------------------------------------------------- migrate


@dataclass
class Parsed:
    r"""A document split into its parts, for migration.

    Attributes:
        meta: Frontmatter.
        title: The `# ` title line.
        preamble: Text between the title and the first section.
        sections: (heading, content) for each section.

    Example:
        >>> p = parse_sections("# 제목\n소개\n## 하나\n내용\n")
        >>> p.title, p.preamble, p.sections
        ('# 제목', '소개', [('하나', '내용')])
    """

    meta: dict
    title: str
    preamble: str
    sections: list[tuple[str, str]] = field(default_factory=list)  # (heading, content incl. trailing lines)


def parse_sections(text: str, level: int = 2) -> Parsed:
    r"""Split a document into title, preamble and sections of one heading level.

    Args:
        text: The document.
        level: Heading level that starts a section.

    Returns:
        The parts.

    Example:
        >>> parse_sections("# 제목\n## 하나\n### 작은\n내용\n").sections
        [('하나', '### 작은\n내용')]
    """
    doc = frontmatter.parse(text)
    body = templating.strip_template_only(doc.body) if templating.TEMPLATE_ONLY in doc.body else doc.body
    lines = body.split("\n")
    title, pre, sections = "", [], []
    cur_head: str | None = None
    cur: list[str] = []
    in_fence = False
    prefix = "#" * level + " "
    for line in lines:
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        if not in_fence and line.startswith("# ") and not title and cur_head is None:
            title = line
            continue
        if not in_fence and (line.startswith(prefix) or (level == 2 and title and line.startswith("# "))):
            if cur_head is not None:
                sections.append((cur_head, "\n".join(cur).strip("\n")))
            cur_head = line.lstrip("#").strip()
            cur = []
            continue
        (cur if cur_head is not None else pre).append(line)
    if cur_head is not None:
        sections.append((cur_head, "\n".join(cur).strip("\n")))
    return Parsed(doc.meta, title, "\n".join(pre).strip("\n"), sections)


def _is_blank_section(content: str) -> bool:
    stripped = [l for l in content.split("\n") if l.strip() and not l.startswith("> [!guide]") and not l.startswith(">")]
    return all(templating.PLACEHOLDER_RE.fullmatch(l.strip().lstrip("-0123456789. ").strip()) for l in stripped) if stripped else True


def migrate_text(
    project: Project, old_text: str, template_name: str, maps: dict[str, str], legacy: bool = False, values: dict | None = None
) -> str:
    r"""Move a document's content into the current version of a template.

    Sections match by heading (with renames from maps); content of sections the template no longer has
    goes into a "📦 옮기지 못한 내용" section — nothing is dropped. The old frontmatter lines stay as written;
    only new keys and the version are added.

    Args:
        project: The project.
        old_text: The document.
        template_name: The template to move into.
        maps: Old heading → new heading.
        legacy: The document comes from outside (a legacy original): build fresh frontmatter and keep the template's glance.
        values: Extra `${…}` values for the template.

    Returns:
        The migrated document.

    Raises:
        FileNotFoundError: The project has no template by that name.

    Example:
        >>> migrate_text(project, read(path), "기획", {"목적": "목표"})  # doctest: +SKIP
        '---\nid: W-012\n…'
    """
    bin_title = project.names.marker("migrate_bin")
    tmpl_raw = read(template_path(project, template_name))
    vals = base_values(project)
    old = parse_sections(old_text)
    for k, v in old.meta.items():
        vals.setdefault(k, frontmatter.as_str(v))
    vals.update(values or {})
    rendered = templating.render(tmpl_raw, vals, condition_context(project))
    rendered = _SYS_RE.sub("", rendered)
    new = parse_sections(rendered)
    norm_map = {_norm_heading(k): _norm_heading(v) for k, v in maps.items()}
    old_by: dict[str, tuple[str, str]] = {}
    for h, c in old.sections:
        key = norm_map.get(_norm_heading(h), _norm_heading(h))
        if key in old_by:
            old_by[key] = (old_by[key][0], old_by[key][1] + "\n\n" + c)
        else:
            old_by[key] = (h, c)
    used = set()
    parts: list[str] = [old.title or new.title, ""]
    # keep the old glance/preamble when it has content; otherwise the template's
    if legacy:  # a legacy intro is content, the template's glance still has to be filled
        pre = new.preamble + ("\n\n" + old.preamble if old.preamble.strip() else "")
    else:
        pre = old.preamble if old.preamble.strip() else new.preamble
    parts += [pre.strip(), ""]
    for h, c in new.sections:
        key = _norm_heading(h)
        if key in old_by:
            parts += [f"## {h}", old_by[key][1] if old_by[key][1].strip() else c, ""]
            used.add(key)
        else:
            parts += [f"## {h}", c, ""]
    leftovers = [
        (h, c)
        for h, c in old.sections
        if norm_map.get(_norm_heading(h), _norm_heading(h)) not in used
        and _norm_heading(h) != _norm_heading(bin_title)
        and not _is_blank_section(c)
    ]
    bin_existing = [c for h, c in old.sections if _norm_heading(h) == _norm_heading(bin_title)]
    if leftovers or bin_existing:
        parts += [
            f"## {bin_title}",
            msg(
                "> [!guide] Content with no place in the new template, gathered here rather than deleted — "
                "move it to the right section or tidy it up, then delete this section."
            ),
            "",
        ]
        for c in bin_existing:
            parts += [c, ""]
        for h, c in leftovers:
            parts += [f"### {h}", c, ""]
    body = re.sub(r"\n{3,}", "\n\n", "\n".join(parts)).strip() + "\n"
    new_meta = frontmatter.parse(rendered).meta
    old_doc = frontmatter.parse(old_text)
    if old_doc.has_frontmatter and not legacy:
        # keep the old frontmatter lines as they were; only add new keys and the version
        updates = {k: v for k, v in new_meta.items() if k not in old.meta and k != "based_on"}
        updates["template"] = template_name
        updates["template_version"] = template_version(tmpl_raw)
        return frontmatter.set_fields(f"---\n{old_doc.raw_meta}\n---\n{body}", updates)
    merged = dict(new_meta)
    for k, v in old.meta.items():
        if k not in ("template", "template_version"):
            merged[k] = v
    merged.pop("based_on", None)
    merged["template"] = template_name
    merged["template_version"] = template_version(tmpl_raw)
    merged["updated"] = today()
    return frontmatter.render(merged, body)


def migrate_targets(project: Project, target: str | None) -> list[tuple[Path, str]]:
    """Work out which documents a migrate target means.

    Args:
        project: The project.
        target: A document path, a template name (its outdated documents), or "all" / None (every outdated document).

    Returns:
        (document, its template) pairs.

    Raises:
        FileNotFoundError: target is neither a document nor a template.

    Example:
        >>> migrate_targets(project, "기획")  # doctest: +SKIP
        [(PosixPath('…/W-012 로그인/기획.md'), '기획')]
    """
    if not target or target == "all":
        return [(o.path, o.template) for o in outdated(project)]
    if target in names(project):
        return [(o.path, o.template) for o in outdated(project, target)]
    p = Path(target)
    if not p.is_absolute():
        cand = [project.docs / target, project.root / target]
        p = next((c for c in cand if c.exists()), cand[0])
    if not p.exists():
        raise FileNotFoundError(msg("Neither a document nor a template: {target}", target=target))
    meta = frontmatter.parse(read(p)).meta
    return [(p, nfc(str(meta.get("template") or "")))]


def migrate(
    project: Project, target: str | None, maps: dict[str, str], apply: bool, to: str | None = None, dest: str | None = None
) -> list[str]:
    """Migrate documents to the current template version (preview unless apply), or a legacy document into a template.

    Args:
        project: The project.
        target: What to migrate (see migrate_targets).
        maps: Old heading → new heading.
        apply: Write the result; otherwise show diffs only.
        to: Migrate a legacy document into this template, as a new document.
        dest: Where the new document goes (path from the documents root); required with to.

    Returns:
        Messages and diffs (or the new document's text when previewing with to).

    Raises:
        ValueError: to is given without dest.
        FileExistsError: dest already exists.
        FileNotFoundError: target is neither a document nor a template.

    Example:
        >>> migrate(project, "기획", {}, apply=False)[-1]  # doctest: +SKIP
        '미리보기입니다. 승인되면 --apply'
    """
    out: list[str] = []
    if to:  # legacy doc → a new document in our template
        src = migrate_targets(project, target)[0][0]
        if not dest:
            raise ValueError(msg("--to also needs --dest (the new document's path)"))
        dest_path = project.docs / dest
        if dest_path.exists():
            raise FileExistsError(msg("Already exists: {rel}", rel=project.rel(dest_path)))
        wid = re.match(r"^(W-\d{3,})\b", nfc(dest_path.parent.name))
        doc_id = wid.group(1) if wid else f"DOC-{dest_path.stem}"
        new_text = migrate_text(project, read(src), to, maps, legacy=True, values={"name": dest_path.stem, "id": doc_id, "work_id": doc_id})
        out.append(msg("📄 {rel} → {rel2} (template '{to}', the original stays)", rel=project.rel(src), rel2=project.rel(dest_path), to=to))
        if apply:
            write(dest_path, new_text)
            out.append(msg("✔ Created"))
        else:
            out.append(new_text)
        return out
    targets = migrate_targets(project, target)
    if not targets:
        return [msg("Nothing to migrate (no active documents on an old template version)")]
    for path, tname in targets:
        if not tname:
            out.append(msg("⚠ {rel}: a document without template — migrate it with --to <template> --dest <path>", rel=project.rel(path)))
            continue
        old = read(path)
        new = migrate_text(project, old, tname, maps)
        diff = "".join(
            difflib.unified_diff(
                old.splitlines(keepends=True),
                new.splitlines(keepends=True),
                fromfile=project.rel(path),
                tofile=project.rel(path) + msg(" (new template)"),
            )
        )
        out.append(msg("📄 {rel} — template '{tname}'", rel=project.rel(path), tname=tname))
        if apply:
            write(path, new)
            bin_title = project.names.marker("migrate_bin")
            out.append(msg("✔ Migrated") + (msg(" — tidy up the '{bin_title}' section", bin_title=bin_title) if bin_title in new else ""))
        else:
            out.append(diff or msg("(no changes)"))
    if not apply:
        out.append(msg("This is a preview. Once approved, --apply"))
    return out
