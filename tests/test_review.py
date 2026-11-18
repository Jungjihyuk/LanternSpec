"""The review after a build: a pack that holds documents and the diff but not the build, the verdict read from the
reviewer's own lines, the rounds counted by code, and the connection to Claude Code's sub-agents."""

import json
from pathlib import Path

import pytest

from conftest import docs
from lanternspec.core.enums import load
from lanternspec.core.names import load as load_names
from lanternspec.core.project import Project, today
from lanternspec.report import retro
from lanternspec.tools import agent_hooks, get
from lanternspec.work import loop, review
from loop_support import commit as _commit
from loop_support import implement as _implement
from loop_support import lines as _lines

CLEAN = "검토: W-001\n- [통과] R1 — AC-1을 확인했다\n- [통과] R2 — 기대값이 구체적이다"
ISSUES = "검토: W-001\n- [통과] R1 — ok\n- [지적] R2 — tests/test_login.py:3 — 기대값이 없다\n- [지적] R3 — 근거를 대지 못했다"


def _built(repo, on=True):
    """A work whose loop ended passed, with the implementation committed after the loop started."""
    repo("loop", "start", "W-001")
    _implement(repo, "login")
    _implement(repo, "logout")
    repo("loop", "attempt", "W-001", "AC-1")
    repo("loop", "attempt", "W-001", "AC-2")
    repo("loop", "finish", "W-001")
    _commit(repo, "implement")
    if on:
        repo("profile", "set", "build.review=on")


def _padded(project, text):
    """The text with a passing line for every item of the waiting pack that it leaves out (a reviewer answers every item)."""
    waiting = review.open_pack(project, "W-001")
    verdict = review.parse_verdict(text, load())
    have = len(verdict.items) if verdict else 0
    return text + "".join(f"\n- [통과] R{i} — ok" for i in range(have + 1, int(waiting["items"] if waiting else 0) + 1))


def _say(repo, text, model="", pack=True, pad=True):
    """Record a reviewer's answer through the command. A pack is made first, as the skill does, unless one waits already."""
    if pack and review.open_pack(Project.load(repo.root), "W-001") is None:
        repo("review", "pack", "W-001", ok=False)
    project = Project.load(repo.root)
    path = repo.root / "verdict.txt"
    path.write_text(_padded(project, text) if pad else text, encoding="utf-8")
    return repo("review", "record", "W-001", "--file", str(path), *(["--model", model] if model else []), ok=False)


# --------------------------------------------------------------------------- reading a verdict


def test_a_verdict_is_read_from_the_reviewers_lines_and_the_count_comes_from_them():
    v = review.parse_verdict(ISSUES, load())
    assert v is not None and v.work == "W-001" and [i.verdict for i in v.items] == ["pass", "issue", "issue"]
    assert len(v.issues) == 2  # no closing line is read: the count is the lines'
    assert (
        review.parse_verdict("Review: W-009\n- [Pass] R1\n- [Issue] R2 — a.py:1 — x", load(language="en")).issues[0].text.startswith("R2")
    )  # type: ignore[union-attr]
    assert review.parse_verdict("- [통과] R1", load()) is None  # names no work
    assert review.parse_verdict("검토: W-001\n판정: 통과", load()) is None  # no item line
    assert review.parse_verdict("검토: W-001\n- [어쩌면] R1", load()) is None  # a word outside the list is no verdict


# --------------------------------------------------------------------------- the pack


def test_the_pack_is_refused_while_the_review_is_off(repo, work):
    _built(repo, on=False)
    code, out = repo("review", "pack", "W-001", ok=False)
    assert code == 1 and "build.review가 off" in out


def test_there_is_nothing_to_review_when_the_code_has_not_changed_since_the_work_started(repo, work):
    repo("profile", "set", "build.review=on")
    _commit(repo, "review on")
    repo("loop", "start", "W-001")  # the work starts here: nothing changes after it
    code, out = repo("review", "pack", "W-001", ok=False)
    assert code == 1 and "검토할 것이 없습니다" in out


