"""Pick what fits this project from the design-principle table and the per-language conventions.

Responsibilities:
    - read principles.yaml · conventions/<language>.yaml (tables bundled with the package), with the
      project language's text picked out of their `ko:` · `en:` blocks
    - set each principle's level (must · should · skip) from kind · external integrations · size
    - pick code conventions by language and size
    - turn line and people counts into sizes (small · medium · large)
    - detect languages, runners and tools already in use from the project's top-level files

Not here:
    - counting lines of code → report/harness.py (code_lines)
    - the text for AGENTS.md → tools/rules.py (principles_section)
    - writing the design-principles document → report/principles_doc.py
    - telling when a size boundary is crossed → check/doctor.py
"""

from __future__ import annotations

import functools
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from .. import resources
from .names import localize

if TYPE_CHECKING:
    from .profile import Profile

SIZES = ("small", "medium", "large")
COMMAND_ROLES = ("format", "lint", "typecheck")  # commands recorded in lantern.yaml build.<role>


@functools.cache
def _raw_table() -> dict[str, Any]:
    """Read principles.yaml once, with every language's text."""
    return yaml.safe_load(resources.read_text("principles.yaml"))


@functools.cache
def table(locale: str = "ko") -> dict[str, Any]:
    """Read the design-principle table (principles.yaml) with one language's text.

    Args:
        locale: Language of the text (lantern.yaml project.language).

    Returns:
        All of principles.yaml (levels · words · roles · rules · kinds · external · sizes · principles · always).

    Example:
        >>> table()["levels"]["must"], table()["principles"]["simplicity"]["grows_with"]
        ('지킴', 'none')
    """
    return localize(_raw_table(), locale)


@functools.cache
def _raw_conventions(language: str) -> dict[str, Any]:
    """Read conventions/<language>.yaml once, with every language's text."""
    if language not in language_names():
        raise LookupError(f"'{language}' 컨벤션이 없습니다 (가능: {', '.join(language_names())})")
    return yaml.safe_load(resources.read_text(f"conventions/{language}.yaml"))


def conventions(language: str, locale: str = "ko", comment_locale: str | None = None) -> dict[str, Any]:
    """Read one programming language's code conventions (conventions/<language>.yaml).

    Args:
        language: Programming language, e.g. "python".
        locale: Language of the rules and notes (lantern.yaml project.language).
        comment_locale: Language of the doc-comment style and example (lantern.yaml project.comment_language);
            the same as locale when None.

    Returns:
        That language's conventions (tools · runners · existing · docs · levels).

    Raises:
        LookupError: There is no conventions file for that language.

    Example:
        >>> conventions("python")["tools"]["lint"]["name"], conventions("python")["docs"]["style"]
        ('ruff', 'Google 스타일 docstring')
    """
    raw = _raw_conventions(language)
    out = localize({k: v for k, v in raw.items() if k != "docs"}, locale)
    out["docs"] = localize(raw.get("docs") or {}, comment_locale or locale)
    return out


def role_label(role: str, locale: str = "ko") -> str:
    """Return the name of a check command's role, e.g. "린트" for lint.

    Args:
        role: "package", "format", "lint", "typecheck" or "test".
        locale: Language of the name.

    Returns:
        The name; the role itself when it has none.

    Example:
        >>> role_label("typecheck")
        '타입 검사'
    """
    return str(table(locale)["roles"].get(role, role))


def rule_label(item: str, locale: str = "ko") -> str:
    """Return the name of a convention rule item, e.g. "타입 힌트" for type_hints.

    Args:
        item: "lint", "typecheck", "type_hints", "docs" or "tests".
        locale: Language of the name.

    Returns:
        The name; the item itself when it has none.

    Example:
        >>> rule_label("type_hints")
        '타입 힌트'
    """
    return str(table(locale)["rules"].get(item, item))


def comment_languages(locale: str = "ko") -> dict[str, str]:
    """Return the languages code comments can be written in (lantern.yaml project.comment_language).

    Args:
        locale: Language of the names.

    Returns:
        Code → name, e.g. {"ko": "한국어", "en": "영어"}.

    Example:
        >>> comment_languages()
        {'ko': '한국어', 'en': '영어'}
    """
    return {str(c["code"]): str(c["name"]) for c in table(locale)["comment_languages"]}


def kind_names() -> tuple[str, ...]:
    """Return the project-kind names in table order.

    Returns:
        Tuple of kind names.

    Example:
        >>> kind_names()
        ('script', 'cli', 'library', 'service', 'data')
    """
    return tuple(table()["kinds"])


