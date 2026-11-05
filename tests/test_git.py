"""The git side: hooks (commit message · schema record · document check · structure · docs-local push) · docs-mode ·
work worktrees · scan · sync adopt."""

import json
import os
import shlex
import shutil
import subprocess
import tomllib

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


def _on_work_with_tasks(repo):
    """A committed work with three tasks; returns its tasks file."""
    init_project(repo)
    repo("scaffold", "work", "작업")
    repo("scaffold", "doc", "W-001", "할 일")
    repo("task", "add", "W-001", "하나", "--size", "S")
    repo("task", "add", "W-001", "둘", "--size", "S")
    repo("task", "add", "W-001", "셋", "--size", "S", "--after", "T01")
    repo.git("add", "-A")
    commit(repo, "docs: 작업 [W-001]")
    return work_dir(repo, "W-001") / "할 일.md"


def test_a_new_work_branch_starts_from_the_base_branch(repo):
    init_project(repo)
    repo("scaffold", "work", "작업")
    repo("scaffold", "work", "급한 일")
    repo.git("add", "-A")
    commit(repo, "docs: 작업 [W-001]")
    repo("work", "branch", "W-001")
    write(repo, "src/a.py", "a = 1\n")
    repo.git("add", "src")
    commit(repo, "feat: 미완성 [W-001-T01]")
    # on another work's branch: don't silently carry its unfinished code along
    code, out = repo("work", "branch", "W-002", ok=False)
    assert code != 0 and "main" in out and "--from" in out
    assert repo.git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == "work/W-001"
    # building on it is a choice the person makes
    repo("work", "branch", "W-002", "--from", "work/W-001")
    assert (repo.root / "src/a.py").exists()
    repo.git("checkout", "-q", "main")
    repo.git("branch", "-q", "-D", "work/W-002")
    repo("work", "branch", "W-002")
    assert not (repo.root / "src/a.py").exists()
    # an existing branch is only switched to, from anywhere
    repo("work", "branch", "W-001")
    assert repo.git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == "work/W-001"


def test_task_next_warns_when_the_order_differs_from_the_last_commit(repo):
    tasks = _on_work_with_tasks(repo)
    _, out = repo("task", "next", "W-001")
    assert "⚠" not in out
    # what isn't an order change stays quiet: start times, planned dates, new tasks
    repo("task", "start", "W-001-T01")
    repo("task", "add", "W-001", "넷", "--size", "S")
    text = tasks.read_text(encoding="utf-8")
    tasks.write_text(text.replace("W-001-T02 둘 [크기:: S]", "W-001-T02 둘 [크기:: S] [시작 예정:: 2026-11-10]"), encoding="utf-8")
    _, out = repo("task", "next", "W-001")
    assert "⚠" not in out
    # the line order changed
    lines = tasks.read_text(encoding="utf-8").split("\n")
    first, second = [i for i, l in enumerate(lines) if "W-001-T01" in l or "W-001-T02" in l][:2]
    lines[first], lines[second] = lines[second], lines[first]
    tasks.write_text("\n".join(lines), encoding="utf-8")
    _, out = repo("task", "next", "W-001")
    assert "⚠ W-001" in out and "순서" in out
    _, out = repo("task", "next", "W-001", "--json")
    assert "W-001" in json.loads(out)["order_changes"][0]
    # committing the agreed order clears the warning
    repo.git("add", str(tasks))
    commit(repo, "docs: 순서 변경 [W-001]")
    _, out = repo("task", "next", "W-001")
    assert "⚠" not in out
    # a changed prerequisite counts too
    tasks.write_text(tasks.read_text(encoding="utf-8").replace("[먼저:: T01]", "[먼저:: T02]"), encoding="utf-8")
    _, out = repo("task", "next", "W-001", "--all")
    assert "⚠ W-001" in out and "T01" in out and "T02" in out


def test_task_next_compares_with_the_docs_branch_in_local_mode(repo):
    from lanternspec.core.project import git_version

    if git_version(repo.root) < (2, 42, 0):
        pytest.skip("git 2.42+ needed for worktree --orphan")
    init_project(repo)
    repo.git("add", "-A")
    commit(repo, "chore: 준비")
    repo("docs-mode", "local")
    repo("scaffold", "work", "작업")
    repo("scaffold", "doc", "W-001", "할 일")
    repo("task", "add", "W-001", "하나", "--size", "S")
    repo("task", "add", "W-001", "둘", "--size", "S", "--after", "T01")
    d = docs(repo)
    sh(d, "git", "add", "-A")
    sh(d, "git", "commit", "-q", "-m", "docs: 작업")
    tasks = work_dir(repo, "W-001") / "할 일.md"
    tasks.write_text(tasks.read_text(encoding="utf-8").replace(" [먼저:: T01]", ""), encoding="utf-8")
    _, out = repo("task", "next", "W-001")
    assert "⚠ W-001" in out