def test_the_pack_holds_the_items_the_documents_give_and_leaves_out_the_rest(repo, work):
    _built(repo)
    _, out = repo("review", "pack", "W-001")
    text = (repo.root / ".lantern" / "review" / "W-001.md").read_text(encoding="utf-8")
    assert "✔" in out and text.startswith("# 검토 꾸러미 — W-001")
    assert "R1: 구현이 AC-1의 기준을 만족하는가" in text and "R2: 구현이 AC-2의 기준을 만족하는가" in text
    assert "테스트가 수락 기준을 실제로 확인하는가" in text  # the fixed item
    assert "설계대로 만들었는가" not in text  # there is no design document: the item is left out
    assert "src/login.txt" in text and "```diff" in text  # the diff since the loop started
    assert "- [통과] R1" in text and "- [지적] R2" in text  # the form of the answer, with the project's words


def test_a_design_document_adds_its_item(repo, work):
    repo("scaffold", "doc", "W-001", "설계")
    _commit(repo, "design")
    _built(repo)
    repo("review", "pack", "W-001")
    text = (repo.root / ".lantern" / "review" / "W-001.md").read_text(encoding="utf-8")
    assert "설계대로 만들었는가" in text and "## 설계" in text


def test_files_not_added_to_git_are_named_and_not_hidden(repo, work):
    _built(repo)
    (repo.root / "src" / "brand_new.py").write_text("print('hi')\n", encoding="utf-8")  # made, never added
    repo("review", "pack", "W-001")
    text = (repo.root / ".lantern" / "review" / "W-001.md").read_text(encoding="utf-8")
    assert "아직 git에 더하지 않아" in text and "- src/brand_new.py" in text


def test_a_change_that_only_adds_files_is_still_something_to_review(repo, work):
    repo("profile", "set", "build.review=on")
    _commit(repo, "review on")
    repo("loop", "start", "W-001")
    (repo.root / "src").mkdir(exist_ok=True)
    (repo.root / "src" / "only_new.py").write_text("x = 1\n", encoding="utf-8")  # nothing tracked changed
    repo("review", "pack", "W-001")
    assert "- src/only_new.py" in (repo.root / ".lantern" / "review" / "W-001.md").read_text(encoding="utf-8")


def test_the_first_huge_file_is_cut_too(repo, work, monkeypatch):
    _built(repo)
    big = repo.root / "src" / "lock.txt"
    big.write_text("line\n" * 5000, encoding="utf-8")
    _commit(repo, "a big file")
    monkeypatch.setattr(review, "DIFF_LIMIT", 2000)
    repo("review", "pack", "W-001")
    text = (repo.root / ".lantern" / "review" / "W-001.md").read_text(encoding="utf-8")
    assert len(text) < 40_000 and "- src/lock.txt" in text  # the limit held, and the file is named for the reviewer to read


def test_the_pack_carries_neither_the_tries_nor_the_conversation(repo, work):
    repo("loop", "start", "W-001")
    repo("loop", "attempt", "W-001", "AC-1", ok=False)  # a failing try leaves a trace in the run log
    run = loop.last_start(work, "W-001")["run"]
    _implement(repo, "login")
    _implement(repo, "logout")
    repo("loop", "attempt", "W-001", "AC-1")
    repo("loop", "attempt", "W-001", "AC-2")
    repo("loop", "finish", "W-001")
    _commit(repo, "implement")
    repo("profile", "set", "build.review=on")
    repo("review", "pack", "W-001")
    text = (repo.root / ".lantern" / "review" / "W-001.md").read_text(encoding="utf-8")
    assert run not in text and "failed_check" not in text and "시도" not in text and "연속" not in text


def test_a_diff_too_big_for_the_pack_is_named_and_not_cut_in_the_middle(repo, work, monkeypatch):
    _built(repo)
    monkeypatch.setattr(review, "DIFF_LIMIT", 10)
    repo("review", "pack", "W-001")
    text = (repo.root / ".lantern" / "review" / "W-001.md").read_text(encoding="utf-8")
    assert "직접 읽어 주세요" in text and "- src/" in text


def test_the_pack_for_other_tools_comes_with_the_command_that_starts_a_fresh_reviewer(repo, work):
    _built(repo)
    repo("profile", "set", "build.review_model=gpt-5.1-codex")
    _, out = repo("review", "pack", "W-001", "--tool", "codex")
    assert "codex exec --ephemeral -s read-only -m gpt-5.1-codex -o .lantern/review/W-001.out - < " in out
    assert "lantern review record W-001 --file .lantern/review/W-001.out" in out
    _, out = repo("review", "pack", "W-001", "--tool", "antigravity")
    assert 'agy --print --sandbox --model gpt-5.1-codex "$(cat ' in out
    _, out = repo("review", "pack", "W-001", "--tool", "claude")
    assert "lantern-reviewer" in out and "서브 에이전트" in out


