"""Is each AI tool's connection still working? Versions, hook runs and unexpected payloads.

A tool may rename a hook event or change its payload in a new version; nothing fails then, the
hook just goes quiet or reads empty fields. These tests keep the evidence that shows it working.
"""

import json
from pathlib import Path

import pytest

from lanternspec.check import doctor
from lanternspec.core.project import Project
from lanternspec.tools import REGISTRY, agent_hooks, get, health
from lanternspec.tools.base import Tool

SAMPLES = Path(__file__).parent / "fixtures" / "hooks"


def _samples():
    for tool_dir in sorted(p for p in SAMPLES.iterdir() if p.is_dir()):
        for f in sorted(tool_dir.glob("*.json")):
            yield tool_dir.name, f.name.split(".")[0], f


@pytest.mark.parametrize(("tool", "event", "path"), list(_samples()), ids=lambda x: str(x) if not isinstance(x, Path) else x.name)
def test_documented_payloads_fill_every_expected_field(tool, event, path):
    t = get(tool)
    assert event in t.hook_events(), f"{tool} doesn't install the {event} hook"
    inp = t.parse_hook(event, json.loads(path.read_text(encoding="utf-8")))
    assert health.missing_fields(event, inp) == []


def test_every_installed_hook_event_has_a_sample():
    for name, t in REGISTRY.items():
        have = {f.stem.split(".")[0] for f in (SAMPLES / name).glob("*.json")}
        assert set(t.hook_events()) <= have, f"{name}: no sample for {set(t.hook_events()) - have}"


def test_compaction_restart_is_read_on_both_tools_that_have_it():
    for name in ("claude", "codex"):
        data = json.loads((SAMPLES / name / "session-start.json").read_text(encoding="utf-8"))
        assert get(name).parse_hook("session-start", data).source == "compact"


class _Pinned(Tool):
    name, label, launch = "pinned", "Pinned", "pinned"
    min_version, verified_version = "1.2.0", "1.4.0"


def test_versions_below_min_or_past_verified_are_told_apart():
    t = _Pinned()
    assert [health.version_verdict(t, v) for v in ("1.1.9", "1.2.0", "1.4.0", "1.4.1", "")] == ["old", "ok", "ok", "new", ""]
    assert health.version_verdict(get("claude"), "2.1.276") == "old"  # before Claude Code read AGENTS.md itself
    assert health.version_verdict(get("codex"), "0.0.1") == "ok"  # no known minimum: never "old"


def _hook(project, tool, event, data):
    return agent_hooks.run(project, event, get(tool), json.dumps(data))


def test_every_hook_run_is_counted_per_tool_and_event(repo):
    project = Project.load(repo.root)
    for _ in range(2):
        _hook(project, "codex", "session-start", {"session_id": "s1", "source": "startup"})
        _hook(project, "codex", "stop", {"session_id": "s1"})
    beats = health.heartbeat(project)["codex"]
    assert beats["starts"] == 2
    assert beats["events"]["stop"]["count"] == 2 and beats["events"]["stop"]["at_start"] == 2
    assert health.silent_events(get("codex"), beats) == []  # prompt never ran, but only 2 sessions so far
    _hook(project, "codex", "session-start", {"session_id": "s2", "source": "startup"})
    assert health.silent_events(get("codex"), health.heartbeat(project)["codex"]) == ["prompt"]


def test_a_hook_that_goes_quiet_is_reported_but_a_working_one_is_not():
    t = get("claude")
    working = {"starts": 4, "events": {e: {"count": 4, "at_start": 4} for e in ("session-start", "prompt", "stop")}}
    assert health.silent_events(t, working) == []
    renamed = {"starts": 0, "events": {"prompt": {"count": 5, "at_start": 0}, "stop": {"count": 5, "at_start": 0}}}
    assert health.silent_events(t, renamed) == ["session-start"]  # the others ran, session-start never did


def test_payloads_missing_expected_fields_are_kept_as_key_names_only(repo):
    project = Project.load(repo.root)
    _hook(project, "claude", "post-tool", {"session_id": "s1", "toolName": "Write", "secret": "user words"})
    _hook(project, "claude", "stop", {"session_id": "s1"})  # fine: not recorded
    calls = health.unexpected(project)
    assert len(calls) == 1
    assert calls[0]["missing"] == ["tool"] and calls[0]["keys"] == ["secret", "session_id", "toolName"]
    assert "user words" not in (project.state / "hook-state" / health.UNEXPECTED).read_text(encoding="utf-8")


def test_only_the_newest_unexpected_calls_are_kept(repo):
    project = Project.load(repo.root)
    for _ in range(health.KEEP_UNEXPECTED + 5):
        _hook(project, "claude", "stop", {})
    assert len(health.unexpected(project)) == health.KEEP_UNEXPECTED


def test_bookkeeping_errors_never_break_the_hook(repo, monkeypatch):
    project = Project.load(repo.root)

    def broken(_project):
        raise OSError("disk full")

    monkeypatch.setattr(health, "hook_state_dir", broken)
    assert _hook(project, "claude", "stop", {"session_id": "s1"}).code == 0


def test_doctor_shows_version_hook_runs_and_odd_payloads(repo, monkeypatch):
    project = Project.load(repo.root)
    monkeypatch.setattr(health, "installed_version", lambda tool: {"claude": "2.1.400", "codex": None}[tool.name])
    for _ in range(3):
        _hook(project, "claude", "session-start", {"session_id": "s1"})
    _hook(project, "claude", "post-tool", {"session_id": "s1"})
    rows = dict((text, icon) for icon, text in doctor._tool_rows(project, ["claude", "codex"]))
    text = "\n".join(rows)
    assert "Claude Code 2.1.400" in text and "2.1.308" in text  # newer than checked → told
    assert "prompt, stop" in text  # installed, never ran over 3 sessions
    assert "hook 호출 1건" in text  # post-tool without a tool name
    assert "codex 명령이 PATH에 없어" in text and "한 번도 실행되지 않았습니다" in text
