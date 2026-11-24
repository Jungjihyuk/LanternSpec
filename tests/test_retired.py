"""What earlier versions registered in the AI tools' settings is taken out, and nothing else is."""

import json

import pytest

from conftest import init_project
from lanternspec.cli import build_parser
from lanternspec.core.project import Project
from lanternspec.tools.retired import PLUGIN, TOML, clean, without_server, without_server_toml

SERVER = {"lantern-knowledge": {"command": "lantern", "args": ["mcp"]}}


def _old(repo) -> None:
    """The files as version 0.4.0 wrote them, next to the person's own entries."""
    (repo.root / ".mcp.json").write_text(json.dumps({"mcpServers": {**SERVER, "qmd": {"command": "qmd"}}}), encoding="utf-8")
    (repo.root / ".codex").mkdir(exist_ok=True)
    (repo.root / ".codex/config.toml").write_text(f'model = "x"\n\n{TOML}\n[mcp_servers.qmd]\ncommand = "qmd"\n', encoding="utf-8")
    plugin = repo.root / PLUGIN
    plugin.mkdir(parents=True)
    (plugin / "plugin.json").write_text(json.dumps({"name": "lanternspec"}, indent=2) + "\n", encoding="utf-8")
    (plugin / "mcp_config.json").write_text(json.dumps({"mcpServers": SERVER}), encoding="utf-8")


def test_an_upgrade_takes_the_server_out_of_every_tool_and_keeps_the_persons_own(repo):
    init_project(repo)
    _old(repo)

    _, out = repo("upgrade")

    assert json.loads((repo.root / ".mcp.json").read_text(encoding="utf-8")) == {"mcpServers": {"qmd": {"command": "qmd"}}}
    toml = (repo.root / ".codex/config.toml").read_text(encoding="utf-8")
    assert "lantern-knowledge" not in toml and "[mcp_servers.qmd]" in toml and 'model = "x"' in toml
    assert not (repo.root / ".agents/plugins").exists()
    assert out.count("lantern-knowledge") == 3  # each file is said once
    assert "lantern-knowledge" not in repo("upgrade")[1]  # and never again
    assert "mcp" not in json.loads((repo.root / ".lantern/installed.json").read_text(encoding="utf-8"))


def test_a_file_that_held_only_the_server_goes_with_it(repo):
    init_project(repo)
    (repo.root / ".mcp.json").write_text(json.dumps({"mcpServers": SERVER}), encoding="utf-8")
    clean(Project.load(repo.root))
    assert not (repo.root / ".mcp.json").exists()


@pytest.mark.parametrize(
    "entry", [{"command": "/opt/lantern", "args": ["mcp"]}, {"command": "lantern", "args": ["mcp"], "env": {"A": "1"}}, "broken"]
)
def test_an_entry_the_person_changed_stays_and_is_named(repo, entry):
    init_project(repo)
    text = json.dumps({"mcpServers": {"lantern-knowledge": entry}})
    (repo.root / ".mcp.json").write_text(text, encoding="utf-8")
    (line,) = clean(Project.load(repo.root))
    assert (repo.root / ".mcp.json").read_text(encoding="utf-8") == text and ".mcp.json" in line


def test_texts_that_are_not_what_was_written_are_left():
    assert without_server("{broken") is None and without_server("[]") is None and without_server('{"mcpServers": []}') is None
    for text in ('model = "x"\n', TOML + 'env = {A = "1"}\n', TOML + "\n[mcp_servers.lantern-knowledge.env]\nA = 1\n", "x" + TOML):
        assert without_server_toml(text) is None, text
    assert without_server_toml(TOML) == ""


def test_a_plugin_folder_with_anything_else_in_it_stays(repo):
    init_project(repo)
    _old(repo)
    (repo.root / PLUGIN / "mine.md").write_text("x", encoding="utf-8")
    clean(Project.load(repo.root))
    assert sorted(p.name for p in (repo.root / PLUGIN).iterdir()) == ["mine.md", "plugin.json"]


def test_there_is_no_server_command_or_option():
    import argparse

    commands = next(a for a in build_parser()._actions if isinstance(a, argparse._SubParsersAction)).choices
    assert "mcp" not in commands and "--mcp" not in commands["install"].format_help()
