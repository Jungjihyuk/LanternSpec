"""The component card: why an MCP server, plugin, skill or hook was added and what it should achieve; and noticing new ones.

A card is a decision-record-like document (`CMP-001 …`) in the decisions folder. At the start of a conversation lantern
tells the AI about an MCP server or plugin that was not there before (once, and only when it has no card yet).
"""

import json

import pytest

from conftest import init_project
from lanternspec.core import frontmatter
from lanternspec.core.new_id import next_id
from lanternspec.core.project import Project, read
from lanternspec.report import components as components_report
from lanternspec.tools import agent_hooks, get, health
from lanternspec.tools.components import notice
from lanternspec.work import scaffold


def _project(repo) -> Project:
    init_project(repo)
    return Project.load(repo.root)


def _mcp(project: Project, *names: str) -> None:
    (project.root / ".mcp.json").write_text(json.dumps({"mcpServers": {n: {"command": "x"} for n in names}}), encoding="utf-8")


# --------------------------------------------------------------------------- the card


def test_component_cards_have_their_own_numbers_apart_from_decisions(repo):
    project = _project(repo)
    assert next_id(project, "component") == "CMP-001"
    scaffold.new_component_card(project, "obsidian", "mcp")
    assert next_id(project, "component") == "CMP-002" and next_id(project, "adr") == "ADR-001"


def test_a_card_is_made_in_the_decisions_folder_with_its_component_and_a_watching_status(repo):
    project = _project(repo)

    dest = scaffold.new_component_card(project, "obsidian", "mcp")

    meta = frontmatter.parse(read(dest)).meta
    assert dest.parent == project.folder("decisions") and dest.name == "CMP-001 obsidian.md"
    assert meta["id"] == "CMP-001" and meta["type"] == "component" and meta["component"] == "obsidian"
    assert meta["kind"] == project.enums.value("component_kind", "mcp")
    assert meta["status"] == project.enums.value("component_status", "watching")
    assert "{{" in read(dest)  # blanks for the person (the reason, the expected effect, what to measure, when to look again)


def test_a_card_for_an_unknown_kind_is_refused(repo):
    project = _project(repo)
    with pytest.raises(ValueError, match="foo"):
        scaffold.new_component_card(project, "x", "foo")


def test_the_scaffold_command_makes_a_card(repo):
    init_project(repo)
    _, out = repo("scaffold", "component", "obsidian", "--kind", "mcp")
    assert "✔" in out and "CMP-001 obsidian.md" in out
    _, out = repo("check")
    block = out.split("CMP-001 obsidian.md")[1].split("📄")[0]
    assert "✖" not in block and "필수 칸이 비어 있습니다" in block  # a fresh card is a draft: blanks are warnings, not errors


def test_component_kinds_are_named_by_the_choice_list_not_by_the_report(repo):
    project = _project(repo)
    assert components_report.kind_label("mcp", project.enums) == project.enums.value("component_kind", "mcp")
    assert components_report.kind_label("unknown", project.enums) == "unknown"


# --------------------------------------------------------------------------- noticing a new component


def test_the_first_conversation_only_takes_stock_and_a_later_new_server_is_told_once(repo):
    project = _project(repo)
    _mcp(project, "obsidian")
    assert notice(project, {"mcp": ["obsidian"]}) == ""  # what was already there is not asked about

    _mcp(project, "obsidian", "qmd")
    text = notice(project, {"mcp": ["obsidian", "qmd"]})

    assert "qmd" in text and "obsidian" not in text
    assert 'scaffold component "qmd" --kind mcp' in text
    assert notice(project, {"mcp": ["obsidian", "qmd"]}) == ""  # once


def test_a_component_that_already_has_a_card_is_not_asked_about(repo):
    project = _project(repo)
    notice(project, {"mcp": ["obsidian"]})
    scaffold.new_component_card(project, "qmd", "mcp")

    assert notice(project, {"mcp": ["obsidian", "qmd"]}) == ""


def test_only_mcp_servers_and_plugins_are_asked_about(repo):
    project = _project(repo)
    notice(project, {"mcp": ["obsidian"]})

    text = notice(project, {"mcp": ["obsidian"], "plugin": ["memo@market"], "skill": ["new-skill"], "hook": ["Stop"]})

    assert "memo@market" in text and "--kind plugin" in text
    assert "new-skill" not in text and "Stop" not in text


def test_no_components_and_a_broken_state_file_give_no_note_and_no_error(repo):
    project = _project(repo)
    assert notice(project, {}) == ""
    (project.state / "components-seen.json").write_text("{broken", encoding="utf-8")
    assert notice(project, {"mcp": ["qmd"]}) == ""  # it takes stock again instead of failing


def test_session_start_hands_the_ai_a_line_about_a_new_server(repo, monkeypatch):
    project = _project(repo)
    monkeypatch.setattr(health, "installed_version", lambda tool, timeout=10: "2.1.323")
    _mcp(project, "obsidian")
    start = json.dumps({"session_id": "s1", "source": "startup"})
    agent_hooks.run(project, "session-start", get("claude"), start)
    _mcp(project, "obsidian", "qmd")

    reply = agent_hooks.run(project, "session-start", get("claude"), json.dumps({"session_id": "s2", "source": "startup"}))

    assert 'scaffold component \\"qmd\\"' in str(reply) or 'scaffold component "qmd"' in str(reply)
    again = agent_hooks.run(project, "session-start", get("claude"), json.dumps({"session_id": "s3", "source": "startup"}))
    assert "scaffold component" not in str(again)


def test_a_card_is_not_asked_for_after_compaction(repo, monkeypatch):
    project = _project(repo)
    monkeypatch.setattr(health, "installed_version", lambda tool, timeout=10: "2.1.323")
    _mcp(project, "obsidian")
    agent_hooks.run(project, "session-start", get("claude"), json.dumps({"session_id": "s1", "source": "startup"}))
    _mcp(project, "obsidian", "qmd")

    reply = agent_hooks.run(project, "session-start", get("claude"), json.dumps({"session_id": "s1", "source": "compact"}))

    assert "scaffold component" not in str(reply)  # the same conversation: it was not a new start


def test_the_record_of_seen_components_is_a_personal_file_that_git_never_gets(repo):
    from lanternspec.core.state import IGNORED

    project = _project(repo)
    assert "components-seen.json" in IGNORED

    notice(project, {"mcp": ["obsidian"]})  # the first conversation writes the file

    assert (project.state / "components-seen.json").exists()
    assert "components-seen.json" in (project.state / ".gitignore").read_text(encoding="utf-8").splitlines()
    ignored = repo.git("check-ignore", str(project.state / "components-seen.json"), check=False)
    assert ignored.returncode == 0  # git itself agrees
