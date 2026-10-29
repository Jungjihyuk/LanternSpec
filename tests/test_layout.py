"""Documents follow names.yaml: an older layout is moved to the current one by `lantern upgrade --apply`.

Each document is found by its frontmatter id, so the move works from any older layout. `lantern upgrade`
alone only shows what would move; `--apply` moves with git (history continues), rewrites the links that
would break, and makes one commit.
"""

import pytest

from conftest import docs, init_project, sh

OLD = "3. 현재 상태/규칙 · 결정 기록"  # the 0.1.2 folder that held both rules and decisions


def _git(r, *args):
    return r.git(*args).stdout.strip()


def _old_layout(r, *extra):
    """Build a project, then put it back into the 0.1.2 layout and commit it."""
    init_project(r, "--team", "team", "--members", "지혁,민수", *extra)
    r("scaffold", "adr", "인증 방식")
    d = docs(r)
    (d / OLD).mkdir(parents=True)
    log = (d / "3. 현재 상태/규칙/작업 나누기 기준.md").read_text(encoding="utf-8")
    log = log.replace("template: 작업 나누기 기준", "template: 작업 단위 기록")
    (d / OLD / "작업 단위 기록.md").write_text(log, encoding="utf-8")
    (d / "3. 현재 상태/규칙/작업 나누기 기준.md").unlink()
    (d / "3. 현재 상태/규칙/협업 규칙.md").rename(d / OLD / "협업 규칙.md")
    (d / "3. 현재 상태/결정 기록/ADR-001 인증 방식.md").rename(d / OLD / "ADR-001 인증 방식.md")
    (d / "3. 현재 상태/배포 · 운영/배포.md").rename(d / "3. 현재 상태/배포.md")
    for empty in ("3. 현재 상태/규칙", "3. 현재 상태/결정 기록", "3. 현재 상태/배포 · 운영"):
        (d / empty).rmdir()
    _old_template_copy(r, d)
    features = d / "3. 현재 상태/기능 목록.md"
    features.write_text(
        features.read_text(encoding="utf-8")
        + f"\n- 기준: [[{OLD}/작업 단위 기록|작업 나누기]]\n- 결정: [[ADR-001 인증 방식]]\n- 배포: [배포](배포.md)\n",
        encoding="utf-8",
    )
    r.git("add", "-A")
    r.git("commit", "-q", "-m", "docs: 0.1.2 layout")
    return d


def _old_template_copy(r, d):
    """The project's copy of the template under its 0.1.2 name, recorded as unedited."""
    from lanternspec.core import state
    from lanternspec.core.project import Project

    new = d / "0. 템플릿/작업 나누기 기준.md"
    text = new.read_text(encoding="utf-8").replace("template: 작업 나누기 기준", "template: 작업 단위 기록")
    (d / "0. 템플릿/작업 단위 기록.md").write_text(text, encoding="utf-8")
    new.unlink()
    project = Project.load(r.root)
    st = state.load(project)
    rec = st["templates"].pop("작업 나누기 기준")
    st["templates"]["작업 단위 기록"] = {**rec, "sha256": state.sha256_text(text)}
    state.save(project, st)


def test_upgrade_shows_the_moves_and_changes_nothing(repo):
    d = _old_layout(repo)
    head = _git(repo, "rev-parse", "HEAD")
    _, out = repo("upgrade")
    assert "📦 문서 5개" in out and "lantern upgrade --apply" in out
    assert f"{OLD}/ADR-001 인증 방식.md → 3. 현재 상태/결정 기록/ADR-001 인증 방식.md" in out
    assert "작업 단위 기록 → 작업 나누기 기준" in out  # the old template name is shown too
    assert _git(repo, "rev-parse", "HEAD") == head and not _git(repo, "status", "--porcelain")
    assert (d / OLD / "ADR-001 인증 방식.md").exists() and not (d.parent / "AGENTS.md").exists()  # nothing installed either


