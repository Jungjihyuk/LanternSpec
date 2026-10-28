"""📒 Debt ledger — one card per debt. Counting and status changes are scripted.

Responsibilities:
    - find debt cards by ID, title or alias
    - create cards, count asks (once per conversation), resolve, promote to competency debt, log practice
    - the known-tech list that keeps familiar terms out of the candidates
    - the generated debt status page (`부채 현황.md`)

Not here:
    - reading the person's knowledge store → learn/knowledge/
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from ..core import frontmatter, sections, templating
from ..core.new_id import next_id
from ..core.project import Project, nfc, now_minute, read, safe_name, today, wikilink, write


def norm(term: str) -> str:
    """Normalize a term for matching: lower case, NFC, no spaces or separators.

    Args:
        term: A term as written, e.g. "Server-Side Rendering".

    Returns:
        The normalized form.

    Example:
        >>> norm("Server-Side Rendering") == norm("serverside rendering")
        True
    """
    return re.sub(r"[\s\-_.·/]+", "", nfc(term).lower())


@dataclass
class Card:
    """One debt card.

    Attributes:
        path: The card file.
        meta: Its frontmatter.

    Example:
        >>> card = Card(Path("D-007 JWT.md"), {"id": "D-007", "aliases": ["JSON Web Token"]})
        >>> card.id, card.title, card.names
        ('D-007', 'JWT', ['JWT', 'JSON Web Token'])
    """

    path: Path
    meta: dict

    @property
    def id(self) -> str:
        """The card's ID, e.g. "D-007"."""
        return str(self.meta.get("id", ""))

    @property
    def title(self) -> str:
        """The card's title: the file name without the ID."""
        stem = nfc(self.path.stem)
        return stem.split(" ", 1)[1] if " " in stem else stem

    @property
    def names(self) -> list[str]:
        """The title followed by the aliases."""
        return [self.title] + [str(a) for a in frontmatter.as_list(self.meta.get("aliases"))]

    def matches(self, term: str) -> bool:
        """Tell whether a term names this card (title or alias, ignoring case, spaces and separators).

        Args:
            term: The term.

        Returns:
            True when the term matches one of the names.

        Example:
            >>> Card(Path("D-007 JWT.md"), {"aliases": ["JSON Web Token"]}).matches("json web-token")
            True
        """
        t = norm(term)
        return any(norm(n) == t for n in self.names if n)


def cards(project: Project) -> list[Card]:
    """Read every debt card.

    Args:
        project: The project.

    Returns:
        The cards, sorted by file name; empty when there is no card folder.

    Example:
        >>> [c.id for c in cards(project)]  # doctest: +SKIP
        ['D-001', 'D-002']
    """
    folder = project.folder("debt_cards")
    if not folder.exists():
        return []
    return [Card(p, frontmatter.parse(read(p)).meta) for p in sorted(folder.glob("*.md"))]


def kind_of(project: Project, card: Card) -> str:
    """Return a card's debt kind.

    Args:
        project: The project.
        card: The card.

    Returns:
        Its `kind`; the "understanding" kind when the card has none.

    Example:
        >>> kind_of(project, cards(project)[0])  # doctest: +SKIP
        '이해'
    """
    return str(card.meta.get("kind") or project.enums.value("debt_kind", "understanding"))


def status_label(project: Project, status: str) -> str:
    """Return the icon and name of a debt status, from enums.yaml.

    Args:
        project: The project.
        status: A debt_status value.

    Returns:
        "icon name".

    Example:
        >>> status_label(project, "되물음")  # doctest: +SKIP
        '🤔 되물음'
    """
    return project.enums["debt_status"].labelled(status)


def find(project: Project, term: str, kind: str | None = None) -> Card | None:
    """Find a card by ID, title or alias.

    Args:
        project: The project.
        term: An ID such as "D-007", a title or an alias.
        kind: A debt_kind role (understanding · competency · tech) to limit the search; any kind when None.

    Returns:
        The first matching card; None when nothing matches.

    Example:
        >>> find(project, "json web token").id  # doctest: +SKIP
        'D-007'
    """
    want = project.enums.value("debt_kind", kind) if kind else None
    for c in cards(project):
        if want and kind_of(project, c) != want:
            continue
        if c.id.upper() == term.upper() or c.matches(term):
            return c
    return None


