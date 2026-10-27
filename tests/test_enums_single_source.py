"""enums.yaml 한 곳에서 상태 이름 · 아이콘을 바꾸면 코드 출력 · 카드 · 스킬 · 템플릿 · 검사가 모두 따라간다."""

import re

from conftest import docs, init_project
from lanternspec import resources
from lanternspec.core import enums as enums_mod
from lanternspec.core import frontmatter


def _enums_file(repo):
    return docs(repo) / "0. 템플릿/_meta/enums.yaml"


def test_every_enum_token_in_skills_and_templates_resolves():
    ctx = enums_mod.load().context()
    names = set(enums_mod.load().enums)
    for _, p in list(resources.iter_files("skills")) + list(resources.iter_files("templates")):
        text = p.read_text(encoding="utf-8")
        for tok in re.findall(r"<<([a-z_.]+)>>|\$\{([a-z_.]+)\}", text):
            key = tok[0] or tok[1]
            if "." in key and key.split(".")[0] in names:
                assert key in ctx, f"{p.name}: {key}"
    assert enums_mod.load().problems() == []


def test_icon_change_and_rename_follow_everywhere(repo, vault):
    repo("install")
    init_project(repo, vault=vault)
    repo("debt", "new", "CRDT", "--area", "data", "--session", "s1")
    repo("debt", "ask", "CRDT", "--session", "s2")
    card = next((docs(repo) / "📒 부채/카드").glob("D-001*.md"))
    assert frontmatter.parse(card.read_text(encoding="utf-8")).meta["status"] == "되물음"

    # 1) icon only: edit enums.yaml → CLI output and (after upgrade) skills follow
    f = _enums_file(repo)
    f.write_text(f.read_text(encoding="utf-8").replace("되물음: {icon: 🤔", "되물음: {icon: 💬"), encoding="utf-8")
    _, out = repo("debt", "list")
    assert "💬 되물음" in out
    repo("upgrade")
    assert "💬 되물음" in (repo.root / ".claude/skills/l-learn/SKILL.md").read_text(encoding="utf-8")

    # 2) rename: one command changes enums.yaml, stored values, skills and generated pages
    _, out = repo("enums", "rename", "debt_status", "되물음", "다시 물음")
    assert "문서 1개" in out
    assert frontmatter.parse(card.read_text(encoding="utf-8")).meta["status"] == "다시 물음"
    skill = (repo.root / ".claude/skills/l-learn/SKILL.md").read_text(encoding="utf-8")
    assert "💬 다시 물음" in skill and "되물음" not in skill
    assert "다시 물음" in (docs(repo) / "📒 부채/부채 현황.md").read_text(encoding="utf-8")
    repo("debt", "ask", "CRDT", "--session", "s3")  # the code finds the value by role, not by name
    assert frontmatter.parse(card.read_text(encoding="utf-8")).meta["status"] == "다시 물음"
    code, out = repo("check", ok=False)
    assert "enum" not in out and code == 0

    # 3) work stages: a renamed stage is what task start writes, and new docs get it from the template
    repo("enums", "rename", "work_status", "구현", "개발")
    repo("scaffold", "work", "로그인")
    repo("scaffold", "doc", "W-001", "할 일")
    repo("task", "add", "W-001", "버튼", "--size", "S")
    repo("task", "start", "W-001-T01")
    plan = docs(repo) / "2. 작업/W-001 로그인/기획.md"
    assert frontmatter.parse(plan.read_text(encoding="utf-8")).meta["status"] == "개발"
    repo("scaffold", "doc", "W-001", "기록")
    rec = docs(repo) / "2. 작업/W-001 로그인/기록.md"
    assert frontmatter.parse(rec.read_text(encoding="utf-8")).meta["status"] == "개발"
    code, out = repo("check", ok=False)
    assert code == 0, out


def test_a_missing_role_is_reported(repo):
    init_project(repo)
    f = _enums_file(repo)
    # renamed by hand and the role dropped with it: the code can no longer find "resolved"
    f.write_text(f.read_text(encoding="utf-8").replace("해결: {icon: ✅, role: resolved}", "끝: ✅"), encoding="utf-8")
    code, out = repo("doctor", ok=False)
    assert "debt_status: role 'resolved'" in out and code == 1
    code, out = repo("enums", "list", "debt_status", ok=False)
    assert code == 1 and "✖" in out
