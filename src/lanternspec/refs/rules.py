r"""Company rules for the AI: the sections people approved, with where they apply and how strongly.

`/l-ref rules` proposes, per section, a scope (the whole project, one part, or one language) and a
strength (must · should); `lantern ref tag` stores what the person approved in the index. Only
approved sections reach the AI, word for word. Rules inside the project go into the AGENTS.md of
their scope (committed); rules outside it never go into a committed file — AGENTS.md only says to
run `lantern ref rules`, which prints them from this computer.

Responsibilities:
    - list the approved rules (dropping those in `references.exclude`) and where each one goes
    - render the company-rules section of one AGENTS.md (a should rule becomes a pointer when space is short)
    - render the outside rules of one place for `lantern ref rules` and the session-start hook

Not here:
    - storing the scope and strength → refs/index.py (tag)
    - putting the section into AGENTS.md and the budget → tools/rules.py · tools/install.py
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..core import outline
from ..core.messages import msg
from ..core.project import Project, read
from . import index as index_mod
from . import sources as src_mod

ALL = "all"  # the scope of a rule for the whole project
STRENGTHS = ("must", "should")
OUTSIDE_LINE = "lantern ref rules"  # the command AGENTS.md points at for rules kept outside the project
_HEADING = re.compile(r"^(#{1,6})(?=[ \t])")


@dataclass(frozen=True)
class Rule:
    """One approved section of a company-rules document.

    Attributes:
        document: The document.
        section: The section.
        scope: "all", a part's folder or a language.
        strength: "must" or "should".

    Example:
        >>> src = src_mod.Source("rules", "rules", Path("/p/rules"), False)  # doctest: +SKIP
        >>> Rule(src_mod.Document(src, Path("/p/rules/API.md"), "rules/API.md"), section, "all", "must").address  # doctest: +SKIP
        'API#API#오류 응답'
    """

    document: src_mod.Document
    section: outline.Section
    scope: str
    strength: str

    @property
    def address(self) -> str:
        """The address to read it with: `문서#위#아래`."""
        return f"{self.document.name}#{self.section.address}"


def scopes(project: Project) -> list[str]:
    """List the scopes a rule can have here: all, each recorded part, each language of the project or a part.

    Args:
        project: The project.

    Returns:
        "all" first, then the parts' folders, then the languages.

    Example:
        >>> scopes(project)  # doctest: +SKIP
        ['all', 'backend', 'frontend', 'python', 'typescript']
    """
    parts = [p for p in project.profile.get("code.parts") or [] if isinstance(p, dict) and p.get("path")]
    langs = [*(project.profile.get("project.languages") or []), *(x for p in parts for x in p.get("languages") or [])]
    return [ALL, *(str(p["path"]) for p in parts), *dict.fromkeys(str(x) for x in langs)]


def _excluded(project: Project) -> list[tuple[src_mod.Document, outline.Section | None]]:
    """The documents and sections named in `references.exclude` (lantern.yaml's and `.lantern/`'s) that still exist."""
    out = []
    for address in [*(project.profile.get("references.exclude") or []), *index_mod.outside_exclude(project)]:
        try:
            out.append(src_mod.locate(project, str(address)))
        except LookupError:
            continue
    return out


def _within(inner: outline.Section, outer: outline.Section) -> bool:
    return outer.start <= inner.start and inner.end <= outer.end


def approved(project: Project) -> list[Rule]:
    """List the approved company rules in document order, without excluded ones or ones whose section is gone.

    A section inside another approved section of the same scope is dropped — the outer one already carries it.

    Args:
        project: The project.

    Returns:
        The rules.

    Example:
        >>> [(r.address, r.scope, r.strength) for r in approved(project)]  # doctest: +SKIP
        [('API#API#오류 응답', 'backend', 'must')]
    """
    stores = {False: index_mod.load(project, False), True: index_mod.load(project, True)}
    skip = _excluded(project)
    out: list[Rule] = []
    for doc in src_mod.all_documents(project):
        if doc.source.kind != "rules":
            continue
        applies = (stores[doc.source.outside].get(doc.shown) or {}).get("applies") or {}
        if not applies:
            continue
        found = {s.address: s for s in outline.sections(read(doc.path))}
        mine = []
        for address, tag in applies.items():
            section = found.get(address)
            if section is None or not isinstance(tag, dict):
                continue
            if any(d.path == doc.path and (s is None or _within(section, s)) for d, s in skip):
                continue
            mine.append(Rule(doc, section, str(tag.get("scope") or ALL), str(tag.get("strength") or "should")))
        mine.sort(key=lambda r: r.section.start)
        out += [r for r in mine if not any(o is not r and o.scope == r.scope and _within(r.section, o.section) for o in mine)]
    return out


def places(project: Project, rule: Rule) -> list[str]:
    """Tell which AGENTS.md files a rule goes to: "" for the root, else a part's folder.

    Without two or more parts everything goes to the root. A language rule goes to every part of
    that language, or to the root when no part has it.

    Args:
        project: The project.
        rule: The rule.

    Returns:
        The places.

    Example:
        >>> places(project, rule)  # doctest: +SKIP
        ['backend']
    """
    from ..tools.rules import active_parts

    parts = active_parts(project.profile)
    if not parts or rule.scope == ALL:
        return [""]
    if any(p["path"] == rule.scope for p in parts):
        return [rule.scope]
    langs = [p["path"] for p in parts if rule.scope in (p.get("languages") or [])]
    return langs or [""]


def _text(project: Project, rule: Rule, level: int) -> str:
    """The rule's words as written, with its headings moved down so its top heading has the given level."""
    lines = outline.cut(read(rule.document.path), rule.section).rstrip("\n").split("\n")
    shift = level - rule.section.level
    out = []
    fence = ""
    for line in lines:
        mark = outline.FENCE.match(line)
        if mark:
            fence = "" if fence == mark.group(1) else fence or mark.group(1)
        h = None if fence else _HEADING.match(line)
        out.append("#" * min(6, max(1, len(h.group(1)) + shift)) + line[h.end() :] if h else line)
    return "\n".join(out)