# --------------------------------------------------------------------------- known tech


def known_file(project: Project) -> Path:
    """Return the known-tech list file (`📒 부채/아는 기술.md`).

    Args:
        project: The project.

    Returns:
        Its path (it may not exist).

    Example:
        >>> known_file(project).name  # doctest: +SKIP
        '아는 기술.md'
    """
    return project.folder("debt") / project.names.file("known_tech")


def known_list(project: Project) -> list[list[str]]:
    """Read the known-tech list.

    Args:
        project: The project.

    Returns:
        One list of names per entry: the name, then its aliases. Empty when there is no list.

    Example:
        >>> known_list(project)  # doctest: +SKIP
        [['React', 'ReactJS']]
    """
    p = known_file(project)
    if not p.exists():
        return []
    out = []
    for line in read(p).split("\n"):
        m = re.match(r"^- (.+?)(?: \((.+?)\))?(?: — .*)?$", line.strip())
        if m and not line.strip().startswith("- {{"):
            names = [m.group(1).strip()] + [a.strip() for a in (m.group(2) or "").split(",") if a.strip()]
            out.append(names)
    return out


def is_known(project: Project, term: str) -> bool:
    """Tell whether a term is on the known-tech list.

    Args:
        project: The project.
        term: The term.

    Returns:
        True when it matches a name or alias on the list.

    Example:
        >>> is_known(project, "reactjs")  # doctest: +SKIP
        True
    """
    t = norm(term)
    return any(norm(n) == t for names in known_list(project) for n in names)


def known_add(project: Project, name: str, aliases: list[str] | None = None) -> Path:
    """Add a term to the known-tech list (creating the list when missing); known terms are skipped.

    Args:
        project: The project.
        name: The term.
        aliases: Other names for it.

    Returns:
        The known-tech list file.

    Example:
        >>> known_add(project, "React", ["ReactJS"]).name  # doctest: +SKIP
        '아는 기술.md'
    """
    n = project.names
    p = known_file(project)
    if not p.exists():
        from ..work.scaffold import create_from_template

        create_from_template(project, n.doc("known_tech"), p)
    if is_known(project, name) or n.is_unused("known_list"):
        return p
    alias = f" ({', '.join(aliases)})" if aliases else ""
    text = sections.append(read(p), n.titles("known_list"), f"- {name}{alias} — {today()}")
    if text is None:
        raise sections.SectionMissing(n, "known_list", p)
    write(p, frontmatter.set_fields(text, {}))
    return p


# --------------------------------------------------------------------------- cards


def new_card(
    project: Project,
    name: str,
    area: str = "기타",
    aliases: list[str] | None = None,
    work: str | None = None,
    note: str | None = None,
    session: str = "",
    context: str = "",
    kind: str | None = None,
) -> Path:
    """Create a debt card under the next debt ID.

    Understanding debt by default — or technical debt recorded by hand (`--kind 기술`).
    Competency debt comes from promote.

    Args:
        project: The project.
        name: The term.
        area: Topic, one of enums.yaml `area`.
        aliases: Other names for the term.
        work: The work it came up in.
        note: A link or name of the person's own note about it.
        session: The conversation it came up in (so asks are counted once per conversation).
        context: One line on where it came up.
        kind: The understanding or tech kind; understanding when None.

    Returns:
        The new card.

    Raises:
        ValueError: The topic or kind is not allowed.
        FileExistsError: A card of that kind already has the name.

    Example:
        >>> new_card(project, "JWT", area="보안", work="W-012").name  # doctest: +SKIP
        'D-008 JWT.md'
    """
    enums = project.enums
    allowed = [enums.value("debt_kind", "understanding"), enums.value("debt_kind", "tech")]
    kind = kind or allowed[0]
    if area not in enums.values("area"):
        raise ValueError(f"주제 '{area}'은 enums.yaml area 값이 아닙니다 (가능: {', '.join(enums.values('area'))})")
    if kind not in allowed:
        raise ValueError(f"새 카드의 종류는 {' · '.join(allowed)} (역량 부채는 lantern debt promote D-NNN)")
    existing = find(project, name, kind=enums["debt_kind"].role_of(kind))
    if existing:
        raise FileExistsError(f"이미 카드가 있습니다: {existing.id} {existing.title} (lantern debt ask {existing.id})")
    debt_id = next_id(project, "debt")
    dest = project.folder("debt_cards") / f"{debt_id} {safe_name(name)}.md"
    owner = (project.profile.get("project.members") or [""])[0] if project.profile.team else ""
    work_link = _work_link(project, work) if work else ""
    status = enums.value("debt_status", "new")
    from ..work.scaffold import create_from_template

    create_from_template(
        project,
        project.names.doc("debt_card"),
        dest,
        {
            "id": debt_id,
            "name": safe_name(name),
            "status": templating.yaml_str(status),
            "kind": kind,
            "area": templating.yaml_str(area),
            "aliases": templating.yaml_list(aliases or []),
            "owner": templating.yaml_str(owner),
            "note": templating.yaml_str(note or ""),
            "work": templating.yaml_list([work_link] if work_link else []),
            "session": templating.yaml_str(session),
            "links": templating.yaml_list([work_link] if work_link else []),
            "work_text": " · ".join(x for x in [work_link or "직접 물음", context] if x),
        },
    )
    return dest


