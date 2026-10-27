"""`lantern scan` — finding (the first half of /l-sync, docs-vs-code status in /l-report).

* unowned changes: commits without a work ID (SY-01)
* stale documents: `3. 현재 상태` docs whose `code` paths changed after `checked_commit`
* unrecorded schema changes: schema files changed but no `기록.md` entry (H-2)
* DBML ↔ migration drift (DE-03)
* failing acceptance tests (build.test, with --tests)
"""

from __future__ import annotations

import fnmatch
import json
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ..core import frontmatter
from ..core.project import Project, git, git_out, nfc, read, today, write
from ..work import dbml

ID_RE = re.compile(r"\b((?:IDEA|W|ADR|D)-\d{3,}(?:-T\d{2,})?)\b")
TASK_ID_RE = re.compile(r"\bW-\d{3,}-T\d{2,}\b")
NO_WORK_FILE = "4. 운영 기록/작업 없이 고친 것.md"
SKIP_SUBJECT = re.compile(r"^(Merge |Revert \"|fixup! |squash! |amend! )|\[lantern\]")


@dataclass
class Commit:
    hash: str
    short: str
    date: str
    subject: str
    body: str
    files: list[str]

    @property
    def ids(self) -> list[str]:
        return sorted(set(ID_RE.findall(self.subject + "\n" + self.body)))

    @property
    def task_ids(self) -> list[str]:
        return sorted(set(TASK_ID_RE.findall(self.subject + "\n" + self.body)))

    @property
    def work_ids(self) -> list[str]:
        return sorted({i.rsplit("-T", 1)[0] for i in self.ids if i.startswith("W-")})


def commits(project: Project, rev: str | None = None, limit: int = 200, paths: list[str] | None = None) -> list[Commit]:
    args = ["log", f"-n{limit}", "--no-merges", "--date=short", "--name-only", "--format=%x1e%H%x1f%h%x1f%ad%x1f%s%x1f%b%x1f"]
    if rev:
        args.append(rev)
    if paths:
        args += ["--", *paths]
    out = git(args, project.root)
    if out.returncode != 0:
        return []
    result: list[Commit] = []
    for chunk in out.stdout.split("\x1e"):
        if not chunk.strip():
            continue
        parts = chunk.split("\x1f")
        if len(parts) < 6:
            continue
        files = [nfc(f.strip()) for f in parts[5].strip().split("\n") if f.strip()]
        result.append(Commit(parts[0].strip(), parts[1], parts[2], parts[3], parts[4].strip(), files))
    return result


def is_doc_path(project: Project, rel: str) -> bool:
    root = project.profile.docs_root.rstrip("/") + "/"
    from ..tools import is_config_path

    return rel.startswith(root) or is_config_path(rel)


def matches_any(rel: str, patterns: list[str]) -> bool:
    for pat in patterns:
        if fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch("/" + rel, pat) or (pat.startswith("**/") and fnmatch.fnmatch(rel, pat[3:])):
            return True
    return False


def schema_files(project: Project, files: list[str]) -> list[str]:
    return [f for f in files if not is_doc_path(project, f) and matches_any(f, project.profile.schema_paths)]


def _owned_hashes(project: Project) -> str:
    """Text of every record that may mention a commit hash (`기록.md` files + the no-work log)."""
    texts = []
    for w in project.work_dirs(include_archive=True):
        r = w / "기록.md"
        if r.exists():
            texts.append(read(r))
    nf = project.docs / NO_WORK_FILE
    if nf.exists():
        texts.append(read(nf))
    return "\n".join(texts)