def _work(repo, name="작업"):
    repo("scaffold", "work", name)
    repo.git("add", "-A")
    commit(repo, "docs: 작업 [W-001]")


def _branch_now(repo):
    return repo.git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()


def test_a_branch_rule_with_only_the_id_needs_no_name(repo):
    init_project(repo)
    repo("profile", "set", "git.branch=feature/{id}")
    _work(repo)
    repo("work", "branch", "W-001")
    assert _branch_now(repo) == "feature/W-001"
    _, out = repo("work", "list")
    assert "W-001  feature/W-001" in out
    # any branch carrying a work ID reserves the number
    repo.git("branch", "feature/W-007-other")
    assert repo("new-id", "work")[1].strip() == "W-008"
    _, out = repo("work", "finish", "W-001", "--no-test")
    assert "feature/W-001 → main" in out
    assert repo.git("branch", "--list", "feature/W-001").stdout.strip() == ""


def test_a_branch_rule_with_other_blanks_records_the_name_in_the_plan(repo):
    init_project(repo)
    repo("profile", "set", "git.branch=feature/{ticket}-{slug}")
    _work(repo)
    code, out = repo("work", "branch", "W-001", ok=False)
    assert code != 0 and "--name" in out and "feature/{ticket}-{slug}" in out
    code, out = repo("work", "branch", "W-001", "--name", "fix/JS-15", ok=False)
    assert code != 0 and "feature/{ticket}-{slug}" in out
    assert _branch_now(repo) == "main"
    repo("work", "branch", "W-001", "--name", "feature/JS-15-login")
    assert _branch_now(repo) == "feature/JS-15-login"
    plan = work_dir(repo, "W-001") / "기획.md"
    assert frontmatter.parse(plan.read_text(encoding="utf-8")).meta["branch"] == "feature/JS-15-login"
    # no ID in the name: the plan links the two both ways
    _, out = repo("work", "list")
    assert "W-001  feature/JS-15-login" in out
    assert "이미" in repo("work", "branch", "W-001")[1]
    repo.git("add", "-A")
    commit(repo, "docs: 브랜치 [W-001]")
    _, out = repo("work", "finish", "W-001", "--no-test")
    assert "feature/JS-15-login → main" in out
    assert _branch_now(repo) == "main"


def test_the_branch_name_can_be_chosen_when_planning(repo):
    init_project(repo)
    repo("profile", "set", "git.branch=feature/{ticket}")
    code, out = repo("scaffold", "work", "작업", "--branch", "bugfix/1", ok=False)
    assert code != 0 and "feature/{ticket}" in out
    assert not list((docs(repo) / "2. 작업").glob("W-*"))
    repo("scaffold", "work", "작업", "--branch", "feature/JS-1")
    repo.git("add", "-A")
    commit(repo, "docs: 작업 [W-001]")  # on the base branch: every branch can see the name
    repo("work", "branch", "W-001")
    assert _branch_now(repo) == "feature/JS-1"


def test_a_work_already_on_its_old_branch_keeps_it_after_the_rule_changes(repo):
    init_project(repo)
    _work(repo)
    repo("work", "branch", "W-001")
    repo.git("checkout", "-q", "main")
    repo("profile", "set", "git.branch=feature/{id}")
    repo.git("add", "-A")
    commit(repo, "chore: 규칙 [W-001]")
    repo("work", "branch", "W-001")
    assert _branch_now(repo) == "work/W-001"


def test_finish_tests_the_work_merged_with_the_base(repo):
    init_project(repo)
    _work(repo)
    repo("work", "branch", "W-001")
    write(repo, "src/a.py", "a = 1\n")
    repo.git("add", "src")
    commit(repo, "feat: a [W-001-T01]")
    repo.git("checkout", "-q", "main")
    write(repo, "from_base.txt", "x\n")
    repo.git("add", "from_base.txt")
    commit(repo, "chore: 기준 브랜치에 들어온 변경 [W-001]")
    repo.git("checkout", "-q", "work/W-001")
    repo("profile", "set", "build.test=test -f from_base.txt")
    repo.git("add", "-A")
    commit(repo, "chore: 테스트 설정 [W-001]")
    _, out = repo("work", "finish", "W-001")
    assert "테스트 통과" in out and "→ main 머지" in out
    assert (repo.root / "from_base.txt").exists() and (repo.root / "src/a.py").exists()