# --------------------------------------------------------------------------- the rounds


def test_a_verdict_with_issues_is_written_as_one_round_and_leaves_the_review_open(repo, work):
    _built(repo)
    code, out = _say(repo, ISSUES, "claude-opus-5-5")
    assert code == 1 and "1회차: 항목 4개, 지적 2개" in out and "⚠ R2 — tests/test_login.py:3" in out
    (line,) = _lines(work, "review")
    assert (line["work"], line["items"], line["issues"], line["unsupported"], line["review_model"], line["source"]) == (
        "W-001",
        4,
        2,
        1,
        "claude-opus-5-5",
        "cli",
    )  # one of the two issues named no file and line
    assert line["issue_list"][0].startswith("R2") and review.standing(work, "W-001") == "open"
    code, out = repo("review", "status", "W-001", ok=False)
    assert code == 1 and "고치고 다시 검토하세요" in out and "claude-opus-5-5" in out


def test_a_clean_round_ends_the_review_and_no_second_pack_is_made(repo, work):
    _built(repo)
    code, _ = _say(repo, CLEAN)
    assert code == 0 and review.standing(work, "W-001") == "clean"
    code, out = repo("review", "pack", "W-001", ok=False)
    assert code == 1 and "지적이 없었습니다" in out
    code, out = repo("review", "status", "W-001", ok=False)
    assert code == 0 and "남은 지적 없음" in out


def test_the_rounds_are_counted_by_code_and_the_pack_is_refused_when_none_is_left(repo, work):
    _built(repo)
    _say(repo, ISSUES)
    repo("review", "pack", "W-001")  # build.review_limit is 1: one more round may follow
    _say(repo, ISSUES)
    assert review.standing(work, "W-001") == "limit"
    code, out = repo("review", "pack", "W-001", ok=False)
    assert code == 1 and "검토 회차가 남지 않았습니다" in out
    code, out = repo("review", "status", "W-001", ok=False)
    assert code == 1 and "사람에게 넘기세요" in out


def test_a_round_needs_a_pack_that_waits_for_it_and_every_item_answered(repo, work):
    _built(repo)
    code, out = _say(repo, CLEAN, pack=False, pad=False)  # no pack was made: a verdict written out of the blue
    assert code == 1 and "답을 기다리는 검토 꾸러미가 없습니다" in out and _lines(work, "review") == []
    repo("review", "pack", "W-001")
    code, out = _say(repo, CLEAN, pad=False)  # the pack asks about four items and the verdict answers two
    assert code == 1 and "4개 중 2개만" in out and _lines(work, "review") == []
    code, out = repo("review", "status", "W-001", ok=False)
    assert code == 1 and "답을 기다리는 중" in out  # still waiting: the reviewer is to be called once more
    assert _say(repo, CLEAN)[0] == 0 and len(_lines(work, "review")) == 1


def test_a_pack_asked_for_twice_before_the_answer_is_still_one_round(repo, work):
    _built(repo)
    repo("review", "pack", "W-001")
    repo("review", "pack", "W-001")
    assert len(_lines(work, "review_pack")) == 1
    _say(repo, ISSUES)
    repo("review", "pack", "W-001")  # the second round gets its own pack
    assert len(_lines(work, "review_pack")) == 2


def test_no_round_is_recorded_once_the_review_is_over(repo, work):
    _built(repo)
    _say(repo, ISSUES)
    _say(repo, ISSUES)  # the limit: no round is left
    assert review.standing(work, "W-001") == "limit"
    code, out = _say(repo, CLEAN, pack=False)  # a pass written afterwards cannot lift the limit
    assert code == 1 and "검토는 끝났습니다" in out and review.standing(work, "W-001") == "limit" and len(_lines(work, "review")) == 2
    _, out = repo("work", "archive", "W-001", "--now")
    assert "지적 2개가 남았습니다" in out


