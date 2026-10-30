"""profile · templating · frontmatter · ids — the pieces every skill relies on."""

import datetime as dt

import pytest
import yaml

from lanternspec.core import frontmatter, profile, templating
from lanternspec.core.profile import Profile, enabled_docs

# --------------------------------------------------------------------------- profile


def test_profile_render_roundtrip_and_spec_example(tmp_path):
    data = {
        "project": {"name": "소셜 가계부", "clients": ["mobile"], "server": "external", "members": ["지혁"]},
        "knowledge": {"type": "obsidian", "path": "~/vault", "areas_from": "2. Study"},
    }
    profile.save(tmp_path, data)
    loaded = profile.load(tmp_path)
    assert loaded.exists
    assert loaded.get("project.name") == "소셜 가계부"
    assert loaded.clients == ["mobile"]
    assert loaded.knowledge["write"] == "direct"
    assert profile.validate(loaded.data) == []
    text = (tmp_path / "lantern.yaml").read_text(encoding="utf-8")
    assert "# greenfield(새로) | brownfield(기존 코드 있음)" in text


def test_bare_off_in_yaml_means_the_word(tmp_path):
    # lantern.yaml writes `ui_reference: off` — YAML 1.1 would read False
    (tmp_path / "lantern.yaml").write_text("lantern: 1\nplan:\n  ui_reference: off\ndesign:\n  approval: off\n", encoding="utf-8")
    p = profile.load(tmp_path)
    assert p.get("plan.ui_reference") == "off"
    assert p.get("design.approval") == "off"
    assert profile.validate(p.data) == []


def test_validate_rejects_bad_values():
    data = profile._deep_merge(
        profile.DEFAULTS, {"plan": {"max_questions": 0}, "git": {"hooks": "loud"}, "project": {"clients": ["tv"], "team": "team"}}
    )
    problems = "\n".join(profile.validate(data))
    assert "plan.max_questions" in problems and "최소 1" in problems
    assert "git.hooks" in problems
    assert "'tv'" in problems
    assert "project.members" in problems


def test_set_in_text_keeps_comments():
    text = "git:\n  hooks: warn              # warn | block\n  base: dev\nplan:\n  max_questions: 3  # 최소 1\n"
    new = profile.set_in_text(text, "git.hooks", "block")
    assert "  hooks: block  # warn | block" in new
    assert "base: dev" in new
    new = profile.set_in_text(new, "plan.max_questions", 5)
    assert "max_questions: 5  # 최소 1" in new
    assert profile.set_in_text(text, "nope.key", 1) is None


def _keys(data):
    return {s.key for s in enabled_docs(Profile(data=profile._deep_merge(profile.DEFAULTS, data)))}


def test_enabled_docs_follow_the_08_table():
    solo = _keys({})
    assert {"project-definition", "features", "architecture", "data", "schema", "unit-log"} <= solo
    assert not solo & {"api", "server-ops", "collab", "meetings", "screens", "legacy", "debt-cards"}
    team = _keys({"project": {"team": "team", "members": ["a"]}})
    assert {"collab", "meetings"} <= team
    assert "api" not in _keys({"project": {"server": "external"}})
    assert "api" in _keys({"project": {"server": "external"}, "docs": {"extra": ["api"]}})
    custom = _keys({"project": {"server": "custom"}})
    assert {"api", "server-ops"} <= custom
    mobile = enabled_docs(Profile(data=profile._deep_merge(profile.DEFAULTS, {"project": {"clients": ["mobile", "web"]}})))
    deploy = next(s for s in mobile if s.key == "deploy")
    assert deploy.sections == ["mobile", "web"]
    assert "debt-cards" in _keys({"knowledge": {"path": "x"}})
    assert "legacy-map" in _keys({"project": {"origin": "brownfield"}})


# --------------------------------------------------------------------------- templating


