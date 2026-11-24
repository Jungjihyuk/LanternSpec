"""The project definition's table of /l-init answers follows lantern.yaml, and nothing else in the document changes."""

import pytest

from conftest import docs, init_project
from lanternspec.core import profile as pm
from lanternspec.core.names import load
from lanternspec.core.project import Project
from lanternspec.work.scaffold import refresh_profile_table


def _definition(repo):
    return docs(repo) / "3. 현재 상태" / "프로젝트 정의서.md"


def _edit(repo, old: str, new: str) -> None:
    path = _definition(repo)
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new), encoding="utf-8")


def _no_store_then_notion(repo) -> None:
    """A project set up without a knowledge store, whose lantern.yaml then gets Notion."""
    init_project(repo)
    data = pm.load(repo.root).data
    data["knowledge"] = None
    pm.save(repo.root, data)
    repo("scaffold", "init")
    assert "| 지식 저장소 | 없음" in _definition(repo).read_text(encoding="utf-8")
    data["knowledge"] = {"type": "notion", "path": "abc", "write": "direct"}
    pm.save(repo.root, data)


@pytest.mark.parametrize("command", [("scaffold", "init"), ("upgrade",)])
def test_the_table_follows_lantern_yaml_and_the_rest_stays(repo, command):
    _no_store_then_notion(repo)
    _edit(repo, "{{주 사용자와 문제 (필수)}}", "내가 쓴 글 | 표가 아님")
    before = _definition(repo).read_text(encoding="utf-8")

    _, out = repo(*command)

    after = _definition(repo).read_text(encoding="utf-8")
    assert "| 지식 저장소 | notion · `abc` |" in after and "프로젝트 정의서" in out
    changed = [(a, b) for a, b in zip(before.splitlines(), after.splitlines(), strict=True) if a != b]
    assert all(a.startswith(("| 지식 저장소 ", "updated:")) for a, _ in changed)


def test_nothing_is_written_when_the_table_is_already_right(repo):
    init_project(repo)
    path = _definition(repo)
    before = path.read_text(encoding="utf-8")
    assert refresh_profile_table(Project.load(repo.root)) is None
    assert path.read_text(encoding="utf-8") == before


def test_a_document_without_frontmatter_gets_none(repo):
    _no_store_then_notion(repo)
    path = _definition(repo)
    path.write_text("# 정의서\n\n## 프로젝트 성격" + path.read_text(encoding="utf-8").split("## 프로젝트 성격", 1)[1], encoding="utf-8")
    refresh_profile_table(Project.load(repo.root))
    text = path.read_text(encoding="utf-8")
    assert text.startswith("# 정의서") and "notion" in text


def test_a_row_the_person_added_stays(repo):
    _no_store_then_notion(repo)
    _edit(repo, "| 문서 저장 |", "| 배포처 | 사내 |\n| 문서 저장 |")
    repo("scaffold", "init")
    text = _definition(repo).read_text(encoding="utf-8")
    assert "| 배포처 | 사내 |" in text and "notion" in text


def test_a_table_taken_out_or_reshaped_is_left_alone(repo):
    _no_store_then_notion(repo)
    _edit(repo, "| 질문 | 답 |", "| 항목 | 내용 | 메모 |")
    before = _definition(repo).read_text(encoding="utf-8")
    repo("scaffold", "init")
    assert _definition(repo).read_text(encoding="utf-8") == before

    _edit(repo, "## 프로젝트 성격", "## 성격")  # the section itself has another name now, and the project was not told
    before = _definition(repo).read_text(encoding="utf-8")
    repo("scaffold", "init")
    assert _definition(repo).read_text(encoding="utf-8") == before

    _definition(repo).unlink()
    assert refresh_profile_table(Project.load(repo.root)) is None  # no document: nothing to refresh


def test_a_renamed_section_is_still_found_and_one_not_used_is_left_alone(repo):
    _no_store_then_notion(repo)
    repo("sections", "rename", "project_profile", "우리 프로젝트")
    repo("scaffold", "init")
    assert "notion · `abc`" in _definition(repo).read_text(encoding="utf-8")

    data = pm.load(repo.root).data
    data["knowledge"] = None
    pm.save(repo.root, data)
    repo("sections", "off", "project_profile")
    repo("scaffold", "init")
    assert "notion · `abc`" in _definition(repo).read_text(encoding="utf-8")


def test_the_section_is_a_protected_one_in_both_languages():
    assert load("ko").section("project_profile").docs == load("en").section("project_profile").docs == ("project_definition",)