def test_a_clean_review_takes_no_further_round(repo, work):
    _built(repo)
    _say(repo, CLEAN)
    code, out = _say(repo, ISSUES, pack=False)
    assert code == 1 and "검토는 끝났습니다" in out and review.standing(work, "W-001") == "clean"


def test_no_round_is_recorded_while_the_review_is_off(repo, work):
    _built(repo)
    repo("review", "pack", "W-001")
    repo("profile", "set", "build.review=off")
    code, out = _say(repo, CLEAN, pack=False)
    assert code == 1 and "off" in out and _lines(work, "review") == []


def test_the_archive_marks_a_round_written_by_hand_where_the_reviewers_hook_was_installed(repo, work):
    _built(repo)
    repo("install")  # the reviewer's definition (and with it the hook that would record its answer) is there
    _say(repo, CLEAN)
    _, out = repo("work", "archive", "W-001", "--now")
    assert "손으로 기록됐습니다" in out


def test_a_text_without_a_verdict_or_about_another_work_is_not_recorded(repo, work):
    _built(repo)
    code, out = _say(repo, "다 좋아 보입니다")
    assert code == 1 and "판정을 찾지 못했습니다" in out and _lines(work, "review") == []
    code, out = _say(repo, CLEAN.replace("W-001", "W-009"))
    assert code == 1 and "W-009" in out and _lines(work, "review") == []


def test_the_archive_warns_about_a_review_that_was_asked_for_and_not_done_or_not_settled(repo, work):
    _built(repo)
    _, out = repo("work", "archive", "W-001", "--now")
    assert "검토하지 않았습니다" in out


def test_the_archive_says_nothing_of_a_clean_review(repo, work):
    _built(repo)
    _say(repo, CLEAN)
    _, out = repo("work", "archive", "W-001", "--now")
    assert "검토하지 않았습니다" not in out and "검토에 지적" not in out


def test_the_archive_says_nothing_when_the_review_is_off(repo, work):
    _built(repo, on=False)
    _, out = repo("work", "archive", "W-001", "--now")
    assert "검토하지 않았습니다" not in out and "검토에 지적" not in out


def test_the_archive_warns_of_issues_left(repo, work):
    _built(repo)
    _say(repo, ISSUES)
    _, out = repo("work", "archive", "W-001", "--now")
    assert "검토에 지적 2개가 남았습니다" in out


# --------------------------------------------------------------------------- the retro


def _retro_rows(repo):
    path = docs(repo) / "4. 운영 기록" / "AI 회고" / f"{today()[:7]}.md"
    return retro.parse(path.read_text(encoding="utf-8"), load_names("ko")) if path.exists() else []


def test_a_review_that_found_issues_leaves_a_retro_row_once_it_is_over(repo, work):
    _built(repo)
    _say(repo, ISSUES)
    assert _retro_rows(repo) == []  # still open: another round may follow
    _say(repo, CLEAN)
    (row,) = _retro_rows(repo)
    assert (row.is_check, row.key, row.tries, row.result, row.work) == (True, "검토", 2, "통과", "W-001")
    assert "[검증:: 검토] [시도:: 2] [결과:: 통과]" in (docs(repo) / "4. 운영 기록" / "AI 회고" / f"{today()[:7]}.md").read_text(
        encoding="utf-8"
    )


def test_a_review_left_with_issues_is_a_stopped_row_and_a_clean_first_round_leaves_none(repo, work):
    _built(repo)
    _say(repo, ISSUES)
    _say(repo, ISSUES)
    (row,) = _retro_rows(repo)
    assert (row.key, row.tries, row.result) == ("검토", 2, "중단")


def test_a_review_that_found_nothing_leaves_no_row(repo, work):
    _built(repo)
    _say(repo, CLEAN)
    assert _retro_rows(repo) == []


def test_the_review_row_is_judged_like_any_other(repo, work):
    _built(repo)
    _say(repo, ISSUES)
    _say(repo, CLEAN)
    run = _retro_rows(repo)[0].run
    repo("retro", "judge", run, "review", "--weakness", "검증", "--remedy", "하네스 설정", "--hypothesis", "테스트가 약했다")
    assert _retro_rows(repo)[0].judged


# --------------------------------------------------------------------------- the reviewer's definition for Claude Code


