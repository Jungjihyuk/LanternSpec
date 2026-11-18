"""What the run log keeps: the setup a session ran with, the tokens a turn spent, and the attempt lines a loop will write.

The log is raw material for `lantern eval`; older lines (written before these fields) must keep reading.
"""

import json
import subprocess
from pathlib import Path

from conftest import init_project
from lanternspec.core.project import Project
from lanternspec.report import evaluate
from lanternspec.tools import agent_hooks, get, health, runlog


def _hook(project, tool, event, payload):
    return agent_hooks.run(project, event, get(tool), json.dumps(payload))


def _lines(project):
    return [json.loads(l) for l in (project.state / "runs.jsonl").read_text(encoding="utf-8").splitlines()]


def _jsonl(path: Path, records: list[dict]) -> Path:
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
    return path


# --------------------------------------------------------------------------- the setup a session ran with


def test_session_start_records_the_harness_and_its_versions(repo, monkeypatch):
    init_project(repo)
    config = repo.root.parent / "harness"
    config.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=config, check=True)
    subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "settings"], cwd=config, check=True)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=config, capture_output=True, text=True, check=True).stdout.strip()
    monkeypatch.setenv("LANTERN_HARNESS_CONFIG", str(config))
    monkeypatch.setattr(health, "installed_version", lambda tool, timeout=10: "2.1.311")
    project = Project.load(repo.root)

    _hook(project, "claude", "session-start", {"session_id": "s1", "model": "claude-opus-5-5", "source": "startup"})

    (rec,) = _lines(project)
    assert rec["kind"] == "session" and rec["session"] == "s1" and rec["model"] == "claude-opus-5-5"
    assert rec["harness"] == "claude" and rec["harness_version"] == "2.1.311" and rec["harness_config"] == head
    from lanternspec import __version__

    assert rec["lanternspec_version"] == __version__


def test_session_start_after_compaction_is_the_same_session_and_is_not_logged_twice(repo, monkeypatch):
    init_project(repo)
    monkeypatch.setattr(health, "installed_version", lambda tool, timeout=10: "2.1.311")
    project = Project.load(repo.root)
    _hook(project, "claude", "session-start", {"session_id": "s1", "source": "startup"})
    _hook(project, "claude", "session-start", {"session_id": "s1", "source": "compact"})
    assert [r["kind"] for r in _lines(project)] == ["session"]


def test_a_broken_version_command_or_config_path_still_logs_the_session_and_never_stops_the_hook(repo, monkeypatch):
    init_project(repo)
    monkeypatch.setattr(health, "installed_version", lambda tool, timeout=10: None)  # the command is not installed
    monkeypatch.setenv("LANTERN_HARNESS_CONFIG", str(repo.root / "no-such-folder"))
    project = Project.load(repo.root)

    reply = _hook(project, "codex", "session-start", {"session_id": "s1", "source": "startup"})

    assert reply.code == 0
    (rec,) = _lines(project)
    assert rec["harness"] == "codex" and rec["harness_version"] == "" and rec["harness_config"] == ""