def test_finish_works_from_the_base_branch_and_stops_cleanly_on_a_conflict(repo):
    init_project(repo)
    _work(repo)
    write(repo, "same.txt", "처음\n")
    repo.git("add", "same.txt")
    commit(repo, "chore: 파일 [W-001]")
    repo("work", "branch", "W-001")
    write(repo, "same.txt", "작업\n")
    repo.git("add", "same.txt")
    commit(repo, "feat: 작업 쪽 [W-001-T01]")
    repo.git("checkout", "-q", "main")
    write(repo, "same.txt", "기준\n")
    repo.git("add", "same.txt")
    commit(repo, "chore: 기준 쪽 [W-001]")
    code, out = repo("work", "finish", "W-001", "--no-test", ok=False)
    assert code != 0 and "same.txt" in out and "git merge main" in out
    assert repo.git("status", "--porcelain").stdout.strip() == ""  # the merge was aborted
    assert repo.git("branch", "--list", "work/W-001").stdout.strip() != ""
    assert (repo.root / "same.txt").read_text(encoding="utf-8") == "작업\n"


def test_finish_leaves_merging_to_the_pr_when_each_work_gets_one(repo):
    init_project(repo)
    repo("profile", "set", "git.pr=work")
    _work(repo)
    repo("work", "branch", "W-001")
    write(repo, "src/a.py", "a = 1\n")
    repo.git("add", "src")
    commit(repo, "feat: a [W-001-T01]")
    main_before = repo.git("rev-parse", "main").stdout
    _, out = repo("work", "finish", "W-001", "--no-test")
    assert "PR" in out and "머지" not in out.split("PR")[0]
    assert repo.git("rev-parse", "main").stdout == main_before
    assert _branch_now(repo) == "work/W-001"


def test_finish_says_how_to_deploy_when_the_base_goes_out_by_pr(repo):
    init_project(repo)
    repo.git("branch", "dev")
    repo("profile", "set", "git.base=dev", "git.pr=deploy", "git.deploy=main")
    repo.git("add", "-A")
    commit(repo, "chore: 설정")
    repo.git("checkout", "-q", "dev")
    repo.git("merge", "-q", "main")
    _work(repo)
    repo("work", "branch", "W-001")
    _, out = repo("work", "finish", "W-001", "--no-test")
    assert "→ dev 머지" in out and "dev" in out.split("머지", 1)[1] and "main" in out.split("머지", 1)[1]
    assert _branch_now(repo) == "dev"


def _two_worktrees(repo):
    init_project(repo)
    repo("scaffold", "work", "하나")
    repo("scaffold", "work", "둘")
    repo.git("add", "-A")
    commit(repo, "docs: 기획 [lantern]")
    repo("work", "start", "W-001", "W-002", "--no-install")
    return repo.root.parent / "proj-W-001", repo.root.parent / "proj-W-002"


def _commit_in(folder, name, message):
    (folder / name).write_text("x\n", encoding="utf-8")
    sh(folder, "git", "add", name)
    sh(folder, "git", "commit", "-q", "-m", message)


def test_finish_from_inside_a_worktree_merges_where_the_base_is_open(repo, monkeypatch):
    first, second = _two_worktrees(repo)
    _commit_in(first, "a.py", "feat: a [W-001-T01]")
    _commit_in(second, "b.py", "feat: b [W-002-T01]")
    monkeypatch.chdir(first)
    _, out = repo("work", "finish", "W-001", "--no-test")
    assert "→ main 머지" in out and "남겨 둡니다" in out and "lantern work finish W-001 --no-test" in out
    assert (repo.root / "a.py").exists() and _branch_now(repo) == "main"
    assert sh(first, "git", "branch", "--show-current").stdout.strip() == "work/W-001" and first.exists()
    assert sh(second, "git", "branch", "--show-current").stdout.strip() == "work/W-002"
    assert (second / "b.py").exists() and not (second / "a.py").exists()
    monkeypatch.chdir(repo.root)
    _, out = repo("work", "finish", "W-001", "--no-test")
    assert "worktree 정리" in out and "브랜치 삭제" in out and not first.exists()


def test_finish_merges_in_the_worktree_that_has_the_base_open(repo, monkeypatch):
    init_project(repo)
    repo("profile", "set", "git.base=dev")
    repo("scaffold", "work", "하나")
    repo.git("add", "-A")
    commit(repo, "docs: 기획 [lantern]")
    dev = repo.root.parent / "proj-dev"
    repo.git("worktree", "add", "-q", "-b", "dev", str(dev))
    repo("work", "start", "W-001", "--no-install")
    first = repo.root.parent / "proj-W-001"
    _commit_in(first, "a.py", "feat: a [W-001-T01]")
    monkeypatch.chdir(first)
    _, out = repo("work", "finish", "W-001", "--no-test")
    assert "→ dev 머지" in out
    assert (dev / "a.py").exists() and not (repo.root / "a.py").exists() and _branch_now(repo) == "main"