def test_claude_code_gets_the_reviewer_only_while_the_review_is_on(repo, work):
    repo("install")
    agent = repo.root / ".claude" / "agents" / "lantern-reviewer.md"
    assert not agent.exists()
    repo("profile", "set", "build.review=on")
    repo("install")
    text = agent.read_text(encoding="utf-8")
    assert text.startswith("---\nname: lantern-reviewer\n") and "disallowedTools: Edit, Write, NotebookEdit" in text
    assert "model:" not in text and "<<" not in text and "lantern:" not in text  # no model line while build.review_model is empty
    assert "- [통과] R1" in text
    assert "확인하지 못한 항목은 통과로 두지 않는다" in text and "[지적]" in text  # an item it could not check goes to the person
    repo("profile", "set", "build.review_model=opus")
    repo("install")
    assert "\nmodel: opus\n" in agent.read_text(encoding="utf-8")
    repo("profile", "set", "build.review=off")
    repo("install")
    assert not agent.exists()  # turned off: the file we made goes away


def test_a_reviewer_definition_the_person_edited_is_left_alone(repo, work):
    repo("profile", "set", "build.review=on")
    repo("install")
    agent = repo.root / ".claude" / "agents" / "lantern-reviewer.md"
    agent.write_text(agent.read_text(encoding="utf-8") + "\n내가 더한 규칙\n", encoding="utf-8")
    repo("profile", "set", "build.review_model=opus")
    _, out = repo("install")
    assert "내가 더한 규칙" in agent.read_text(encoding="utf-8") and "lantern-reviewer.md" in out


def test_other_tools_get_no_agent_file(repo, work):
    repo("profile", "set", "build.review=on")
    assert get("codex").agent_files(work.profile) == {} and get("antigravity").agent_files(work.profile) == {}
    assert get("claude").owns_agent_file(".claude/agents/x.md") and not get("codex").owns_agent_file(".claude/agents/x.md")


