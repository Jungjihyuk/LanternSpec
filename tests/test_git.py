"""The git side: hooks (commit message · schema record · document check · structure · docs-local push) · docs-mode ·
work worktrees · scan · sync adopt."""

import pytest

from conftest import docs, fill, init_project, sh, work_dir
from lanternspec.core import frontmatter


def commit(r, msg, check=True):
    return r.git("commit", "-q", "-m", msg, check=check)


def write(r, rel, text):
    p = r.root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def test_commit_msg_warns_then_blocks(repo):
    init_project(repo)
    repo("hooks", "install")
    repo.git("add", "-A")
    assert commit(repo, "docs: 준비").returncode == 0  # docs-only commit: no ID needed
    write(repo, "src/a.py", "a = 1\n")
    repo.git("add", "src")
    res = commit(repo, "feat: a")
    assert "커밋 메시지:" in res.stderr  # warned, still committed
    write(repo, "src/a.py", "a = 2\n")
    repo.git("add", "src")
    res = commit(repo, "feat: a [W-001-T01] [W-001-T02]")
    assert "할 일 여러 개가 한 커밋에 섞였습니다" in res.stderr
    repo("profile", "set", "git.hooks=block")
    write(repo, "src/a.py", "a = 3\n")
    repo.git("add", "src", "lantern.yaml")
    res = commit(repo, "fix: a", check=False)
    assert res.returncode != 0 and "커밋 메시지:" in res.stderr
    assert commit(repo, "fix: a [W-001-T03]").returncode == 0
    repo("hooks", "uninstall")
    _, out = repo("hooks", "status")
    assert "✔" not in out


def test_existing_hook_is_kept_and_chained(repo):
    hooks = repo.root / ".git" / "hooks"
    (hooks / "pre-commit").write_text('#!/bin/sh\necho mine > "$(git rev-parse --show-toplevel)/ran.txt"\n', encoding="utf-8")
    (hooks / "pre-commit").chmod(0o755)
    init_project(repo)
    _, out = repo("hooks", "install")
    assert "pre-commit.local" in out
    repo.git("add", "-A")
    commit(repo, "docs: 준비")
    assert (repo.root / "ran.txt").exists()
    repo("hooks", "uninstall")
    assert "mine" in (hooks / "pre-commit").read_text(encoding="utf-8")


def test_schema_change_needs_a_record_and_doc_check(repo):
    init_project(repo)
    repo("hooks", "install")
    repo.git("add", "-A")
    commit(repo, "docs: 준비")
    write(repo, "migrations/001.sql", "CREATE TABLE a (id int);\n")
    repo.git("add", "migrations")
    res = commit(repo, "feat: a [W-001-T01]")
    assert "스키마 기록:" in res.stderr
    repo("scaffold", "work", "작업")
    repo("scaffold", "doc", "W-001", "기록")
    write(repo, "migrations/002.sql", "CREATE TABLE b (id int);\n")
    repo.git("add", "-A")
    res = commit(repo, "feat: b [W-001-T02]")
    assert "스키마 기록:" not in res.stderr
    # document check: a broken link in a staged doc
    idea_dir = docs(repo) / "1. 아이디어"
    repo("scaffold", "idea", "링크")
    idea = next(idea_dir.glob("IDEA-001*"))
    fill(idea, [("{{관련 문서}}", "[[없음]]")])
    repo.git("add", "-A")
    res = commit(repo, "docs: 아이디어 [IDEA-001]")
    assert "문서 양식:" in res.stderr and "깨진 링크" in res.stderr


def test_structure_rules_always_block(repo):
    init_project(repo)
    repo("hooks", "install")
    repo("profile", "set", "git.hooks=warn")
    (docs(repo) / ".git").mkdir()
    repo.git("add", "lantern.yaml")
    res = commit(repo, "chore: x [W-001]", check=False)
    assert res.returncode != 0 and "docs/ 안에 .git" in res.stderr


@pytest.fixture
def local_repo(repo):
    from lanternspec.core.project import git_version

    if git_version(repo.root) < (2, 42, 0):
        pytest.skip("git 2.42+ needed for worktree --orphan")
    init_project(repo)
    repo.git("add", "-A")
    commit(repo, "docs: 준비 [lantern]")
    return repo


