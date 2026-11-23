"""The tools and add-ons a session ran with: read from the AI tool's settings, logged at session start, shown by `lantern eval`.

Only names are kept (never a command, an address or a variable), and a settings file that is missing or broken
never stops a hook.
"""

import json
from pathlib import Path

from conftest import init_project
from lanternspec.core.project import Project
from lanternspec.report import evaluate
from lanternspec.tools import agent_hooks, get, health


def _json(path: Path, data: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _log(project: Project, records: list[dict]) -> None:
    project.state.mkdir(parents=True, exist_ok=True)
    (project.state / "runs.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")


def _session(sid: str, start: str, components: dict | None, harness: str = "claude") -> dict:
    rec = {"kind": "session", "session": sid, "start": start, "harness": harness}
    if components is not None:
        rec["components"] = components
    return rec


def _turn(sid: str, tools: dict[str, int]) -> dict:
    return {"kind": "turn", "session": sid, "tools": tools, "tool_calls": sum(tools.values())}


# --------------------------------------------------------------------------- reading the AI tool's settings


def test_claude_reads_the_names_of_mcp_servers_from_the_project_and_the_local_scope(repo):
    init_project(repo)
    project = Project.load(repo.root)
    _json(project.root / ".mcp.json", {"mcpServers": {"qmd": {"command": "qmd", "env": {"TOKEN": "secret"}}}})
    _json(Path.home() / ".claude.json", {"projects": {str(project.root): {"mcpServers": {"stripe": {"type": "http", "url": "https://x"}}}}})

    got = get("claude").components(project)

    assert got["mcp"] == ["qmd", "stripe"]
    assert "secret" not in json.dumps(got) and "https://x" not in json.dumps(got)  # names only


def test_claude_reads_plugin_names_and_skips_the_skills_lanternspec_made(repo):
    init_project(repo)
    project = Project.load(repo.root)
    _json(Path.home() / ".claude" / "plugins" / "installed_plugins.json", {"version": 2, "plugins": {"memo@market": [{"scope": "user"}]}})
    own = project.root / ".claude" / "skills" / "my-skill"
    own.mkdir(parents=True)
    (own / "SKILL.md").write_text("---\nname: my-skill\n---\nhi\n", encoding="utf-8")
    person = Path.home() / ".claude" / "skills" / "personal"
    person.mkdir(parents=True)
    (person / "SKILL.md").write_text("---\nname: personal\n---\nhi\n", encoding="utf-8")

    got = get("claude").components(project)

    assert got["plugin"] == ["memo@market"]
    assert got["skill"] == ["my-skill", "personal"]  # the l-* skills that `lantern install` wrote are not listed


def test_claude_lists_the_hook_events_that_are_not_ours(repo):
    init_project(repo)
    project = Project.load(repo.root)
    assert "hook" not in get("claude").components(project)  # only our own hooks are installed
    _json(
        Path.home() / ".claude" / "settings.json",
        {"hooks": {"PostToolUse": [{"hooks": [{"type": "command", "command": "echo hi --token=abc"}]}], "Stop": [{"hooks": []}]}},
    )

    got = get("claude").components(project)

    assert got["hook"] == ["PostToolUse"]  # "Stop" has no handler of the person's, and the command text is not kept
    assert "abc" not in json.dumps(got)


def test_claude_components_never_raise_on_missing_or_broken_files(repo):
    init_project(repo)
    project = Project.load(repo.root)
    (project.root / ".mcp.json").write_text("{not json", encoding="utf-8")
    _json(Path.home() / ".claude.json", ["not", "an", "object"])
    _json(Path.home() / ".claude" / "plugins" / "installed_plugins.json", {"plugins": ["wrong shape"]})

    assert get("claude").components(project) == {}  # empty kinds are left out


def test_tools_that_cannot_say_report_no_components(repo):
    init_project(repo)
    project = Project.load(repo.root)
    assert get("codex").components(project) == {} and get("antigravity").components(project) == {}


# --------------------------------------------------------------------------- which listed add-on a tool call belongs to


def test_call_component_ties_an_mcp_tool_name_to_the_listed_server():
    claude = get("claude")
    listed = {"mcp": ["qmd", "my server"], "plugin": ["memo@market"]}
    assert claude.call_component("mcp__qmd__query", listed) == ("mcp", "qmd")
    assert claude.call_component("mcp__my_server__read", listed) == ("mcp", "my server")  # odd characters become "_" in the tool name
    assert claude.call_component("mcp__plugin_memo_db__query", listed) == ("plugin", "memo@market")
    assert claude.call_component("mcp__other__query", listed) is None  # a server that was not listed
    assert claude.call_component("Read", listed) is None


def test_a_tool_without_mcp_names_ties_nothing():
    assert get("codex").call_component("mcp__qmd__query", {"mcp": ["qmd"]}) is None


# --------------------------------------------------------------------------- the session line


def test_session_start_logs_the_components_and_a_broken_settings_file_does_not_stop_it(repo, monkeypatch):
    init_project(repo)
    monkeypatch.setattr(health, "installed_version", lambda tool, timeout=10: "2.1.323")
    project = Project.load(repo.root)
    _json(project.root / ".mcp.json", {"mcpServers": {"qmd": {}}})

    agent_hooks.run(project, "session-start", get("claude"), json.dumps({"session_id": "s1", "source": "startup"}))
    (project.root / ".mcp.json").write_text("{broken", encoding="utf-8")
    reply = agent_hooks.run(project, "session-start", get("claude"), json.dumps({"session_id": "s2", "source": "startup"}))

    lines = [json.loads(line) for line in (project.state / "runs.jsonl").read_text(encoding="utf-8").splitlines()]
    assert reply.code == 0
    assert lines[0]["components"] == {"mcp": ["qmd"]}
    assert "components" not in lines[1] or lines[1]["components"] == {}


# --------------------------------------------------------------------------- lantern eval


def test_eval_counts_mcp_calls_per_listed_component_and_names_the_ones_never_called(repo):
    init_project(repo)
    project = Project.load(repo.root)
    _log(
        project,
        [
            _session("s1", "2026-11-23T10:00:00", {"mcp": ["qmd", "obsidian"], "skill": ["my-skill"]}),
            _turn("s1", {"mcp__qmd__query": 3, "mcp__qmd__get": 1, "Read": 2}),
            _session("s2", "2026-11-23T12:00:00", {"mcp": ["qmd", "obsidian"]}),
            _turn("s2", {"Read": 1}),
        ],
    )

    rows = {(r["kind"], r["name"]): r for r in evaluate.summary(project)["components"]["rows"]}

    assert rows[("mcp", "qmd")] == {"kind": "mcp", "name": "qmd", "sessions": 2, "sessions_with_calls": 1, "calls": 4}
    assert rows[("mcp", "obsidian")]["calls"] == 0 and rows[("mcp", "obsidian")]["sessions_with_calls"] == 0
    assert rows[("skill", "my-skill")]["calls"] is None  # skills' calls are not counted: not "0"


def test_eval_shows_what_appeared_and_disappeared_between_sessions(repo):
    init_project(repo)
    project = Project.load(repo.root)
    _log(
        project,
        [
            _session("s1", "2026-11-23T10:00:00", {"mcp": ["qmd", "obsidian"]}),
            _session("s2", "2026-11-23T12:00:00", {"mcp": ["qmd"], "plugin": ["memo@market"]}),
        ],
    )

    changes = evaluate.summary(project)["components"]["changes"]

    assert [(c["change"], c["kind"], c["name"]) for c in changes] == [("removed", "mcp", "obsidian"), ("added", "plugin", "memo@market")]
    assert changes[0]["at"] == "2026-11-23T12:00:00"


def test_eval_reads_a_log_from_before_components_were_kept(repo):
    init_project(repo)
    project = Project.load(repo.root)
    _log(
        project,
        [_session("s1", "2026-11-01T10:00:00", None), _turn("s1", {"Read": 1}), _session("s2", "2026-11-02T10:00:00", {"mcp": ["qmd"]})],
    )

    got = evaluate.summary(project)["components"]

    assert [(r["kind"], r["name"], r["sessions"]) for r in got["rows"]] == [("mcp", "qmd", 1)]
    assert got["changes"] == []  # the first session with a list has nothing to be compared with


def test_eval_report_has_a_components_section_only_when_there_is_something_to_show(repo):
    init_project(repo)
    project = Project.load(repo.root)
    _log(project, [_session("s1", "2026-11-23T10:00:00", None), _turn("s1", {"Read": 1})])
    assert "qmd" not in evaluate.markdown(project)

    _log(project, [_session("s1", "2026-11-23T10:00:00", {"mcp": ["qmd"]}), _turn("s1", {"Read": 1})])
    text = evaluate.markdown(project)
    assert "qmd" in text and "| mcp" not in text  # the kind is shown with its label, not the log's key
    assert "MCP" in text  # the note says only MCP calls are counted


def test_an_unknown_harness_name_leaves_the_calls_uncounted_instead_of_failing(repo):
    init_project(repo)
    project = Project.load(repo.root)
    _log(project, [_session("s1", "2026-11-23T10:00:00", {"mcp": ["qmd"]}, harness="no-such-tool"), _turn("s1", {"mcp__qmd__query": 2})])

    (row,) = evaluate.summary(project)["components"]["rows"]

    assert row["name"] == "qmd" and row["calls"] is None


def test_eval_keeps_skills_and_hooks_out_of_the_table_and_counts_them_in_one_line(repo):
    init_project(repo)
    project = Project.load(repo.root)
    _log(
        project,
        [
            _session("s1", "2026-11-23T10:00:00", {"mcp": ["qmd"], "skill": ["a", "b"], "hook": ["Stop", "PostToolUse", "PreToolUse"]}),
            _turn("s1", {"Read": 1}),
        ],
    )

    text = evaluate.markdown(project)

    assert "| qmd" in text
    assert "| a " not in text and "PostToolUse" not in text  # their names would crowd the table: they have no call count anyway
    assert "스킬: 2" in text and "hook 이벤트: 3" in text
    kinds = {r["kind"] for r in evaluate.summary(project)["components"]["rows"]}
    assert kinds == {"mcp", "skill", "hook"}  # `--json` still has every name


def test_eval_has_no_one_line_summary_when_there_are_only_mcp_servers_and_plugins(repo):
    init_project(repo)
    project = Project.load(repo.root)
    _log(project, [_session("s1", "2026-11-23T10:00:00", {"mcp": ["qmd"]}), _turn("s1", {"Read": 1})])

    text = evaluate.markdown(project)

    assert "| qmd" in text and "그 밖에 기록된 것" not in text


def test_eval_says_how_many_turns_came_from_sessions_without_a_component_list(repo):
    init_project(repo)
    project = Project.load(repo.root)
    _log(
        project,
        [
            _session("s1", "2026-11-23T10:00:00", {"mcp": ["qmd"]}),
            _turn("s1", {"Read": 1}),
            _turn("s2", {"mcp__qmd__query": 2}),  # no session line at all: an older lantern wrote this turn
            _turn("s2", {"Read": 1}),
            _session("s3", "2026-11-23T12:00:00", None),  # a session line from before components were kept
            _turn("s3", {}),
        ],
    )

    assert evaluate.summary(project)["components"]["unlisted"] == {"sessions": 2, "turns": 3}
    assert "세션 2개의 턴 3개" in evaluate.markdown(project)


def test_eval_does_not_mention_unlisted_turns_when_every_turn_has_a_list_or_no_session_has_one(repo):
    init_project(repo)
    project = Project.load(repo.root)
    _log(project, [_session("s1", "2026-11-23T10:00:00", {"mcp": ["qmd"]}), _turn("s1", {"Read": 1})])
    assert "목록이 없는 세션" not in evaluate.markdown(project)

    _log(project, [_turn("s9", {"Read": 1})])  # a log from before the lists existed at all
    assert "목록이 없는 세션" not in evaluate.markdown(project)