def test_the_hooks_for_sub_agents_are_installed_for_claude_code_only(repo, work):
    repo("install")
    settings = json.loads((repo.root / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert {"SubagentStart", "SubagentStop"} <= set(settings["hooks"])
    assert "lantern hook subagent-stop" in json.dumps(settings["hooks"]["SubagentStop"])
    assert not {"SubagentStart", "SubagentStop"} & set(get("codex").hooks())
    assert not {"SubagentStart", "SubagentStop"} & set(get("antigravity").hooks())


# --------------------------------------------------------------------------- the hooks


def _transcript(tmp_path) -> Path:
    answer = {
        "type": "assistant",
        "message": {
            "id": "m1",
            "model": "claude-opus-5-5",
            "usage": {"input_tokens": 10, "cache_creation_input_tokens": 5, "cache_read_input_tokens": 100, "output_tokens": 7},
        },
    }
    path = tmp_path / "agent-a1.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in (answer, answer)) + "\n", encoding="utf-8")  # a response written on two lines
    return path


def _hook(project, event, **fields):
    return agent_hooks.run(project, event, get("claude"), json.dumps({"session_id": "s1", "agent_id": "a1", **fields}))


def test_a_sub_agent_call_is_written_with_its_model_and_tokens(repo, work, tmp_path):
    _hook(work, "subagent-start", agent_type="Explore")
    reply = _hook(
        work, "subagent-stop", agent_type="Explore", agent_transcript_path=str(_transcript(tmp_path)), last_assistant_message="done"
    )
    (line,) = _lines(work, "subagent")
    assert reply.code == 0 and (line["agent"], line["model"], line["agent_id"]) == ("Explore", "claude-opus-5-5", "a1")
    assert line["tokens"] == {"input": 15, "cached": 100, "output": 7} and line["start"] and line["end"]
    assert _lines(work, "review") == []  # an ordinary sub-agent is no review


def test_the_reviewers_stop_writes_its_verdict_as_a_round_whatever_the_builder_says(repo, work, tmp_path):
    _built(repo)
    repo("review", "pack", "W-001")
    fresh = Project.load(repo.root)  # a hook reads the settings anew each time: the review is on now
    asked = review.open_pack(fresh, "W-001")["items"]
    _hook(fresh, "subagent-start", agent_type="lantern-reviewer")
    _hook(
        fresh,
        "subagent-stop",
        agent_type="lantern-reviewer",
        agent_transcript_path=str(_transcript(tmp_path)),
        last_assistant_message=_padded(fresh, ISSUES),
    )
    (line,) = _lines(work, "review")
    assert (line["source"], line["review_model"], line["issues"], line["items"]) == ("hook", "claude-opus-5-5", 2, asked)
    assert review.standing(work, "W-001") == "open"


def test_a_hook_that_cannot_read_the_subagents_transcript_still_writes_the_call(repo, work, tmp_path):
    _hook(work, "subagent-stop", agent_type="Explore", agent_transcript_path=str(tmp_path / "missing.jsonl"))
    (line,) = _lines(work, "subagent")
    assert line["agent"] == "Explore" and "tokens" not in line


def test_the_start_of_a_session_logs_a_hash_of_every_agent_definition_it_reads(repo, work, monkeypatch, tmp_path):
    home = tmp_path / "home"
    (home / ".claude" / "agents").mkdir(parents=True)
    (home / ".claude" / "agents" / "mine.md").write_text("---\nname: mine\n---\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))
    repo("profile", "set", "build.review=on")
    repo("install")
    agents = agent_hooks.harness_fields(get("claude"), Project.load(repo.root))["agents"]
    assert set(agents) == {".claude/agents/lantern-reviewer.md", "~/.claude/agents/mine.md"}
    assert all(len(h) == 12 for h in agents.values())
    first = dict(agents)
    (repo.root / ".claude" / "agents" / "lantern-reviewer.md").write_text("changed", encoding="utf-8")
    assert (
        agent_hooks.harness_fields(get("claude"), Project.load(repo.root))["agents"][".claude/agents/lantern-reviewer.md"]
        != first[".claude/agents/lantern-reviewer.md"]
    )


# --------------------------------------------------------------------------- the skill and the suggestion


@pytest.mark.parametrize(
    ("tool", "word"), [("claude", "lantern-reviewer"), ("codex", "--tool codex"), ("antigravity", "--tool antigravity")]
)
def test_the_build_skill_has_the_review_only_when_it_is_on_and_one_way_per_tool(tool, word):
    from lanternspec.core.profile import DEFAULTS, Profile, _deep_merge
    from lanternspec.tools.skills import generate

    t = get(tool)
    path = next(
        p for p in generate(Profile(data=_deep_merge(DEFAULTS, {"build": {"review": "on"}})), [t]) if p.endswith("l-build/SKILL.md")
    )
    body = generate(Profile(data=_deep_merge(DEFAULTS, {"build": {"review": "on"}})), [t])[path]
    assert "3¾" in body and word in body and "lantern:if" not in body and "lantern:endif" not in body
    others = {"lantern-reviewer", "--tool codex", "--tool antigravity"} - {word}
    assert not any(o in body for o in others)
    off = generate(Profile(data=_deep_merge(DEFAULTS, {})), [t])[path]
    assert "3¾" not in off and "lantern review" not in off


def test_the_suggestion_for_a_loop_project_includes_the_review(repo, work, monkeypatch):
    from lanternspec.report import build_mode

    monkeypatch.setattr(
        build_mode,
        "facts",
        lambda p: {
            "has_test": True,
            "skill_runs": 9,
            "clean_rate": 90,
            "loc": 10,
            "active_works": 1,
            "waiting_works": [],
            "parallel_ready": 0,
            "team": False,
            "code_files": 1,
            "tasks": 0,
        },
    )
    suggestion = build_mode.suggest(work)
    assert suggestion.settings["build.review"] == "on"
    off = {
        "has_test": False,
        "skill_runs": 0,
        "clean_rate": None,
        "loc": 10,
        "active_works": 1,
        "waiting_works": [],
        "parallel_ready": 0,
        "team": False,
        "code_files": 1,
        "tasks": 0,
    }
    monkeypatch.setattr(build_mode, "facts", lambda p: off)
    assert "build.review" not in build_mode.suggest(work).settings


def test_the_new_settings_are_checked(repo, work):
    code, out = repo("profile", "set", "build.review=maybe", ok=False)
    assert code == 1 and "build.review" in out
    code, out = repo("profile", "set", "build.review_limit=0", ok=False)
    assert code == 1 and "build.review_limit" in out