def language_names() -> tuple[str, ...]:
    """Return the names of languages that have conventions.

    Returns:
        Tuple of language names (sorted).

    Example:
        >>> language_names()
        ('go', 'python', 'rust', 'swift', 'typescript')
    """
    return tuple(sorted(Path(rel).stem for rel, _ in resources.iter_files("conventions")))


def code_size(lines: int) -> str:
    """Turn a line count into a size (boundaries from sizes.code in the table).

    Args:
        lines: Lines of code, excluding tests and docs.

    Returns:
        One of "small" · "medium" · "large".

    Example:
        >>> code_size(9_999), code_size(10_000), code_size(50_000)
        ('small', 'medium', 'large')
    """
    for size, spec in table()["sizes"]["code"].items():
        if "below" not in spec or lines < spec["below"]:
            return size
    return SIZES[-1]


def people_size(team: bool, members: int) -> str:
    """Turn the team size into a size (boundaries from sizes.people in the table).

    Args:
        team: Two or more people (lantern.yaml project.team).
        members: Number of members (project.members); a team listing one or none counts as two.

    Returns:
        One of "small" · "medium" · "large".

    Example:
        >>> people_size(False, 0), people_size(True, 3), people_size(True, 6)
        ('small', 'medium', 'large')
    """
    count = max(members, 2) if team else 1
    for size, spec in table()["sizes"]["people"].items():
        if "max" not in spec or count <= spec["max"]:
            return size
    return SIZES[-1]


def level_for(pid: str, kind: str, external: bool, code: str, people: str, locale: str = "ko") -> tuple[str, str]:
    """Decide one principle's level, and why, from the table.

    The base level comes from the kind (and external integrations), then size adjusts it:
    should → must when the grows_with signal is medium or more; at least min_when_large when the code is large.

    Args:
        pid: Principle name (key of principles), e.g. "single_responsibility".
        kind: Project kind, e.g. "cli".
        external: Whether it integrates with outside tools or services.
        code: Code size.
        people: Team size.
        locale: Language of the reason.

    Returns:
        (level, reason). Level is "must" · "should" · "skip".

    Raises:
        KeyError: The principle or kind is not in the table.

    Example:
        >>> level_for("extension_points", "cli", True, "small", "small")
        ('must', 'CLI 도구 · 바깥 연결 → 지킴')
        >>> level_for("dependency_direction", "cli", False, "medium", "small")
        ('must', 'CLI 도구 → 권장, 코드 중간 → 지킴')
    """
    t = table(locale)
    w = t["words"]
    p = t["principles"][pid]
    rule = p["levels"][kind]
    kind_label = t["kinds"][kind]["label"]
    if isinstance(rule, dict):
        level = rule["external" if external else "else"]
        why = f"{kind_label} · {w['external'] if external else w['no_external']} → {t['levels'][level]}"
    else:
        level = rule
        why = f"{kind_label} → {t['levels'][level]}"
    signal = {"code": (w["code"], code), "people": (w["people"], people)}.get(p["grows_with"])
    if level == "should" and signal and signal[1] != SIZES[0]:
        level = "must"
        why += f", {signal[0]} {t['sizes'][p['grows_with']][signal[1]]['label']} → {t['levels'][level]}"
    floor = p.get("min_when_large")
    if floor and code == SIZES[-1] and _rank(level) < _rank(floor):
        level = floor
        why += f", {w['code']} {t['sizes']['code'][code]['label']} → {t['levels'][level]}"
    return level, why


@dataclass(frozen=True)
class Principle:
    """One chosen design principle.

    Attributes:
        id: Principle name (key of principles).
        name: Display name, e.g. "단일 책임 (SRP)".
        level: "must" · "should" · "skip".
        reason: One line on why this level.
        explain: One-line description of the principle.
        rules: How to follow it.
        note: Kind-specific addition (data_note for data · ML); empty otherwise.

    Example:
        >>> from lanternspec.core.profile import DEFAULTS, Profile
        >>> data = {**DEFAULTS, "project": {**DEFAULTS["project"], "kind": "script"}}
        >>> first = select(Profile(data)).principles[0]
        >>> first.id, first.level
        ('simplicity', 'must')
    """

    id: str
    name: str
    level: str
    reason: str
    explain: str
    rules: tuple[str, ...]
    note: str = ""