def _work_link(project: Project, work_id: str) -> str:
    folder = project.find_work(work_id)
    if folder is None:
        return work_id.upper()
    return wikilink(project, project.doc_path(folder, "plan"), work_id.upper())


def _append_origin(project: Project, text: str, line: str) -> str:
    """Add a line to the card's "어디서 나왔나"; unchanged when the section is missing or turned off."""
    n = project.names
    if n.is_unused("origin"):
        return text
    return sections.append(text, n.titles("origin"), line) or text


@dataclass
class AskResult:
    """What `lantern debt ask` did.

    Attributes:
        card: The card file.
        counted: Whether this ask was counted (once per conversation).
        status: The card's status now.
        ask_count: How many times it has been asked.
        reopened: Whether a resolved card was opened again.

    Example:
        >>> AskResult(Path("D-007 JWT.md"), True, "되물음", 2, False).ask_count
        2
    """

    card: Path
    counted: bool
    status: str
    ask_count: int
    reopened: bool


def ask(project: Project, term: str, work: str | None = None, session: str = "", context: str = "") -> AskResult:
    """Count one more ask of an understanding-debt card: once per conversation; resolved cards reopen.

    Args:
        project: The project.
        term: The card's ID, title or alias.
        work: The work it came up in; linked from the card.
        session: The conversation; a second ask in the same conversation is not counted.
        context: One line on where it came up.

    Returns:
        What happened.

    Raises:
        LookupError: There is no understanding-debt card for the term.

    Example:
        >>> ask(project, "JWT", work="W-012", session="s1").ask_count  # doctest: +SKIP
        2
    """
    card = find(project, term, kind="understanding")
    if card is None:
        raise LookupError(f"'{term}' 카드가 없습니다 — lantern debt new 로 만드세요")
    st = project.enums["debt_status"]
    meta = card.meta
    count = int(meta.get("ask_count") or 0)
    status = str(meta.get("status") or st.value("new"))
    if session and str(meta.get("last_session") or "") == session:
        return AskResult(card.path, False, status, count, False)
    reopened = status == st.value("resolved")
    new_status = st.value("asked_again")
    updates: dict = {"ask_count": count + 1, "status": new_status, "last_asked": today()}
    if session:
        updates["last_session"] = session
    if reopened:
        updates["resolved"] = ""
    links = frontmatter.as_list(meta.get("work"))
    if work:
        wl = _work_link(project, work)
        if wl not in links:
            updates["work"] = links + [wl]
            all_links = frontmatter.as_list(meta.get("links"))
            if wl not in all_links:
                updates["links"] = all_links + [wl]
    text = frontmatter.set_fields(read(card.path), updates)
    again = f"↩️ {st.value('resolved')} 뒤 다시 물음 · " if reopened else ""
    origin = f"- {today()} {again}{_work_link(project, work) if work else '직접 물음'}"
    if context:
        origin += f" · {context}"
    write(card.path, _append_origin(project, text, origin))
    return AskResult(card.path, True, new_status, count + 1, reopened)


