"""📒 부채 장부 — one card per debt. Counting and status changes are scripted (LE-01 · LE-03)."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from ..core import frontmatter, templating
from ..core.new_id import next_id
from ..core.project import Project, nfc, now_minute, read, safe_name, today, wikilink, write


def norm(term: str) -> str:
    return re.sub(r"[\s\-_.·/]+", "", nfc(term).lower())


@dataclass
class Card:
    path: Path
    meta: dict

    @property
    def id(self) -> str:
        return str(self.meta.get("id", ""))

    @property
    def title(self) -> str:
        stem = nfc(self.path.stem)
        return stem.split(" ", 1)[1] if " " in stem else stem

    @property
    def names(self) -> list[str]:
        return [self.title] + [str(a) for a in frontmatter.as_list(self.meta.get("aliases"))]

    def matches(self, term: str) -> bool:
        t = norm(term)
        return any(norm(n) == t for n in self.names if n)


def cards(project: Project) -> list[Card]:
    folder = project.folder("debt_cards")
    if not folder.exists():
        return []
    return [Card(p, frontmatter.parse(read(p)).meta) for p in sorted(folder.glob("*.md"))]


def kind_of(project: Project, card: Card) -> str:
    return str(card.meta.get("kind") or project.enums.value("debt_kind", "understanding"))


def status_label(project: Project, status: str) -> str:
    """Icon + name of a debt status, from enums.yaml."""
    return project.enums["debt_status"].labelled(status)


def find(project: Project, term: str, kind: str | None = None) -> Card | None:
    """kind: a debt_kind role (understanding · competency · tech), or None for any."""
    want = project.enums.value("debt_kind", kind) if kind else None
    for c in cards(project):
        if want and kind_of(project, c) != want:
            continue
        if c.id.upper() == term.upper() or c.matches(term):
            return c
    return None


# --------------------------------------------------------------------------- known tech (LE-02)


def known_file(project: Project) -> Path:
    return project.folder("debt") / "아는 기술.md"


def known_list(project: Project) -> list[list[str]]:
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
    t = norm(term)
    return any(norm(n) == t for names in known_list(project) for n in names)


def known_add(project: Project, name: str, aliases: list[str] | None = None) -> Path:
    p = known_file(project)
    if not p.exists():
        from ..work.scaffold import create_from_template

        create_from_template(project, "아는 기술", p)
    if is_known(project, name):
        return p
    text = read(p)
    alias = f" ({', '.join(aliases)})" if aliases else ""
    line = f"- {name}{alias} — {today()}"
    marker = "## 목록"
    if marker in text:
        head, tail = text.split(marker, 1)
        tail_lines = tail.split("\n")
        # insert after the last list item of the section (before the next heading / template-only)
        insert_at = 1
        for i, l in enumerate(tail_lines[1:], start=1):
            if l.startswith("## ") or l.startswith("<!--"):
                break
            if l.startswith("- "):
                insert_at = i + 1
        if insert_at == 1:
            insert_at = 2 if len(tail_lines) > 1 and tail_lines[1] == "" else 1
        tail_lines.insert(insert_at, line)
        text = head + marker + "\n".join(tail_lines)
    else:
        text = text.rstrip() + f"\n\n{marker}\n{line}\n"
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
    """이해 부채 (default) — or 기술 부채 recorded by hand (`--kind 기술`). 역량 부채 comes from `promote`."""
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
        "부채 카드",
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
    return wikilink(project, folder / "기획.md", work_id.upper())


def _append_origin(text: str, line: str) -> str:
    marker = "## 어디서 나왔나"
    if marker not in text:
        return text.rstrip() + f"\n\n{marker}\n{line}\n"
    head, tail = text.split(marker, 1)
    parts = tail.split("\n")
    insert_at = len(parts)
    for i, l in enumerate(parts[1:], start=1):
        if l.startswith("## "):
            insert_at = i
            while insert_at > 1 and parts[insert_at - 1] == "":
                insert_at -= 1
            break
    parts.insert(insert_at, line)
    return head + marker + "\n".join(parts)


@dataclass
class AskResult:
    card: Path
    counted: bool
    status: str
    ask_count: int
    reopened: bool


def ask(project: Project, term: str, work: str | None = None, session: str = "", context: str = "") -> AskResult:
    """Count one more ask (LE-01): once per conversation; resolved cards reopen (LE-03)."""
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
    write(card.path, _append_origin(text, origin))
    return AskResult(card.path, True, new_status, count + 1, reopened)


def resolve(project: Project, term: str, note: str | None = None) -> Path:
    card = find(project, term)
    if card is None:
        raise LookupError(f"'{term}' 카드가 없습니다")
    updates: dict = {"status": project.enums.value("debt_status", "resolved"), "resolved": today()}
    if note:
        updates["note"] = note
    write(card.path, frontmatter.set_fields(read(card.path), updates))
    return card.path


# --------------------------------------------------------------------------- 역량 부채 (이해 → 역량)


def promote(project: Project, term: str, name: str | None = None) -> Path:
    """이해 부채가 해결되면 "직접 만들어 볼까?" → 역량 부채 카드 (08 · LE-03)."""
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
        "역량 카드",
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
    write(src.path, _append_origin(read(src.path), f"- {today()} {competency} 부채로 넘김 → {wikilink(project, dest, debt_id)}"))
    return dest


def practice(project: Project, term: str, result: str) -> Path:
    competency = project.enums.value("debt_kind", "competency")
    card = next(
        (c for c in cards(project) if kind_of(project, c) == competency and (c.id.upper() == term.upper() or c.matches(term))), None
    )
    if card is None:
        raise LookupError(f"'{term}' 역량 카드가 없습니다 (lantern debt promote 먼저)")
    text = frontmatter.set_fields(read(card.path), {"status": project.enums.value("debt_status", "practicing")})
    marker = "## 만들어 본 것"
    line = f"- {today()} {result}"
    if marker in text:
        head, tail = text.split(marker, 1)
        parts = tail.split("\n")
        insert_at = len(parts)
        for i, l in enumerate(parts[1:], start=1):
            if l.startswith("## ") or l.startswith("<!--"):
                insert_at = i
                break
        while insert_at > 1 and parts[insert_at - 1].strip() == "":
            insert_at -= 1
        parts.insert(insert_at, line)
        text = head + marker + "\n".join(parts)
    else:
        text = text.rstrip() + f"\n\n{marker}\n{line}\n"
    write(card.path, text)
    return card.path


# --------------------------------------------------------------------------- 부채 현황 (generated)


def stats(project: Project) -> dict:
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
    p = project.folder("debt") / "부채 현황.md"
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
            "> [!abstract] 한눈에 보기",
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