@dataclass(frozen=True)
class Convention:
    """Code conventions chosen for one language.

    Attributes:
        language: Language name, e.g. "python".
        label: Display name, e.g. "Python".
        size: Size the rules were picked for (doc comments may be stricter depending on kind).
        tools: Role (package · format · lint · typecheck · test) → (tool name, default command or note).
        rules: Item (lint · typecheck · type_hints · docs · tests) → one-line rule.
        docs_style: Doc-comment style, e.g. "Google 스타일 docstring".
        example: Example doc comment.
    """

    language: str
    label: str
    size: str
    tools: dict[str, tuple[str, str]]
    rules: dict[str, str]
    docs_style: str
    example: str


@dataclass(frozen=True)
class Selection:
    """Everything chosen for one project: principles, ways of working, conventions.

    Attributes:
        kind: Project kind.
        external: Whether it integrates with outside tools or services.
        code: Code size (as recorded in lantern.yaml).
        people: Team size.
        principles: All principles in table order (including skip).
        always: Ways of working always included (name, rules).
        conventions: One per language.
        locale: Language of the text (lantern.yaml project.language).

    Example:
        >>> from lanternspec.core.profile import DEFAULTS, Profile
        >>> data = {**DEFAULTS, "project": {**DEFAULTS["project"], "kind": "script", "languages": ["python"]}}
        >>> sel = select(Profile(data))
        >>> sel.kind, sel.code, [c.language for c in sel.conventions]
        ('script', 'small', ['python'])
    """

    kind: str
    external: bool
    code: str
    people: str
    principles: tuple[Principle, ...]
    always: tuple[tuple[str, tuple[str, ...]], ...]
    conventions: tuple[Convention, ...] = field(default=())
    locale: str = "ko"

    def at(self, level: str) -> list[Principle]:
        """Return the principles at one level, in table order.

        Args:
            level: "must" · "should" · "skip".

        Returns:
            The principles at that level.

        Example:
            >>> [p.id for p in selection.at("must")]  # doctest: +SKIP
            ['simplicity', 'single_responsibility', 'single_source']
        """
        return [p for p in self.principles if p.level == level]

    def summary(self) -> str:
        """Return kind, external integrations and size as one line.

        Returns:
            e.g. "CLI 도구 · 바깥 연결 · 코드 작음 · 1인".

        Example:
            >>> selection.summary()  # doctest: +SKIP
            'CLI 도구 · 바깥 연결 · 코드 작음 · 1인'
        """
        t = table(self.locale)
        w = t["words"]
        parts = [t["kinds"][self.kind]["label"]] + ([w["external"]] if self.external else [])
        parts += [f"{w['code']} {t['sizes']['code'][self.code]['label']}", t["sizes"]["people"][self.people]["label"]]
        return " · ".join(parts)


def select(profile: Profile) -> Selection | None:
    """Pick principles, ways of working and conventions from the lantern.yaml answers.

    Args:
        profile: Project profile. Nothing is picked without project.kind.
            Code size is the recorded project.code_size, small when missing.

    Returns:
        The selection; None without project.kind.

    Example:
        >>> from lanternspec.core.profile import DEFAULTS, Profile
        >>> data = {**DEFAULTS, "project": {**DEFAULTS["project"], "kind": "script", "languages": ["python"]}}
        >>> sel = select(Profile(data))
        >>> [p.id for p in sel.at("must")], sel.conventions[0].rules["typecheck"]
        (['simplicity'], 'pyright basic')
    """
    kind = profile.get("project.kind")
    if not kind:
        return None
    locale = profile.language
    t = table(locale)
    external = bool(profile.get("project.external"))
    code = str(profile.get("project.code_size") or SIZES[0])
    people = people_size(profile.team, len(profile.get("project.members") or []))
    principles = []
    for pid, p in t["principles"].items():
        level, why = level_for(pid, kind, external, code, people, locale)
        note = str(p.get("data_note") or "") if kind == "data" else ""
        principles.append(Principle(pid, p["name"], level, why, p["explain"], tuple(p["rules"]), note))
    always = tuple((a["name"], tuple(a["rules"])) for a in t["always"].values())
    docs_size = t["kinds"][kind].get("docs") or code
    convs = []
    for lang in profile.get("project.languages") or []:
        c = conventions(lang, locale, profile.comment_language)
        rules = dict(c["levels"][code])
        rules["docs"] = c["levels"][docs_size]["docs"]
        tools = {role: (spec["name"], _default_command(c, role)) for role, spec in c["tools"].items()}
        convs.append(Convention(lang, c["label"], code, tools, rules, c["docs"]["style"], c["docs"]["example"]))
    return Selection(kind, external, code, people, tuple(principles), always, tuple(convs), locale)