def _render(project: Project, rules: list[Rule], level: int, pointers: bool) -> list[str]:
    """Must rules then should rules, each word for word (a should rule as a pointer when pointers is True)."""
    out: list[str] = []
    for strength, title in (("must", msg("Must follow")), ("should", msg("Follow where you can"))):
        chosen = [r for r in rules if r.strength == strength]
        if not chosen:
            continue
        out += ["", "#" * (level - 1) + " " + title]
        for r in chosen:
            if pointers and strength == "should":
                out.append(f'- {r.section.title} — `lantern ref read "{r.address}"`')
                continue
            out += ["", f"<!-- {r.address} ({r.document.label}) -->", _text(project, r, level)]
    return out


def agents_section(project: Project, place: str, pointers: bool = False) -> str:
    """Build the company-rules section of one AGENTS.md.

    Inside rules are written word for word; rules outside the project are only pointed at with
    `lantern ref rules`, so nothing of them goes into the repository. Once AGENTS.md said so, the
    pointer stays — a teammate without the outside material must not take it out again.

    Args:
        project: The project.
        place: "" for the root AGENTS.md, else a part's folder.
        pointers: True to write should rules as a title and an address instead of their words (when space is short).

    Returns:
        The section; "" when this place has no company rules.

    Example:
        >>> print(agents_section(project, ""))  # doctest: +SKIP
        ## 사내 규칙
        …
    """
    rules = [r for r in approved(project) if place in places(project, r)]
    inside = [r for r in rules if not r.document.source.outside]
    path = project.root / place / "AGENTS.md"
    command = f"{OUTSIDE_LINE} {place}".strip()
    pointed = path.exists() and f"`{command}`" in read(path)
    if not inside and not pointed and not any(r.document.source.outside for r in rules):
        return ""
    lines = [msg("## Company rules"), msg("Rules the company set — written as they are; follow them over the project's own rules.")]
    if pointed or any(r.document.source.outside for r in rules):
        lines.append(
            msg(
                "- Company rules kept outside the project: run `{command}` and follow what it prints (nothing printed = none).",
                command=command,
            )
        )
    lines += _render(project, inside, 4, pointers)
    return "\n".join(lines)


def outside_rules(project: Project, place: str, strength: str = "") -> str:
    """Print the rules kept outside the project for one place, word for word.

    Args:
        project: The project.
        place: "" for the whole project (the root), else a part's folder.
        strength: "must" for must rules only; "" for all.

    Returns:
        The rules; "" when there are none on this computer.

    Example:
        >>> print(outside_rules(project, "backend"))  # doctest: +SKIP
        ## 반드시 지킴
        <!-- API#API#오류 응답 (API.md) -->
        ### 오류 응답
        …
    """
    rules = [r for r in approved(project) if r.document.source.outside and place in places(project, r)]
    rules = [r for r in rules if not strength or r.strength == strength]
    return "\n".join(_render(project, rules, 3, False)).strip("\n")