def test_a_machine_without_git_still_gets_its_status_line(repo, monkeypatch):
    init_project(repo)
    folder = repo.root.parent / "harness"
    folder.mkdir()
    monkeypatch.setenv("LANTERN_HARNESS_CONFIG", str(folder))

    def no_git(*args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(agent_hooks, "git_out", no_git)
    reply = _hook(Project.load(repo.root), "claude", "session-start", {"session_id": "s1", "source": "startup"})
    assert reply.code == 0 and "[LanternSpec 지금 상황]" in reply.stdout
    assert _lines(Project.load(repo.root))[0]["harness_config"] == ""


def test_without_a_harness_config_path_the_field_is_empty(repo, monkeypatch):
    init_project(repo)
    monkeypatch.delenv("LANTERN_HARNESS_CONFIG", raising=False)
    monkeypatch.setattr(health, "installed_version", lambda tool, timeout=10: "0.167.2")
    project = Project.load(repo.root)
    _hook(project, "codex", "session-start", {"session_id": "s1"})
    assert _lines(project)[0]["harness_config"] == ""


def test_the_version_lookup_in_a_hook_has_a_short_deadline(repo, monkeypatch):
    init_project(repo)
    seen = []
    monkeypatch.setattr(health, "installed_version", lambda tool, timeout=10: seen.append(timeout) or "1")
    _hook(Project.load(repo.root), "claude", "session-start", {"session_id": "s1"})
    assert seen and seen[0] < 10  # a hook may not wait as long as its own time limit


# --------------------------------------------------------------------------- tokens a turn spent


def _usage(inp, out, cache_read=0, cache_write=0):
    return {"input_tokens": inp, "output_tokens": out, "cache_read_input_tokens": cache_read, "cache_creation_input_tokens": cache_write}


def _claude_user(text):
    return {"type": "user", "message": {"role": "user", "content": text}}


def _claude_assistant(msg_id, usage, block="text", sidechain=False):
    return {
        "type": "assistant",
        "isSidechain": sidechain,
        "message": {"id": msg_id, "role": "assistant", "content": [{"type": block}], "usage": usage},
    }


def test_claude_turn_tokens_count_each_response_once_and_only_after_the_last_prompt(tmp_path):
    transcript = _jsonl(
        tmp_path / "t.jsonl",
        [
            _claude_user("처음 질문"),
            _claude_assistant("m0", _usage(1000, 500)),  # an earlier turn: not counted
            _claude_user("지금 질문"),
            _claude_assistant("m1", _usage(10, 100, cache_read=2000, cache_write=300), block="thinking"),
            _claude_assistant("m1", _usage(10, 100, cache_read=2000, cache_write=300), block="text"),  # same response, second line
            {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "content": "ok"}]}},  # not a prompt
            _claude_assistant("m2", _usage(20, 50, cache_read=2500)),
            _claude_assistant("sub", _usage(9999, 9999), sidechain=True),  # a sub-agent's: recorded on its own
        ],
    )
    tokens = get("claude").turn_tokens(transcript)
    assert tokens == {"input": 10 + 300 + 20, "cached": 2000 + 2500, "output": 100 + 50}


def test_claude_turn_tokens_are_unknown_without_a_readable_transcript(tmp_path):
    assert get("claude").turn_tokens(tmp_path / "missing.jsonl") is None
    assert get("claude").turn_tokens(_jsonl(tmp_path / "t.jsonl", [_claude_user("질문")])) is None  # no answer yet


def _codex_total(inp, cached, out):
    usage = {"input_tokens": inp, "cached_input_tokens": cached, "output_tokens": out, "total_tokens": inp + out}
    return {"type": "event_msg", "payload": {"type": "token_count", "info": {"total_token_usage": usage, "last_token_usage": usage}}}


def test_codex_turn_tokens_are_the_growth_of_the_running_total_since_the_turn_started(tmp_path):
    started = {"type": "event_msg", "payload": {"type": "task_started"}}
    transcript = _jsonl(
        tmp_path / "rollout.jsonl",
        [
            started,
            _codex_total(1000, 400, 50),  # first turn
            {"type": "event_msg", "payload": {"type": "task_complete"}},
            started,
            {"type": "event_msg", "payload": {"type": "token_count", "info": None}},  # rate limits only
            _codex_total(3000, 1400, 150),
            _codex_total(3000, 1400, 150),  # repeated total: must not be counted twice
            _codex_total(6000, 3400, 260),
        ],
    )
    # input is what was not read from the cache; Codex counts cached tokens inside input_tokens
    assert get("codex").turn_tokens(transcript) == {"input": (6000 - 1000) - (3400 - 400), "cached": 3400 - 400, "output": 260 - 50}


def test_codex_turn_with_only_a_repeated_total_spent_nothing_new(tmp_path):
    started = {"type": "event_msg", "payload": {"type": "task_started"}}
    transcript = _jsonl(tmp_path / "rollout.jsonl", [started, _codex_total(1000, 400, 50), started, _codex_total(1000, 400, 50)])
    assert get("codex").turn_tokens(transcript) is None


def test_a_tool_that_does_not_report_tokens_says_so():
    assert get("antigravity").turn_tokens(Path("whatever.jsonl")) is None