def test_finish_stops_before_merging_when_the_base_is_open_nowhere(repo, monkeypatch):
    first, _ = _two_worktrees(repo)
    _commit_in(first, "a.py", "feat: a [W-001-T01]")
    repo.git("checkout", "-q", "-b", "other")
    monkeypatch.chdir(first)
    code, out = repo("work", "finish", "W-001", "--no-test", ok=False)
    assert code == 1 and "git checkout main" in out
    assert "a.py" not in repo.git("ls-tree", "--name-only", "main").stdout
    assert _branch_now(repo) == "other"
    assert sh(first, "git", "branch", "--show-current").stdout.strip() == "work/W-001"


def test_finish_stops_when_the_folder_to_merge_in_has_changes(repo, monkeypatch):
    first, _ = _two_worktrees(repo)
    _commit_in(first, "a.py", "feat: a [W-001-T01]")
    (repo.root / "lantern.yaml").write_text((repo.root / "lantern.yaml").read_text(encoding="utf-8") + "\n", encoding="utf-8")
    monkeypatch.chdir(first)
    code, out = repo("work", "finish", "W-001", "--no-test", ok=False)
    assert code == 1 and "커밋 안 된 변경" in out and str(repo.root.name) in out
    assert "a.py" not in repo.git("ls-tree", "--name-only", "main").stdout


def test_finish_from_another_works_worktree_leaves_that_worktree_alone(repo, monkeypatch):
    init_project(repo)
    repo("scaffold", "work", "하나")
    repo("scaffold", "work", "둘")
    repo.git("add", "-A")
    commit(repo, "docs: 기획 [lantern]")
    repo("work", "branch", "W-001")
    write(repo, "a.py", "x\n")
    repo.git("add", "a.py")
    commit(repo, "feat: a [W-001-T01]")
    repo.git("checkout", "-q", "main")
    repo("work", "start", "W-002", "--no-install")
    second = repo.root.parent / "proj-W-002"
    monkeypatch.chdir(second)
    _, out = repo("work", "finish", "W-001", "--no-test")
    assert "→ main 머지" in out and (repo.root / "a.py").exists()
    assert sh(second, "git", "branch", "--show-current").stdout.strip() == "work/W-002"


def test_finish_reports_a_failed_merge_as_it_is_when_nothing_conflicts(repo):
    first, _ = _two_worktrees(repo)
    _commit_in(first, "a.py", "feat: a [W-001-T01]")
    _commit_in(repo.root, "base.py", "chore: 기준 [W-001]")
    lock = repo.root / ".git" / "worktrees" / "proj-W-001" / "index.lock"
    lock.write_text("", encoding="utf-8")
    code, out = repo("work", "finish", "W-001", "--no-test", ok=False)
    lock.unlink()
    assert code == 1 and "index.lock" in out and "충돌" not in out


def test_finish_leaves_a_worktree_this_session_cannot_delete_whole(repo):
    first, _ = _two_worktrees(repo)
    _commit_in(first, "a.py", "feat: a [W-001-T01]")
    parent = first.parent
    mode = parent.stat().st_mode
    parent.chmod(0o555)
    if os.access(parent, os.W_OK):  # e.g. running as root
        parent.chmod(mode)
        pytest.skip("this user can write anywhere")
    try:
        _, out = repo("work", "finish", "W-001", "--no-test")
    finally:
        parent.chmod(mode)
    assert "지울 수 없어" in out and "lantern work finish W-001 --no-test" in out
    assert (first / "a.py").exists() and sh(repo.root, "git", "rev-parse", "--verify", "work/W-001").returncode == 0
    assert (repo.root / "a.py").exists()
    _, out = repo("work", "finish", "W-001", "--no-test")
    assert "worktree 정리" in out and not first.exists()


def _codex_start_line(repo, wid):
    _, out = repo("work", "start", wid, "--no-install")
    return next(line for line in out.splitlines() if "codex " in line).split("&& ", 1)[1]


def test_work_start_prints_a_command_for_each_installed_tool(repo):
    init_project(repo)
    repo("install", "--tools", "claude,codex,antigravity")
    repo("scaffold", "work", "하나")
    repo.git("add", "-A")
    commit(repo, "docs: 기획 [lantern]")
    _, out = repo("work", "start", "W-001", "--no-install")
    assert "claude '/l-build W-001'" in out and "agy -i '/l-build W-001'" in out and "'$l-build W-001'" in out


