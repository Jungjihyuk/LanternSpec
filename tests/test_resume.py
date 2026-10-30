"""Carrying a conversation on in any AI tool: the hooks note each conversation, `lantern resume` sums it up.

Each tool keeps its own transcript in its own format; the hooks note where, so nobody has to find it.
A conversation whose last hook call was not a stop was cut off in the middle of a turn.
"""

import json
from pathlib import Path

from lanternspec.core.project import Project
from lanternspec.tools import agent_hooks, get, sessions

SAMPLES = Path(__file__).parent / "fixtures" / "transcripts"


def test_each_tool_reads_its_own_transcript_format():
    claude = get("claude").read_transcript(SAMPLES / "claude.jsonl")
    assert [(t.role, t.text) for t in claude] == [
        ("user", "로그인 버튼 색을 바꿔 줘"),
        ("assistant", "버튼 파일을 고치겠습니다."),
        ("assistant", "색을 파란색으로 바꿨습니다."),
        ("user", "테스트도 돌려 줘"),
    ]  # tool results, thinking, subagent lines and the half-written last line are left out
    assert claude[1].tools == ["Edit"] and claude[1].files == ["src/Button.tsx"]
    codex = get("codex").read_transcript(SAMPLES / "codex.jsonl")
    assert [(t.role, t.text, t.files) for t in codex] == [
        ("user", "$l-build W-012", []),
        ("assistant", "", ["docs/a.md"]),
        ("assistant", "T03을 끝냈습니다.", []),
    ]  # text Codex adds to user messages itself is left out
    agy = get("antigravity").read_transcript(SAMPLES / "antigravity.jsonl")
    assert [(t.role, t.text) for t in agy] == [("user", "지역 필터 추가해 줘"), ("assistant", ""), ("assistant", "필터를 추가했습니다.")]
    assert agy[1].files == ["/repo/src/filter.ts"]


def _hook(project, tool, event, data):
    agent_hooks.run(project, event, get(tool), json.dumps(data))


def test_hooks_note_each_conversation_and_tell_a_cut_off_one(repo):
    project = Project.load(repo.root)
    claude = str(SAMPLES / "claude.jsonl")
    _hook(project, "claude", "session-start", {"session_id": "c1", "transcript_path": claude, "source": "startup"})
    _hook(project, "claude", "prompt", {"session_id": "c1", "transcript_path": claude, "prompt": "테스트도 돌려 줘"})
    _hook(project, "antigravity", "session-start", {"conversationId": "a1", "transcriptPath": str(SAMPLES / "antigravity.jsonl")})
    _hook(project, "antigravity", "prompt", {"conversationId": "a1", "invocationNum": 0, "lastUserInput": "지역 필터 추가해 줘"})
    _hook(project, "antigravity", "stop", {"conversationId": "a1", "terminationReason": "NO_TOOL_CALL"})
    found = {s.id: s for s in sessions.recent(project)}
    assert found["c1"].cut_off and found["c1"].last_prompt == "테스트도 돌려 줘" and found["c1"].transcript == claude
    assert not found["a1"].cut_off and found["a1"].tool == "antigravity"


def test_resume_shows_where_the_latest_conversation_stopped(repo):
    project = Project.load(repo.root)
    claude = str(SAMPLES / "claude.jsonl")
    _hook(project, "claude", "prompt", {"session_id": "c1", "transcript_path": claude, "prompt": "테스트도 돌려 줘"})
    _hook(project, "codex", "prompt", {"session_id": "x9", "prompt": "$l-resume"})  # the conversation asking to resume
    _, out = repo("resume")
    assert "Claude Code" in out and "⚠ 끊김" in out and "Codex" not in out
    assert "- 테스트도 돌려 줘" in out and "AI의 마지막 말: 색을 파란색으로 바꿨습니다." in out
    assert "고친 파일: src/Button.tsx" in out
    assert "마지막 요청에 답이 없습니다" in out  # cut off right after the request
    _, earlier = repo("resume", "--more", "1")
    assert "더 앞의 내용이 없습니다" in earlier  # the sample fits on one page


def test_resume_falls_back_when_the_transcript_cannot_be_read(repo):
    project = Project.load(repo.root)
    gone = repo.root / "missing.jsonl"
    _hook(project, "claude", "prompt", {"session_id": "c2", "transcript_path": str(gone), "prompt": "계속"})
    _, out = repo("resume")
    assert "대화 기록 파일이 없거나" in out
    odd = repo.root / "odd.jsonl"
    odd.write_text("first\nsecond\nthird\n", encoding="utf-8")
    record = project.state / "sessions" / "c2.json"
    data = json.loads(record.read_text(encoding="utf-8"))
    record.write_text(json.dumps({**data, "tool": "someday-tool", "transcript": str(odd)}), encoding="utf-8")
    _, out = repo("resume")
    assert "형식을 읽지 못했습니다" in out and "third" in out


def test_resume_says_so_when_nothing_was_recorded(repo):
    _, out = repo("resume")
    assert "기록된 지난 대화가 없습니다" in out


def test_every_tool_names_its_transcript_in_the_documented_hook_payloads():
    hooks = Path(__file__).parent / "fixtures" / "hooks"
    for tool in ("claude", "codex", "antigravity"):
        data = json.loads((hooks / tool / "session-start.json").read_text(encoding="utf-8"))
        assert get(tool).parse_hook("session-start", data).transcript.endswith(".jsonl"), tool


def test_conversation_records_never_reach_git_even_in_projects_set_up_earlier(repo):
    project = Project.load(repo.root)
    (project.state).mkdir(exist_ok=True)
    old = "# 옛 버전이 만든 파일\nruns.jsonl\nruns-state/\nhook-state/\npack/\n"
    (project.state / ".gitignore").write_text(old, encoding="utf-8")
    _hook(project, "claude", "prompt", {"session_id": "c1", "prompt": "개인적인 요청"})
    text = (project.state / ".gitignore").read_text(encoding="utf-8")
    assert text.startswith(old) and "sessions/" in text.splitlines()
    assert not repo.git("status", "--porcelain", "--", ".lantern/sessions").stdout.strip()


def test_a_turn_cut_off_while_using_a_tool_says_what_it_was_doing(repo):
    project = Project.load(repo.root)
    transcript = repo.root / "agy.jsonl"
    transcript.write_text(
        json.dumps({"type": "USER_INPUT", "content": "<USER_REQUEST>테스트 돌려 줘</USER_REQUEST>"})
        + "\n"
        + json.dumps({"type": "PLANNER_RESPONSE", "tool_calls": [{"name": "run_command", "args": {"CommandLine": "pytest"}}]})
        + "\n",
        encoding="utf-8",
    )
    _hook(
        project,
        "antigravity",
        "prompt",
        {"conversationId": "a2", "invocationNum": 0, "lastUserInput": "테스트 돌려 줘", "transcriptPath": str(transcript)},
    )
    _, out = repo("resume")
    assert "⚠ 끊김" in out and "하던 일: run_command" in out
