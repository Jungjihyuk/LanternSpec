"""Each AI tool gets a part's rules, whether or not it reads a folder's AGENTS.md by itself.

Claude Code reads a folder's AGENTS.md when it opens a file there; Codex and Antigravity read only the
files from the root to the folder they started in. So the hooks hand a part's AGENTS.md over once per
part and conversation: Codex before the first edit, Antigravity right after it. After compaction the
note says which part the conversation was in.
"""

import json

from conftest import init_project
from lanternspec.core.project import Project
from lanternspec.tools import agent_hooks, get


def _project(repo):
    init_project(repo, "--kind", "service", "--external", "no", "--languages", "python,typescript")
    for folder, manifest in (("backend", "pyproject.toml"), ("web", "package.json")):
        (repo.root / folder).mkdir()
        (repo.root / folder / manifest).write_text("{}\n" if manifest.endswith(".json") else "[project]\nname='b'\n", encoding="utf-8")
    repo("install", "--tools", "claude,codex,antigravity")
    repo("parts", "add", "backend")
    repo("parts", "add", "web")
    repo("upgrade")
    return Project.load(repo.root)


def _run(project, tool, event, data):
    reply = agent_hooks.run(project, event, get(tool), json.dumps(data))
    return reply.stdout


def _patch(path):
    return {"command": f"*** Begin Patch\n*** Update File: {path}\n*** End Patch"}


def test_codex_gets_a_parts_rules_once_before_its_first_edit_there(repo):
    project = _project(repo)
    call = {"session_id": "x1", "cwd": str(repo.root), "tool_name": "apply_patch"}
    first = _run(project, "codex", "pre-tool", {**call, "tool_input": _patch("backend/app.py")})
    context = json.loads(first)["hookSpecificOutput"]["additionalContext"]
    assert "backend 영역의 규칙 (backend/AGENTS.md)" in context and "## 영역 backend" in context
    assert _run(project, "codex", "pre-tool", {**call, "tool_input": _patch("backend/other.py")}) == ""  # once per part
    web = json.loads(_run(project, "codex", "pre-tool", {**call, "tool_input": _patch("web/index.ts")}))
    assert "web 영역의 규칙" in web["hookSpecificOutput"]["additionalContext"]
    assert _run(project, "codex", "pre-tool", {**call, "tool_input": _patch("README.md")}) == ""  # outside every part


def test_codex_started_inside_a_part_already_read_it(repo):
    project = _project(repo)
    data = {"session_id": "x2", "cwd": str(repo.root / "backend"), "tool_name": "apply_patch", "tool_input": _patch("app.py")}
    assert _run(project, "codex", "pre-tool", data) == ""


def test_claude_reads_it_itself_so_nothing_is_added(repo):
    project = _project(repo)
    data = {"session_id": "c1", "cwd": str(repo.root), "tool_name": "Write", "tool_input": {"file_path": str(repo.root / "backend/app.py")}}
    out = _run(project, "claude", "post-tool", data)
    assert "영역의 규칙" not in out


def test_antigravity_gets_it_with_the_next_call_after_the_first_edit(repo):
    project = _project(repo)
    common = {"conversationId": "a1", "workspacePaths": [str(repo.root)]}
    _run(project, "antigravity", "post-tool", {**common, "toolCall": {"name": "write_file", "args": {"Path": str(repo.root / "web/x.ts")}}})
    held = json.loads(_run(project, "antigravity", "feedback", {**common, "invocationNum": 1}))["injectSteps"]
    assert "web 영역의 규칙" in held[0]["systemMessage"]["systemMessage"]
    reminder = json.loads(_run(project, "antigravity", "prompt", {**common, "invocationNum": 2}))["injectSteps"]
    assert reminder == [{"ephemeralMessage": reminder[0]["ephemeralMessage"]}] and "지금 영역: web" in reminder[0]["ephemeralMessage"]


def test_the_note_after_compaction_says_which_part_was_in_progress(repo):
    project = _project(repo)
    call = {"session_id": "x3", "cwd": str(repo.root), "tool_name": "apply_patch", "tool_input": _patch("backend/app.py")}
    _run(project, "codex", "pre-tool", call)
    after = _run(project, "codex", "session-start", {"session_id": "x3", "source": "compact"})
    assert "지금 영역: backend — 규칙은 backend/AGENTS.md에" in json.loads(after)["hookSpecificOutput"]["additionalContext"]


def test_an_agents_md_deeper_than_a_part_folder_is_said_not_to_reach_codex(repo):
    _project(repo)
    (repo.root / "backend/app").mkdir()
    (repo.root / "backend/app/AGENTS.md").write_text("# 앱 규칙\n", encoding="utf-8")
    _, doctor = repo("doctor", ok=False)
    assert "backend/app/AGENTS.md: Codex · Antigravity CLI에는 자동으로 전달되지 않습니다" in doctor
    _, upgrade = repo("upgrade")
    assert "⚠ backend/app/AGENTS.md: Codex · Antigravity CLI에는 자동으로 전달되지 않습니다" in upgrade
    assert "backend/AGENTS.md: " not in doctor  # the part's own AGENTS.md is handed over


def test_claude_alone_needs_no_such_note(repo):
    init_project(repo)
    repo("install", "--tools", "claude")
    (repo.root / "lib").mkdir()
    (repo.root / "lib/AGENTS.md").write_text("# lib\n", encoding="utf-8")
    _, doctor = repo("doctor", ok=False)
    assert "자동으로 전달되지 않습니다" not in doctor