def test_the_stop_hook_puts_tokens_on_the_turn_line_and_survives_a_bad_transcript(repo):
    init_project(repo)
    project = Project.load(repo.root)
    transcript = _jsonl(repo.root.parent / "t.jsonl", [_claude_user("질문"), _claude_assistant("m1", _usage(5, 7, cache_read=11))])
    _hook(project, "claude", "prompt", {"session_id": "s1", "prompt": "/l-build W-001"})
    _hook(project, "claude", "stop", {"session_id": "s1", "transcript_path": str(transcript)})
    _hook(project, "claude", "prompt", {"session_id": "s2", "prompt": "/l-build W-001"})
    reply = _hook(project, "claude", "stop", {"session_id": "s2", "transcript_path": str(repo.root.parent / "missing.jsonl")})
    _hook(project, "claude", "prompt", {"session_id": "s3", "prompt": "/l-build W-001"})
    unreadable = _hook(project, "claude", "stop", {"session_id": "s3", "transcript_path": str(repo.root)})  # a folder: reading it fails
    first, second, third = _lines(project)
    assert unreadable.code == 0 and "tokens" not in third
    assert first["tokens"] == {"input": 5, "cached": 11, "output": 7}
    assert reply.code == 0 and "tokens" not in second  # unknown tokens are left out, not written as zero


# --------------------------------------------------------------------------- attempt lines (written by the build loop)


def test_an_attempt_line_keeps_what_the_loop_needs_to_look_back(repo):
    init_project(repo)
    project = Project.load(repo.root)
    runlog.loop_attempt(project, run="r1", task="T-3", ac="AC-2", attempt=3, result="통과", failed_check="", understood=False, work="W-001")
    (rec,) = _lines(project)
    assert rec == {
        "kind": "attempt",
        "source": "build",
        "run": "r1",
        "work": "W-001",
        "task": "T-3",
        "ac": "AC-2",
        "attempt": 3,
        "result": "통과",
        "failed_check": "",
        "understood": False,
        "scope": "one",
        "at": rec["at"],
    }


def test_a_loop_line_names_its_run_and_work(repo):
    init_project(repo)
    project = Project.load(repo.root)
    runlog.loop_event(project, "start", "r1", "W-001", mode="loop", base="abc1234")
    (rec,) = _lines(project)
    assert rec == {
        "kind": "loop",
        "source": "build",
        "event": "start",
        "run": "r1",
        "work": "W-001",
        "mode": "loop",
        "base": "abc1234",
        "at": rec["at"],
    }
    assert evaluate.summary(project)["skill_runs"] == 0  # the evaluation ignores lines it doesn't know


# --------------------------------------------------------------------------- reading old and new lines


def test_eval_reads_a_log_from_before_these_fields_and_one_with_them(repo):
    init_project(repo)
    project = Project.load(repo.root)
    old = {"kind": "turn", "source": "hook", "session": "a", "skill": "l-build", "model": "m1", "tool_calls": 4,
           "start": "2026-11-01T10:00:00+09:00", "end": "2026-11-01T10:10:00+09:00"}  # fmt: skip
    new = {**old, "session": "b", "model": "m2", "tokens": {"input": 400, "cached": 5000, "output": 100}}
    new2 = {**new, "session": "c", "tokens": {"input": 200, "cached": 100, "output": 300}}
    for rec in (old, new, new2, {"kind": "session", "session": "b", "harness": "claude"}, {"kind": "attempt", "run": "r1"}):
        runlog.append(project, rec)

    s = evaluate.summary(project)

    assert s["turns"] == 3 and s["skill_runs"] == 0  # session and attempt lines are not turns
    assert s["by_model"]["m1"]["avg_tokens"] is None  # no token field on that line: unknown, not zero
    assert s["by_model"]["m2"]["avg_tokens"] == (400 + 100 + 200 + 300) / 2  # fresh input + output; cache reads are cheap
    assert s["by_skill"]["l-build"]["avg_tokens"] == (400 + 100 + 200 + 300) / 2  # only turns that know their tokens count
    assert "평균 토큰" in evaluate.markdown(project)
