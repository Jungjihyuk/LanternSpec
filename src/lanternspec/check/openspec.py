"""Bring OpenSpec changes over as LanternSpec works and ideas (`lantern migrate openspec`).

Responsibilities:
    - read an OpenSpec folder: archived changes, open changes, capabilities
    - decide where each change goes (archive · works · ideas) and under which work ID
    - build our documents from its files, section by section (resources/openspec.yaml)
    - apply: keep the originals in the legacy folder, write the documents, one commit

Not here:
    - putting sections into a template and gathering what has no place → check/templates.py (migrate_text)
    - moving other existing documents aside → check/legacy.py
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote

import yaml

from .. import resources
from ..core import frontmatter, sections, templating
from ..core.links import MD_RE
from ..core.messages import msg
from ..core.names import Names
from ..core.new_id import next_id
from ..core.profile import doc_place
from ..core.project import Project, git, git_out, move_path, nfc, read, safe_name, today, wikilink, write

FOLDER = "openspec"  # where OpenSpec keeps its files, in the repository root
SKIP_HOOKS = {"LANTERN_SKIP_HOOKS": "1"}  # our own git hooks would check the commit we make
WHERE = ("archive", "work", "idea")
TRACES = (
    ".claude/commands/opsx",
    ".claude/commands/openspec",
    ".claude/skills",
    ".codex/prompts",
    ".agents/skills",
    "AGENTS.md",
    "CLAUDE.md",
)

_DATED = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+)$")
_TASK = re.compile(r"^(\s*)[-*] \[([ xX])\]\s+(?:\d+(?:\.\d+)*\.?\s+)?(.*)$")
_STEP = re.compile(r"^\s*[-*]\s*\*\*(GIVEN|WHEN|THEN|AND)\*\*:?\s*(.*)$", re.IGNORECASE)
_NON_GOALS = re.compile(r"^\*\*Non-Goals:?\*\*:?\s*$", re.IGNORECASE)
_LABEL = re.compile(r"^\*\*[^*]+:?\*\*:?\s*$")


class MigrateError(RuntimeError):
    """The OpenSpec folder cannot be brought over as asked.

    Example:
        >>> str(MigrateError("openspec 폴더가 없습니다"))
        'openspec 폴더가 없습니다'
    """


@dataclass
class Change:
    """One OpenSpec change and where it goes.

    Attributes:
        name: The change's name (the folder name without the archive date).
        rel: Its folder, from the OpenSpec folder (e.g. "changes/archive/2026-09-17-fix-login").
        archived_on: The date OpenSpec archived it; "" for an open change.
        created: The date it was started, when OpenSpec recorded one.
        files: The Markdown files in its folder.
        done: Checked tasks.
        total: All tasks.
        where: "archive" (a finished work), "work" (a work in progress) or "idea".
        work_id: The work ID it gets; "" for an idea.

    Example:
        >>> Change("fix-login", "changes/fix-login", "", "", ["proposal.md"], 0, 0, "idea").stage
        'plan'
    """

    name: str
    rel: str
    archived_on: str
    created: str
    files: list[str]
    done: int
    total: int
    where: str
    work_id: str = ""

    @property
    def stage(self) -> str:
        """The work stage (a work_status role) its documents say it is in."""
        if self.where == "archive":
            return "done"
        if self.done:
            return "build"
        return "tasks" if "tasks.md" in self.files else "design" if "design.md" in self.files else "plan"


@dataclass
class MigratePlan:
    """What `lantern migrate openspec` would do.

    Attributes:
        source: The OpenSpec folder.
        changes: Every change, in the order the work IDs are given.
        capabilities: The names under `specs/` (what the system does now).
        notes: Things the person should know before applying.

    Example:
        >>> MigratePlan(Path("openspec")).changes
        []
    """

    source: Path
    changes: list[Change] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _table() -> dict[str, Any]:
    return yaml.safe_load(resources.read_text("openspec.yaml")) or {}


def heading(key: str, language: str) -> str:
    """Return the title of one of our sections OpenSpec content goes into.

    Args:
        key: A key under `headings` in resources/openspec.yaml, e.g. "criteria".
        language: The project's language.

    Returns:
        The section title as the bundled template writes it.

    Example:
        >>> heading("criteria", "ko"), heading("criteria", "en")
        ('수락 기준', 'Acceptance criteria')
    """
    return _table()["headings"][key][language]


def _norm(title: str) -> str:
    return re.sub(r"[^\w]+", "", nfc(title)).casefold()


def task_counts(text: str) -> tuple[int, int]:
    r"""Count the checked and all task lines of an OpenSpec tasks.md.

    Args:
        text: The tasks.md text.

    Returns:
        (checked, all).

    Example:
        >>> task_counts("## 1. 준비\n- [x] 1.1 하나\n- [ ] 1.2 둘\n")
        (1, 2)
    """
    boxes = [m.group(2) for m in map(_TASK.match, text.split("\n")) if m]
    return sum(b != " " for b in boxes), len(boxes)


def suggest(files: list[str], done: int, total: int) -> str:
    """Suggest where an open change goes.

    Every task checked means it is finished; a design or task list means the work has taken shape;
    anything less is still an idea.

    Args:
        files: The Markdown files in the change's folder.
        done: Checked tasks.
        total: All tasks.

    Returns:
        "archive", "work" or "idea".

    Example:
        >>> suggest(["proposal.md", "tasks.md"], 3, 3), suggest(["design.md", "proposal.md"], 0, 0), suggest(["README.md"], 0, 0)
        ('archive', 'work', 'idea')
    """
    if total and done == total:
        return "archive"
    return "work" if "tasks.md" in files or "design.md" in files else "idea"


def convert_tasks(text: str, work_id: str) -> str:
    r"""Turn OpenSpec task lines into ours: each gets a task ID, group titles go one level down.

    Args:
        text: The tasks.md text.
        work_id: The work the tasks belong to.

    Returns:
        The content for our task section.

    Example:
        >>> print(convert_tasks("## 1. 준비\n\n- [x] 1.1 하나\n- [ ] 1.2 둘\n", "W-007"))
        ### 1. 준비
        <BLANKLINE>
        - [x] W-007-T01 하나
        - [ ] W-007-T02 둘
    """
    out: list[str] = []
    count = 0
    fence = False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            fence = not fence
        m = None if fence else _TASK.match(line)
        if m:
            count += 1
            out.append(f"{m.group(1)}- [{' ' if m.group(2) == ' ' else 'x'}] {work_id}-T{count:02d} {m.group(3)}")
        elif not fence and line.startswith("# "):
            continue  # the file's own title
        else:
            out.append("#" + line if not fence and line.startswith("## ") else line)
    return "\n".join(out).strip("\n")


def scenarios(text: str) -> list[dict[str, str]]:
    r"""Read the scenarios of an OpenSpec spec: what is given, what happens, what must follow.

    Args:
        text: A spec.md text (`#### Scenario:` blocks with `- **WHEN** …` · `- **THEN** …` lines).

    Returns:
        One {"given", "when", "then"} per scenario that says at least what happens or what follows.

    Example:
        >>> scenarios("#### Scenario: 로그인\n- **WHEN** 버튼을 누르면\n- **THEN** 홈이 열린다\n- **AND** 이름이 보인다\n")
        [{'given': '', 'when': '버튼을 누르면', 'then': '홈이 열린다, 이름이 보인다'}]
    """
    out: list[dict[str, list[str]]] = []
    cur: dict[str, list[str]] | None = None
    last = ""
    for line in text.split("\n"):
        if line.startswith("#"):
            cur = None
            if line.startswith("#### ") and "scenario" in line.casefold():
                cur = {"given": [], "when": [], "then": []}
                out.append(cur)
                last = ""
            continue
        m = _STEP.match(line)
        if cur is None or not m:
            continue
        key = m.group(1).lower()
        key = last if key == "and" else key
        if key:
            cur[key].append(m.group(2).strip())
            last = key
    return [{k: ", ".join(v) for k, v in s.items()} for s in out if s["when"] or s["then"]]


def criteria_lines(found: list[dict[str, str]], names: Names, ac_format: str, checked: bool) -> str:
    """Write scenarios as our acceptance criteria, one line each.

    Args:
        found: Scenarios from scenarios().
        names: The project's names (the words for situation · action · result).
        ac_format: "gwt" or "simple" (`plan.ac_format`).
        checked: Tick them, for a change that is finished.

    Returns:
        The lines; "" when there are no scenarios.

    Example:
        >>> from lanternspec.core.names import load
        >>> criteria_lines([{"given": "", "when": "버튼을 누르면", "then": "홈이 열린다"}], load("ko"), "gwt", True)
        '- [x] AC-1 행동: 버튼을 누르면 · 결과: 홈이 열린다'
    """
    lines = []
    for i, s in enumerate(found, 1):
        if ac_format == "gwt":
            parts = [
                (names.acceptance("situation"), s["given"]),
                (names.acceptance("action"), s["when"]),
                (names.acceptance("result"), s["then"]),
            ]
            body = " · ".join(f"{label}: {value}" for label, value in parts if value)
        else:
            body = " → ".join(x for x in (s["given"], s["when"], s["then"]) if x)
        lines.append(f"- [{'x' if checked else ' '}] AC-{i} {body}")
    return "\n".join(lines)


def split_non_goals(content: str) -> tuple[str, str]:
    r"""Take the `**Non-Goals:**` block out of a "Goals / Non-Goals" section.

    Args:
        content: The section's content.

    Returns:
        (what is left, the non-goals); the non-goals are "" when there is no such block.

    Example:
        >>> split_non_goals("**Goals:**\n- 로그인\n\n**Non-Goals:**\n- 결제\n")
        ('**Goals:**\n- 로그인', '- 결제')
    """
    keep: list[str] = []
    taken: list[str] = []
    taking = False
    for line in content.split("\n"):
        if _NON_GOALS.match(line.strip()):
            taking = True
        elif taking and _LABEL.match(line.strip()):
            taking = False
            keep.append(line)
        else:
            (taken if taking else keep).append(line)
    return "\n".join(keep).strip("\n"), "\n".join(taken).strip("\n")


def _demote(text: str, by: int = 2) -> str:
    """Push every heading down, so a whole file fits inside one of our sections."""
    out = []
    fence = False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            fence = not fence
        out.append("#" * by + line if not fence and line.startswith("#") else line)
    return "\n".join(out).strip("\n")


def _first_line(content: str) -> str:
    """The first line of prose in a section, for the glance at the top of a document."""
    for line in content.split("\n"):
        plain = line.strip().lstrip("-*0123456789. ").replace("**", "").strip()
        if plain and not line.startswith(("#", ">", "|", "```")):
            return plain if len(plain) <= 200 else plain[:199] + "…"
    return ""


def _read_change(source: Path, folder: Path) -> Change:
    dated = _DATED.match(nfc(folder.name))
    files = sorted(nfc(p.name) for p in folder.iterdir() if p.is_file() and p.suffix == ".md")
    created = ""
    meta_file = folder / ".openspec.yaml"
    if meta_file.exists():
        created = str((yaml.safe_load(read(meta_file)) or {}).get("created") or "")
    done, total = task_counts(read(folder / "tasks.md")) if "tasks.md" in files else (0, 0)
    archived = bool(dated) and folder.parent.name == "archive"
    return Change(
        name=dated.group(2) if dated and archived else nfc(folder.name),
        rel=folder.relative_to(source).as_posix(),
        archived_on=dated.group(1) if dated and archived else "",
        created=created,
        files=files,
        done=done,
        total=total,
        where="archive" if archived else suggest(files, done, total),
    )


def plan(project: Project, choices: dict[str, str] | None = None) -> MigratePlan:
    """Work out what bringing the OpenSpec folder over would do, without touching anything.

    Archived changes become finished works, in the order they were archived; open changes follow,
    going where suggest() says unless the person chose otherwise.

    Args:
        project: The project.
        choices: Open change name → "archive", "work" or "idea", overriding the suggestion.

    Returns:
        The plan.

    Raises:
        MigrateError: There is no OpenSpec folder, or a choice names a change that is not open.

    Example:
        >>> [(c.work_id, c.where) for c in plan(project).changes]  # doctest: +SKIP
        [('W-001', 'archive'), ('W-002', 'work'), ('', 'idea')]
    """
    source = project.root / FOLDER
    changes_dir = source / "changes"
    if not changes_dir.is_dir() and not (source / "specs").is_dir():
        raise MigrateError(msg("No OpenSpec folder here ({rel}/changes · {rel}/specs)", rel=FOLDER))
    archive_dir = changes_dir / "archive"
    folders = [p for p in sorted(changes_dir.iterdir()) if p.is_dir() and p.name != "archive" and not p.name.startswith(".")]
    archived = [p for p in sorted(archive_dir.iterdir()) if p.is_dir() and not p.name.startswith(".")] if archive_dir.is_dir() else []
    done = sorted((_read_change(source, p) for p in archived), key=lambda c: (c.archived_on, c.name))
    active = sorted((_read_change(source, p) for p in folders), key=lambda c: (c.created or "9999", c.name))
    names = {c.name for c in active}
    for name, where in (choices or {}).items():
        if name not in names:
            raise MigrateError(msg("No open OpenSpec change named {name}", name=name))
        next(c for c in active if c.name == name).where = where
    result = MigratePlan(source, done + active)
    number = int(next_id(project, "work").split("-")[1])
    for c in result.changes:
        if c.where != "idea":
            c.work_id = f"W-{number:03d}"
            number += 1
    specs = source / "specs"
    result.capabilities = sorted(nfc(p.name) for p in specs.iterdir() if (p / "spec.md").is_file()) if specs.is_dir() else []
    cwd = project.root
    if git(["rev-parse", "--git-dir"], cwd).returncode == 0 and not git_out(["ls-files", "--", str(source)], cwd):
        result.notes.append(msg("⚠ git does not track {rel}/ — the originals move as plain files and no commit records them", rel=FOLDER))
    traces = [t for t in TRACES if _mentions_openspec(project.root / t)]
    if traces:
        result.notes.append(
            msg("ℹ OpenSpec instructions · commands remain in: {items} — they are left as they are", items=" · ".join(traces))
        )
    return result


def _mentions_openspec(path: Path) -> bool:
    if path.is_dir():
        return "opsx" in path.name or any("openspec" in nfc(p.name).casefold() for p in path.iterdir())
    return path.is_file() and "openspec" in read(path).casefold()


def describe(project: Project, result: MigratePlan) -> list[str]:
    """Say what a plan would do, one line per change.

    Args:
        project: The project.
        result: The plan from plan().

    Returns:
        Lines for the person.

    Example:
        >>> describe(project, plan(project))[1]  # doctest: +SKIP
        '  → 2. 작업/보관/W-001 fix-login  (2026-09-17 끝남)'
    """
    n = project.names
    out = [
        msg(
            "OpenSpec {rel}/ — {archived} archived changes · {active} open changes · {caps} capabilities",
            rel=FOLDER,
            archived=sum(bool(c.archived_on) for c in result.changes),
            active=sum(not c.archived_on for c in result.changes),
            caps=len(result.capabilities),
        )
    ]
    for c in result.changes:
        if c.where == "idea":
            out.append(msg("  → {folder}/ {name}  (a note only — no design or tasks)", folder=n.folder("ideas"), name=c.name))
            continue
        folder = n.folder("archive") if c.where == "archive" else n.folder("works")
        if c.archived_on:
            why = msg("finished {date}", date=c.archived_on)
        elif c.total:
            why = msg("tasks {done}/{total}", done=c.done, total=c.total)
        else:
            why = msg("no tasks yet")
        out.append(f"  → {folder}/{c.work_id} {safe_name(c.name)}  ({why})")
    if result.capabilities:
        out.append(msg("  → {rel}: one row per capability ({count})", rel=doc_place(n, "features"), count=len(result.capabilities)))
    out.append(msg("The originals are kept in {rel}/", rel=project.rel(project.folder("legacy") / FOLDER)))
    return out + result.notes


def _fill_glance(text: str, sentence: str) -> str:
    """Put a sentence into the blank of the glance callout at the top."""
    lines = text.split("\n")
    start = next((i for i, line in enumerate(lines) if line.startswith("> [!abstract]")), None)
    if start is None or not sentence:
        return text
    for i in range(start + 1, len(lines)):
        if not lines[i].startswith(">"):
            break
        if templating.PLACEHOLDER_RE.search(lines[i]):
            lines[i] = templating.PLACEHOLDER_RE.sub(lambda _: sentence, lines[i], count=1)
            break
    return "\n".join(lines)


def _close_required(text: str, mark: str) -> str:
    """In a finished work nobody will fill the required blanks: say the original had nothing for them."""
    note = msg("(not in the OpenSpec original)")
    return templating.PLACEHOLDER_RE.sub(lambda m: note if m.group(1).strip().endswith(mark) else m.group(0), text)


def _render(
    project: Project, role: str, filled: dict[str, list[tuple[str, str]]], rest: list[tuple[str, str]], values: dict[str, Any]
) -> str:
    """Build one of our documents: content by section title, then what has no place of its own."""
    from .templates import migrate_text

    parts = []
    for title, sources in filled.items():
        sources = [(src, content) for src, content in sources if content.strip()]
        if len(sources) == 1:
            parts.append(f"## {title}\n{sources[0][1]}")
        elif sources:
            parts.append(f"## {title}\n" + "\n\n".join(f"**{src}**\n\n{content}" for src, content in sources))
    parts += [f"## {title}\n{content}" for title, content in rest if content.strip()]
    return migrate_text(project, "\n\n".join(parts) + "\n", project.names.doc(role), {}, legacy=True, values=values)


def _mapped(text: str, kind: str, language: str) -> tuple[dict[str, list[tuple[str, str]]], list[tuple[str, str]]]:
    """Split an OpenSpec file into content for our sections and the sections that have no place."""
    from .templates import parse_sections

    table = _table()
    to = {_norm(src): heading(key, language) for src, key in table["sections"][kind].items()}
    parsed = parse_sections(text)
    filled: dict[str, list[tuple[str, str]]] = {}
    rest: list[tuple[str, str]] = [(f"{kind}.md", parsed.preamble)] if parsed.preamble.strip() else []
    for title, content in parsed.sections:
        if _norm(title) in to:
            filled.setdefault(to[_norm(title)], []).append((title, content))
        else:
            rest.append((title, _demote(content, 1)))  # it becomes a `### ` entry of the leftovers
    return filled, rest


def relink(text: str, here: Path, was: Path, dest: Path, project: Project) -> str:
    r"""Point the relative Markdown links of a copied file at where their targets are now.

    A target is looked for next to the kept original, then where the link led before the move,
    then in the legacy folder (for documents `lantern legacy adopt` moved). A link whose target
    is found nowhere stays as written.

    Args:
        text: The file's text.
        here: The folder the kept original is in.
        was: The folder the file was in before it was kept.
        dest: The folder our document goes into.
        project: The project.

    Returns:
        The text with the links rewritten, relative to dest.

    Example:
        >>> relink("[제안](proposal.md)", kept, was, dest, project)  # doctest: +SKIP
        '[제안](../../5.%20기존%20문서/openspec/changes/fix-login/proposal.md)'
    """
    legacy = project.folder("legacy")

    def target_of(link: str) -> Path | None:
        path, _, _ = unquote(link).partition("#")
        candidates = [here / path, was / path]
        try:
            candidates.append(legacy / (was / path).resolve().relative_to(project.docs.resolve()))
        except ValueError:
            pass
        return next((c for c in candidates if c.exists()), None)

    def swap(m: re.Match[str]) -> str:
        link = m.group(3)
        if re.match(r"^[a-z][a-z0-9+.-]*:", link, re.IGNORECASE) or link.startswith(("#", "/")) or "{{" in link:
            return m.group(0)
        found = target_of(link)
        if found is None:
            return m.group(0)
        anchor = "#" + link.split("#", 1)[1] if "#" in link else ""
        return f"{m.group(1)}[{m.group(2)}]({quote(os.path.relpath(found.resolve(), dest.resolve()))}{anchor})"

    out = []
    fence = False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            fence = not fence
        out.append(line if fence else MD_RE.sub(swap, line))
    return "\n".join(out)


def documents(project: Project, change: Change, folder: Path, was: Path, dest: Path) -> dict[str, str]:
    """Build our documents for one change that becomes a work.

    Args:
        project: The project.
        change: The change, with its work ID.
        folder: Where the change's files are now (the kept originals).
        was: Where the change's files were before they were kept (their links were written from there).
        dest: The work folder the documents go into.

    Returns:
        Document role ("plan" · "design" · "tasks" · "record") → text; only the documents the change has content for.

    Example:
        >>> sorted(documents(project, change, folder, was, dest))  # doctest: +SKIP
        ['design', 'plan', 'record', 'tasks']
    """
    n = project.names
    lang = project.profile.language
    finished = change.where == "archive"
    first = next((folder / f for f in ("proposal.md", "README.md", "design.md", "tasks.md") if (folder / f).exists()), folder)
    origin = wikilink(project, first)
    values = {"work_id": change.work_id, "name": safe_name(change.name), "links": templating.yaml_list([origin])}
    status = project.enums.value("work_status", change.stage)
    text_of = {f: relink(read(folder / f), folder, was, dest, project) for f in change.files}
    used = {"proposal.md", "design.md", "tasks.md"}

    design_filled, design_rest = _mapped(text_of["design.md"], "design", lang) if "design.md" in text_of else ({}, [])
    non_goals: list[tuple[str, str]] = []
    for i, (title, content) in enumerate(design_rest):
        left, taken = split_non_goals(content)
        if taken:
            design_rest[i] = (title, left)
            non_goals.append((f"design.md — {title}", taken))

    plan_filled, plan_rest = _mapped(text_of.get("proposal.md", ""), "proposal", lang)
    if non_goals:
        plan_filled.setdefault(heading("out_of_scope", lang), []).extend(non_goals)
    specs = sorted((folder / "specs").glob("*/spec.md")) if (folder / "specs").is_dir() else []
    found = [s for p in specs for s in scenarios(read(p))]
    if found:
        plan_filled[heading("criteria", lang)] = [("specs", criteria_lines(found, n, project.profile.get("plan.ac_format"), finished))]
    why = next((c for src, c in plan_filled.get(heading("why", lang), [])), "")
    what = next((c for src, c in plan_filled.get(heading("what", lang), [])), "")
    out = {"plan": _fill_glance(_render(project, "plan", plan_filled, plan_rest, values), _first_line(why) or _first_line(what))}

    if "design.md" in text_of:
        glance = _first_line(
            next((c for src, c in design_filled.get(heading("structure", lang), []) if _norm(src) == _norm("Decisions")), "")
        )
        out["design"] = _fill_glance(_render(project, "design", design_filled, design_rest, values), glance)
    if "tasks.md" in text_of:
        tasks = _render(
            project, "tasks", {heading("tasks", lang): [("tasks.md", convert_tasks(text_of["tasks.md"], change.work_id))]}, [], values
        )
        out["tasks"] = _fill_glance(
            tasks, msg("{done} of {total} tasks done (brought over from OpenSpec)", done=change.done, total=change.total)
        )
    if change.stage in ("build", "done"):
        extra = [(f, _demote(text_of[f])) for f in change.files if f not in used]
        record = _render(project, "record", {}, extra, values)
        if finished:
            now = msg(
                "- Brought over from the OpenSpec change `{name}` — finished {date}: {origin}",
                name=change.name,
                date=change.archived_on or today(),
                origin=origin,
            )
        else:
            now = msg(
                "- Brought over from the OpenSpec change `{name}` — {done} of {total} tasks done: {origin}",
                name=change.name,
                done=change.done,
                total=change.total,
                origin=origin,
            )
        replaced = sections.replace(record, n.titles("now"), now)
        out["record"] = _fill_glance(replaced[0] if replaced else record, now.lstrip("- "))

    for role, text in out.items():
        text = frontmatter.set_fields(text, {"status": status, "created": change.created or change.archived_on or today()}, touch=False)
        out[role] = _close_required(text, n.marker("required")) if finished else text
    return out


def _feature_rows(project: Project, result: MigratePlan, kept: Path) -> Path | None:
    """Add one row per OpenSpec capability to the feature list, linking the kept spec."""
    n = project.names
    doc = project.docs / doc_place(n, "features")
    if not result.capabilities or not doc.exists():
        return None
    text = read(doc)
    section = sections.find(text, [heading("features", project.profile.language)])
    if section is None:
        return None
    rows = []
    for name in result.capabilities:
        if f"| {name} |" in text:
            continue
        spec = kept / "specs" / name / "spec.md"
        purpose = _first_line(read(spec).split("## Purpose", 1)[-1]).replace("|", "\\|")
        rows.append(f"| {name} |  | {purpose} | {wikilink(project, spec, 'OpenSpec', table=True)} |")
    if not rows:
        return None
    lines = [l for l in section.group(2).split("\n") if not (l.startswith("|") and templating.PLACEHOLDER_RE.search(l))]
    last = max((i for i, l in enumerate(lines) if l.startswith("|")), default=-1)
    lines[last + 1 : last + 1] = rows
    write(doc, text[: section.start(2)] + "\n".join(lines) + text[section.end(2) :])
    return doc


def _map_row(project: Project, result: MigratePlan, kept: Path) -> Path | None:
    """Tell the legacy map about the kept folder in one row, so its files don't each get one."""
    n = project.names
    legacy_map = project.folder("legacy") / n.file("legacy_map")
    if not legacy_map.exists() or n.is_unused("legacy_docs"):
        return None
    text = read(legacy_map)
    section = sections.find(text, n.titles("legacy_docs"))
    target = project.docs_rel(kept)
    if section is None or f"[[{target}\\|" in text:
        return None
    row = msg(
        "| [[{target}\\|{name}]] | OpenSpec originals — {changes} changes · {caps} capabilities | "
        "brought over {today} | 🚚 Move | {works} · {ideas} |",
        target=target,
        name=FOLDER,
        changes=len(result.changes),
        caps=len(result.capabilities),
        today=today(),
        works=n.folder("works"),
        ideas=n.folder("ideas"),
    )
    lines = [l for l in section.group(2).split("\n") if not (l.startswith("|") and templating.PLACEHOLDER_RE.search(l))]
    last = max((i for i, l in enumerate(lines) if l.startswith("|")), default=-1)
    lines[last + 1 : last + 1] = [row]
    write(legacy_map, text[: section.start(2)] + "\n".join(lines) + text[section.end(2) :])
    return legacy_map


