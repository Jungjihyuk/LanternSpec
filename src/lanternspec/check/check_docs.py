"""`lantern check` — format checks (/l-check, the git pre-commit hook, the agent hook after a document is written).

Looks at: required blanks · enums.yaml values · broken links · leftover {{blanks}} ·
old template versions · duplicate IDs · document length · task line format.
The AI only explains the result; the verdict comes from here.

Not here:
    - acceptance-criteria rules → work/epic_rules.py
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path

from ..core import frontmatter, templating
from ..core.links import Resolver, iter_links
from ..core.messages import msg
from ..core.project import Project, git_out, nfc, read
from ..core.taskfile import parse_criteria, parse_tasks

COMMON_FIELDS = ["id", "type", "status", "created", "updated", "links", "template", "template_version"]
LEVEL_ICON = {"error": "✖", "warn": "⚠", "info": "ℹ"}
LEVEL_ORDER = {"error": 0, "warn": 1, "info": 2}


@dataclass
class Finding:
    """One problem found in a document.

    Attributes:
        level: "error", "warn" or "info".
        path: The document, relative to the project root.
        code: A stable short name for the kind of problem, e.g. "broken-link".
        message: What is wrong, for the person.
        line: The 1-based line, when it is about one line.
        hint: How to fix it.

    Example:
        >>> print(Finding("error", "docs/기록.md", "broken-link", "깨진 링크: [[없음]]", 3, "대상 문서 이름을 확인하세요").format())
          ✖ 깨진 링크: [[없음]] (줄 3)
              → 대상 문서 이름을 확인하세요
    """

    level: str
    path: str
    code: str
    message: str
    line: int | None = None
    hint: str | None = None

    def format(self) -> str:
        """Write the finding as an indented line (with its hint on the next line).

        Returns:
            The text.

        Example:
            >>> Finding("warn", "a.md", "blank", "빈 칸 2개").format()
            '  ⚠ 빈 칸 2개'
        """
        loc = f":{self.line}" if self.line else ""
        s = f"  {LEVEL_ICON[self.level]} {self.message}{msg(' (line {line})', line=self.line) if loc else ''}"
        if self.hint:
            s += f"\n      → {self.hint}"
        return s


@dataclass
class Report:
    """The result of a check run.

    Attributes:
        findings: Every finding.
        files: How many documents were checked.

    Example:
        >>> Report(findings=[], files=3).format()
        '✔ 양식에 맞음 — 문서 3개'
    """

    findings: list[Finding]
    files: int

    @property
    def errors(self) -> list[Finding]:
        """The error findings."""
        return [f for f in self.findings if f.level == "error"]

    @property
    def warnings(self) -> list[Finding]:
        """The warning findings."""
        return [f for f in self.findings if f.level == "warn"]

    def counts(self) -> dict[str, int]:
        """Count findings per level.

        Returns:
            {"error": n, "warn": n, "info": n}.

        Example:
            >>> Report([Finding("warn", "a.md", "blank", "빈 칸")], 1).counts()
            {'error': 0, 'warn': 1, 'info': 0}
        """
        c = Counter(f.level for f in self.findings)
        return {"error": c.get("error", 0), "warn": c.get("warn", 0), "info": c.get("info", 0)}

    def format(self, show_info: bool = True) -> str:
        """Write the report grouped by document, most serious first, with a closing summary line.

        Args:
            show_info: Include info findings.

        Returns:
            The text.

        Example:
            >>> print(Report([Finding("error", "a.md", "enum", "status: 'x'는 상태 값이 아닙니다", 1)], 1).format())
            📄 a.md
              ✖ status: 'x'는 상태 값이 아닙니다 (줄 1)
            문서 1개 검사 — ✖ 오류 1개
        """
        lines: list[str] = []
        by_file: dict[str, list[Finding]] = defaultdict(list)
        for f in self.findings:
            if f.level == "info" and not show_info:
                continue
            by_file[f.path].append(f)
        for path in sorted(by_file):
            lines.append(f"📄 {path}")
            for f in sorted(by_file[path], key=lambda x: (LEVEL_ORDER[x.level], x.line or 0)):
                lines.append(f.format())
        c = self.counts()
        if not c["error"] and not c["warn"]:
            lines.append(
                msg("✔ Formats are fine — {files} documents", files=self.files)
                + (msg(" ({info} notes)", info=c["info"]) if c["info"] else "")
            )
        else:
            parts = []
            if c["error"]:
                parts.append(msg("✖ {error} errors", error=c["error"]))
            if c["warn"]:
                parts.append(msg("⚠ {warn} warnings", warn=c["warn"]))
            if c["info"]:
                parts.append(msg("ℹ {info} notes", info=c["info"]))
            lines.append(msg("Checked {files} documents — ", files=self.files) + " · ".join(parts))
        return "\n".join(lines)

    def to_json(self) -> str:
        """Return the report as JSON (files, counts, findings).

        Returns:
            Indented JSON.

        Example:
            >>> '"files": 0' in Report([], 0).to_json()
            True
        """
        return json.dumps(
            {"files": self.files, "counts": self.counts(), "findings": [asdict(f) for f in self.findings]}, ensure_ascii=False, indent=2
        )


def semver(v: object) -> tuple[int, int, int]:
    """Read a version as three numbers; missing parts are 0.

    Args:
        v: A version such as "1.2" or "1.2.3".

    Returns:
        (major, minor, patch); (0, 0, 0) when it is not a version.

    Example:
        >>> semver("1.2"), semver(None)
        ((1, 2, 0), (0, 0, 0))
    """
    m = re.match(r"^\s*(\d+)(?:\.(\d+))?(?:\.(\d+))?", str(v or ""))
    if not m:
        return (0, 0, 0)
    return tuple(int(x or 0) for x in m.groups())  # type: ignore[return-value]


def version_gap(old: object, new: object) -> str | None:
    """Tell which part changed from an old version to a newer one.

    Args:
        old: The document's version.
        new: The template's version.

    Returns:
        "major", "minor" or "patch"; None when old is the same or newer.

    Example:
        >>> version_gap("1.0.0", "1.1.0"), version_gap("2.0", "1.9")
        ('minor', None)
    """
    a, b = semver(old), semver(new)
    if a >= b:
        return None
    if a[0] != b[0]:
        return "major"
    if a[1] != b[1]:
        return "minor"
    return "patch"


# --------------------------------------------------------------------------- helpers


def _section_spans(text: str) -> list[tuple[str, int, int]]:
    """(heading, start_line, end_line) for each `## ` section (1-based, inclusive)."""
    lines = text.split("\n")
    spans: list[tuple[str, int, int]] = []
    current: tuple[str, int] | None = None
    in_fence = False
    for i, line in enumerate(lines, start=1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        if not in_fence and line.startswith("## "):
            if current:
                spans.append((current[0], current[1], i - 1))
            current = (line[3:].strip(), i)
    if current:
        spans.append((current[0], current[1], len(lines)))
    return spans


def _glance_empty(body: str, title: str) -> bool:
    lines = body.split("\n")
    for i, line in enumerate(lines):
        if re.match(rf"^>\s*\[!abstract\][^\n]*{re.escape(title)}", line):
            content = []
            for nxt in lines[i + 1 :]:
                if not nxt.startswith(">"):
                    break
                content.append(nxt.lstrip(">").strip())
            return not any(content)
    return False


def is_generated(meta: dict) -> bool:
    """Tell whether a document is generated by a script (`generated: true`) — such documents skip content checks.

    Args:
        meta: The document's frontmatter.

    Returns:
        True for generated documents.

    Example:
        >>> is_generated({"generated": True}), is_generated({})
        (True, False)
    """
    return bool(meta.get("generated"))


def _active_doc(project: Project, path: Path, meta: dict) -> bool:
    """Only docs still in use get migrate suggestions."""
    rel = project.docs_rel(path)
    n = project.names
    if rel.startswith(nfc(n.folder("current"))):
        return meta.get("status") != project.enums.value("current_status", "inactive")
    if rel.startswith(nfc(n.folder("archive"))):
        return False
    if rel.startswith(nfc(n.folder("works"))):
        return meta.get("status") != project.enums.value("work_status", "done")
    return False


def required_headings(template_text: str, required: str) -> list[str]:
    r"""List the `## ` sections of a template that hold a required `(필수)` blank — removing one breaks the structure.

    Args:
        template_text: The template.
        required: The mark of a required blank, e.g. "(필수)".

    Returns:
        The section headings.

    Example:
        >>> required_headings("## 목표\n{{목표 (필수)}}\n## 메모\n{{메모}}\n", "(필수)")
        ['목표']
    """
    body = templating.strip_template_only(template_text)
    out = []
    for heading, start, end in _section_spans(body):
        section = "\n".join(body.split("\n")[start - 1 : end])
        if f"{required}}}}}" in section:
            out.append(heading)
    return out


class TemplateIndex:
    """The current version and required sections of every template (the project's, else the bundled ones).

    Attributes:
        versions: Template name → template_version.
        required: Template name → headings of sections with required blanks.
        texts: Template name → template text.

    Example:
        >>> TemplateIndex(project).versions["기획"]  # doctest: +SKIP
        '1.0.0'
    """

    def __init__(self, project: Project) -> None:
        """Read the templates.

        Args:
            project: The project.
        """
        self.versions: dict[str, str] = {}
        self.required: dict[str, list[str]] = {}
        self.texts: dict[str, str] = {}
        texts = self.texts
        if project.templates_dir.exists():
            for p in project.templates_dir.glob("*.md"):
                text = read(p)
                meta = frontmatter.parse(text).meta
                texts[nfc(str(meta.get("template") or p.stem))] = text
        if not texts:
            from ..work.scaffold import base_template_names, base_template_text

            language = project.profile.language
            texts.update({name: base_template_text(name, language) for name in base_template_names(language)})
        mark = project.names.marker("required")
        for name, text in texts.items():
            self.versions[name] = frontmatter.as_str(frontmatter.parse(text).meta.get("template_version"))
            self.required[name] = required_headings(text, mark)


# --------------------------------------------------------------------------- protected sections


def missing_sections(project: Project, template: str, text: str) -> list[str]:
    r"""List the protected sections a document (or template) of a kind lacks.

    Sections the project turned off (docs.unused_sections) are not listed.

    Args:
        project: The project.
        template: The template name the text belongs to, e.g. "기록".
        text: The document or template text.

    Returns:
        Roles of the missing protected sections, in names.yaml order.

    Example:
        >>> missing_sections(project, "기록", "## 지금 상황\n- …\n")  # doctest: +SKIP
        ['past', 'schema']
    """
    from ..core import sections

    n = project.names
    role = n.doc_role(template)
    if role is None:
        return []
    return [s.role for s in n.sections_in(role) if not n.is_unused(s.role) and not sections.has(text, n.titles(s.role))]


def section_question(project: Project, path: Path, role: str, template: str, rel: str, code: str) -> Finding:
    """Ask, in a finding, what the person meant when a protected section is gone (no change is made).

    Args:
        project: The project.
        path: The document or template without the section.
        role: The protected section's role, e.g. "now".
        template: The template the document belongs to, e.g. "기록".
        rel: The path to show, relative to the project root.
        code: "section-missing" for a document, "template-section-missing" for a template.

    Returns:
        A warning whose message asks the question and whose hint lists the three answers.

    Example:
        >>> section_question(project, path, "now", "기록", "docs/…/기록.md", "section-missing").message  # doctest: +SKIP
        "'지금 상황' 칸이 없습니다. 이 칸은 대화가 길어져 … 일부러 바꾸셨나요?"
    """
    n = project.names
    s = n.section(role)
    template_rel = f"{n.folder('templates')}/{template}.md"
    return Finding(
        "warn",
        rel,
        code,
        msg(
            "The '{title}' section is missing. This section {feature}. Did you change it on purpose?",
            title=n.title(role),
            feature=s.feature,
        ),
        None,
        msg(
            'If you renamed it, lantern sections rename {role} "new title" · if you don\'t use the '
            "feature, lantern sections off {role} · if it was a mistake, put the '## {title}' section "
            "from {template_rel} back",
            role=role,
            template_rel=template_rel,
            title=s.title,
        ),
    )


def template_findings(project: Project) -> list[Finding]:
    """Ask about protected sections missing from the project's own templates (once per template, not per document).

    Args:
        project: The project.

    Returns:
        One finding per missing protected section.

    Example:
        >>> template_findings(project)  # doctest: +SKIP
        []
    """
    out: list[Finding] = []
    if not project.templates_dir.exists():
        return out
    for p in sorted(project.templates_dir.glob("*.md")):
        name = nfc(p.stem)
        for role in missing_sections(project, name, read(p)):
            out.append(section_question(project, p, role, name, project.rel(p), "template-section-missing"))
    return out


# --------------------------------------------------------------------------- the check


def check_file(project: Project, path: Path, text: str, ctx: _Ctx) -> list[Finding]:
    """Check one document.

    Args:
        project: The project.
        path: The document.
        text: Its text.
        ctx: State shared across one run (enums, link resolver, template index, IDs seen so far).

    Returns:
        The document's findings. Its ID is also recorded in ctx for the duplicate check.

    Example:
        >>> check_file(project, path, read(path), _Ctx(project))  # doctest: +SKIP
        []
    """
    rel = project.rel(path)
    out: list[Finding] = []
    doc = frontmatter.parse(text)
    if doc.error:
        return [Finding("error", rel, "frontmatter", doc.error, 1, msg("Fix the YAML between the --- lines"))]
    meta = doc.meta
    if not doc.has_frontmatter:
        out.append(
            Finding(
                "warn",
                rel,
                "no-frontmatter",
                msg("No frontmatter (a document outside the templates)"),
                hint=msg("Check that the document was made from a template (lantern scaffold …)"),
            )
        )
    generated = is_generated(meta)
    disabled = meta.get("status") == project.enums.value("current_status", "inactive")
    doc_type = str(meta.get("type") or "")

    # common frontmatter
    if doc.has_frontmatter and meta.get("template") and not generated:
        missing = [k for k in COMMON_FIELDS if k not in meta]
        if missing:
            out.append(
                Finding("error", rel, "common-fields", msg("Missing common frontmatter fields: {items}", items=", ".join(missing)), 1)
            )

    # enums
    if doc_type and not generated:
        for fieldname, enum in ctx.enums.rules_for(doc_type).items():
            if fieldname not in meta:
                continue
            value = frontmatter.as_str(meta.get(fieldname))
            if "{{" in value:
                continue
            if value and value not in enum.values:
                out.append(
                    Finding(
                        "error",
                        rel,
                        "enum",
                        msg("{fieldname}: '{value}' is not a {label} value", fieldname=fieldname, value=value, label=enum.label),
                        1,
                        msg("Available: {items} (enums.yaml)", items=", ".join(enum.values)),
                    )
                )

    # placeholders
    if not generated and not disabled:
        optional_lines: list[int] = []
        for name, required, line_no in templating.placeholders(text, project.names.marker("required")):
            if required:
                out.append(Finding("warn", rel, "required-blank", msg("A required blank is empty: {{{{{name}}}}}", name=name), line_no))
            else:
                optional_lines.append(line_no)
        if optional_lines:
            out.append(
                Finding(
                    "info",
                    rel,
                    "blank",
                    msg("{count} blanks", count=len(optional_lines)),
                    optional_lines[0],
                    msg("Fill them in, or delete the section if it doesn't apply"),
                )
            )
        glance = project.names.marker("glance")
        if _glance_empty(doc.body, glance):
            out.append(Finding("warn", rel, "glance-empty", msg("The '{glance}' section is empty", glance=glance)))

    # unknowns
    unknown = project.names.marker("unknown")
    unknown_lines = [i for i, l in enumerate(text.split("\n"), start=1) if unknown in l and "`" + unknown not in l and "[!guide]" not in l]
    if unknown_lines and not generated:
        out.append(
            Finding(
                "info",
                rel,
                "unknown",
                msg("{unknown} {count}", unknown=unknown, count=len(unknown_lines)),
                unknown_lines[0],
                msg("Once answered, put the answer in that section"),
            )
        )

    # links
    for link in iter_links(text):
        if ctx.resolver.resolve(link, path) is None:
            out.append(
                Finding(
                    "error",
                    rel,
                    "broken-link",
                    msg("Broken link: {raw}", raw=link.raw),
                    link.line_no,
                    msg("Check the target document's name · path"),
                )
            )

    # template version
    tname = nfc(str(meta.get("template") or ""))
    if tname and tname in ctx.templates.versions and not generated:
        gap = version_gap(meta.get("template_version"), ctx.templates.versions[tname])
        if gap and _active_doc(project, path, meta):
            if gap == "major":
                out.append(
                    Finding(
                        "warn",
                        rel,
                        "template-major",
                        msg(
                            "Template '{tname}' changed a lot: {get} → {value}",
                            tname=tname,
                            get=meta.get("template_version"),
                            value=ctx.templates.versions[tname],
                        ),
                        1,
                        msg('Move it with lantern template migrate "{docs_rel}" (/l-template migrate)', docs_rel=project.docs_rel(path)),
                    )
                )
            elif gap == "minor":
                out.append(
                    Finding(
                        "info",
                        rel,
                        "template-minor",
                        msg(
                            "Template '{tname}' changed ({get} → {value}) — its '{section}' section says what changed",
                            tname=tname,
                            get=meta.get("template_version"),
                            value=ctx.templates.versions[tname],
                            section=project.names.marker("changelog"),
                        ),
                        1,
                    )
                )

    # structure: sections holding required blanks must survive (the AI changed the template structure)
    if tname and tname in ctx.templates.required and not generated and not disabled:
        have = {h for h, _, _ in _section_spans(text)}
        for heading in ctx.templates.required[tname]:
            if heading not in have:
                out.append(
                    Finding(
                        "error",
                        rel,
                        "template-structure",
                        msg("The required section '## {heading}' of template '{tname}' is gone", tname=tname, heading=heading),
                        None,
                        msg("Don't delete the section; fill it in. If it doesn't apply, write 'none'"),
                    )
                )

    # protected sections: ask only when the template still has the section (a template change is asked about once, there)
    if tname and tname in ctx.templates.texts and not generated and not disabled:
        in_template = set(missing_sections(project, tname, ctx.templates.texts[tname]))
        for role in missing_sections(project, tname, text):
            if role not in in_template:
                out.append(section_question(project, path, role, tname, rel, "section-missing"))

    # idea: dropped needs a reason
    if (
        doc_type == "idea"
        and meta.get("status") == project.enums.value("idea_status", "dropped")
        and not str(meta.get("dropped_reason") or "").strip()
    ):
        out.append(Finding("warn", rel, "dropped-reason", msg("A dropped idea needs a one-line reason (dropped_reason)"), 1))

    # tasks
    if doc_type == "tasks":
        out += _check_tasks(project, path, text, rel)

    # length
    max_lines = int(project.profile.get("check.max_lines") or 300)
    n_lines = text.count("\n") + 1
    if not generated and n_lines > max_lines:
        spans = [(h, e - s + 1) for h, s, e in _section_spans(text) if h != project.names.marker("changelog")]
        hint = msg("Split sections into separate documents and link them")
        if spans:
            big = max(spans, key=lambda x: x[1])
            hint = msg("'## {big}' is {big2} lines → split it into '{big}.md' and link?", big=big[0], big2=big[1])
        out.append(
            Finding(
                "warn",
                rel,
                "too-long",
                msg("The document is {n_lines} lines (limit {max_lines})", n_lines=n_lines, max_lines=max_lines),
                None,
                hint,
            )
        )

    # remember ids
    if meta.get("id") and doc_type:
        ctx.ids[(doc_type, str(meta["id"]))].append(rel)
    return out


def _check_tasks(project: Project, path: Path, text: str, rel: str) -> list[Finding]:
    out: list[Finding] = []
    tasks = parse_tasks(text, project.names)
    ids = Counter(t.id for t in tasks)
    known = set(ids)
    plan = project.doc_path(path.parent, "plan")
    acs = {c.id for c in parse_criteria(read(plan))} if plan.exists() else set()
    team = project.profile.team
    for t in tasks:
        line = t.line_no + 1
        if ids[t.id] > 1:
            out.append(Finding("error", rel, "task-dup", msg("Duplicate task ID: {id}", id=t.id), line))
        if t.size and t.size not in ("S", "M", "L") and "{{" not in t.size:
            out.append(Finding("warn", rel, "task-size", msg("{id} size is one of S · M · L (now '{size}')", id=t.id, size=t.size), line))
        if not t.size:
            out.append(
                Finding("warn", rel, "task-size", msg("{id} has no size [{attr}:: S|M|L]", id=t.id, attr=project.names.attr("size")), line)
            )
        for dep in t.deps:
            if dep not in known:
                out.append(
                    Finding("warn", rel, "task-dep", msg("{id}: the prerequisite task {dep} is not in the list", id=t.id, dep=dep), line)
                )
            elif dep == t.id:
                out.append(Finding("warn", rel, "task-dep", msg("{id}: lists itself as a prerequisite", id=t.id), line))
        for ac in t.criteria:
            if acs and ac not in acs:
                out.append(
                    Finding(
                        "warn",
                        rel,
                        "task-ac",
                        msg("{id}: acceptance criterion {ac} is not in {name}", id=t.id, ac=ac, name=plan.name),
                        line,
                    )
                )
        if team and not t.attrs.get("owner") and not t.done:
            owner = project.names.attr("owner")
            out.append(Finding("info", rel, "task-owner", msg("{id} has no {owner} [{owner}:: name]", id=t.id, owner=owner), line))
    covered = {ac for t in tasks for ac in t.criteria}
    real_tasks = [t for t in tasks if "{{" not in t.title]
    if real_tasks:
        for ac in sorted(acs - covered, key=lambda x: int(x.split("-")[1])):
            out.append(
                Finding(
                    "warn",
                    rel,
                    "ac-uncovered",
                    msg("No task is linked to acceptance criterion {ac}", ac=ac),
                    None,
                    f"lantern task add … --ac {ac}",
                )
            )
    if len(tasks) > 10:
        out.append(Finding("info", rel, "task-many", msg("{count} tasks — consider splitting the work", count=len(tasks))))
    # cycles
    graph: dict[str, list[str]] = {}
    for t in tasks:  # a duplicated ID keeps every line's dependencies
        graph.setdefault(t.id, []).extend(t.deps)
    state: dict[str, int] = {}

    def visit(n: str, stack: list[str]) -> list[str] | None:
        state[n] = 1
        for d in graph.get(n, []):
            if d not in graph:
                continue
            if state.get(d) == 1:
                return stack + [n, d]
            if state.get(d) is None:
                r = visit(d, stack + [n])
                if r:
                    return r
        state[n] = 2
        return None

    for n in graph:
        if state.get(n) is None:
            cyc = visit(n, [])
            if cyc:
                out.append(Finding("error", rel, "task-cycle", msg("Prerequisite tasks form a cycle: {items}", items=" → ".join(cyc))))
                break
    return out


class _Ctx:
    def __init__(self, project: Project) -> None:
        self.enums = project.enums
        self.resolver = Resolver(project.docs)
        self.templates = TemplateIndex(project)
        self.ids: dict[tuple[str, str], list[str]] = defaultdict(list)


def changed_docs(project: Project) -> list[Path]:
    """List the documents with uncommitted changes (in the docs worktree for local mode).

    Args:
        project: The project.

    Returns:
        Changed or new `.md` files under the documents root.

    Example:
        >>> [p.name for p in changed_docs(project)]  # doctest: +SKIP
        ['기록.md']
    """
    cwd = project.docs_git_cwd()
    out = git_out(["status", "--porcelain", "--untracked-files=all", "--", "."], cwd)
    paths: list[Path] = []
    for line in out.splitlines():
        p = line[3:].strip().strip('"')
        if " -> " in p:
            p = p.split(" -> ", 1)[1]
        full = cwd / p
        if full.suffix == ".md" and full.exists():
            try:
                full.resolve().relative_to(project.docs.resolve())
            except ValueError:
                continue
            paths.append(full)
    return paths


def run(project: Project, paths: Iterable[Path] | None = None, templates: bool = False) -> Report:
    """Check documents, then look for IDs used twice across all documents.

    Templates and legacy originals are not checked as documents.

    Args:
        project: The project.
        paths: Documents to check; every document when None.
        templates: Also ask about protected sections missing from the project's templates.

    Returns:
        The report.

    Example:
        >>> run(project).counts()  # doctest: +SKIP
        {'error': 0, 'warn': 1, 'info': 2}
    """
    ctx = _Ctx(project)
    all_docs = list(project.iter_docs())
    targets = [Path(p).resolve() for p in paths] if paths is not None else [p.resolve() for p in all_docs]
    tmpl = project.templates_dir.resolve()
    legacy = project.folder("legacy").resolve()
    targets = [p for p in targets if p.suffix == ".md" and p.exists() and tmpl not in p.parents and legacy not in p.parents]
    findings: list[Finding] = []
    target_set = set(targets)
    for p in targets:
        findings += check_file(project, p, read(p), ctx)
    # duplicate ids need every doc, not only the targets
    if paths is not None:
        for p in all_docs:
            if p.resolve() in target_set:
                continue
            meta = frontmatter.parse(read(p)).meta
            if meta.get("id") and meta.get("type"):
                ctx.ids[(str(meta["type"]), str(meta["id"]))].append(project.rel(p))
    target_rels = {project.rel(p) for p in targets}
    for (_doc_type, doc_id), files in ctx.ids.items():
        if len(files) > 1:
            for f in files:
                if f in target_rels:
                    others = ", ".join(x for x in files if x != f)
                    findings.append(
                        Finding(
                            "error",
                            f,
                            "dup-id",
                            msg("ID {doc_id} is shared with other documents: {others}", doc_id=doc_id, others=others),
                            1,
                        )
                    )
    # task ids across all task files
    seen: dict[str, str] = {}
    for p in all_docs:
        if nfc(p.name) != nfc(project.names.file("tasks")):
            continue
        for t in parse_tasks(read(p), project.names):
            r = project.rel(p)
            if t.id in seen and seen[t.id] != r and r in target_rels:
                findings.append(
                    Finding("error", r, "task-dup", msg("Task ID {id} is also in {seen}", id=t.id, seen=seen[t.id]), t.line_no + 1)
                )
            seen.setdefault(t.id, r)
    if templates:
        findings += template_findings(project)
    return Report(findings=findings, files=len(targets))