@dataclass
class Detected:
    """What was detected from the project's files.

    Attributes:
        languages: Language names (whose conventions' detect matched).
        evidence: Language → the file it was detected from.
        runners: Language → the runner prefix for commands (from the lock file, else the first runner).
        existing: Language → role → (tool name, command with runner, evidence). Only tools already configured.

    Example:
        >>> found = Detected(languages=["python"], runners={"python": "uv run"})
        >>> found.commands(fill_defaults=False)
        {}
    """

    languages: list[str] = field(default_factory=list)
    evidence: dict[str, str] = field(default_factory=dict)
    runners: dict[str, str] = field(default_factory=dict)
    existing: dict[str, dict[str, tuple[str, str, str]]] = field(default_factory=dict)

    def commands(self, fill_defaults: bool) -> dict[str, str]:
        """Build the commands to record in lantern.yaml build.<role>.

        Args:
            fill_defaults: Fill roles without an existing tool with the convention's default (new projects).
                False for existing projects — record only what is configured, bring in no new tools.

        Returns:
            Role (format · lint · typecheck) → command; joined with " && " for several languages.

        Example:
            >>> d = Detected(["python"], runners={"python": "uv run "})
            >>> d.commands(fill_defaults=True)["lint"]
            'uv run ruff check .'
            >>> d.commands(fill_defaults=False)
            {}
        """
        out: dict[str, str] = {}
        for role in COMMAND_ROLES:
            cmds = []
            for lang in self.languages:
                found = self.existing.get(lang, {}).get(role)
                if found:
                    cmds.append(found[1])
                elif fill_defaults:
                    c = conventions(lang)
                    cmds.append(self.runners.get(lang, c["runners"][0]["prefix"]) + c["tools"][role]["command"])
            if cmds:
                out[role] = " && ".join(cmds)
        return out


def detect(root: Path) -> Detected:
    """Detect languages, runners and tools in use from the project's top-level files.

    Config files are only read, never changed.

    Args:
        root: Project root.

    Returns:
        What was detected; an empty Detected for a new project.

    Example:
        >>> detect(project.root).languages  # doctest: +SKIP
        ['python']
    """
    out = Detected()
    for lang in language_names():
        c = conventions(lang)
        hit = next((e for pat in c["detect"] if (e := _found(root, pat))), None)
        if not hit:
            continue
        out.languages.append(lang)
        out.evidence[lang] = hit
        out.runners[lang] = find_runner(root, lang)["prefix"]
        roles: dict[str, tuple[str, str, str]] = {}
        for role, candidates in (c.get("existing") or {}).items():
            for cand in candidates or []:
                ev = next((e for pat in cand["find"] if (e := _found(root, pat))), None)
                if ev:
                    roles[role] = (cand["name"], out.runners[lang] + cand["command"], ev)
                    break
        out.existing[lang] = roles
    return out


def find_runner(root: Path, language: str) -> dict[str, Any]:
    """Find the runner for a language from its lock file.

    Args:
        root: Project root.
        language: Language name.

    Returns:
        One runners entry of the conventions (name · prefix · ci); the first one when no lock file matches (default for new projects).

    Example:
        >>> find_runner(Path("/없는/폴더"), "python")["name"]
        'uv'
    """
    runners = conventions(language)["runners"]
    for r in runners:
        locks = r.get("lock") or []
        if any((root / f).exists() for f in ([locks] if isinstance(locks, str) else locks)):
            return r
    return runners[0]


def _default_command(c: dict[str, Any], role: str) -> str:
    """Prefix the convention's default command with the default runner (a note for roles without a command)."""
    spec = c["tools"][role]
    if "command" not in spec:
        return str(spec.get("note") or "")
    return c["runners"][0]["prefix"] + spec["command"] + (f" ({spec['note']})" if spec.get("note") else "")


def _found(root: Path, pattern: str) -> str | None:
    """Return evidence text when one `file` · `glob` · `file:contained text` pattern matches, else None."""
    name, _, needle = pattern.partition(":")
    paths = sorted(root.glob(name)) if any(ch in name for ch in "*?[") else [root / name]
    for p in paths:
        if not p.exists():
            continue
        if not needle:
            return p.name
        try:
            if needle in p.read_text(encoding="utf-8", errors="ignore"):
                return f"{p.name} {needle}"
        except OSError:
            continue
    return None


def _rank(level: str) -> int:
    return ("skip", "should", "must").index(level)