def resolve(project: Project, term: str, note: str | None = None) -> Path:
    """Mark a card resolved (with today's date).

    Args:
        project: The project.
        term: The card's ID, title or alias.
        note: A note to record with it.

    Returns:
        The card file.

    Raises:
        LookupError: There is no card for the term.

    Example:
        >>> resolve(project, "D-007").name  # doctest: +SKIP
        'D-007 JWT.md'
    """
    card = find(project, term)
    if card is None:
        raise LookupError(f"'{term}' 카드가 없습니다")
    updates: dict = {"status": project.enums.value("debt_status", "resolved"), "resolved": today()}
    if note:
        updates["note"] = note
    write(card.path, frontmatter.set_fields(read(card.path), updates))
    return card.path


# --------------------------------------------------------------------------- competency debt (understanding → competency)


def promote(project: Project, term: str, name: str | None = None) -> Path:
    """Create a competency-debt card ("build it myself") from a resolved understanding-debt card.

    Args:
        project: The project.
        term: The understanding card's ID, title or alias.
        name: The new card's title; "<title> 직접 만들기" when None.

    Returns:
        The new competency card.

    Raises:
        LookupError: There is no understanding card for the term.
        ValueError: The understanding card is not resolved yet.
        FileExistsError: It already has a competency card.

    Example:
        >>> promote(project, "D-007").name  # doctest: +SKIP
        'D-009 JWT 직접 만들기.md'
    """
    src = find(project, term, kind="understanding")
    if src is None:
        raise LookupError(f"'{term}' 이해 부채 카드가 없습니다")
    if src.meta.get("status") != project.enums.value("debt_status", "resolved"):
        raise ValueError(f"{src.id}는 아직 해결되지 않았습니다 — 이해가 먼저, 역량은 그다음 (lantern debt resolve {src.id})")
    for c in cards(project):
        if kind_of(project, c) == project.enums.value("debt_kind", "competency") and str(c.meta.get("from") or "") == src.id:
            raise FileExistsError(f"이미 역량 카드가 있습니다: {c.id} {c.title}")
    debt_id = next_id(project, "debt")
    title = safe_name(name or f"{src.title} 직접 만들기")
    dest = project.folder("debt_cards") / f"{debt_id} {title}.md"
    from ..work.scaffold import create_from_template

    link = wikilink(project, src.path, src.id)
    create_from_template(
        project,
        project.names.doc("competency_card"),
        dest,
        {
            "status": templating.yaml_str(project.enums.value("debt_status", "new")),
            "kind": project.enums.value("debt_kind", "competency"),
            "id": debt_id,
            "name": title,
            "area": templating.yaml_str(str(src.meta.get("area") or "기타")),
            "aliases": templating.yaml_list([str(a) for a in frontmatter.as_list(src.meta.get("aliases"))]),
            "owner": templating.yaml_str(str(src.meta.get("owner") or "")),
            "source": src.id,
            "source_link": link,
            "links": templating.yaml_list([link]),
        },
    )
    competency = project.enums.label("debt_kind", "competency")
    write(src.path, _append_origin(project, read(src.path), f"- {today()} {competency} 부채로 넘김 → {wikilink(project, dest, debt_id)}"))
    return dest


def practice(project: Project, term: str, result: str) -> Path:
    """Log something built for a competency-debt card and mark it practicing.

    Args:
        project: The project.
        term: The competency card's ID, title or alias.
        result: What was built, in one line.

    Returns:
        The card file.

    Raises:
        LookupError: There is no competency card for the term.

    Example:
        >>> practice(project, "D-009", "토큰 발급 직접 구현").name  # doctest: +SKIP
        'D-009 JWT 직접 만들기.md'
    """
    competency = project.enums.value("debt_kind", "competency")
    card = next(
        (c for c in cards(project) if kind_of(project, c) == competency and (c.id.upper() == term.upper() or c.matches(term))), None
    )
    if card is None:
        raise LookupError(f"'{term}' 역량 카드가 없습니다 (lantern debt promote 먼저)")
    text = frontmatter.set_fields(read(card.path), {"status": project.enums.value("debt_status", "practicing")})
    n = project.names
    if not n.is_unused("practice"):  # a missing section only loses the log line; check asks about it
        text = sections.append(text, n.titles("practice"), f"- {today()} {result}") or text
    write(card.path, text)
    return card.path


# --------------------------------------------------------------------------- debt status page (generated)