def test_apply_moves_with_history_rewrites_links_and_commits_once(repo):
    d = _old_layout(repo)
    _, out = repo("upgrade", "--apply")
    assert "문서 5개를 옮기고 링크 2곳을 고쳤습니다" in out
    assert (d / "3. 현재 상태/결정 기록/ADR-001 인증 방식.md").exists()
    assert (d / "3. 현재 상태/배포 · 운영/배포.md").exists()
    rules = d / "3. 현재 상태/규칙/작업 나누기 기준.md"
    assert "template: 작업 나누기 기준" in rules.read_text(encoding="utf-8")
    assert not (d / OLD).exists()  # no empty old folder left
    features = (d / "3. 현재 상태/기능 목록.md").read_text(encoding="utf-8")
    assert "[[3. 현재 상태/규칙/작업 나누기 기준|작업 나누기]]" in features
    assert "[[ADR-001 인증 방식]]" in features  # a bare name still finds the file: left alone
    assert "[배포](배포 · 운영/배포.md)" in features
    log = _git(repo, "log", "--follow", "--format=%s", "--", "docs/3. 현재 상태/결정 기록/ADR-001 인증 방식.md")
    assert log.splitlines() == ["docs: 문서를 지금 구조의 위치로 옮김 [lantern]", "docs: 0.1.2 layout"]  # history continues
    changed = _git(repo, "-c", "core.quotepath=false", "show", "--name-only", "--format=", "HEAD").splitlines()
    assert changed and all(p.startswith("docs/") for p in changed)  # the commit holds only the move
    assert (repo.root / "AGENTS.md").exists()  # then the usual upgrade went on
    _, again = repo("upgrade")
    assert "📦" not in again and "--apply" not in again


def test_apply_refuses_while_documents_have_uncommitted_changes(repo):
    d = _old_layout(repo)
    (d / "1. 아이디어/메모.md").write_text("# 메모\n", encoding="utf-8")
    code, out = repo("upgrade", "--apply", ok=False)
    assert code != 0 and "커밋하지 않은 변경" in out
    assert (d / OLD / "ADR-001 인증 방식.md").exists()


def test_a_taken_place_is_left_for_a_person_while_the_rest_moves(repo):
    d = _old_layout(repo)
    (d / "3. 현재 상태/배포 · 운영").mkdir()
    (d / "3. 현재 상태/배포 · 운영/배포.md").write_text("# 손으로 만든 배포\n", encoding="utf-8")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "docs: a hand-made deploy doc")
    _, out = repo("upgrade", "--apply")
    assert "이미 파일이 있습니다" in out
    assert (d / "3. 현재 상태/배포.md").exists()  # not moved over the other one
    assert (d / "3. 현재 상태/결정 기록/ADR-001 인증 방식.md").exists()


def test_apply_in_local_mode_commits_on_the_docs_branch(repo):
    from lanternspec.core.project import git_version

    if git_version(repo.root) < (2, 42, 0):
        pytest.skip("git 2.42+ needed for worktree --orphan")
    d = _old_layout(repo)
    repo("docs-mode", "local")
    code_head = _git(repo, "rev-parse", "HEAD")
    repo("upgrade", "--apply")
    assert (d / "3. 현재 상태/결정 기록/ADR-001 인증 방식.md").exists()
    assert sh(d, "git", "log", "-1", "--format=%s").stdout.strip() == "docs: 문서를 지금 구조의 위치로 옮김 [lantern]"
    assert sh(d, "git", "rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == "docs-local"
    assert _git(repo, "rev-parse", "HEAD") == code_head  # the code branch got no commit


def test_the_legacy_map_gets_its_links_fixed_but_legacy_originals_stay_as_they_were(repo):
    d = _old_layout(repo, "--origin", "brownfield")
    legacy = d / "5. 기존 문서"
    (legacy / "옛 설계.md").write_text("# 옛 설계\n- 배포: [[3. 현재 상태/배포]]\n", encoding="utf-8")
    legacy_map = legacy / "기존 문서 지도.md"
    legacy_map.write_text(legacy_map.read_text(encoding="utf-8") + "\n- 흡수: [[3. 현재 상태/배포]]\n", encoding="utf-8")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "docs: brownfield")
    repo("upgrade", "--apply")
    assert "[[3. 현재 상태/배포 · 운영/배포]]" in legacy_map.read_text(encoding="utf-8")
    assert "[[3. 현재 상태/배포]]" in (legacy / "옛 설계.md").read_text(encoding="utf-8")  # originals are never edited


def test_documents_never_committed_get_a_clear_message(repo):
    d = _old_layout(repo)
    repo.git("update-ref", "-d", "HEAD")  # as if the documents' branch had no commit yet
    code, out = repo("upgrade", "--apply", ok=False)
    assert code != 0 and "한 번도 커밋되지 않았습니다" in out
    assert (d / OLD / "ADR-001 인증 방식.md").exists()


def test_a_renamed_template_copy_follows_and_is_refreshed_when_nobody_edited_it(repo):
    d = _old_layout(repo)
    repo("upgrade", "--apply")
    assert not (d / "0. 템플릿/작업 단위 기록.md").exists()
    copy = (d / "0. 템플릿/작업 나누기 기준.md").read_text(encoding="utf-8")
    assert "template: 작업 나누기 기준" in copy and "template_version: 1.1.0" in copy
    _, out = repo("template", "list")
    assert "작업 나누기 기준  v1.1.0  (기본 양식)" in out and "작업 단위 기록" not in out
