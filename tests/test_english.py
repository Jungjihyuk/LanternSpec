"""The English language pack: nothing Korean in it, the same structure as the Korean pack, and a project that works end to end."""

import re

import pytest
import yaml

from conftest import sh
from lanternspec import resources
from lanternspec.core import frontmatter
from lanternspec.core.names import localize
from lanternspec.core.profile import DEFAULTS, Profile, _deep_merge
from lanternspec.tools import resolve
from lanternspec.tools.rules import agents_block
from lanternspec.tools.skills import SKILL_NAMES, generate

HANGUL = re.compile("[가-힣]")


def _pack_files(language):
    return [p for _, p in resources.iter_files(f"locales/{language}")]


def test_the_english_pack_has_no_korean():
    files = _pack_files("en")
    assert len(files) == len(_pack_files("ko"))
    for p in files:
        lines = [f"{i}: {l}" for i, l in enumerate(p.read_text(encoding="utf-8").split("\n"), 1) if HANGUL.search(l)]
        assert not lines, f"{p.name}:\n" + "\n".join(lines[:5])


@pytest.mark.parametrize(
    "rel", ["names.yaml", "principles.yaml", *(f"conventions/{p.name}" for _, p in resources.iter_files("conventions"))]
)
def test_english_text_in_the_tables_has_no_korean(rel):
    english = localize(yaml.safe_load(resources.read_text(rel)), "en")
    found = [s for s in re.findall(r"'([^']*)'", repr(english)) if HANGUL.search(s)]
    assert not found, f"{rel}: {found[:5]}"


def _structure(text):
    """What must match between languages: conditions, tokens and the commands a skill runs."""
    conditions = re.findall(r"<!-- lantern:[^>]*-->", text)
    tokens = sorted(set(re.findall(r"<<[a-z_.A-Z]+>>", text)))
    commands = sorted({" ".join(m.split()[:2]) for m in re.findall(r"(?:`|^\s*)(lantern [a-z-]+)", text, re.M)})
    return conditions, tokens, commands


@pytest.mark.parametrize("rel", [*(f"skills/{n}/SKILL.md" for n in SKILL_NAMES), "agents/AGENTS.md"])
def test_english_skills_match_the_korean_ones(rel):
    ko = resources.read_text(f"locales/ko/{rel}")
    en = resources.read_text(f"locales/en/{rel}")
    for what, a, b in zip(("conditions", "tokens", "commands"), _structure(ko), _structure(en), strict=True):
        assert a == b, f"{rel} {what}: {set(a) ^ set(b)}"
    assert frontmatter.parse(ko).meta.keys() == frontmatter.parse(en).meta.keys()


def test_installed_english_skills_and_rules_have_no_korean():
    data = {
        "project": {"language": "en", "kind": "cli", "external": True, "languages": ["python", "go"], "team": "team", "members": ["Ana"]}
    }
    profile = Profile(data=_deep_merge(DEFAULTS, {**data, "knowledge": {"path": "x"}}))
    files = generate(profile, resolve(["claude", "codex"]))
    files["AGENTS.md"] = agents_block(profile, resolve(["claude"]))
    for rel, text in files.items():
        found = [l for l in text.split("\n") if HANGUL.search(l)]
        assert not found, f"{rel}: {found[:3]}"


def test_an_english_project_end_to_end(repo):
    repo("install", "--language", "en")
    assert "Set up LanternSpec" in (repo.root / ".claude/skills/l-init/SKILL.md").read_text(encoding="utf-8")
    repo("profile", "write", "--name", "Budget", "--origin", "greenfield", "--team", "solo", "--clients", "web", "--server", "none")
    assert yaml.safe_load((repo.root / "lantern.yaml").read_text(encoding="utf-8"))["project"]["language"] == "en"
    repo("scaffold", "init")
    docs = repo.root / "docs"
    assert (docs / "0. Templates/Plan.md").exists() and (docs / "3. Current State/Project Definition.md").exists()
    assert "Inactive" in (docs / "0. Templates/_meta/enums.yaml").read_text(encoding="utf-8")
    repo("scaffold", "work", "Sign in")
    repo("scaffold", "doc", "W-001", "Tasks")
    repo("scaffold", "doc", "W-001", "log")
    work = docs / "2. Work/W-001 Sign in"
    assert (work / "Plan.md").exists() and (work / "Log.md").exists()
    assert frontmatter.parse((work / "Plan.md").read_text(encoding="utf-8")).meta["status"] == "Plan"
    repo("task", "add", "W-001", "Sign-in button", "--size", "S", "--ac", "AC-1")
    tasks = (work / "Tasks.md").read_text(encoding="utf-8")
    assert "- [ ] W-001-T01 Sign-in button [size:: S] [ac:: AC-1]" in tasks and "{{Task" not in tasks
    repo("task", "start", "W-001-T01")
    assert "[started:: " in (work / "Tasks.md").read_text(encoding="utf-8")
    _, out = repo("check", str(work / "Plan.md"))
    assert "At a glance (required)" in out

    # protected sections are found by their English titles
    from lanternspec.core.project import Project
    from lanternspec.work.progress import save_before_compact

    saved = save_before_compact(Project.load(repo.root))
    log = (work / "Log.md").read_text(encoding="utf-8")
    assert work / "Log.md" in saved and log.count("## Now") == 1 and "## 지금 상황" not in log

    # the language is fixed once lantern.yaml exists
    code, out = repo("install", "--language", "ko", ok=False)
    assert code == 1 and "'en'" in out
    sh(repo.root, "git", "status")