def stats(project: Project) -> dict:
    """Count the debt cards.

    Args:
        project: The project.

    Returns:
        total, open and resolved counts, by_status (status → count) and
        table (kind → topic → open count).

    Example:
        >>> stats(project)["open"]  # doctest: +SKIP
        3
    """
    cs = cards(project)
    enums = project.enums
    resolved = enums.value("debt_status", "resolved")
    table: dict[str, Counter] = {k: Counter() for k in enums.values("debt_kind")}
    status = Counter()
    for c in cs:
        st = str(c.meta.get("status") or "")
        status[st] += 1
        if st != resolved:
            table.setdefault(kind_of(project, c), Counter())[str(c.meta.get("area") or "기타")] += 1
    return {
        "total": len(cs),
        "open": sum(1 for c in cs if c.meta.get("status") != resolved),
        "resolved": status.get(resolved, 0),
        "by_status": dict(status),
        "table": {k: dict(v) for k, v in table.items()},
    }


def status_markdown(project: Project) -> str:
    """Build the table of open debt by kind and topic.

    Args:
        project: The project.

    Returns:
        A Markdown table: one row per kind, one column per topic, plus a total.

    Example:
        >>> status_markdown(project).splitlines()[0]  # doctest: +SKIP
        '| 부채 (열린 것) | 프론트 | 백엔드 | 기타 | 합계 |'
    """
    enums = project.enums
    areas = enums.values("area")
    kinds = enums.values("debt_kind")
    s = stats(project)
    lines = ["| 부채 (열린 것) | " + " | ".join(areas) + " | 합계 |", "|---|" + ":-:|" * (len(areas) + 1)]
    for k in kinds:
        row = s["table"].get(k, {})
        icon = enums["debt_kind"].icon(k) if enums.get("debt_kind") else ""
        cells, total = [str(row.get(a, 0)) for a in areas], str(sum(row.values()))
        lines.append(f"| {icon} {k} | " + " | ".join(cells) + f" | {total} |")
    return "\n".join(lines)


def write_status(project: Project) -> Path:
    """Write the generated debt status page (`📒 부채/부채 현황.md`).

    Args:
        project: The project.

    Returns:
        The page.

    Example:
        >>> write_status(project).name  # doctest: +SKIP
        '부채 현황.md'
    """
    p = project.folder("debt") / project.names.file("debt_status")
    s = stats(project)
    cs = cards(project)
    resolved = project.enums.value("debt_status", "resolved")
    open_cards = [c for c in cs if c.meta.get("status") != resolved]
    open_cards.sort(key=lambda c: (-int(c.meta.get("ask_count") or 0), c.id))
    rows = ["| 카드 | 종류 | 주제 | 상태 | 물은 횟수 | 노트 |", "|---|---|---|---|---|---|"]
    for c in open_cards:
        st = str(c.meta.get("status") or "")
        note = str(c.meta.get("note") or "")
        rows.append(
            f"| {wikilink(project, c.path, c.id + ' ' + c.title, table=True)} | {kind_of(project, c)} | {c.meta.get('area', '')} | "
            f"{status_label(project, st)} | {c.meta.get('ask_count', 0)} | {note.replace('|', chr(92) + '|')} |"
        )
    if len(rows) == 2:
        rows.append("| (열린 부채 없음) | | | | | |")
    open_counts = " · ".join(
        f"{status_label(project, v)} {s['by_status'].get(v, 0)}" for v in project.enums.values("debt_status") if v != resolved
    )
    body = "\n".join(
        [
            "# 📒 부채 현황",
            "",
            f"> ⚙️ 자동 생성 — `lantern debt status` · 기준: {now_minute()}. 손으로 고치지 마세요.",
            "",
            f"> [!abstract] {project.names.marker('glance')}",
            f"> 열린 부채 {s['open']}개 ({open_counts}) · {project.enums.label('debt_status', 'resolved')} {s['resolved']}개",
            "",
            "## 종류별 · 주제별 개수",
            status_markdown(project),
            "",
            "## 열린 카드 (많이 물은 순)",
            *rows,
            "",
        ]
    )
    meta = {
        "id": "DEBT-status",
        "type": "report",
        "status": project.enums.value("current_status", "active"),
        "generated": True,
        "updated": today(),
        "stats": {"open": s["open"], "resolved": s["resolved"], "total": s["total"]},
    }
    write(p, frontmatter.render(meta, body))
    return p