def test_conditions_nested_inline_and_block():
    text = (
        "A\n<!-- lantern:if team -->\nTEAM\n<!-- lantern:if clients=web -->\nWEB\n<!-- lantern:endif -->\n"
        "<!-- lantern:endif -->\nB x<!-- lantern:if !team --> solo<!-- lantern:endif -->.\n"
    )
    assert templating.apply_conditions(text, {"team": True, "clients": ["web"]}) == "A\nTEAM\nWEB\nB x.\n"
    assert templating.apply_conditions(text, {"team": True, "clients": ["mobile"]}) == "A\nTEAM\nB x.\n"
    assert templating.apply_conditions(text, {"team": False, "clients": ["web"]}) == "A\nB x solo.\n"


def test_render_strips_template_only_and_based_on():
    tmpl = (
        "---\nid: ${id}\ntemplate: X\ntemplate_version: 1.0.0\nbased_on: 1.0.0\n---\n# ${name}\n"
        "{{칸 (필수)}}\n<!-- lantern:template-only -->\n## 변경 기록\n| 1.0.0 |\n"
    )
    out = templating.render(tmpl, {"id": "IDEA-001", "name": "이름"})
    assert "based_on" not in out
    assert "변경 기록" not in out
    assert "# 이름" in out and "id: IDEA-001" in out
    assert templating.placeholders(out, "(필수)") == [("칸 (필수)", True, 7)]


# --------------------------------------------------------------------------- frontmatter


def test_set_fields_preserves_other_lines_and_touches_updated():
    text = "---\nid: X\n# 주석\nstatus: 기획  \nlinks:\n  - a\nupdated: 2020-01-01\n---\n본문\n"
    new = frontmatter.set_fields(text, {"status": "설계", "approved": "2026-10-27 지혁"})
    assert "# 주석" in new and "links:\n  - a" in new
    meta = frontmatter.parse(new).meta
    assert meta["status"] == "설계" and meta["approved"] == "2026-10-27 지혁"
    assert meta["updated"] == dt.date.today()
    assert new.endswith("본문\n")
    gone = frontmatter.set_fields(new, {"approved": frontmatter.DELETE}, touch=False)
    assert "approved" not in gone


def test_render_is_block_style_with_inline_lists():
    out = frontmatter.render({"id": "X", "links": ["[[a|b]]"], "stats": {"open": 1}, "updated": "2026-10-27"}, "b")
    meta = yaml.safe_load(out.split("---")[1])
    assert meta == {"id": "X", "links": ["[[a|b]]"], "stats": {"open": 1}, "updated": dt.date(2026, 10, 27)}
    assert "{id" not in out


def test_frontmatter_error_is_reported():
    doc = frontmatter.parse("---\nid: [unclosed\n---\nbody")
    assert doc.error and "YAML" in doc.error


# --------------------------------------------------------------------------- ids


def test_ids_are_sequential_and_typed(repo):
    from conftest import init_project

    init_project(repo)
    assert repo("new-id", "idea")[1].strip() == "IDEA-001"
    repo("scaffold", "idea", "하나")
    repo("scaffold", "idea", "둘")
    assert repo("new-id", "idea")[1].strip() == "IDEA-003"
    repo("scaffold", "work", "작업")
    assert repo("new-id", "work")[1].strip() == "W-002"
    assert repo("new-id", "adr")[1].strip() == "ADR-001"
    assert repo("new-id", "debt")[1].strip() == "D-001"
    repo("scaffold", "doc", "W-001", "할 일")
    repo("task", "add", "W-001", "첫 일", "--size", "S")
    assert repo("new-id", "task", "W-001")[1].strip() == "W-001-T02"
    # a reserved work branch also counts
    repo.git("branch", "work/W-007")
    assert repo("new-id", "work")[1].strip() == "W-008"


def test_skill_names_follow_the_rule():
    from lanternspec.tools.skills import SKILL_NAMES, validate_name

    assert len(SKILL_NAMES) == 14
    for n in SKILL_NAMES:
        validate_name(n)
    for bad in ("l:init", "-l", "l--x", "L-init", "x" * 65):
        with pytest.raises(ValueError):
            validate_name(bad)