def apply(project: Project, result: MigratePlan) -> list[str]:
    """Carry out a plan: keep the originals in the legacy folder, write works and ideas, then commit once.

    The documents' git must have nothing staged and no changes in the documents or the OpenSpec
    folder, so the commit holds only this and one revert undoes it.

    Args:
        project: The project.
        result: The plan from plan().

    Returns:
        What was done.

    Raises:
        MigrateError: There are uncommitted changes, nothing has ever been committed, or the originals were already kept.

    Example:
        >>> apply(project, plan(project))[0]  # doctest: +SKIP
        '✔ 작업 3개 · 아이디어 1개를 만들었습니다 (보관 2개)'
    """
    from ..work.scaffold import new_idea, work_folder_name

    kept = project.folder("legacy") / FOLDER
    if kept.exists():
        raise MigrateError(msg("{rel} already exists — the OpenSpec folder was brought over before", rel=project.rel(kept)))
    cwd = project.docs_git_cwd()
    in_git = git(["rev-parse", "--git-dir"], cwd).returncode == 0
    if in_git:
        if git(["rev-parse", "--verify", "-q", "HEAD"], cwd).returncode != 0:
            raise MigrateError(msg("Nothing has been committed yet — commit once, then run lantern migrate openspec --apply again"))
        scope = [str(project.docs), str(result.source)]
        if git_out(["diff", "--cached", "--name-only"], cwd) or git_out(["status", "--porcelain", "--", *scope], cwd):
            raise MigrateError(msg("Commit or stash the changes in the documents first, then run lantern migrate openspec --apply again"))
    move_path(project, result.source, kept)
    made: list[Path] = []
    counts = {where: 0 for where in WHERE}
    for change in result.changes:
        folder = kept / change.rel
        counts[change.where] += 1
        if change.where == "idea":
            raw = next((read(folder / f) for f in ("README.md", "proposal.md") if (folder / f).exists()), change.name)
            note = next((folder / f for f in ("README.md", "proposal.md") if (folder / f).exists()), None)
            idea = new_idea(project, change.name, raw=raw.strip(), links=[wikilink(project, note)] if note else [])
            write(idea, _fill_glance(read(idea), _first_line(raw)))
            made.append(idea)
            continue
        dest = (project.folder("archive") if change.where == "archive" else project.folder("works")) / work_folder_name(
            change.work_id, change.name
        )
        for role, text in documents(project, change, folder, result.source / change.rel, dest).items():
            write(project.doc_path(dest, role), text)
        made.append(dest)
    made += [p for p in (_feature_rows(project, result, kept), _map_row(project, result, kept)) if p]
    out = [
        msg(
            "✔ Created {works} works ({archived} of them archived) · {ideas} ideas from OpenSpec",
            works=counts["work"] + counts["archive"],
            archived=counts["archive"],
            ideas=counts["idea"],
        ),
        msg("   the originals are in {rel}/", rel=project.rel(kept)),
    ]
    if in_git:
        for path in made:  # never stage what git was told to ignore
            if git(["check-ignore", "-q", "--", str(path)], cwd).returncode != 0:
                git(["add", "--", str(path)], cwd)
        if git(["diff", "--cached", "--quiet"], cwd).returncode == 0:  # git tracks none of it: nothing to commit
            return out
        r = git(["commit", "-q", "-m", msg("docs: bring OpenSpec changes over as works and ideas [lantern]")], cwd, env=SKIP_HOOKS)
        if r.returncode == 0:
            out.append(msg("   one commit {sha} — git revert {sha} undoes it", sha=git_out(["rev-parse", "--short", "HEAD"], cwd)))
        else:
            out.append(msg("⚠ The changes are staged but not committed — commit them yourself: {error}", error=r.stderr.strip()[:200]))
    return out
