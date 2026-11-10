r"""Terms: the project's glossary and the company's, merged into one view, and the words to avoid in documents.

The project glossary is a table in `3. 현재 상태/규칙/용어집.md` (term · meaning · words to avoid ·
scope), read by column position. A company glossary may have any shape, so it stays as it is; the
terms people approved from it (`lantern ref term`) are kept in the index. When a term is in both,
the company's wins.

Responsibilities:
    - read the project glossary and the approved company terms, and merge them (company first)
    - find the words to avoid in a document's text (outside code and frontmatter)
    - keep the glossary candidates (words people asked about that the documents use) and add approved ones to the glossary

Not here:
    - storing approved company terms → refs/index.py (set_term)
    - noticing a question about a word in conversation → tools/agent_hooks.py (term_detect)
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


CANDIDATES = "term-candidates.json"  # in .lantern/ — words people asked about, waiting for approval


def find(project: Project, word: str) -> Term | None:
    """Find a term in the merged glossary (company first).

    Args:
        project: The project.
        word: The word asked about.

    Returns:
        The term; None when neither glossary has it.

    Example:
        >>> find(project, "회원").meaning  # doctest: +SKIP
        '가입한 사람'
    """
    want = _key(word)
    return next((t for t in merged(project)[0] if _key(t.term) == want), None)


# Rule documents every project gets as they come: their words are LanternSpec's general advice, not this project's language.
GENERAL_RULE_DOCS = ("tech_criteria", "repo_files", "task_rules")


def general_rule_docs(project: Project) -> set[Path]:
    """The rule documents every project gets as bundled (see GENERAL_RULE_DOCS), resolved.

    Args:
        project: The project.

    Returns:
        Their paths, whether they exist or not.

    Example:
        >>> sorted(p.name for p in general_rule_docs(project))  # doctest: +SKIP
        ['기술 선택 기준.md', '저장소 파일 규칙.md', '할 일 나누기 기준.md']
    """
    rules = project.folder("rules")
    return {(rules / project.names.file(role)).resolve() for role in GENERAL_RULE_DOCS}


def in_documents(project: Project, word: str) -> bool:
    """Tell whether the project's own documents use a word (templates, legacy originals, the debt ledger and general rules aside).

    Args:
        project: The project.
        word: The word.

    Returns:
        True when some document mentions it.

    Example:
        >>> in_documents(project, "정산 주기")  # doctest: +SKIP
        True
    """
    pat = _pattern(word)
    skipped = {glossary_path(project).resolve(), *general_rule_docs(project)}
    debt = project.folder("debt").resolve()  # the learning track's own cards are about technologies, not the project
    for p in project.iter_docs():
        if (
            p.resolve() not in skipped
            and debt not in p.resolve().parents
            and any(pat.search(line) for _, line in _visible(unicodedata.normalize("NFC", read(p))))
        ):
            return True
    return False


def _candidate_file(project: Project) -> Path:
    return project.state / CANDIDATES


def candidates(project: Project) -> list[dict]:
    """List the glossary candidates: words people asked about that the project's documents use.

    Args:
        project: The project.

    Returns:
        {term, asked, last} entries, most asked first.

    Example:
        >>> candidates(project)  # doctest: +SKIP
        [{'term': '정산 주기', 'asked': 2, 'last': '2026-11-01'}]
    """
    import json

    try:
        data = json.loads(read(_candidate_file(project)))
    except (OSError, ValueError):
        return []
    items = [x for x in data if isinstance(x, dict) and x.get("term")] if isinstance(data, list) else []
    return sorted(items, key=lambda x: -int(x.get("asked") or 0))


def _save_candidates(project: Project, items: list[dict]) -> None:
    import json

    from ..core.state import ensure_state_dir

    ensure_state_dir(project)
    _candidate_file(project).write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")


def add_candidate(project: Project, word: str) -> int:
    """Count one more ask of a word as a glossary candidate.

    Args:
        project: The project.
        word: The word.

    Returns:
        How many times it has been asked.

    Example:
        >>> add_candidate(project, "정산 주기")  # doctest: +SKIP
        1
    """
    from ..core.project import today

    items = candidates(project)
    hit = next((x for x in items if _key(x["term"]) == _key(word)), None)
    if hit is None:
        hit = {"term": word, "asked": 0}
        items.append(hit)
    hit["asked"] = int(hit.get("asked") or 0) + 1
    hit["last"] = today()
    _save_candidates(project, items)
    return hit["asked"]


def drop_candidate(project: Project, word: str) -> bool:
    """Forget a glossary candidate.

    Args:
        project: The project.
        word: The word.

    Returns:
        True when it was a candidate.

    Example:
        >>> drop_candidate(project, "정산 주기")  # doctest: +SKIP
        True
    """
    items = candidates(project)
    rest = [x for x in items if _key(x["term"]) != _key(word)]
    if len(rest) == len(items):
        return False
    _save_candidates(project, rest)
    return True


def add_to_glossary(project: Project, term: str, meaning: str, avoid: list[str], scope: str = "") -> Path:
    """Add one row to the project glossary (or replace the row of the same term), and drop it from the candidates.

    Args:
        project: The project.
        term: The term.
        meaning: What it means, in one line.
        avoid: Words not to use for it.
        scope: "all" (or ""), a part's folder or a language.

    Returns:
        The glossary document.

    Raises:
        sections.SectionMissing: The glossary has no terms section any more (the message says what to do).

    Example:
        >>> add_to_glossary(project, "정산 주기", "가맹점에 돈을 보내는 간격", ["정산일"])  # doctest: +SKIP
        PosixPath('…/3. 현재 상태/규칙/용어집.md')
    """
    from ..core import frontmatter
    from ..core.project import write

    path = glossary_path(project)
    if not path.exists():
        from ..work.scaffold import create_from_template

        create_from_template(project, project.names.doc("glossary"), path)
    text = read(path)
    m = sections.find(text, project.names.titles("glossary"))
    if m is None:
        raise sections.SectionMissing(project.names, "glossary", path)
    clean = [c.replace("|", "/").replace("\n", " ").strip() for c in (term, meaning, ", ".join(avoid), scope if scope != "all" else "")]
    row = "| " + " | ".join(clean) + " |"
    lines = m.group(2).split("\n")
    rows = [i for i, line in enumerate(lines) if line.strip().startswith("|")][2:]  # past the header and the separator
    same = next((i for i in rows if _key(lines[i].strip().strip("|").split("|")[0]) == _key(term)), None)
    if same is not None:
        lines[same] = row
    else:
        last = max((i for i, line in enumerate(lines) if line.strip().startswith("|")), default=None)
        lines.insert(0 if last is None else last + 1, row)
    text = text[: m.start(2)] + "\n".join(lines) + text[m.end(2) :]
    write(path, frontmatter.set_fields(text, {}))
    drop_candidate(project, term)
    return path
