"""DBML is the source of truth for data.

* `check`       — syntax · duplicates · references
* `render`      — Mermaid ERD + data dictionary into `데이터.md` (generated, never hand-edited)
* `from_sql`    — brownfield: rebuild DBML from SQL migrations
* `diff`        — DBML vs migrations drift (/l-sync)

The parser covers the DBML that data documents use (tables, refs, enums); it is not a full DBML implementation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

ERD_START, ERD_END = "<!-- lantern:erd:start -->", "<!-- lantern:erd:end -->"
DICT_START, DICT_END = "<!-- lantern:dictionary:start -->", "<!-- lantern:dictionary:end -->"


@dataclass
class Column:
    r"""One column of a table.

    Attributes:
        name: Column name.
        type: Column type as written, e.g. "varchar(20)".
        settings: Settings inside `[…]`, e.g. ["pk", "not null"].
        note: The column's note.
        line: The 1-based line it is on (0 when built from SQL).

    Example:
        >>> col = parse("Table users {\n  id int [pk]\n}").tables["users"].columns[0]
        >>> col.name, col.type, col.pk
        ('id', 'int', True)
    """

    name: str
    type: str
    settings: list[str] = field(default_factory=list)
    note: str = ""
    line: int = 0

    @property
    def pk(self) -> bool:
        """Whether the column is the primary key."""
        return any(s.lower() in ("pk", "primary key") for s in self.settings)

    @property
    def unique(self) -> bool:
        """Whether the column is unique."""
        return any(s.lower() == "unique" for s in self.settings)

    @property
    def not_null(self) -> bool:
        """Whether the column is not null."""
        return any(s.lower() == "not null" for s in self.settings)


@dataclass
class Table:
    r"""One table.

    Attributes:
        name: Table name.
        columns: Its columns, in order.
        note: The table's note.
        line: The 1-based line it starts on.
        alias: The `as` alias, if any.

    Example:
        >>> parse("Table users as U {\n  id int\n}").tables["users"].alias
        'U'
    """

    name: str
    columns: list[Column] = field(default_factory=list)
    note: str = ""
    line: int = 0
    alias: str | None = None

    def column(self, name: str) -> Column | None:
        r"""Find a column by name.

        Args:
            name: Column name.

        Returns:
            The column; None when the table has none by that name.

        Example:
            >>> parse("Table users {\n  id int\n}").tables["users"].column("id").type
            'int'
        """
        for c in self.columns:
            if c.name == name:
                return c
        return None


@dataclass
class Ref:
    """One reference between two columns.

    Attributes:
        left: (table, column) on the left.
        op: ">" many-to-one, "<" one-to-many, "-" one-to-one, "<>" many-to-many.
        right: (table, column) on the right.
        line: The 1-based line it is on.

    Example:
        >>> parse("Ref: posts.user_id > users.id").refs[0].op
        '>'
    """

    left: tuple[str, str]
    op: str
    right: tuple[str, str]
    line: int = 0


@dataclass
class Schema:
    r"""A parsed DBML file (or a schema rebuilt from SQL).

    Attributes:
        tables: Table name → table, in file order.
        refs: All references.
        enums: Enum name → values.
        problems: (level, line, message) found while parsing.

    Example:
        >>> list(parse("Table a {\n  id int\n}\nTable b {\n  id int\n}").tables)
        ['a', 'b']
    """

    tables: dict[str, Table] = field(default_factory=dict)
    refs: list[Ref] = field(default_factory=list)
    enums: dict[str, list[str]] = field(default_factory=dict)
    problems: list[tuple[str, int, str]] = field(default_factory=list)  # (level, line, message)


# --------------------------------------------------------------------------- lexing helpers


def _strip_comments(text: str) -> str:
    out: list[str] = []
    i, n = 0, len(text)
    quote: str | None = None
    while i < n:
        if quote:
            if text.startswith(quote, i):
                out.append(quote)
                i += len(quote)
                quote = None
                continue
            if text[i] == "\\" and i + 1 < n:
                out.append(text[i : i + 2])
                i += 2
                continue
            out.append(text[i])
            i += 1
            continue
        if text.startswith("'''", i):
            quote = "'''"
            out.append(quote)
            i += 3
            continue
        if text[i] in "'\"`":
            quote = text[i]
            out.append(quote)
            i += 1
            continue
        if text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j == -1 else j
            continue
        if text.startswith("/*", i):
            j = text.find("*/", i + 2)
            seg = text[i : (n if j == -1 else j + 2)]
            out.append("\n" * seg.count("\n"))
            i = n if j == -1 else j + 2
            continue
        out.append(text[i])
        i += 1
    return "".join(out)


def _match_brace(text: str, start: int) -> int:
    """Index of the `}` matching text[start] == '{' (strings aware), or -1."""
    depth, i, n = 0, start, len(text)
    quote: str | None = None
    while i < n:
        c = text[i]
        if quote:
            if text.startswith(quote, i):
                i += len(quote)
                quote = None
                continue
            i += 1
            continue
        if text.startswith("'''", i):
            quote = "'''"
            i += 3
            continue
        if c in "'\"`":
            quote = c
            i += 1
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _split_top(s: str, sep: str = ",") -> list[str]:
    parts, depth, cur, quote = [], 0, [], None
    for c in s:
        if quote:
            cur.append(c)
            if c == quote:
                quote = None
            continue
        if c in "'\"`":
            quote = c
        elif c in "([":
            depth += 1
        elif c in ")]":
            depth -= 1
        if c == sep and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
            continue
        cur.append(c)
    if "".join(cur).strip():
        parts.append("".join(cur).strip())
    return parts


def _unquote(s: str) -> str:
    s = s.strip()
    if s.startswith("'''") and s.endswith("'''") and len(s) >= 6:
        return s[3:-3].strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"`":
        return s[1:-1]
    return s


def parse(text: str) -> Schema:
    r"""Parse DBML text.

    Never raises: syntax problems are collected in Schema.problems instead.

    Args:
        text: DBML text.

    Returns:
        The schema.

    Example:
        >>> schema = parse("Table users {\n  id int [pk]\n  name varchar [not null]\n}")
        >>> [c.name for c in schema.tables["users"].columns], schema.problems
        (['id', 'name'], [])
        >>> parse("Table users {").problems[0][2]
        '중괄호 { } 짝이 맞지 않습니다'
    """
    schema = Schema()
    src = _strip_comments(text)
    if src.count("{") != src.count("}"):
        schema.problems.append(("error", 0, "중괄호 { } 짝이 맞지 않습니다"))
    pos, n = 0, len(src)
    while pos < n:
        m = re.compile(r"\S").search(src, pos)
        if not m:
            break
        start = m.start()
        line = src.count("\n", 0, start) + 1
        rest = src[start:]
        kw = re.match(r"(?i)(Table|Ref|Enum|Project|TableGroup|Note|Records|TablePartial)\b", rest)
        if not kw:
            eol = src.find("\n", start)
            bad = src[start : (n if eol == -1 else eol)].strip()
            schema.problems.append(("error", line, f"알 수 없는 문장: {bad[:60]}"))
            pos = n if eol == -1 else eol + 1
            continue
        keyword = kw.group(1).lower()
        if keyword == "ref":
            # Ref name: a.b > c.d   |   Ref name { a.b > c.d }
            brace = src.find("{", start)
            eol = src.find("\n", start)
            eol = n if eol == -1 else eol
            if brace != -1 and brace < eol:
                end = _match_brace(src, brace)
                if end == -1:
                    break
                for raw in src[brace + 1 : end].split("\n"):
                    if raw.strip():
                        _parse_ref(raw.strip(), schema, line)
                pos = end + 1
            else:
                body = src[start:eol]
                body = body.split(":", 1)[1] if ":" in body else ""
                _parse_ref(body.strip(), schema, line)
                pos = eol + 1
            continue
        brace = src.find("{", start)
        if brace == -1:
            schema.problems.append(("error", line, f"{kw.group(1)} 블록에 {{ 가 없습니다"))
            break
        end = _match_brace(src, brace)
        if end == -1:
            schema.problems.append(("error", line, f"{kw.group(1)} 블록이 닫히지 않았습니다"))
            break
        header = src[start + len(kw.group(0)) : brace].strip()
        body = src[brace + 1 : end]
        body_line = src.count("\n", 0, brace + 1) + 1
        if keyword == "table":
            _parse_table(header, body, body_line, line, schema)
        elif keyword == "enum":
            name = _unquote(header.split("[")[0].strip())
            vals = [_unquote(v.strip().split("[")[0].strip()) for v in body.split("\n") if v.strip()]
            schema.enums[name] = vals
        pos = end + 1
    return schema


def _parse_ref(expr: str, schema: Schema, line: int) -> None:
    expr = expr.split("[")[0].strip()
    m = re.match(r"^([\w.\"]+)\s*(<>|>|<|-)\s*([\w.\"]+)$", expr)
    if not m:
        if expr:
            schema.problems.append(("error", line, f"Ref 형식이 올바르지 않습니다: {expr}"))
        return
    schema.refs.append(Ref(_split_col(m.group(1)), m.group(2), _split_col(m.group(3)), line))


def _split_col(s: str) -> tuple[str, str]:
    s = s.replace('"', "")
    if "." not in s:
        return (s, "")
    table, col = s.rsplit(".", 1)
    return (table, col)


def _parse_table(header: str, body: str, body_line: int, line: int, schema: Schema) -> None:
    head = header.split("[")[0].strip()
    alias = None
    am = re.match(r"^(.*?)\s+as\s+(\w+)$", head, re.I)
    if am:
        head, alias = am.group(1).strip(), am.group(2)
    name = _unquote(head)
    if not name:
        schema.problems.append(("error", line, "테이블 이름이 없습니다"))
        return
    table = Table(name=name, line=line, alias=alias)
    if name in schema.tables:
        schema.problems.append(("error", line, f"테이블 '{name}'이 두 번 정의되었습니다"))
    schema.tables[name] = table
    lines = body.split("\n")
    i = 0
    while i < len(lines):
        raw = lines[i].strip()
        ln = body_line + i
        i += 1
        if not raw:
            continue
        low = raw.lower()
        if low.startswith("indexes") or low.startswith("note") and raw.rstrip().endswith("{"):
            # skip nested block
            depth = raw.count("{") - raw.count("}")
            while depth > 0 and i < len(lines):
                depth += lines[i].count("{") - lines[i].count("}")
                i += 1
            continue
        if re.match(r"(?i)^note\s*:", raw):
            table.note = _unquote(raw.split(":", 1)[1].strip())
            continue
        settings: list[str] = []
        sm = re.search(r"\[(.*)\]\s*$", raw)
        core = raw
        if sm:
            settings = _split_top(sm.group(1))
            core = raw[: sm.start()].strip()
        cm = re.match(r'^("[^"]+"|`[^`]+`|[\w]+)\s*(.*)$', core)
        if not cm:
            schema.problems.append(("error", ln, f"{name}: 컬럼을 읽지 못했습니다: {raw[:60]}"))
            continue
        cname, ctype = _unquote(cm.group(1)), _unquote(cm.group(2).strip())
        if not ctype:
            schema.problems.append(("error", ln, f"{name}.{cname}: 타입이 없습니다"))
        if table.column(cname):
            schema.problems.append(("error", ln, f"{name}.{cname}: 컬럼이 두 번 정의되었습니다"))
        note = ""
        clean_settings: list[str] = []
        for s in settings:
            sl = s.lower()
            if sl.startswith("note:"):
                note = _unquote(s.split(":", 1)[1].strip())
            elif sl.startswith("ref:"):
                rm = re.match(r"(?i)ref:\s*(<>|>|<|-)\s*([\w.\"]+)", s)
                if rm:
                    schema.refs.append(Ref((name, cname), rm.group(1), _split_col(rm.group(2)), ln))
                else:
                    schema.problems.append(("error", ln, f"{name}.{cname}: ref 형식이 올바르지 않습니다"))
            else:
                clean_settings.append(s.strip())
        table.columns.append(Column(name=cname, type=ctype, settings=clean_settings, note=note, line=ln))
    if not table.columns:
        schema.problems.append(("warn", line, f"테이블 '{name}'에 컬럼이 없습니다"))


def check(schema: Schema) -> list[tuple[str, int, str]]:
    r"""Check a schema: parse problems, references to missing tables or columns, tables without a primary key.

    Args:
        schema: A parsed schema.

    Returns:
        (level, line, message) per problem; level is "error" or "info".

    Example:
        >>> check(parse("Table posts {\n  id int [pk]\n  user_id int\n}\nRef: posts.user_id > users.id"))
        [('error', 5, "Ref: 테이블 'users'이 없습니다")]
    """
    problems = list(schema.problems)
    alias = {t.alias: t.name for t in schema.tables.values() if t.alias}
    for ref in schema.refs:
        for side in (ref.left, ref.right):
            tname = alias.get(side[0], side[0])
            table = schema.tables.get(tname)
            if table is None:
                problems.append(("error", ref.line, f"Ref: 테이블 '{side[0]}'이 없습니다"))
            elif side[1] and table.column(side[1]) is None:
                problems.append(("error", ref.line, f"Ref: '{side[0]}.{side[1]}' 컬럼이 없습니다"))
    for t in schema.tables.values():
        if t.columns and not any(c.pk for c in t.columns):
            problems.append(("info", t.line, f"테이블 '{t.name}'에 기본 키(pk)가 없습니다"))
    return problems


# --------------------------------------------------------------------------- render


def _ent(name: str) -> str:
    return re.sub(r"[^\w-]", "_", name)


def _mtype(t: str) -> str:
    t = re.sub(r"\s+", "_", t.strip()) or "unknown"
    t = re.sub(r"[^\w()\[\]-]", "_", t)  # Mermaid types: no commas or spaces
    if not re.match(r"[A-Za-z]", t):
        t = "t_" + t
    return t


REL = {">": "}o--||", "<": "||--o{", "-": "||--||", "<>": "}o--o{"}


def to_mermaid(schema: Schema) -> str:
    r"""Draw a schema as a Mermaid ER diagram (in a code fence).

    Args:
        schema: A parsed schema.

    Returns:
        The Mermaid block, with PK · FK · UK marks and column notes.

    Example:
        >>> print(to_mermaid(parse("Table users {\n  id int [pk]\n}")))
        ```mermaid
        erDiagram
          users {
            int id PK
          }
        ```
    """
    lines = ["```mermaid", "erDiagram"]
    fks = {(r.left[0], r.left[1]) for r in schema.refs if r.op in (">", "-")} | {
        (r.right[0], r.right[1]) for r in schema.refs if r.op == "<"
    }
    for t in schema.tables.values():
        lines.append(f"  {_ent(t.name)} {{")
        for c in t.columns:
            keys = []
            if c.pk:
                keys.append("PK")
            if (t.name, c.name) in fks:
                keys.append("FK")
            if c.unique and not c.pk:
                keys.append("UK")
            key = " " + ", ".join(keys) if keys else ""
            note = f' "{c.note.replace(chr(34), chr(39))}"' if c.note else ""
            lines.append(f"    {_mtype(c.type)} {_ent(c.name)}{key}{note}")
        lines.append("  }")
    for r in schema.refs:
        label = r.left[1] or "ref"
        lines.append(f'  {_ent(r.left[0])} {REL[r.op]} {_ent(r.right[0])} : "{label}"')
    lines.append("```")
    return "\n".join(lines)


def to_dictionary(schema: Schema) -> str:
    r"""Write a schema as a data-dictionary table.

    A column note "뜻 예: 값" is split into meaning and example.

    Args:
        schema: A parsed schema.

    Returns:
        A Markdown table with one row per column.

    Example:
        >>> print(to_dictionary(parse("Table users {\n  id int [pk, note: '번호 예: 1']\n}")).splitlines()[-1])
        | users | id | `int` | pk | 번호 | 1 |
    """
    rows = ["| 테이블 | 컬럼 | 타입 | 제약 | 뜻 | 예시 |", "|---|---|---|---|---|---|"]
    for t in schema.tables.values():
        for c in t.columns:
            meaning, example = c.note, ""
            m = re.split(r"\s*(?:예:|예시:|e\.g\.)\s*", c.note, maxsplit=1)
            if len(m) == 2:
                meaning, example = m[0].strip().rstrip(".,·"), m[1].strip()
            cons = ", ".join(s for s in c.settings if not s.lower().startswith("default")) or ""
            rows.append(f"| {t.name} | {c.name} | `{c.type}` | {cons} | {meaning or '—'} | {example} |")
    if len(rows) == 2:
        rows.append("| (아직 테이블 없음) | | | | | |")
    return "\n".join(rows)


def _replace_block(text: str, start: str, end: str, content: str) -> str:
    s, e = text.find(start), text.find(end)
    if s == -1 or e == -1 or e < s:
        return text.rstrip() + f"\n\n{start}\n{content}\n{end}\n"
    return text[: s + len(start)] + "\n" + content + "\n" + text[e:]


def render_into(doc_text: str, schema: Schema, source_note: str) -> str:
    r"""Put the ERD and the data dictionary into a data document, between their markers.

    Missing marker pairs are added at the end; everything outside the markers stays.

    Args:
        doc_text: The data document.
        schema: The schema to draw.
        source_note: Where the schema came from, shown in the "generated" note.

    Returns:
        The updated document.

    Example:
        >>> text = render_into("# 데이터\n", parse("Table a {\n  id int\n}"), "schema.dbml")
        >>> ERD_START in text and DICT_END in text
        True
    """
    erd = f"> ⚙️ 자동 생성 — 원본: {source_note}. 손으로 고치지 마세요 (`lantern dbml render`).\n\n" + to_mermaid(schema)
    doc_text = _replace_block(doc_text, ERD_START, ERD_END, erd)
    return _replace_block(doc_text, DICT_START, DICT_END, to_dictionary(schema))


def to_dbml(schema: Schema, header: str = "") -> str:
    r"""Write a schema as DBML text.

    Args:
        schema: The schema (often rebuilt from SQL).
        header: A first line to put on top, e.g. a comment.

    Returns:
        The DBML text.

    Example:
        >>> print(to_dbml(parse("Table users {\n  id int [pk]\n}")), end="")
        Table users {
          id int [pk]
        }
    """
    out: list[str] = [header] if header else []
    for t in schema.tables.values():
        out.append(f"Table {t.name} {{")
        for c in t.columns:
            settings = list(c.settings)
            if c.note:
                settings.append(f"note: '{c.note}'")
            s = f" [{', '.join(settings)}]" if settings else ""
            out.append(f"  {c.name} {c.type}{s}")
        out.append("}\n")
    for r in schema.refs:
        out.append(f"Ref: {r.left[0]}.{r.left[1]} {r.op} {r.right[0]}.{r.right[1]}")
    return "\n".join(out).rstrip() + "\n"


# --------------------------------------------------------------------------- SQL → DBML


def _match_paren(s: str, start: int) -> int:
    depth = 0
    quote = None
    for i in range(start, len(s)):
        c = s[i]
        if quote:
            if c == quote:
                quote = None
            continue
        if c in "'\"`":
            quote = c
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i
    return -1


_IDENT = r'(?:"[^"]+"|`[^`]+`|\[[^\]]+\]|[\w.]+)'


def _ident(s: str) -> str:
    s = s.strip().strip('"`[]')
    if "." in s:
        s = s.split(".")[-1].strip('"`[]')
    return s


def _sql_statements(sql: str) -> list[str]:
    sql = re.sub(r"--[^\n]*", "", sql)
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.S)
    return [s.strip() for s in _split_top(sql, ";") if s.strip()]


def from_sql(files: list[Path]) -> Schema:
    """Rebuild a schema from SQL migration files, applied in the given order.

    CREATE TABLE, ALTER TABLE (add · drop · rename column), DROP TABLE and foreign keys are understood.

    Args:
        files: SQL files, oldest first.

    Returns:
        The schema the migrations end with.

    Example:
        >>> list(from_sql(sorted(Path("migrations").glob("*.sql"))).tables)  # doctest: +SKIP
        ['users', 'posts']
    """
    schema = Schema()
    for f in files:
        for stmt in _sql_statements(f.read_text(encoding="utf-8", errors="replace")):
            _apply_sql(stmt, schema)
    return schema


def _col_from_sql(table: str, definition: str, schema: Schema) -> Column | None:
    m = re.match(rf"^({_IDENT})\s+(.*)$", definition.strip(), re.S)
    if not m:
        return None
    name = _ident(m.group(1))
    rest = m.group(2).strip()
    tm = re.match(
        r"^([\w ]+?(?:\([^)]*\))?(?:\[\])?)"
        r"(?=\s+(?:NOT|NULL|PRIMARY|UNIQUE|DEFAULT|REFERENCES|CHECK|CONSTRAINT|GENERATED|COLLATE|AUTO_INCREMENT|AUTOINCREMENT)\b|\s*$)",
        rest,
        re.I,
    )
    ctype = (tm.group(1) if tm else rest.split()[0]).strip().lower()
    settings: list[str] = []
    up = rest.upper()
    if "PRIMARY KEY" in up:
        settings.append("pk")
    if "NOT NULL" in up and "PRIMARY KEY" not in up:
        settings.append("not null")
    if re.search(r"\bUNIQUE\b", up):
        settings.append("unique")
    if "AUTO_INCREMENT" in up or "AUTOINCREMENT" in up or ctype in ("serial", "bigserial"):
        settings.append("increment")
    dm = re.search(r"(?i)\bDEFAULT\s+('(?:[^']|'')*'|\S+)", rest)
    if dm:
        val = dm.group(1)
        settings.append(f"default: {val}" if val.startswith("'") else f"default: `{val}`")
    rm = re.search(rf"(?i)\bREFERENCES\s+({_IDENT})\s*\(\s*({_IDENT})\s*\)", rest)
    if rm:
        schema.refs.append(Ref((table, name), ">", (_ident(rm.group(1)), _ident(rm.group(2)))))
    return Column(name=name, type=ctype, settings=settings)


def _apply_sql(stmt: str, schema: Schema) -> None:
    m = re.match(rf"(?is)^CREATE\s+(?:TEMP(?:ORARY)?\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?({_IDENT})\s*\(", stmt)
    if m:
        name = _ident(m.group(1))
        open_i = m.end() - 1
        close_i = _match_paren(stmt, open_i)
        body = stmt[open_i + 1 : close_i]
        table = Table(name=name)
        schema.tables[name] = table
        for part in _split_top(body):
            up = part.upper().lstrip()
            if up.startswith(("PRIMARY KEY", "CONSTRAINT", "FOREIGN KEY", "UNIQUE", "CHECK", "KEY ", "INDEX ")):
                pk = re.search(r"(?i)PRIMARY\s+KEY\s*\(([^)]*)\)", part)
                if pk:
                    for col in pk.group(1).split(","):
                        c = table.column(_ident(col))
                        if c and "pk" not in c.settings:
                            c.settings.insert(0, "pk")
                fk = re.search(rf"(?i)FOREIGN\s+KEY\s*\(\s*({_IDENT})\s*\)\s*REFERENCES\s+({_IDENT})\s*\(\s*({_IDENT})\s*\)", part)
                if fk:
                    schema.refs.append(Ref((name, _ident(fk.group(1))), ">", (_ident(fk.group(2)), _ident(fk.group(3)))))
                continue
            col = _col_from_sql(name, part, schema)
            if col:
                table.columns.append(col)
        return
    m = re.match(rf"(?is)^ALTER\s+TABLE\s+(?:IF\s+EXISTS\s+)?(?:ONLY\s+)?({_IDENT})\s+(.*)$", stmt)
    if m:
        name = _ident(m.group(1))
        table = schema.tables.setdefault(name, Table(name=name))
        for action in _split_top(m.group(2)):
            a = action.strip()
            am = re.match(r"(?is)^ADD\s+(?:COLUMN\s+)?(?:IF\s+NOT\s+EXISTS\s+)?(.*)$", a)
            if am and not re.match(r"(?i)^(CONSTRAINT|PRIMARY|FOREIGN|UNIQUE|CHECK)\b", am.group(1)):
                col = _col_from_sql(name, am.group(1), schema)
                if col:
                    table.columns = [c for c in table.columns if c.name != col.name] + [col]
                continue
            if am:
                fk = re.search(rf"(?i)FOREIGN\s+KEY\s*\(\s*({_IDENT})\s*\)\s*REFERENCES\s+({_IDENT})\s*\(\s*({_IDENT})\s*\)", a)
                if fk:
                    schema.refs.append(Ref((name, _ident(fk.group(1))), ">", (_ident(fk.group(2)), _ident(fk.group(3)))))
                continue
            dm = re.match(rf"(?is)^DROP\s+(?:COLUMN\s+)?(?:IF\s+EXISTS\s+)?({_IDENT})", a)
            if dm:
                col = _ident(dm.group(1))
                table.columns = [c for c in table.columns if c.name != col]
                schema.refs = [r for r in schema.refs if r.left != (name, col) and r.right != (name, col)]
                continue
            rn = re.match(rf"(?is)^RENAME\s+COLUMN\s+({_IDENT})\s+TO\s+({_IDENT})", a)
            if rn:
                c = table.column(_ident(rn.group(1)))
                if c:
                    c.name = _ident(rn.group(2))
                continue
            rt = re.match(rf"(?is)^RENAME\s+TO\s+({_IDENT})", a)
            if rt:
                new = _ident(rt.group(1))
                schema.tables.pop(name, None)
                table.name = new
                schema.tables[new] = table
                for r in schema.refs:
                    if r.left[0] == name:
                        r.left = (new, r.left[1])
                    if r.right[0] == name:
                        r.right = (new, r.right[1])
                continue
            at = re.match(rf"(?is)^ALTER\s+(?:COLUMN\s+)?({_IDENT})\s+(?:SET\s+DATA\s+)?TYPE\s+(.+)$", a)
            if at:
                c = table.column(_ident(at.group(1)))
                if c:
                    c.type = at.group(2).strip().lower()
        return
    m = re.match(rf"(?is)^DROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?({_IDENT})", stmt)
    if m:
        name = _ident(m.group(1))
        schema.tables.pop(name, None)
        schema.refs = [r for r in schema.refs if r.left[0] != name and r.right[0] != name]


def _norm_type(t: str) -> str:
    t = t.lower().strip()
    t = re.sub(r"\s+", " ", t)
    aliases = {
        "integer": "int",
        "int4": "int",
        "int8": "bigint",
        "bool": "boolean",
        "character varying": "varchar",
        "timestamptz": "timestamp with time zone",
        "serial": "int",
        "bigserial": "bigint",
    }
    base = re.sub(r"\(.*\)", "", t).strip()
    return aliases.get(base, base)


def diff(doc_schema: Schema, real: Schema) -> list[str]:
    r"""List the differences between the documented schema and the real one (migrations are the reference).

    Args:
        doc_schema: The schema in the DBML document.
        real: The schema rebuilt from migrations.

    Returns:
        One line per difference: ✚ missing from DBML, ✎ type differs, ✖ only in DBML.

    Example:
        >>> diff(parse("Table users {\n  id int\n}"), parse("Table users {\n  id bigint\n}"))
        ["✎ 컬럼 'users.id' 타입: DBML int ≠ 마이그레이션 bigint"]
    """
    out: list[str] = []
    for name, t in real.tables.items():
        d = doc_schema.tables.get(name)
        if d is None:
            out.append(f"✚ 테이블 '{name}'이 마이그레이션에는 있는데 DBML에 없습니다")
            continue
        for c in t.columns:
            dc = d.column(c.name)
            if dc is None:
                out.append(f"✚ 컬럼 '{name}.{c.name}'이 DBML에 없습니다")
            elif _norm_type(dc.type) != _norm_type(c.type):
                out.append(f"✎ 컬럼 '{name}.{c.name}' 타입: DBML {dc.type} ≠ 마이그레이션 {c.type}")
        for dc in d.columns:
            if t.column(dc.name) is None:
                out.append(f"✖ 컬럼 '{name}.{dc.name}'이 DBML에만 있습니다")
    for name in doc_schema.tables:
        if name not in real.tables:
            out.append(f"✖ 테이블 '{name}'이 DBML에만 있습니다")
    return out
