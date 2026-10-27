"""`lantern template …` — the scripted half of /l-template.

list · lint · level · bump · outdated · diff · new · usage · migrate
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..core import enums as enums_mod
from ..core import frontmatter, state, templating
from ..core.project import Project, git, nfc, read, today, write
from ..work.scaffold import base_template_names, base_template_text, base_values, condition_context, template_version
from .check_docs import Finding, _active_doc, semver, version_gap

SYSTEM_KEYS = {
    "id",
    "name",
    "today",
    "work_id",
    "links",
    "project",
    "kind",
    "status",
    "variant",
    "owner",
    "aliases",
    "area",
    "auto",
    "raw",
    "note",
    "work",
    "session",
    "work_text",
    "profile_table",
    "members_table",
    "legacy_rows",
    "base",
}
MIGRATE_BIN = "📦 옮기지 못한 내용"
_SYS_RE = re.compile(r"\$\{([a-z_]+(?:\.[a-z_]+)*)\}")


def template_path(project: Project, name: str) -> Path:
    p = project.templates_dir / f"{name}.md"
    if p.exists():
        return p
    for cand in project.templates_dir.glob("*.md"):
        if nfc(cand.stem) == nfc(name):
            return cand
    raise FileNotFoundError(f"양식 '{name}'이 docs/0. 템플릿에 없습니다 (lantern template list)")


def names(project: Project) -> list[str]:
    if not project.templates_dir.exists():
        return []
    return sorted(nfc(p.stem) for p in project.templates_dir.glob("*.md"))


# --------------------------------------------------------------------------- list · diff


def list_rows(project: Project) -> list[str]:
    st = state.load(project)
    base_names = set(base_template_names())
    rows = []
    for name in names(project):
        text = read(template_path(project, name))
        ver = template_version(text)
        info = st["templates"].get(name) or {}
        modified = info.get("sha256") and state.sha256_text(text) != info.get("sha256")
        base = ""
        if name in base_names:
            bv = template_version(base_template_text(name))
            if version_gap(info.get("based_on") or ver, bv):
                base = f" · 기본 양식 {bv} 나옴"
        origin = "기본 양식" if name in base_names else "직접 만든 양식"
        rows.append(f"{name}  v{ver}  ({origin}{', 다듬음' if modified else ''}{base})")
    return rows


def diff_base(project: Project, name: str) -> str:
    mine = read(template_path(project, name)).splitlines(keepends=True)
    base = base_template_text(name).splitlines(keepends=True)
    out = "".join(difflib.unified_diff(base, mine, fromfile=f"기본 양식/{name}.md", tofile=f"0. 템플릿/{name}.md"))
    return out or "기본 양식과 같습니다"


# --------------------------------------------------------------------------- lint


def lint(project: Project, name: str) -> list[Finding]:
    p = template_path(project, name)
    rel = project.rel(p)
    text = read(p)
    out: list[Finding] = []
    doc = frontmatter.parse(text)
    if doc.error or not doc.has_frontmatter:
        return [Finding("error", rel, "frontmatter", doc.error or "frontmatter가 없습니다")]
    meta = doc.meta
    for key in ("id", "type", "status", "created", "updated", "links", "template", "template_version"):
        if key not in meta:
            out.append(Finding("error", rel, "common-fields", f"공통 frontmatter '{key}'가 없습니다"))
    if meta.get("template") and nfc(str(meta["template"])) != nfc(p.stem):
        out.append(Finding("warn", rel, "template-name", f"template: '{meta['template']}'가 파일 이름 '{p.stem}'과 다릅니다"))
    if not re.match(r"^\d+\.\d+\.\d+$", frontmatter.as_str(meta.get("template_version"))):
        out.append(Finding("error", rel, "version", "template_version은 1.2.0 형식이어야 합니다"))
    if "based_on" not in meta:
        out.append(Finding("info", rel, "based-on", "based_on이 없습니다 (직접 만든 양식이면 template_version과 같게)"))
    enums = enums_mod.load(project.enums_file)
    if meta.get("type") and str(meta["type"]) not in enums.values("doc_type"):
        out.append(Finding("error", rel, "enum", f"type '{meta['type']}'가 enums.yaml doc_type에 없습니다"))
    for pname, _req, line in templating.placeholders(text):
        base = templating.field_base_name(pname).lower()
        if base in templating.FORBIDDEN_FIELD_NAMES:
            out.append(Finding("error", rel, "forbidden-name", f"칸 이름 '{pname}'은 쓸 수 없습니다 (date · time · title 금지)", line))
        if "|" in pname:
            out.append(Finding("error", rel, "pipe", "칸 이름에 '|'가 있습니다 — 필수는 '(필수)'로 표시", line))
    enum_keys = project.enums.context()  # ${work_status.plan} · ${debt_status.new.label} …
    for m in _SYS_RE.finditer(text):
        if m.group(1) not in SYSTEM_KEYS and m.group(1) not in enum_keys:
            out.append(Finding("warn", rel, "system-key", f"스크립트가 모르는 값 ${{{m.group(1)}}}"))
    if not re.search(r"^>\s*\[!abstract\][^\n]*한눈에 보기\s*\n>\s*\S", text, re.M):
        out.append(Finding("warn", rel, "glance", "맨 위 '> [!abstract] 한눈에 보기' 칸이 없습니다"))
    if templating.TEMPLATE_ONLY not in text or "## 변경 기록" not in text:
        out.append(Finding("warn", rel, "changelog", f"맨 아래 {templating.TEMPLATE_ONLY} + '## 변경 기록'이 없습니다"))
    else:
        rows = re.findall(r"^\|\s*(\d+\.\d+\.\d+)\s*\|", text.split(templating.TEMPLATE_ONLY, 1)[1], re.M)
        if rows and rows[-1] != frontmatter.as_str(meta.get("template_version")):
            out.append(
                Finding(
                    "warn", rel, "changelog-version", f"변경 기록 마지막 버전 {rows[-1]} ≠ template_version {meta.get('template_version')}"
                )
            )
    if "> [!guide]" not in text:
        out.append(Finding("info", rel, "guide", "작성 안내 '> [!guide]'가 하나도 없습니다"))
    return out


# --------------------------------------------------------------------------- level · bump


def _norm_heading(h: str) -> str:
    h = re.sub(r"[^\w가-힣]+", "", nfc(h)).lower()
    return h


def structure(text: str) -> tuple[list[str], list[str]]:
    body = templating.strip_template_only(text)
    heads = [l[3:].strip() for l in body.split("\n") if l.startswith("## ")]
    fields = [templating.field_base_name(n) for n, _, _ in templating.placeholders(body)]
    return heads, list(dict.fromkeys(fields))


def change_level(old: str, new: str) -> str | None:
    """TE-02: patch = guides only · minor = fields added · major = fields removed/renamed."""
    if templating.strip_template_only(old) == templating.strip_template_only(new):
        return None
    oh, of = structure(old)
    nh, nf = structure(new)
    removed = (set(of) - set(nf)) | (set(oh) - set(nh))
    added = (set(nf) - set(of)) | (set(nh) - set(oh))
    old_meta = set(frontmatter.parse(old).meta) - {"updated", "template_version"}
    new_meta = set(frontmatter.parse(new).meta) - {"updated", "template_version"}
    removed |= {f"frontmatter {k}" for k in old_meta - new_meta}
    added |= {f"frontmatter {k}" for k in new_meta - old_meta}
    if removed:
        return "major"
    if added:
        return "minor"
    return "patch"


def committed_text(project: Project, path: Path, rev: str = "HEAD") -> str | None:
    cwd = project.docs_git_cwd()
    try:
        rel = nfc(str(path.resolve().relative_to(cwd.resolve())))
    except ValueError:
        return None
    r = git(["show", f"{rev}:{rel}"], cwd)
    return r.stdout if r.returncode == 0 else None


def level(project: Project, name: str, rev: str = "HEAD") -> tuple[str | None, str]:
    p = template_path(project, name)
    old = committed_text(project, p, rev)
    source = f"git {rev}"
    if old is None:
        if name in base_template_names():
            old, source = base_template_text(name), "기본 양식"
        else:
            return None, "비교할 이전 버전이 없습니다 (커밋된 적 없음)"
    return change_level(old, read(p)), source


def bump_version(ver: str, lvl: str) -> str:
    a, b, c = semver(ver)
    if lvl == "major":
        return f"{a + 1}.0.0"
    if lvl == "minor":
        return f"{a}.{b + 1}.0"
    return f"{a}.{b}.{c + 1}"


def bump(project: Project, name: str, lvl: str, note: str) -> str:
    p = template_path(project, name)
    text = read(p)
    if lvl == "auto":
        detected, _ = level(project, name)
        if detected is None:
            raise ValueError("바뀐 내용이 없습니다 — 버전을 올리지 않습니다")
        lvl = detected
    if lvl not in ("patch", "minor", "major"):
        raise ValueError("level은 patch · minor · major · auto 중 하나")
    new_ver = bump_version(template_version(text), lvl)
    text = frontmatter.set_fields(text, {"template_version": new_ver}, touch=False)
    row = f"| {new_ver} | {today()} | {note} |"
    if templating.TEMPLATE_ONLY in text and "## 변경 기록" in text:
        text = text.rstrip("\n") + "\n" + row + "\n"
    else:
        text = (
            text.rstrip("\n") + f"\n\n{templating.TEMPLATE_ONLY}\n## 변경 기록\n| 버전 | 날짜 | 무엇이 바뀌었나 |\n|---|---|---|\n{row}\n"
        )
    write(p, text)
    return f"{name}: {lvl} → v{new_ver}"


# --------------------------------------------------------------------------- outdated · usage


@dataclass
class Outdated:
    path: Path
    template: str
    have: str
    current: str
    gap: str
    active: bool


def outdated(project: Project, name: str | None = None, include_inactive: bool = False) -> list[Outdated]:
    versions = {n: template_version(read(template_path(project, n))) for n in names(project)}
    out: list[Outdated] = []
    for p in project.iter_docs():
        meta = frontmatter.parse(read(p)).meta
        t = nfc(str(meta.get("template") or ""))
        if not t or t not in versions or (name and t != nfc(name)):
            continue
        gap = version_gap(meta.get("template_version"), versions[t])
        if not gap:
            continue
        active = _active_doc(project, p, meta)
        if active or include_inactive:
            out.append(Outdated(p, t, frontmatter.as_str(meta.get("template_version")), versions[t], gap, active))
    return out


def usage(project: Project, name: str) -> list[str]:
    tmpl = read(template_path(project, name))
    _, fields = structure(tmpl)
    docs = [p for p in project.iter_docs() if nfc(str(frontmatter.parse(read(p)).meta.get("template") or "")) == nfc(name)]
    if not docs:
        return [f"'{name}' 양식으로 만든 문서가 아직 없습니다"]
    rows = [f"'{name}' 양식 문서 {len(docs)}개 — 칸마다 아직 비어 있는 문서 수:"]
    for f in fields:
        blank = sum(1 for p in docs if re.search(r"\{\{\s*" + re.escape(f) + r"(\s*\(필수\))?\s*\}\}", read(p)))
        mark = "  ← 늘 비어 있음 (지우거나 안내를 고칠 후보)" if blank == len(docs) and len(docs) >= 2 else ""
        rows.append(f"  {blank}/{len(docs)}  {{{{{f}}}}}{mark}")
    return rows


# --------------------------------------------------------------------------- new (시안 → 양식)


def skeleton_from(project: Project, name: str, source: Path) -> str:
    """시안 문서 → 빈칸 양식 뼈대: 제목 · 섹션 · 표 머리는 남기고 내용은 {{칸}}으로."""
    body = frontmatter.parse(read(source)).body
    out: list[str] = ["# ${name}", "", "> [!abstract] 한눈에 보기", "> {{한눈에 보기 (필수)}}"]
    in_fence = False
    current: str | None = None
    filled = False  # the current section already got its blank
    table_state = ""  # "" | "header" | "body"
    for line in body.split("\n"):
        s = line.strip()
        if s.startswith("```"):
            in_fence = not in_fence
            out.append(line)  # keep the fence (mermaid · dbml spot), drop its content
            continue
        if in_fence:
            continue
        if s.startswith("# "):
            continue  # the title becomes ${name}
        m = re.match(r"^(#{2,4})\s+(.+)$", s)
        if m:
            current = re.sub(r"[{}|]", "", m.group(2)).strip()
            out += ["", f"{m.group(1)} {current}", f"> [!guide] 🟦 원본 칸 · '{current}'에 무엇을 쓰는지 한 줄 안내", ""]
            filled, table_state = False, ""
            continue
        if s.startswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if table_state == "":
                out.append("| " + " | ".join(re.sub(r"[{}]", "", c) for c in cells) + " |")
                table_state = "header"
            elif table_state == "header" and re.match(r"^\|[\s\-:|]+\|$", s):
                out.append(line)
            elif table_state == "header":
                out.append("| " + " | ".join("{{" + f"{current or '값'} {i + 1}" + "}}" for i in range(len(cells))) + " |")
                table_state = "body"
            continue
        table_state = ""
        if s and current and not filled and not s.startswith(">"):
            out.append(("- " if s.startswith(("- ", "* ", "1. ")) else "") + "{{" + current + "}}")
            filled = True
    meta = (
        "---\nid: ${id}\ntype: current\nstatus: 사용\ncreated: ${today}\nupdated: ${today}\nlinks: []\n"
        f"template: {name}\ntemplate_version: 1.0.0\nbased_on: 1.0.0\n---\n"
    )
    tail = (
        f"\n\n{templating.TEMPLATE_ONLY}\n## 변경 기록\n| 버전 | 날짜 | 무엇이 바뀌었나 |\n|---|---|---|\n"
        f"| 1.0.0 | {today()} | {source.name} 시안에서 만듦 |\n"
    )
    return meta + re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip() + tail


# --------------------------------------------------------------------------- migrate


@dataclass
class Parsed:
    meta: dict
    title: str
    preamble: str
    sections: list[tuple[str, str]] = field(default_factory=list)  # (heading, content incl. trailing lines)


def parse_sections(text: str, level: int = 2) -> Parsed:
    doc = frontmatter.parse(text)
    body = templating.strip_template_only(doc.body) if templating.TEMPLATE_ONLY in doc.body else doc.body
    lines = body.split("\n")
    title, pre, sections = "", [], []
    cur_head: str | None = None
    cur: list[str] = []
    in_fence = False
    prefix = "#" * level + " "
    for line in lines:
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        if not in_fence and line.startswith("# ") and not title and cur_head is None:
            title = line
            continue
        if not in_fence and (line.startswith(prefix) or (level == 2 and title and line.startswith("# "))):
            if cur_head is not None:
                sections.append((cur_head, "\n".join(cur).strip("\n")))
            cur_head = line.lstrip("#").strip()
            cur = []
            continue
        (cur if cur_head is not None else pre).append(line)
    if cur_head is not None:
        sections.append((cur_head, "\n".join(cur).strip("\n")))
    return Parsed(doc.meta, title, "\n".join(pre).strip("\n"), sections)


def _is_blank_section(content: str) -> bool:
    stripped = [l for l in content.split("\n") if l.strip() and not l.startswith("> [!guide]") and not l.startswith(">")]
    return all(templating.PLACEHOLDER_RE.fullmatch(l.strip().lstrip("-0123456789. ").strip()) for l in stripped) if stripped else True


def migrate_text(
    project: Project, old_text: str, template_name: str, maps: dict[str, str], legacy: bool = False, values: dict | None = None
) -> str:
    tmpl_raw = read(template_path(project, template_name))
    vals = base_values(project)
    old = parse_sections(old_text)
    for k, v in old.meta.items():
        vals.setdefault(k, frontmatter.as_str(v))
    vals.update(values or {})
    rendered = templating.render(tmpl_raw, vals, condition_context(project))
    rendered = _SYS_RE.sub("", rendered)
    new = parse_sections(rendered)
    norm_map = {_norm_heading(k): _norm_heading(v) for k, v in maps.items()}
    old_by: dict[str, tuple[str, str]] = {}
    for h, c in old.sections:
        key = norm_map.get(_norm_heading(h), _norm_heading(h))
        if key in old_by:
            old_by[key] = (old_by[key][0], old_by[key][1] + "\n\n" + c)
        else:
            old_by[key] = (h, c)
    used = set()
    parts: list[str] = [old.title or new.title, ""]
    # keep the old glance/preamble when it has content; otherwise the template's
    if legacy:  # a legacy intro is content, the template's glance still has to be filled
        pre = new.preamble + ("\n\n" + old.preamble if old.preamble.strip() else "")
    else:
        pre = old.preamble if old.preamble.strip() else new.preamble
    parts += [pre.strip(), ""]
    for h, c in new.sections:
        key = _norm_heading(h)
        if key in old_by:
            parts += [f"## {h}", old_by[key][1] if old_by[key][1].strip() else c, ""]
            used.add(key)
        else:
            parts += [f"## {h}", c, ""]
    leftovers = [
        (h, c)
        for h, c in old.sections
        if norm_map.get(_norm_heading(h), _norm_heading(h)) not in used
        and _norm_heading(h) != _norm_heading(MIGRATE_BIN)
        and not _is_blank_section(c)
    ]
    bin_existing = [c for h, c in old.sections if _norm_heading(h) == _norm_heading(MIGRATE_BIN)]
    if leftovers or bin_existing:
        parts += [
            f"## {MIGRATE_BIN}",
            "> [!guide] 새 양식에 자리가 없는 내용. 지우지 않고 모았다 — 맞는 칸으로 옮기거나 정리한 뒤 이 칸을 지운다.",
            "",
        ]
        for c in bin_existing:
            parts += [c, ""]
        for h, c in leftovers:
            parts += [f"### {h}", c, ""]
    body = re.sub(r"\n{3,}", "\n\n", "\n".join(parts)).strip() + "\n"
    new_meta = frontmatter.parse(rendered).meta
    old_doc = frontmatter.parse(old_text)
    if old_doc.has_frontmatter and not legacy:
        # keep the old frontmatter lines as they were; only add new keys and the version
        updates = {k: v for k, v in new_meta.items() if k not in old.meta and k != "based_on"}
        updates["template"] = template_name
        updates["template_version"] = template_version(tmpl_raw)
        return frontmatter.set_fields(f"---\n{old_doc.raw_meta}\n---\n{body}", updates)
    merged = dict(new_meta)
    for k, v in old.meta.items():
        if k not in ("template", "template_version"):
            merged[k] = v
    merged.pop("based_on", None)
    merged["template"] = template_name
    merged["template_version"] = template_version(tmpl_raw)
    merged["updated"] = today()
    return frontmatter.render(merged, body)


def migrate_targets(project: Project, target: str | None) -> list[tuple[Path, str]]:
    if not target or target == "all":
        return [(o.path, o.template) for o in outdated(project)]
    if target in names(project):
        return [(o.path, o.template) for o in outdated(project, target)]
    p = Path(target)
    if not p.is_absolute():
        cand = [project.docs / target, project.root / target]
        p = next((c for c in cand if c.exists()), cand[0])
    if not p.exists():
        raise FileNotFoundError(f"문서도 양식도 아닙니다: {target}")
    meta = frontmatter.parse(read(p)).meta
    return [(p, nfc(str(meta.get("template") or "")))]


def migrate(
    project: Project, target: str | None, maps: dict[str, str], apply: bool, to: str | None = None, dest: str | None = None
) -> list[str]:
    out: list[str] = []
    if to:  # legacy doc → a new document in our template
        src = migrate_targets(project, target)[0][0]
        if not dest:
            raise ValueError("--to를 쓰면 --dest(새 문서 경로)도 필요합니다")
        dest_path = project.docs / dest
        if dest_path.exists():
            raise FileExistsError(f"이미 있습니다: {project.rel(dest_path)}")
        wid = re.match(r"^(W-\d{3,})\b", nfc(dest_path.parent.name))
        doc_id = wid.group(1) if wid else f"DOC-{dest_path.stem}"
        new_text = migrate_text(project, read(src), to, maps, legacy=True, values={"name": dest_path.stem, "id": doc_id, "work_id": doc_id})
        out.append(f"📄 {project.rel(src)} → {project.rel(dest_path)} (양식 '{to}', 원본은 그대로)")
        if apply:
            write(dest_path, new_text)
            out.append("✔ 만들었습니다")
        else:
            out.append(new_text)
        return out
    targets = migrate_targets(project, target)
    if not targets:
        return ["옮길 문서가 없습니다 (아직 쓰는 문서 중 옛 양식 버전 없음)"]
    for path, tname in targets:
        if not tname:
            out.append(f"⚠ {project.rel(path)}: template이 없는 문서 — --to <양식> --dest <경로>로 옮기세요")
            continue
        old = read(path)
        new = migrate_text(project, old, tname, maps)
        diff = "".join(
            difflib.unified_diff(
                old.splitlines(keepends=True),
                new.splitlines(keepends=True),
                fromfile=project.rel(path),
                tofile=project.rel(path) + " (새 양식)",
            )
        )
        out.append(f"📄 {project.rel(path)} — 양식 '{tname}'")
        if apply:
            write(path, new)
            out.append("✔ 옮겼습니다" + (f" — '{MIGRATE_BIN}' 칸을 정리하세요" if MIGRATE_BIN in new else ""))
        else:
            out.append(diff or "(바뀌는 내용 없음)")
    if not apply:
        out.append("미리보기입니다. 승인되면 --apply")
    return out