def test_codex_worktree_command_opens_only_what_git_needs(repo):
    init_project(repo)
    repo("install", "--tools", "codex")
    repo("scaffold", "work", "하나")
    repo.git("add", "-A")
    commit(repo, "docs: 기획 [lantern]")
    args = shlex.split(_codex_start_line(repo, "W-001"))
    wt = repo.root.parent / "proj-W-001"
    profile = tomllib.loads(args[2])["permissions"]["lantern-worktree"]
    git_dir = (repo.root / ".git").resolve()
    assert profile["extends"] == ":workspace" and profile["filesystem"] == {
        str(git_dir): "write",
        str(git_dir / "worktrees" / wt.name): "write",
        str(git_dir / "hooks"): "read",
        str(git_dir / "config"): "read",
        str(repo.root.resolve()): "write",
    }
    assert args[3:] == ["-c", 'default_permissions="lantern-worktree"', "$l-build W-001"]


def test_codex_sandbox_commits_with_the_worktree_command_but_keeps_git_config_closed(repo):
    if shutil.which("codex") is None:
        pytest.skip("codex is not installed")
    init_project(repo)
    repo("install", "--tools", "codex")
    repo("scaffold", "work", "하나")
    repo.git("add", "-A")
    commit(repo, "docs: 기획 [lantern]")
    args = shlex.split(_codex_start_line(repo, "W-001"))
    wt = repo.root.parent / "proj-W-001"
    sandbox = ["codex", "sandbox", *args[1:5], "-P", "lantern-worktree", "-C", str(wt), "--"]
    env = {**os.environ, "LANTERN_SKIP_HOOKS": "1"}
    r = subprocess.run([*sandbox, "git", "commit", "--allow-empty", "-qm", "chore: x [W-001]"], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    r = subprocess.run([*sandbox, "git", "config", "lantern.W-001.x", "1"], capture_output=True, text=True, env=env)
    assert r.returncode != 0


def _dev_project(repo):
    init_project(repo)
    repo.git("branch", "dev")
    repo("profile", "set", "git.base=dev", "git.pr=deploy", "git.deploy=main")
    repo("scaffold", "work", "장애 수정")
    repo.git("add", "-A")
    commit(repo, "docs: 기획 [lantern]")
    repo.git("checkout", "-q", "dev")
    repo.git("merge", "-q", "main")
    write(repo, "only_dev.txt", "배포 전\n")
    repo.git("add", "only_dev.txt")
    commit(repo, "feat: 아직 배포 전 [W-999-T01]")


def test_into_starts_from_and_merges_into_that_branch_without_the_base_branchs_code(repo):
    _dev_project(repo)
    _, out = repo("work", "branch", "W-001", "--into", "main")
    assert "평소의 dev 대신 main" in out and _branch_now(repo) == "work/W-001"
    assert not (repo.root / "only_dev.txt").exists()
    write(repo, "fix.py", "x = 1\n")
    repo.git("add", "fix.py")
    commit(repo, "fix: 장애 [W-001-T01]")
    _, listed = repo("work", "list")
    assert "→ main" in listed
    repo.git("checkout", "-q", "dev")
    _, out = repo("work", "finish", "W-001", "--no-test", ok=False)
    assert "→ main 머지" in out and "dev에는 아직" in out and "/l-pr" not in out
    tree = repo.git("ls-tree", "--name-only", "main").stdout
    assert "fix.py" in tree and "only_dev.txt" not in tree
    assert "fix.py" not in repo.git("ls-tree", "--name-only", "dev").stdout
    assert repo.git("config", "--get", "lantern.W-001.into", check=False).stdout.strip() == ""


def test_into_is_seen_from_every_worktree_and_survives_until_cleanup(repo, monkeypatch):
    _dev_project(repo)
    _, out = repo("work", "start", "W-001", "--into", "main", "--no-install")
    assert "평소의 dev 대신 main" in out
    first = repo.root.parent / "proj-W-001"
    assert not (first / "only_dev.txt").exists()
    _commit_in(first, "fix.py", "fix: 장애 [W-001-T01]")
    repo.git("checkout", "-q", "main")
    monkeypatch.chdir(first)
    _, out = repo("work", "finish", "W-001", "--no-test")
    assert "→ main 머지" in out and "남겨 둡니다" in out
    assert (repo.root / "fix.py").exists()
    monkeypatch.chdir(repo.root)
    _, out = repo("work", "finish", "W-001", "--no-test")
    assert "worktree 정리" in out and "→ main 머지" in out
    assert "fix.py" not in repo.git("ls-tree", "--name-only", "dev").stdout


def test_into_refuses_a_branch_that_already_started_elsewhere(repo):
    _dev_project(repo)
    repo("work", "branch", "W-001")
    assert (repo.root / "only_dev.txt").exists()
    code, out = repo("work", "branch", "W-001", "--into", "main", ok=False)
    assert code == 1 and "git branch -D work/W-001" in out
    assert repo.git("config", "--get", "lantern.W-001.into", check=False).stdout.strip() == ""


def test_finish_finds_a_chosen_name_while_only_the_work_branch_has_it_in_the_plan(repo):
    init_project(repo)
    repo("profile", "set", "git.branch=feature/{id}-{slug}")
    repo("scaffold", "work", "하나", "--branch", "feature/W-001-one")
    repo.git("add", "-A")
    commit(repo, "docs: 기획 [lantern]")
    repo("scaffold", "work", "둘")
    repo.git("add", "-A")
    commit(repo, "docs: 기획 [lantern]")
    repo("work", "branch", "W-002", "--name", "feature/W-002-two")
    repo.git("add", "-A")
    commit(repo, "docs: 이름 [W-002]")
    repo.git("checkout", "-q", "main")
    _, out = repo("work", "finish", "W-002", "--no-test")
    assert "feature/W-002-two → main 머지" in out and "브랜치 삭제" in out
    assert repo.git("config", "--get", "lantern.W-002.branch", check=False).stdout.strip() == ""


def test_into_needs_a_branch_that_exists(repo):
    _dev_project(repo)
    code, out = repo("work", "branch", "W-001", "--into", "없는브랜치", ok=False)
    assert code == 1 and "없는브랜치" in out and _branch_now(repo) == "dev"


def test_here_commits_on_the_current_branch_and_finish_only_tests(repo):
    _dev_project(repo)
    before = repo.git("branch", "--list").stdout
    _, out = repo("work", "branch", "W-001", "--here")
    assert "dev에 바로 커밋" in out and repo.git("branch", "--list").stdout == before
    _, listed = repo("work", "list")
    assert "W-001  dev" in listed
    write(repo, "fix.py", "x = 1\n")
    repo.git("add", "fix.py")
    commit(repo, "fix: 바로 [W-001-T01]")
    repo("profile", "set", 'build.test="false"')
    repo.git("add", "-A")
    commit(repo, "chore: 테스트 [W-001]")
    code, out = repo("work", "finish", "W-001", ok=False)
    assert code == 1 and "테스트 실패" in out
    repo("profile", "set", 'build.test="true"')
    repo.git("add", "-A")
    commit(repo, "chore: 테스트 [W-001]")
    tip = repo.git("rev-parse", "dev").stdout
    _, out = repo("work", "finish", "W-001")
    assert "합칠 것이 없습니다" in out and repo.git("rev-parse", "dev").stdout == tip
    assert repo.git("branch", "--list", "dev").stdout.strip() != ""
    _, out = repo("work", "list")
    assert "W-001" not in out


def test_here_on_main_warns_that_dev_still_needs_it(repo):
    _dev_project(repo)
    repo.git("checkout", "-q", "main")
    _, out = repo("work", "branch", "W-001", "--here")
    assert "main에 바로 커밋" in out
    _, out = repo("work", "finish", "W-001", "--no-test")
    assert "합칠 것이 없습니다" in out and "dev에는 아직" in out


def test_here_refuses_another_works_branch_and_an_existing_branch(repo):
    _dev_project(repo)
    repo("work", "branch", "W-001")
    repo("scaffold", "work", "다른 작업")
    code, out = repo("work", "branch", "W-002", "--here", ok=False)
    assert code == 1 and "W-001의 브랜치" in out
    repo.git("checkout", "-q", "dev")
    code, out = repo("work", "branch", "W-001", "--here", ok=False)
    assert code == 1 and "work/W-001" in out


def test_here_and_into_are_refused_where_they_mean_nothing(repo):
    _dev_project(repo)
    code, out = repo("work", "branch", "W-001", "--here", "--into", "main", ok=False)
    assert code != 0 and "--here" in out
    code, out = repo("work", "start", "W-001", "--here", ok=False)
    assert code != 0 and "--here" in out
    code, out = repo("work", "finish", "W-001", "--into", "main", ok=False)
    assert code != 0 and "--into" in out


def test_a_new_work_branch_warns_when_the_remote_base_is_ahead(repo, tmp_path):
    init_project(repo)
    _work(repo)
    bare = tmp_path / "origin.git"
    sh(tmp_path, "git", "init", "-q", "--bare", "-b", "main", str(bare))
    repo.git("remote", "add", "origin", str(bare))
    repo.git("push", "-q", "origin", "main", "--no-verify")
    _, out = repo("work", "branch", "W-001")
    assert "⚠" not in out
    repo.git("checkout", "-q", "main")
    repo.git("branch", "-q", "-D", "work/W-001")
    other = tmp_path / "other"
    sh(tmp_path, "git", "clone", "-q", str(bare), str(other))
    sh(other, "git", "commit", "-q", "--allow-empty", "-m", "다른 사람의 커밋")
    sh(other, "git", "push", "-q", "origin", "main")
    _, out = repo("work", "branch", "W-001")
    assert "⚠" in out and "origin/main" in out and "git pull" in out


def test_the_build_skill_follows_the_branch_settings(repo):
    from lanternspec.core.profile import load
    from lanternspec.tools import get
    from lanternspec.tools.skills import generate

    init_project(repo)
    build = next(t for rel, t in generate(load(repo.root), [get("claude")]).items() if "l-build/" in rel)
    assert "머지는 하지 않는다" not in build and "<<" not in build and "lantern:if" not in build
    repo("profile", "set", "git.pr=work", "git.branch=feature/{id}")
    build = next(t for rel, t in generate(load(repo.root), [get("claude")]).items() if "l-build/" in rel)
    assert "머지는 하지 않는다" in build and "feature/{id}" in build


def _skill(repo, name, tool="claude"):
    from lanternspec.core.profile import load
    from lanternspec.tools import get
    from lanternspec.tools.skills import generate

    return next(t for rel, t in generate(load(repo.root), [get(tool)]).items() if f"{name}/SKILL.md" in rel)


def test_the_pr_skill_follows_the_branch_flow_and_is_only_called_by_a_person(repo):
    init_project(repo)
    text = _skill(repo, "l-pr")
    assert "disable-model-invocation: true" in text
    assert "git.pr: none" in text and "<<git" not in text and "lantern:if" not in text
    repo("profile", "set", "git.base=dev", "git.pr=deploy", "git.deploy=release")
    text = _skill(repo, "l-pr")
    assert "`dev` → `release`" in text and "git merge origin/release" in text and "git.pr: none" not in text
    repo("profile", "set", "git.pr=work")
    text = _skill(repo, "l-pr")
    assert "작업 브랜치 → `dev`" in text and "git merge origin/" not in text
    assert "gh pr create" in text and "gh pr merge" not in text
    assert "l-pr" in _skill(repo, "l-pr", "codex")


def test_check_pr_looks_at_the_title_and_the_code_commits(repo):
    init_project(repo)
    repo.git("add", "-A")
    commit(repo, "chore: 준비", check=True)
    repo.git("checkout", "-q", "-b", "work/W-001")
    write(repo, "src/a.py", "a = 1\n")
    repo.git("add", "src")
    commit(repo, "feat: 번호 없는 코드")
    write(repo, "docs/note.md", "메모\n")
    repo.git("add", "docs/note.md")
    commit(repo, "docs: 문서는 번호가 없어도 된다")
    _, out = repo("check-pr", "--title", "로그인", "--range", "main..HEAD")
    assert "PR 제목" in out and "번호 없는 코드" in out and "문서는 번호가" not in out and "경고만" in out
    write(repo, "src/b.py", "b = 1\n")
    repo.git("add", "src")
    commit(repo, "feat: 번호 있음 [W-001-T01]")
    repo.git("rebase", "-q", "--exec", "true", "main")
    _, out = repo("check-pr", "--title", "로그인 [W-001]", "--range", "HEAD~1..HEAD")
    assert "✔" in out
    # git.hooks: block fails the check
    repo("profile", "set", "git.hooks=block")
    code, out = repo("check-pr", "--title", "로그인", "--range", "HEAD~1..HEAD", ok=False)
    assert code == 1 and "✖" in out


def test_the_workflow_runs_check_pr_on_pull_requests_only(repo):
    import yaml

    init_project(repo)
    repo("install", "--ci")
    wf = yaml.safe_load((repo.root / ".github/workflows/lanternspec.yml").read_text(encoding="utf-8"))
    step = next(s for s in wf["jobs"]["docs-and-acceptance"]["steps"] if "check-pr" in s.get("run", ""))
    assert "pull_request" in step["if"] and "[bot]" in step["if"]
    assert step["env"]["PR_TITLE"] == "${{ github.event.pull_request.title }}"  # never pasted into the shell
    assert "$PR_TITLE" in step["run"] and "github.event" not in step["run"]


def test_the_pr_template_is_written_once_and_shared_with_the_skill(repo):
    init_project(repo)
    tpl = repo.root / ".github/pull_request_template.md"
    assert not tpl.exists()
    repo("install", "--pr-template")
    assert "## To Reviewer" in tpl.read_text(encoding="utf-8") and "Closes #" in tpl.read_text(encoding="utf-8")
    assert "## To Reviewer" in _skill(repo, "l-pr") and "<<pr.template>>" not in _skill(repo, "l-pr")
    tpl.write_text("우리 양식\n", encoding="utf-8")
    _, out = repo("install", "--pr-template")
    assert "그대로" in out and tpl.read_text(encoding="utf-8") == "우리 양식\n"
    _, out = repo("upgrade")
    assert tpl.read_text(encoding="utf-8") == "우리 양식\n"


def test_the_commit_template_is_written_once_and_guides_a_real_commit(repo, tmp_path):
    init_project(repo)
    repo("install", "--commit-template")
    tpl = repo.root / ".gitmessage"
    assert "enhance" in tpl.read_text(encoding="utf-8")
    assert repo.git("config", "commit.template").stdout.strip() == ".gitmessage"
    build = _skill(repo, "l-build")
    assert "enhance" in build and "<<commit" not in build
    assert "Co-Authored-By" in build  # the rule that keeps AI marks out of commit messages
    # the comments go away and an issue line stays
    editor = tmp_path / "editor.sh"
    editor.write_text('#!/bin/sh\n{ printf "feat: Add login [W-001-T01]\\n\\nRefs #12\\n"; cat "$1"; } > "$1.new" && mv "$1.new" "$1"\n')
    editor.chmod(0o755)
    repo.git("add", "-A")
    sh(repo.root, "env", f"GIT_EDITOR={editor}", "git", "commit", "-q")
    assert repo.git("log", "-1", "--format=%B").stdout.strip() == "feat: Add login [W-001-T01]\n\nRefs #12"
    # an edited template stays
    tpl.write_text("# 우리 양식\n", encoding="utf-8")
    _, out = repo("install", "--commit-template")
    assert "그대로" in out and tpl.read_text(encoding="utf-8") == "# 우리 양식\n"


def test_upgrade_after_init_carries_the_branch_flow_into_the_skills(repo):
    # /l-init writes the answers after the skills were installed, so it must remake them
    init_project(repo)
    repo("install")
    assert "git.pr: none" in (repo.root / ".claude/skills/l-pr/SKILL.md").read_text(encoding="utf-8")
    assert "lantern upgrade" in _skill(repo, "l-init").split("## 4.")[0]
    repo("profile", "set", "git.base=dev", "git.pr=work")
    repo("upgrade")
    assert "작업 브랜치 → `dev`" in (repo.root / ".claude/skills/l-pr/SKILL.md").read_text(encoding="utf-8")


def test_the_branch_flow_recommendation_follows_the_project_state():
    from lanternspec.work.branches import recommend_flow

    def flow(branches, remote=True, team="solo", origin="greenfield"):
        f = recommend_flow(branches, remote, team, origin)
        return f.recommended, "".join(f.choices)

    # no remote: nowhere to open a PR, and a new project with one branch has nothing to keep
    assert flow(["main"], remote=False) == ("A", "A")
    assert flow(["main"], remote=False, team="team") == ("A", "A")
    assert flow(["main", "dev"], remote=False) == ("A", "AD")
    # first matching line wins
    assert flow(["main"]) == ("A", "ABC")
    assert flow(["main", "dev"]) == ("B", "ABCD")
    assert flow(["main"], team="team") == ("C", "ABC")
    assert flow(["main", "dev"], team="team") == ("C", "ABCD")
    assert flow(["main", "dev", "release/1.2"]) == ("D", "ABCD")
    assert flow(["main", "hotfix/login"], team="team") == ("D", "ABCD")
    assert flow(["main", "develop"], remote=False) == ("D", "AD")
    assert flow(["main", "staging"]) == ("D", "ABCD")
    # branches that say nothing about the flow
    assert flow(["main", "docs-local", "work/W-001"]) == ("A", "ABC")
    assert flow(["main", "feature/JS-1"]) == ("A", "ABCD")
    # an existing project can always keep what it does
    assert flow(["main"], origin="brownfield") == ("A", "ABCD")
    assert recommend_flow(["master", "dev"], True, "solo", "brownfield").default_branch == "master"


def test_work_flow_reads_the_repository(repo):
    repo.git("branch", "dev")
    _, out = repo("work", "flow", "--team", "solo", "--origin", "greenfield")
    assert "추천: A" in out and "선택지: A D" in out  # no remote yet
    repo.git("remote", "add", "origin", "https://github.com/example/example.git")
    _, out = repo("work", "flow", "--team", "solo", "--origin", "greenfield")
    assert "추천: B" in out and "선택지: A B C D" in out and "기본 브랜치: main" in out and "dev" in out
    # a remote branch counts too
    sh(repo.root, "git", "update-ref", "refs/remotes/origin/release/1.0", "HEAD")
    _, out = repo("work", "flow", "--team", "team", "--origin", "brownfield")
    assert "추천: D" in out
    # a remote that isn't GitHub has no PR flow for /l-pr
    repo.git("remote", "set-url", "origin", "https://gitlab.example.com/a/b.git")
    repo.git("update-ref", "-d", "refs/remotes/origin/release/1.0")
    _, out = repo("work", "flow", "--team", "solo", "--origin", "greenfield")
    assert "추천: A" in out


def test_the_init_skill_leaves_the_recommendation_to_the_command(repo):
    init_project(repo)
    text = _skill(repo, "l-init")
    assert "lantern work flow --team" in text and "A. 단순하게" in text
    assert "release/*" not in text  # the rule itself lives only in the code
