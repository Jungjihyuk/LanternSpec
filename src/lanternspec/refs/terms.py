r"""Terms: the project's glossary and the company's, merged into one view, and the words to avoid in documents.

The project glossary is a table in `3. 현재 상태/규칙/용어집.md` (term · meaning · words to avoid ·
scope), read by column position. A company glossary may have any shape, so it stays as it is; the
terms people approved from it (`lantern ref term`) are kept in the index. When a term is in both,
the company's wins.

Responsibilities:
    - read the project glossary and the approved company terms, and merge them (company first)
    - find the words to avoid in a document's text (outside code and frontmatter)

Not here:
    - storing approved company terms → refs/index.py (set_term)
    - reporting them as document findings → check/check_docs.py
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from ..core import outline, sections
from ..core.messages import msg
from ..core.project import Project, read
from . import index as index_mod
from . import sources as src_mod


@dataclass(frozen=True)
class Term:
    """One term and the words to use it instead of.

    Attributes:
        term: The term.
        meaning: What it means.
        avoid: Words not to use for it.
        scope: "all" (or ""), a part's folder or a language.
        company: True when it comes from the company glossary.

    Example:
        >>> Term("회원", "가입한 사람", ("유저", "사용자"), "", False).avoid
        ('유저', '사용자')
    """

    term: str
    meaning: str
    avoid: tuple[str, ...]
    scope: str
    company: bool


def _key(word: str) -> str:
    return " ".join(unicodedata.normalize("NFC", word).casefold().split())


def split_words(text: str) -> tuple[str, ...]:
    """Split a "words to avoid" cell into words (commas, `·` or `/` between them).

    Args:
        text: The cell.

    Returns:
        The words, without blanks.

    Example:
        >>> split_words("유저, 사용자 · user")
        ('유저', '사용자', 'user')
    """
    return tuple(w.strip() for w in re.split(r"[,，·/]", text) if w.strip())


def glossary_path(project: Project) -> Path:
    """Where the project glossary lives.

    Args:
        project: The project.

    Returns:
        `docs/3. 현재 상태/규칙/용어집.md` in the project's language.

    Example:
        >>> glossary_path(project).name  # doctest: +SKIP
        '용어집.md'
    """
    return project.folder("rules") / project.names.file("glossary")


def parse_table(body: str) -> list[Term]:
    r"""Read the rows of a glossary table (by column position: term · meaning · words to avoid · scope).

    Args:
        body: The section holding the table.

    Returns:
        One Term per row with a term; the header and the separator are skipped.

    Example:
        >>> body = "| 용어 | 뜻 | 쓰지 말 표현 | 범위 |\n|---|---|---|---|\n| 회원 | 가입한 사람 | 유저, 사용자 | |\n"
        >>> parse_table(body)
        [Term(term='회원', meaning='가입한 사람', avoid=('유저', '사용자'), scope='', company=False)]
    """
    rows = [line.strip() for line in body.split("\n") if line.strip().startswith("|")]
    out = []
    for row in rows[1:]:
        cells = [c.strip() for c in row.strip("|").split("|")]
        if not cells or not cells[0] or set(cells[0]) <= set("-: "):
            continue
        cells += [""] * (4 - len(cells))
        out.append(Term(cells[0], cells[1], split_words(cells[2]), cells[3], False))
    return out


def project_terms(project: Project) -> list[Term]:
    """Read the project glossary.

    Args:
        project: The project.

    Returns:
        Its terms; [] when the document or its protected section is missing (`lantern check` asks about that).

    Example:
        >>> [t.term for t in project_terms(project)]  # doctest: +SKIP
        ['회원']
    """
    path = glossary_path(project)
    if not path.exists() or project.names.is_unused("glossary"):
        return []
    m = sections.find(read(path), project.names.titles("glossary"))
    return parse_table(m.group(2)) if m else []


def company_terms(project: Project) -> list[Term]:
    """Read the terms people approved from company glossaries (kept in the index).

    Args:
        project: The project.

    Returns:
        The terms, in document order then term order.

    Example:
        >>> [(t.term, t.avoid) for t in company_terms(project)]  # doctest: +SKIP
        [('고객', ('손님',))]
    """
    out = []
    for doc in src_mod.all_documents(project):
        if doc.source.kind != "terms":
            continue
        rec = index_mod.load(project, doc.source.outside).get(doc.shown) or {}
        for term, v in (rec.get("terms") or {}).items():
            v = v if isinstance(v, dict) else {}
            out.append(
                Term(str(term), str(v.get("meaning") or ""), tuple(str(x) for x in v.get("avoid") or []), str(v.get("scope") or ""), True)
            )
    return out


def merged(project: Project) -> tuple[list[Term], list[str]]:
    """Merge the company terms and the project glossary; the company's wins on the same term.

    Args:
        project: The project.

    Returns:
        (terms — company first, then the project's not overridden; terms in both that differ).

    Example:
        >>> merged(project)[1]  # doctest: +SKIP
        ['고객']
    """
    company = company_terms(project)
    theirs = {_key(t.term): t for t in company}
    ours, clash = [], []
    for t in project_terms(project):
        c = theirs.get(_key(t.term))
        if c is None:
            ours.append(t)
        elif (t.meaning, set(t.avoid)) != (c.meaning, set(c.avoid)) and (t.meaning or t.avoid):
            clash.append(t.term)
    return company + ours, clash


def _visible(text: str) -> list[tuple[int, str]]:
    """The document's own words as (1-based number, line): no frontmatter, code, `{{blanks}}` or `> [!guide]` notes from the template."""
    lines = text.split("\n")
    first = 0
    if lines and lines[0].strip() == "---":
        first = next((i + 1 for i in range(1, len(lines)) if lines[i].strip() == "---"), 0)
    out = []
    fence = ""
    guide = False
    for i in range(first, len(lines)):
        mark = outline.FENCE.match(lines[i])
        if mark:
            fence = "" if fence == mark.group(1) else fence or mark.group(1)
            continue
        if fence:
            continue
        line = lines[i]
        guide = line.lstrip().startswith("> [!guide]") or (guide and line.lstrip().startswith(">"))
        if not guide:
            out.append((i + 1, re.sub(r"`[^`]*`|\{\{.*?\}\}", lambda m: " " * len(m.group(0)), line)))
    return out


def _pattern(word: str) -> re.Pattern[str]:
    """Match a word: whole words for Latin letters, anywhere for Korean (which has no spaces inside words)."""
    w = re.escape(unicodedata.normalize("NFC", word))
    return re.compile(rf"(?<![A-Za-z0-9_]){w}(?![A-Za-z0-9_])" if word.isascii() else w, re.I)


def avoid_hits(text: str, terms: list[Term]) -> list[tuple[int, str, Term]]:
    r"""Find the words to avoid in a document, outside frontmatter and code.

    Where the term itself contains the word (term "회원 정보", word "정보"), the term's own uses don't count.

    Args:
        text: The document.
        terms: The merged terms.

    Returns:
        (line number, the word found, its term), in line order.

    Example:
        >>> t = Term("회원", "", ("유저",), "", False)
        >>> avoid_hits("# 기획\n유저가 가입한다\n`유저` 코드\n", [t])
        [(2, '유저', Term(term='회원', meaning='', avoid=('유저',), scope='', company=False))]
    """
    out = []
    lines = _visible(unicodedata.normalize("NFC", text))
    for t in terms:
        own = _pattern(t.term)
        for word in t.avoid:
            if _key(word) == _key(t.term):
                continue
            pat = _pattern(word)
            for n, line in lines:
                if pat.search(own.sub(lambda m: " " * len(m.group(0)), line)):
                    out.append((n, word, t))
    return sorted(out, key=lambda x: x[0])


def table(project: Project) -> str:
    """Write the merged terms as one table, for `lantern ref terms`.

    Args:
        project: The project.

    Returns:
        A Markdown table with where each term comes from, and a line on terms both glossaries define differently.

    Example:
        >>> print(table(project))  # doctest: +SKIP
        | 용어 | 뜻 | 쓰지 말 표현 | 범위 | 출처 |
        …
    """
    terms, clash = merged(project)
    if not terms:
        return ""
    lines = [msg("| Term | Meaning | Words to avoid | Scope | From |"), "|---|---|---|---|---|"]
    for t in terms:
        cells = [t.term, t.meaning, ", ".join(t.avoid), t.scope or "all", msg("company") if t.company else msg("project")]
        lines.append("| " + " | ".join(c.replace("|", "\\|") for c in cells) + " |")
    if clash:
        lines += ["", msg("⚠ Also in the project glossary with another meaning — the company's wins: {items}", items=", ".join(clash))]
    return "\n".join(lines)
