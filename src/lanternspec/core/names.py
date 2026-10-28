"""Read names.yaml and provide every name the program reads and writes, looked up by role.

Responsibilities:
    - read `resources/names.yaml` (folders · documents · task attributes · markers · protected sections) in one language
    - pick one language's text out of tables that keep it under language keys (localize)
    - apply the project's own decisions about protected sections (renamed · unused) from lantern.yaml
    - build the values skills and rules are filled with (`<<folder.current>>` · `<<file.plan>>` · `<<section.now>>`)

Not here:
    - choice lists such as statuses → core/enums.py
    - finding a section in a document → core/sections.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cache
from typing import Any

import yaml

from .. import resources

WORK_DOCS = ("plan", "design", "tasks", "record")  # the four documents of a work folder, in order


@dataclass(frozen=True)
class Section:
    """A protected section: one lantern reads or writes.

    Attributes:
        role: Key, e.g. "now".
        title: The default title in this language, e.g. "지금 상황".
        docs: Document roles the section lives in, e.g. ("record", "session").
        feature: What lantern does with it, in words shown to the user.

    Example:
        >>> load("ko").section("now").docs
        ('record', 'session')
    """

    role: str
    title: str
    docs: tuple[str, ...]
    feature: str


@dataclass
class Names:
    """Every name of one language, plus one project's decisions about protected sections.

    Attributes:
        language: Language code, e.g. "ko".
        table: names.yaml with this language's names picked out.
        renamed: Protected-section role → titles the project uses instead of the default, newest first.
        unused: Protected-section roles the project chose not to use.

    Example:
        >>> names = load("ko", renamed={"now": "오늘 한 일"})
        >>> names.folder("templates"), names.file("plan"), names.titles("now")
        ('0. 템플릿', '기획.md', ['오늘 한 일', '지금 상황'])
    """

    language: str
    table: dict[str, Any]
    renamed: dict[str, list[str]] = field(default_factory=dict)
    unused: frozenset[str] = frozenset()

    def folder(self, key: str) -> str:
        """Return a folder path under the documents root.

        Args:
            key: Folder key, e.g. "works".

        Returns:
            The path, e.g. "2. 작업".

        Raises:
            KeyError: The key is not in names.yaml.

        Example:
            >>> load("ko").folder("archive")
            '2. 작업/보관'
        """
        return str(self.table["folders"][key])

    def folders(self) -> dict[str, str]:
        """Return every folder key and path.

        Returns:
            Folder key → path, in names.yaml order.

        Example:
            >>> list(load("ko").folders())[:2]
            ['templates', 'ideas']
        """
        return {k: str(v) for k, v in self.table["folders"].items()}

    def doc(self, role: str) -> str:
        """Return a document name without extension — also the name of its template.

        Args:
            role: Document role, e.g. "plan".

        Returns:
            The name, e.g. "기획".

        Raises:
            KeyError: The role is not in names.yaml.

        Example:
            >>> load("ko").doc("debt_card")
            '부채 카드'
        """
        return str(self.table["docs"][role])

    def file(self, role: str) -> str:
        """Return a document's file name.

        Args:
            role: Document role, e.g. "tasks".

        Returns:
            The name with `.md`.

        Raises:
            KeyError: The role is not in names.yaml.

        Example:
            >>> load("ko").file("tasks")
            '할 일.md'
        """
        return self.doc(role) + ".md"

    def doc_role(self, name: str) -> str | None:
        """Return the role of a document or template name (the reverse of doc).

        Args:
            name: A document or template name, e.g. "기록".

        Returns:
            The role; None when no document has that name.

        Example:
            >>> load("ko").doc_role("기록"), load("ko").doc_role("메모")
            ('record', None)
        """
        return next((r for r, n in self.table["docs"].items() if str(n) == name), None)

    def attr(self, role: str) -> str:
        """Return the name of a task-line attribute (`[name:: value]`).

        Args:
            role: Attribute role, e.g. "size".

        Returns:
            The name.

        Raises:
            KeyError: The role is not in names.yaml.

        Example:
            >>> load("ko").attr("after")
            '먼저'
        """
        return str(self.table["task_attrs"][role])

    def attr_role(self, name: str) -> str:
        """Return the role of a task-line attribute name (the reverse of attr).

        Args:
            name: Attribute name as written in a document.

        Returns:
            The role; the name itself when it is not a known attribute.

        Example:
            >>> load("ko").attr_role("크기"), load("ko").attr_role("메모")
            ('size', '메모')
        """
        return next((r for r, n in self.table["task_attrs"].items() if n == name), name)

    def marker(self, key: str) -> str:
        """Return a marker lantern recognizes in documents.

        Args:
            key: Marker key, e.g. "unknown" or "required".

        Returns:
            The marker text.

        Raises:
            KeyError: The key is not in names.yaml.

        Example:
            >>> load("ko").marker("required")
            '(필수)'
        """
        return str(self.table["markers"][key])

    def acceptance(self, key: str) -> Any:
        """Return a word or word list used to check acceptance criteria.

        Args:
            key: e.g. "action", "result" or "vague".

        Returns:
            The word, or the list of words.

        Raises:
            KeyError: The key is not in names.yaml.

        Example:
            >>> load("ko").acceptance("result")
            '결과'
        """
        return self.table["acceptance"][key]

    def section(self, role: str) -> Section:
        """Return a protected section's definition.

        Args:
            role: Section role, e.g. "now".

        Returns:
            The section, with its default title.

        Raises:
            KeyError: The role is not a protected section.

        Example:
            >>> load("ko").section("origin").title
            '어디서 나왔나'
        """
        spec = self.table["sections"][role]
        return Section(role, str(spec["title"]), tuple(spec.get("docs") or ()), str(spec.get("feature") or ""))

    def sections(self) -> list[Section]:
        """Return every protected section, in names.yaml order.

        Returns:
            The sections.

        Example:
            >>> [s.role for s in load("ko").sections()][:3]
            ['now', 'past', 'schema']
        """
        return [self.section(r) for r in self.table["sections"]]

    def sections_in(self, doc_role: str) -> list[Section]:
        """Return the protected sections a kind of document has.

        Args:
            doc_role: Document role, e.g. "record".

        Returns:
            The sections, in names.yaml order.

        Example:
            >>> [s.role for s in load("ko").sections_in("record")]
            ['now', 'past', 'schema']
        """
        return [s for s in self.sections() if doc_role in s.docs]

    def title(self, role: str) -> str:
        """Return the title this project uses for a protected section.

        Args:
            role: Section role.

        Returns:
            The newest title the project chose; the default title otherwise.

        Example:
            >>> load("ko", renamed={"now": ["오늘", "현재"]}).title("now")
            '오늘'
        """
        return self.titles(role)[0]

    def titles(self, role: str) -> list[str]:
        """Return every title a protected section may have in this project, newest first.

        Documents made before a rename keep the older title, so all of them are accepted.

        Args:
            role: Section role.

        Returns:
            The renamed titles (newest first), then the default title.

        Example:
            >>> load("ko").titles("past")
            ['지난 기록']
        """
        out = list(self.renamed.get(role, []))
        default = self.section(role).title
        return out + ([default] if default not in out else [])

    def is_unused(self, role: str) -> bool:
        """Tell whether the project chose not to use a protected section.

        Args:
            role: Section role.

        Returns:
            True when the role is listed in docs.unused_sections.

        Example:
            >>> load("ko", unused={"schema"}).is_unused("schema")
            True
        """
        return role in self.unused

    def context(self) -> dict[str, str]:
        """Build the values skills and rules are filled with.

        Returns:
            `folder.<key>`, `doc.<role>`, `file.<role>`, `attr.<role>`, `marker.<key>` and
            `section.<role>` (the project's current title) → name.

        Example:
            >>> ctx = load("ko").context()
            >>> ctx["folder.current"], ctx["file.record"], ctx["section.now"]
            ('3. 현재 상태', '기록.md', '지금 상황')
        """
        ctx: dict[str, str] = {}
        ctx.update({f"folder.{k}": v for k, v in self.folders().items()})
        for role in self.table["docs"]:
            ctx[f"doc.{role}"] = self.doc(role)
            ctx[f"file.{role}"] = self.file(role)
        ctx.update({f"attr.{r}": self.attr(r) for r in self.table["task_attrs"]})
        ctx.update({f"marker.{k}": self.marker(k) for k in self.table["markers"]})
        ctx.update({f"section.{s.role}": self.title(s.role) for s in self.sections()})
        return ctx


def languages() -> list[str]:
    """List the languages that have a language pack (`resources/locales/<language>/`).

    Returns:
        Language codes, sorted.

    Example:
        >>> "ko" in languages()
        True
    """
    return sorted(p.name for p in resources.path("locales").iterdir() if p.is_dir() and not p.name.startswith("_"))


def localize(node: Any, locale: str) -> Any:
    """Pick one language's text out of a table where text sits under language keys (`ko:` · `en:`).

    A mapping whose keys are all language codes becomes that language's value; a mapping that also has
    other keys gets that language's mapping merged in. A missing language falls back to Korean.

    Args:
        node: Part of a table read from YAML.
        locale: Language code (lantern.yaml project.language, or project.comment_language for doc comments).

    Returns:
        The same shape with every language block resolved.

    Example:
        >>> localize({"grows_with": "code", "ko": {"name": "단순함"}, "en": {"name": "Simplicity"}}, "en")
        {'grows_with': 'code', 'name': 'Simplicity'}
        >>> localize({"must": {"ko": "지킴"}}, "en")
        {'must': '지킴'}
    """
    codes = set(languages()) | {"ko", "en"}
    if isinstance(node, list):
        return [localize(x, locale) for x in node]
    if not isinstance(node, dict):
        return node
    langs = [k for k in node if k in codes]
    if not langs:
        return {k: localize(v, locale) for k, v in node.items()}
    chosen = node.get(locale, node.get("ko"))
    rest = {k: localize(v, locale) for k, v in node.items() if k not in codes}
    if not rest:
        return localize(chosen, locale)
    rest.update(localize(chosen, locale) or {})
    return rest


@cache
def _raw() -> dict[str, Any]:
    """Read names.yaml once, with every language's names."""
    return yaml.safe_load(resources.read_text("names.yaml")) or {}


@cache
def _table(language: str) -> dict[str, Any]:
    """One language's names (once per process)."""
    if language not in languages():
        raise ValueError(f"언어 '{language}' 묶음이 없습니다 (가능: {', '.join(languages())})")
    return localize(_raw(), language)


def load(language: str = "ko", renamed: dict[str, Any] | None = None, unused: Any = None) -> Names:
    """Load the names of a language with a project's decisions about protected sections.

    Args:
        language: Language code (lantern.yaml project.language).
        renamed: Section role → new title, or a list of titles newest first (lantern.yaml docs.sections).
        unused: Section roles not used (lantern.yaml docs.unused_sections).

    Returns:
        The names.

    Raises:
        ValueError: The language has no names table.

    Example:
        >>> load("ko").doc("plan")
        '기획'
    """
    titles = {role: ([str(v)] if isinstance(v, str) else [str(x) for x in v or []]) for role, v in (renamed or {}).items()}
    return Names(language, _table(language), titles, frozenset(unused or ()))
