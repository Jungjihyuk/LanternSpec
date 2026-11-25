"""`lantern upgrade` gives an older project's enums.yaml the lists and document types a newer version needs, and changes nothing else."""

import re

import pytest

from conftest import init_project, work_dir
from lanternspec.core.enums import add_list_in_text
from lanternspec.core.project import Project
from lanternspec.tools.components import notice

NEWER = ("component_status", "component_kind", "retro_result", "retro_check", "retro_weakness", "retro_remedy", "review_verdict")


def _older(repo, language: str = "ko") -> Project:
    """A project whose enums.yaml was made before the newer lists, with a list and a value of its own."""
    init_project(repo, "--language", language)
    project = Project.load(repo.root)
    text = project.enums_file.read_text(encoding="utf-8")
    for name in NEWER:
        text, n = re.subn(rf"^{name}:[ \t]*\n(?:[ \t].*\n|\n)*", "", text, flags=re.M)
        assert n == 1, name
    text = text.replace("    component: 🧩\n", "").replace("    infra:", "    mobile: 📱\n    infra:")
    project.enums_file.write_text(text.rstrip() + "\n\nmine:\n  values:\n    하나: 1️⃣  # 내 목록\n", encoding="utf-8")
    return Project.load(repo.root)


@pytest.mark.parametrize("language", ["ko", "en"])
def test_an_upgrade_adds_the_missing_lists_and_keeps_the_rest(repo, language):
    before = _older(repo, language)
    old_text = before.enums_file.read_text(encoding="utf-8")
    base_roles = {n: r for n, r in ((n, before.enums.get(n)) for n in NEWER) if r}
    assert not base_roles

    _, out = repo("upgrade")

    project = Project.load(repo.root)
    assert all(project.enums[n].values and set(project.enums[n].roles.values()) == set(project.enums[n].values) for n in NEWER)
    assert all(n in out for n in NEWER) and "component" in project.enums["doc_type"].values
    text = project.enums_file.read_text(encoding="utf-8")
    assert "# 내 목록" in text and "    mobile: 📱\n" in text
    assert [line for line in old_text.splitlines() if line not in text.splitlines()] == []  # nothing of it is gone

    _, again = repo("upgrade")
    assert "enums.yaml" not in again and project.enums_file.read_text(encoding="utf-8") == text


def test_what_uses_the_lists_works_after_the_upgrade(repo):
    _older(repo)
    assert "--weakness (없음)" in _built_skill(repo)
    repo("upgrade")

    assert "(없음)" not in re.findall(r"lantern retro note .*", _built_skill(repo))[0]
    repo("scaffold", "component", "qmd", "--kind", "mcp")
    _, out = repo("check", ok=False)
    assert "component" not in "\n".join(line for line in out.splitlines() if "✖" in line)
    repo("scaffold", "work", "작업")
    repo("scaffold", "doc", "W-001", "할 일")
    repo("task", "add", "W-001", "하나", "--size", "1h")
    assert (work_dir(repo, "W-001") / "할 일.md").exists()
    _, out = repo("retro", "note", "W-001-T01", "--stuck", "a", "--weakness", "환경", "--remedy", "연결 도구", "--hypothesis", "h")
    assert "[약점:: 환경]" in out


def _built_skill(repo) -> str:
    repo("install")
    return (repo.root / ".claude/skills/l-build/SKILL.md").read_text(encoding="utf-8")


def test_a_list_the_person_took_out_that_the_code_does_not_need_stays_out(repo):
    project = _older(repo)
    text = re.sub(r"^legacy_route:[ \t]*\n(?:[ \t].*\n|\n)*", "", project.enums_file.read_text(encoding="utf-8"), flags=re.M)
    project.enums_file.write_text(text, encoding="utf-8")
    repo("upgrade")
    assert Project.load(repo.root).enums.get("legacy_route") is None


def test_a_new_component_is_not_marked_as_told_when_it_could_not_be(repo):
    project = _older(repo)
    notice(project, {"mcp": ["a"]})
    with pytest.raises(LookupError):  # the new lantern before `lantern upgrade`
        notice(project, {"mcp": ["a", "b"]})
    repo("upgrade")
    assert "b" in notice(Project.load(repo.root), {"mcp": ["a", "b"]})


def test_a_list_is_copied_from_the_default_text():
    base = "version: 1\n\nsize:\n  label: 크기\n  values:\n    S: {icon: 🟢, role: s}\n\nother:\n  values:\n    A: 1\n"
    assert add_list_in_text("version: 1\n", base, "size") == ("version: 1\n\nsize:\n  label: 크기\n  values:\n    S: {icon: 🟢, role: s}\n")
    with pytest.raises(LookupError):
        add_list_in_text("version: 1\n", base, "없음")