def _section(text: str, heading: str) -> str:
    m = re.search(rf"^## {re.escape(heading)}\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    return m.group(1) if m else ""


def _has_schema_rows(record_text: str) -> bool:
    sec = _section(record_text, "스키마 변경")
    rows = [l for l in sec.split("\n") if l.startswith("|") and not re.match(r"^\|[\s\-|:]*\|$", l)]
    return len(rows) > 1  # header + at least one row


@dataclass
class ScanResult:
    orphans: list[dict] = field(default_factory=list)
    mixed: list[dict] = field(default_factory=list)
    stale: list[dict] = field(default_factory=list)
    schema: list[dict] = field(default_factory=list)
    dbml_drift: list[str] = field(default_factory=list)
    tests: dict | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        failed = 1 if self.tests and not self.tests.get("ok") else 0
        return len(self.orphans) + len(self.stale) + len(self.schema) + len(self.dbml_drift) + failed

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    def format(self) -> str:
        lines = []
        if self.orphans:
            lines.append(f"## 주인 없는 변경 ({len(self.orphans)}) — 어느 작업인지 묻기")
            lines += [f"- `{c['short']}` {c['date']} {c['subject']}" for c in self.orphans]
        if self.stale:
            lines.append(f"## 오래된 문서 ({len(self.stale)}) — 코드가 기준이면 문서 갱신")
            for s in self.stale:
                lines.append(f"- {s['doc']} — {s['reason']}")
        if self.schema:
            lines.append(f"## 기록 없는 스키마 변경 ({len(self.schema)}) — 기록.md 스키마 변경 칸")
            lines += [
                f"- `{s['short']}` {s['subject']} ({', '.join(s['files'])}){' · ' + s['work'] if s.get('work') else ''}"
                for s in self.schema
            ]
        if self.dbml_drift:
            lines.append(f"## DBML ↔ 마이그레이션 ({len(self.dbml_drift)}) — 데이터는 마이그레이션이 기준")
            lines += [f"- {d}" for d in self.dbml_drift]
        if self.tests is not None:
            ok = self.tests.get("ok")
            lines.append(f"## 수락 기준 테스트 — {'✔ 통과' if ok else '✖ 실패'} (`{self.tests.get('command')}`)")
            if not ok:
                lines.append("```\n" + self.tests.get("tail", "") + "\n```")
        if self.mixed:
            lines.append(f"## 참고: 할 일 여러 개가 섞인 커밋 ({len(self.mixed)}) — 할 일 하나 = 커밋 하나")
            lines += [f"- `{c['short']}` {c['subject']} ({', '.join(c['ids'])})" for c in self.mixed]
        lines += [f"> {n}" for n in self.notes]
        if not lines or self.total == 0 and not self.mixed:
            lines.insert(0, "✔ 문서와 코드가 맞습니다 — 어긋난 곳 없음")
        return "\n".join(lines)


def run(project: Project, rev: str | None = None, limit: int = 200, tests: bool = False) -> ScanResult:
    res = ScanResult()
    if git(["rev-parse", "--verify", "HEAD"], project.root).returncode != 0:
        res.notes.append("아직 커밋이 없습니다")
        return res
    owned = _owned_hashes(project)
    for c in commits(project, rev=rev, limit=limit):
        if SKIP_SUBJECT.search(c.subject):
            continue
        code_files = [f for f in c.files if not is_doc_path(project, f)]
        if not code_files:
            continue
        if not c.ids and c.short not in owned and c.hash[:12] not in owned:
            res.orphans.append({"hash": c.hash, "short": c.short, "date": c.date, "subject": c.subject, "files": code_files})
        if len(c.task_ids) > 1:
            res.mixed.append({"short": c.short, "subject": c.subject, "ids": c.task_ids})
        sfiles = schema_files(project, c.files)
        if sfiles:
            recorded = c.short in owned or c.hash[:12] in owned
            work_name = ""
            for wid in c.work_ids:
                folder = project.find_work(wid)
                if folder and (folder / "기록.md").exists() and _has_schema_rows(read(folder / "기록.md")):
                    recorded = True
                work_name = wid
            if not recorded:
                res.schema.append({"short": c.short, "subject": c.subject, "files": sfiles, "work": work_name})
    # stale docs
    current = project.folder("current")
    if current.exists():
        for p in sorted(current.rglob("*.md")):
            meta = frontmatter.parse(read(p)).meta
            if meta.get("status") == project.enums.value("current_status", "inactive"):
                continue
            code = [str(x) for x in frontmatter.as_list(meta.get("code")) if str(x).strip()]
            if not code:
                continue
            checked = frontmatter.as_str(meta.get("checked_commit")).strip()
            rel = project.rel(p)
            if not checked:
                res.stale.append({"doc": rel, "reason": "마지막 확인 커밋(checked_commit)이 비어 있습니다", "commits": []})
                continue
            if git(["cat-file", "-e", f"{checked}^{{commit}}"], project.root).returncode != 0:
                res.stale.append({"doc": rel, "reason": f"checked_commit {checked}를 찾지 못했습니다", "commits": []})
                continue
            changed = git_out(["log", "--format=%h %s", f"{checked}..HEAD", "--", *code], project.root).splitlines()
            if changed:
                res.stale.append(
                    {"doc": rel, "reason": f"{checked} 이후 관련 코드 커밋 {len(changed)}개: " + "; ".join(changed[:3]), "commits": changed}
                )
    # DBML drift
    schema_path = current / "데이터" / "schema.dbml"
    sql_files = sorted(
        (
            p
            for p in project.root.rglob("*.sql")
            if ".git" not in p.parts
            and "node_modules" not in p.parts
            and not is_doc_path(project, project.rel(p))
            and matches_any(project.rel(p), project.profile.schema_paths)
        ),
        key=lambda p: project.rel(p),
    )
    if schema_path.exists() and sql_files:
        res.dbml_drift = dbml.diff(dbml.parse(read(schema_path)), dbml.from_sql(sql_files))
    # tests
    if tests:
        cmd = project.profile.get("build.test")
        if not cmd:
            res.notes.append("build.test가 없어 수락 기준 테스트를 건너뜀 (lantern.yaml build.test)")
        else:
            res.tests = run_tests(project, str(cmd))
    return res


def run_tests(project: Project, cmd: str, cwd: Path | None = None) -> dict:
    r = subprocess.run(cmd, shell=True, cwd=str(cwd or project.root), capture_output=True, text=True)
    tail = "\n".join((r.stdout + r.stderr).strip().split("\n")[-15:])
    return {"command": cmd, "ok": r.returncode == 0, "code": r.returncode, "tail": tail}


# --------------------------------------------------------------------------- adopt (recording sync results)


def record_no_work(project: Project, short: str, reason: str) -> Path:
    p = project.docs / NO_WORK_FILE
    if not p.exists():
        body = (
            "# 작업 없이 고친 것\n\n> [!abstract] 한눈에 보기\n> 작업(W-…)에 속하지 않는 코드 변경. `/l-sync`가 기록한다.\n\n"
            "| 날짜 | 커밋 | 내용 | 이유 |\n|---|---|---|---|\n"
        )
        write(
            p,
            frontmatter.render(
                {
                    "id": "OPS-no-work",
                    "type": "report",
                    "status": project.enums.value("current_status", "active"),
                    "generated": True,
                    "updated": today(),
                },
                body,
            ),
        )
    subject = git_out(["log", "-1", "--format=%s", short], project.root)
    text = read(p).rstrip("\n") + f"\n| {today()} | `{short}` | {subject} | {reason} |\n"
    write(p, text)
    return p


def adopt_into_work(project: Project, short: str, work_id: str) -> Path:
    folder = project.find_work(work_id)
    if folder is None:
        raise ValueError(f"작업 {work_id}를 찾지 못했습니다")
    rec = folder / "기록.md"
    if not rec.exists():
        from ..work.scaffold import work_doc

        work_doc(project, work_id, "기록")
    subject = git_out(["log", "-1", "--format=%s", short], project.root)
    text = read(rec)
    line = f"- {today()} 주인 없는 변경 `{short}` ({subject})을 이 작업으로 연결 (/l-sync)"
    if "## 지난 기록" in text:
        head, tail = text.split("## 지난 기록", 1)
        parts = tail.split("\n")
        insert_at = len(parts)
        for i, l in enumerate(parts[1:], start=1):
            if l.startswith("## ") or l.startswith("<!--"):
                insert_at = i
                break
        parts.insert(insert_at, line)
        text = head + "## 지난 기록" + "\n".join(parts)
    else:
        text = text.rstrip() + f"\n\n## 지난 기록\n{line}\n"
    write(rec, frontmatter.set_fields(text, {}))
    return rec