def test_docs_mode_local_roundtrip(local_repo, tmp_path):
    r = local_repo
    _, out = r("docs-mode", "local")
    d = docs(r)
    assert (d / ".git").is_file()
    assert "docs/" in (r.root / ".gitignore").read_text(encoding="utf-8")
    assert "!docs/" in (r.root / ".ignore").read_text(encoding="utf-8")
    assert "remote: local" in (r.root / "lantern.yaml").read_text(encoding="utf-8")
    assert not r.git("ls-files", "docs").stdout.strip()
    assert sh(d, "git", "rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == "docs-local"
    assert (d / "개발문서 MOC.md").exists()
    code, out = r("doctor", ok=False)
    assert "문서 저장 방식 local — 구조가 맞음" in out
    # code commit with docs mixed in is blocked; push of docs-local is blocked
    write(r, "src/a.py", "a = 1\n")
    r.git("add", "src")
    r.git("add", "-f", "docs/개발문서 MOC.md", check=False)
    assert commit(r, "feat: a [W-001-T01]").returncode == 0  # git refuses to stage a file inside the docs worktree
    remote = tmp_path / "remote.git"
    sh(tmp_path, "git", "init", "-q", "--bare", str(remote))
    r.git("remote", "add", "origin", str(remote))
    assert r.git("push", "-q", "origin", "main", check=False).returncode == 0
    res = r.git("push", "origin", "docs-local", check=False)
    assert res.returncode != 0 and "docs-local 브랜치는 원격" in res.stderr
    r.git("config", "--add", "lantern.allowDocsRemote", "origin")
    assert r.git("push", "-q", "origin", "docs-local", check=False).returncode == 0
    # docs commit in the docs worktree
    fill(d / "3. 현재 상태/기능 목록.md", [("{{지금 되는 기능을 한 문장으로 (필수)}}", "로그인")])
    sh(d, "git", "add", "-A")
    assert sh(d, "git", "commit", "-q", "-m", "docs: 기능 목록 (code abc1234) [W-001]").returncode == 0
    # back to shared
    r("docs-mode", "shared")
    assert not (d / ".git").exists()
    assert "로그인" in (d / "3. 현재 상태/기능 목록.md").read_text(encoding="utf-8")
    assert r.git("ls-files", "docs").stdout.strip()
    assert "remote: shared" in (r.root / "lantern.yaml").read_text(encoding="utf-8")


def test_work_parallel_start_finish(repo, tmp_path):
    init_project(repo)
    for name in ("카카오 로그인", "가계부 공유"):
        repo("scaffold", "work", name)
    for wid in ("W-001", "W-002"):
        repo("scaffold", "doc", wid, "설계")
        fill(
            work_dir(repo, wid) / "설계.md",
            [("// {{변경되는 테이블}}", "Table users {\n  id int [pk]\n}"), ("{{구조 설명}}", "`src/app.py`를 고친다")],
        )
    write(repo, ".env", "SECRET=1\n")
    write(repo, ".gitignore", ".env\n")
    repo.git("add", "-A")
    commit(repo, "docs: 기획 [W-001] [lantern]")
    _, out = repo("work", "start", "W-001", "W-002", "--no-install")
    assert "W-001 · W-002가 같은 곳을 고칩니다: 테이블 users, 파일 src/app.py" in out
    wt = repo.root.parent / "proj-W-001"
    assert (wt / ".env").read_text(encoding="utf-8") == "SECRET=1\n"
    _, out = repo("work", "list")
    assert "W-001  work/W-001" in out and "커밋 안 된" not in out
    write(repo, "../proj-W-001/src/app.py", "x = 1\n")
    sh(wt, "git", "add", "src")
    sh(wt, "git", "commit", "-q", "-m", "feat: x [W-001-T01]")
    repo("profile", "set", 'build.test="false"')
    code, out = repo("work", "finish", "W-001", ok=False)
    assert code == 1 and "테스트 실패" in out
    repo("profile", "set", 'build.test="true"')
    repo.git("commit", "-qam", "chore: test [lantern]")
    _, out = repo("work", "finish", "W-001")
    assert "✔ 테스트 통과" in out and "→ main 머지" in out and "worktree 정리" in out and "브랜치 삭제" in out
    assert not wt.exists()
    assert "merge: W-001" in repo.git("log", "-1", "--format=%s").stdout
    _, out = repo("work", "list")
    assert "W-001" not in out and "W-002" in out


def test_work_branch_in_place(repo):
    init_project(repo)
    repo("scaffold", "work", "작업")
    repo.git("add", "-A")
    commit(repo, "docs: 작업 [W-001]")
    _, out = repo("work", "branch", "W-001")
    assert "만들었습니다" in out
    assert repo.git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == "work/W-001"
    write(repo, "src/a.py", "a = 1\n")
    repo.git("add", "src")
    commit(repo, "feat: a [W-001-T01]")
    _, out = repo("work", "finish", "W-001", "--no-test")
    assert "→ main 머지" in out
    assert repo.git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == "main"


def test_scan_and_sync_adopt(repo):
    init_project(repo)
    repo.git("add", "-A")
    commit(repo, "docs: 준비")
    write(repo, "src/auth.py", "a = 1\n")
    repo.git("add", "src")
    commit(repo, "feat: 손으로 고침")
    write(repo, "migrations/001.sql", "CREATE TABLE users (id int primary key);\n")
    repo.git("add", "migrations")
    commit(repo, "feat: users [W-001-T01]")
    head = repo.git("rev-parse", "--short", "HEAD").stdout.strip()
    arch = docs(repo) / "3. 현재 상태/시스템 구조.md"
    arch.write_text(
        frontmatter.set_fields(arch.read_text(encoding="utf-8"), {"code": ["src/auth.py"], "checked_commit": head}), encoding="utf-8"
    )
    write(repo, "src/auth.py", "a = 2\n")
    repo.git("add", "src")
    commit(repo, "feat: auth [W-001-T02] [W-001-T03]")
    _, out = repo("scan")
    assert "주인 없는 변경 (1)" in out and "손으로 고침" in out
    assert "오래된 문서 (1)" in out and "시스템 구조.md" in out
    assert "기록 없는 스키마 변경 (1)" in out
    assert "DBML ↔ 마이그레이션" in out and "'users'" in out
    assert "할 일 여러 개가 섞인 커밋" in out
    orphan = repo.git("log", "--format=%h", "--grep=손으로").stdout.strip()
    repo("sync", "adopt", orphan, "--none", "실험")
    repo("scaffold", "work", "작업")
    repo("sync", "adopt", head, "--work", "W-001")
    assert head in (work_dir(repo, "W-001") / "기록.md").read_text(encoding="utf-8")
    new_head = repo.git("rev-parse", "--short", "HEAD").stdout.strip()
    repo("meta", "set", str(arch), f"checked_commit={new_head}")
    _, out = repo("scan", "--json")
    import json

    res = json.loads(out)
    assert res["orphans"] == [] and res["stale"] == [] and res["schema"] == []
    _, out = repo("scan", "--tests")
    assert "build.test가 없어" in out
    repo("profile", "set", 'build.test="false"')
    code, out = repo("scan", "--tests", ok=False)
    assert code == 1 and "✖ 실패" in out


def test_docs_mode_regenerates_skills(local_repo):
    r = local_repo
    r("install")
    r.git("add", "-A")
    commit(r, "chore: install [lantern]")
    build = r.root / ".claude/skills/l-build/SKILL.md"
    assert "**한 커밋에**" in build.read_text(encoding="utf-8")
    _, out = r("docs-mode", "local")
    assert "다시 생성" in out
    text = build.read_text(encoding="utf-8")
    assert "git -C docs" in text and "**한 커밋에**" not in text
    assert "docs-local 브랜치" in (r.root / "AGENTS.md").read_text(encoding="utf-8")
    assert not r.git("status", "--porcelain", "--untracked-files=no").stdout.strip()
