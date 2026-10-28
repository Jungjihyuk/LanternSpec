"""Installer · adapters · agent hooks · helper commands (template · map · legacy · doctor)."""

import json
import re
import subprocess
import sys

import pytest

from conftest import docs, fill, init_project, sh
from lanternspec import tools
from lanternspec.core import frontmatter
from lanternspec.core.profile import DEFAULTS, Profile, _deep_merge
from lanternspec.tools.skills import generate as _generate


def gen(profile, names):
    return _generate(profile, tools.resolve(names))


def _profile(**over):
    return Profile(data=_deep_merge(DEFAULTS, over))


# --------------------------------------------------------------------------- adapters


def test_generated_skills_have_no_leftover_marks_for_every_tool_and_profile():
    for prof in (
        _profile(),
        _profile(
            idea={"capture": "auto"},
            learn={"detect": "ask", "verify": "explain"},
            plan={"ui_reference": "required", "ac_format": "simple"},
            docs={"remote": "local"},
            project={"team": "team", "members": ["a"]},
            knowledge={"path": "x"},
            build={"test": "pytest"},
            design={"approval": "off"},
        ),
    ):
        for names in (tools.NAMES, ["codex"], ["antigravity"]):
            files = gen(prof, names)
            for rel, text in files.items():
                assert "lantern:if" not in text and "lantern:endif" not in text, rel
                assert not re.search(r"<<[a-z_.]+>>", text), rel
                assert "<<SESSION_ID>>" not in text
                if rel.startswith(".agents/"):
                    assert "$ARGUMENTS" not in text
                if names == ["codex"]:
                    assert not re.search(r"(?<![\w/$.-])/l-[a-z]+\b", text), f"codex file keeps /l- call: {rel}"
        # Codex and Antigravity share .agents/skills: one set of 13, not two
        assert len([k for k in gen(prof, tools.NAMES) if k.endswith("SKILL.md")]) == 13 * 2


def test_adapter_shapes():
    prof = _profile()
    files = gen(prof, ["claude", "codex"])
    claude = files[".claude/skills/l-idea/SKILL.md"]
    meta = frontmatter.parse(claude).meta
    assert meta["name"] == "l-idea" and meta["disable-model-invocation"] is True
    assert "disable-model-invocation" not in frontmatter.parse(files[".claude/skills/l-plan/SKILL.md"]).meta
    assert files[".agents/skills/l-idea/agents/openai.yaml"].startswith("policy:")
    assert ".agents/skills/l-plan/agents/openai.yaml" not in files
    assert "$l-design" in files[".agents/skills/l-plan/SKILL.md"]
    agy = gen(prof, ["antigravity"])[".agents/skills/l-plan/SKILL.md"]
    assert set(frontmatter.parse(agy).meta) == {"name", "description"}
    assert "/l-design" in agy and "$l-design" not in agy


def test_codex_and_antigravity_share_one_calling_form():
    files = gen(_profile(), ["codex", "antigravity"])
    plan = files[".agents/skills/l-plan/SKILL.md"]
    assert "/l-design" in plan and "$l-design" not in plan  # shared folder → `/`, AGENTS.md tells Codex to use `$`
    assert files[".agents/skills/l-idea/agents/openai.yaml"].startswith("policy:")
    with pytest.raises(ValueError):
        tools.get("gemini")


def test_profile_values_reach_the_skills():
    files = gen(_profile(plan={"max_questions": 5}, idea={"capture": "ask"}), ["claude"])
    assert "최대 5개" in files[".claude/skills/l-plan/SKILL.md"]
    idea = files[".claude/skills/l-idea/SKILL.md"]
    assert "disable-model-invocation" not in frontmatter.parse(idea).meta and "대화당 한 번만" in idea
    learn = gen(_profile(), ["claude"])[".claude/skills/l-learn/SKILL.md"]
    assert "배우는 선로가 꺼져" in learn
    learn_on = gen(_profile(knowledge={"path": "x"}), ["claude"])[".claude/skills/l-learn/SKILL.md"]
    assert "${CLAUDE_SESSION_ID}" in learn_on and "지금 저장소 쓰기 방식: `direct`" in learn_on


# --------------------------------------------------------------------------- install · upgrade


def test_install_merges_rules_and_settings_without_clobbering(repo):
    (repo.root / "AGENTS.md").write_text("# 우리 팀 규칙\n- 테스트 먼저\n", encoding="utf-8")
    (repo.root / "CLAUDE.md").write_text("# 메모\n", encoding="utf-8")
    (repo.root / ".claude").mkdir()
    (repo.root / ".claude/settings.json").write_text(
        json.dumps({"permissions": {"allow": ["Bash(ls)"]}, "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "say done"}]}]}}),
        encoding="utf-8",
    )
    (repo.root / ".agents").mkdir()
    (repo.root / ".agents/hooks.json").write_text(
        json.dumps({"lint": {"PostToolUse": [{"matcher": "edit_file", "hooks": [{"command": "./lint.sh"}]}]}}), encoding="utf-8"
    )
    repo("install", "--tools", "claude,codex,antigravity")
    agents = (repo.root / "AGENTS.md").read_text(encoding="utf-8")
    assert agents.startswith("# 우리 팀 규칙") and "<!-- lanternspec:start -->" in agents
    assert (repo.root / "CLAUDE.md").read_text(encoding="utf-8").startswith("@AGENTS.md")
    settings = json.loads((repo.root / ".claude/settings.json").read_text(encoding="utf-8"))
    assert settings["permissions"] == {"allow": ["Bash(ls)"]}
    stop_cmds = [h["command"] for e in settings["hooks"]["Stop"] for h in e["hooks"]]
    assert "say done" in stop_cmds and any("lantern hook stop" in c for c in stop_cmds)
    assert set(settings["hooks"]) >= {"SessionStart", "PostToolUse", "UserPromptSubmit", "Stop"}
    # idempotent
    repo("install")
    agents2 = (repo.root / "AGENTS.md").read_text(encoding="utf-8")
    assert agents2.count("<!-- lanternspec:start -->") == 1
    settings2 = json.loads((repo.root / ".claude/settings.json").read_text(encoding="utf-8"))
    assert len(settings2["hooks"]["Stop"]) == 2
    agy = json.loads((repo.root / ".agents/hooks.json").read_text(encoding="utf-8"))
    assert set(agy) == {"lint", "lanternspec"}  # the user's named hook stays
    assert set(agy["lanternspec"]) == {"SessionStart", "PreInvocation", "PostToolUse", "PostInvocation", "Stop"}


def test_upgrade_skips_user_edits_and_follows_profile(repo):
    repo("install", "--tools", "claude,codex")
    init_project(repo)
    edited = repo.root / ".claude/skills/l-map/SKILL.md"
    edited.write_text(edited.read_text(encoding="utf-8") + "\n내 메모\n", encoding="utf-8")
    repo("profile", "set", "idea.capture=auto")
    _, out = repo("doctor", ok=False)
    assert "lantern upgrade" in out
    _, out = repo("upgrade")
    assert ".claude/skills/l-map/SKILL.md" in out.split("건드리지 않음")[1]
    assert "내 메모" in edited.read_text(encoding="utf-8")
    assert "알아서 기록" in (repo.root / ".claude/skills/l-idea/SKILL.md").read_text(encoding="utf-8")
    assert not (repo.root / ".agents/skills/l-idea/agents/openai.yaml").exists()
    repo("upgrade", "--force")
    assert "내 메모" not in edited.read_text(encoding="utf-8")


def test_upgrade_refreshes_untouched_templates_only(repo, monkeypatch):
    init_project(repo)
    from lanternspec.work import scaffold

    orig = scaffold.base_template_text

    def newer(name):
        text = orig(name)
        if name in ("ADR", "기획"):
            text = text.replace("template_version: 1.0.0", "template_version: 1.1.0").replace("based_on: 1.0.0", "based_on: 1.1.0")
        return text

    monkeypatch.setattr("lanternspec.tools.install.base_template_text", newer)
    plan_t = docs(repo) / "0. 템플릿/기획.md"
    fill(plan_t, [("## 범위 밖", "## 범위 밖 (다듬음)")])
    _, out = repo("upgrade")
    assert "양식 'ADR' 1.0.0 → 1.1.0" in out
    assert "양식 '기획': 기본 양식이 1.0.0 → 1.1.0로 바뀌었지만 다듬은 양식이라 그대로 둠" in out
    assert "template_version: 1.1.0" in (docs(repo) / "0. 템플릿/ADR.md").read_text(encoding="utf-8")
    assert "(다듬음)" in plan_t.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- agent hooks


def _hook(root, name, payload):
    return subprocess.run(
        [sys.executable, "-m", "lanternspec", "hook", name], cwd=str(root), input=json.dumps(payload), capture_output=True, text=True
    )


def test_agent_hooks_status_check_and_runlog(repo):
    r = _hook(repo.root, "session-start", {"session_id": "s1"})
    assert "/l-init" in r.stdout
    init_project(repo)
    repo("scaffold", "work", "작업")
    r = _hook(repo.root, "session-start", {"session_id": "s1", "model": "claude-opus-5-5", "source": "startup"})
    assert "[LanternSpec 지금 상황]" in r.stdout and "W-001 작업 (기획)" in r.stdout
    plan = docs(repo) / "2. 작업/W-001 작업/기획.md"
    _hook(repo.root, "prompt", {"session_id": "s1", "prompt": "/l-plan 작업"})
    fill(plan, [("## 왜", "## 이유")])
    r = _hook(repo.root, "post-tool", {"session_id": "s1", "tool_name": "Edit", "tool_input": {"file_path": str(plan)}})
    assert r.returncode == 2 and "LanternSpec 문서 양식" in r.stderr and "'## 왜'" in r.stderr
    fill(plan, [("## 이유", "## 왜")])
    r = _hook(repo.root, "post-tool", {"session_id": "s1", "tool_name": "Write", "tool_input": {"file_path": str(plan)}})
    assert r.returncode == 0 and "additionalContext" in r.stdout
    outside = repo.root / "src.py"
    outside.write_text("x", encoding="utf-8")
    r = _hook(repo.root, "post-tool", {"session_id": "s1", "tool_name": "Write", "tool_input": {"file_path": str(outside)}})
    assert r.returncode == 0 and not r.stdout
    _hook(repo.root, "post-tool", {"session_id": "s1", "tool_name": "Bash", "tool_input": {"command": "ls"}})
    transcript = repo.root.parent / "t.jsonl"
    transcript.write_text(json.dumps({"type": "assistant", "message": {"model": "claude-haiku-5-5"}}) + "\nnot json\n", encoding="utf-8")
    _hook(repo.root, "stop", {"session_id": "s1", "transcript_path": str(transcript)})
    rec = json.loads((repo.root / ".lantern/runs.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert rec["skill"] == "l-plan" and rec["model"] == "claude-haiku-5-5"
    assert rec["tools"] == {"Edit": 1, "Write": 2, "Bash": 1} and rec["tool_calls"] == 4
    # broken payload never breaks the agent
    r = subprocess.run(
        [sys.executable, "-m", "lanternspec", "hook", "post-tool"], cwd=str(repo.root), input="not json", capture_output=True, text=True
    )
    assert r.returncode == 0


# --------------------------------------------------------------------------- template · map · legacy · doctor


def test_template_lint_level_bump_usage_new(repo, tmp_path):
    init_project(repo)
    _, out = repo("template", "lint")
    assert "✖" not in out
    t = docs(repo) / "0. 템플릿/기획.md"
    fill(t, [("{{범위 밖}}", "{{title}}")])
    code, out = repo("template", "lint", "기획", ok=False)
    assert code == 1 and "date · time · title 금지" in out
    fill(t, [("{{title}}", "{{범위 밖}}")])
    repo.git("add", "-A")
    repo.git("commit", "-qm", "docs: 준비")
    _, out = repo("template", "level", "기획")
    assert "바뀐 것 없음" in out
    fill(t, [("> [!guide] 🟦 원본 칸 · 이번에", "> [!guide] 🟦 원본 칸 · 이번 작업에서")])
    assert "patch" in repo("template", "level", "기획")[1]
    fill(t, [("## 확인 필요", "## 위험\n{{위험}}\n\n## 확인 필요")])
    assert "minor" in repo("template", "level", "기획")[1]
    _, out = repo("template", "bump", "기획", "--auto", "--note", "위험 칸")
    assert "minor → v1.1.0" in out
    assert "| 1.1.0 |" in t.read_text(encoding="utf-8")
    _, out = repo("template", "lint", "기획")
    assert "변경 기록 마지막 버전" not in out
    repo("scaffold", "work", "하나")
    repo("scaffold", "work", "둘")
    _, out = repo("template", "usage", "기획")
    assert "늘 비어 있음" in out
    draft = tmp_path / "시안.md"
    draft.write_text(
        "# 회고\n\n## 잘한 것\n배포를 자동화했다\n\n## 아쉬운 것\n- 테스트\n\n| 항목 | 점수 |\n|---|---|\n| 속도 | 3 |\n| 품질 | 4 |\n",
        encoding="utf-8",
    )
    _, out = repo("template", "new", "회고", "--from", str(draft))
    assert "{{잘한 것}}" in out and "- {{아쉬운 것}}" in out and "| 항목 | 점수 |" in out and "속도" not in out
    repo("template", "new", "회고", "--from", str(draft), "--apply")
    _, out = repo("template", "lint", "회고")
    assert "✖" not in out
    repo("scaffold", "custom", "회고", "4. 운영 기록/2026-10 회고.md")
    assert (docs(repo) / "4. 운영 기록/2026-10 회고.md").exists()


def test_template_migrate_keeps_every_line(repo):
    init_project(repo)
    repo("scaffold", "work", "작업")
    plan = docs(repo) / "2. 작업/W-001 작업/기획.md"
    fill(plan, [("- {{범위 밖}}", "- 애플 로그인"), ("## 확인 필요", "## 메모\n남기고 싶은 메모\n\n## 확인 필요")])
    t = docs(repo) / "0. 템플릿/기획.md"
    fill(t, [("## 범위 밖", "## 하지 않는 것"), ("template_version: 1.0.0", "template_version: 2.0.0")])
    _, out = repo("template", "outdated")
    assert "1.0.0 → 2.0.0 (major)" in out
    _, preview = repo("template", "migrate", "기획", "--map", "범위 밖=하지 않는 것")
    assert "미리보기" in preview and "template_version: 1.0.0" in plan.read_text(encoding="utf-8")
    repo("template", "migrate", "기획", "--map", "범위 밖=하지 않는 것", "--apply")
    text = plan.read_text(encoding="utf-8")
    assert "## 하지 않는 것\n" in text and "- 애플 로그인" in text
    assert "## 📦 옮기지 못한 내용" in text and "### 메모\n남기고 싶은 메모" in text
    assert frontmatter.parse(text).meta["template_version"] == "2.0.0"
    _, out = repo("template", "outdated")
    assert "없습니다" in out


def test_map_keeps_human_text_and_is_quiet_when_nothing_changed(repo):
    init_project(repo)
    moc = docs(repo) / "개발문서 MOC.md"
    moc.write_text(
        moc.read_text(encoding="utf-8").replace("<!-- l-map:start -->", "사람이 쓴 문단\n\n<!-- l-map:start -->"), encoding="utf-8"
    )
    repo("map")
    first = moc.read_text(encoding="utf-8")
    assert "사람이 쓴 문단" in first
    repo("map")
    assert moc.read_text(encoding="utf-8") == first
    repo("scaffold", "work", "새 작업")
    repo("map")
    assert "W-001 새 작업" in moc.read_text(encoding="utf-8") and "사람이 쓴 문단" in moc.read_text(encoding="utf-8")


def test_brownfield_legacy_adopt(repo):
    old = repo.root / "docs" / "old"
    old.mkdir(parents=True)
    (old / "기획서.md").write_text("# 옛 기획\n\n## 목적\n결제를 쉽게.\n- TODO: 환불은 나중에\n", encoding="utf-8")
    (repo.root / "docs" / "README.md").write_text("# 시스템\n", encoding="utf-8")
    repo.git("add", "-A")
    repo.git("commit", "-qm", "old docs")
    repo(
        "profile",
        "write",
        "--name",
        "결제",
        "--origin",
        "brownfield",
        "--team",
        "solo",
        "--clients",
        "web",
        "--server",
        "custom",
        "--design",
        "none",
    )
    _, out = repo("legacy", "adopt")
    assert "5. 기존 문서/old" in out
    assert "R  " in sh(repo.root, "git", "status", "--short").stdout or "R " in sh(repo.root, "git", "status", "--short").stdout
    repo("scaffold", "init")
    legacy_map = (docs(repo) / "5. 기존 문서/기존 문서 지도.md").read_text(encoding="utf-8")
    assert "[[5. 기존 문서/old/기획서\\|기획서]]" in legacy_map and "[[5. 기존 문서/README\\|README]]" in legacy_map
    _, out = repo("legacy", "todos")
    assert "TODO: 환불은 나중에" in out
    _, out = repo(
        "template", "migrate", "5. 기존 문서/old/기획서.md", "--to", "기획", "--dest", "2. 작업/옛 기획.md", "--map", "목적=왜", "--apply"
    )
    new = (docs(repo) / "2. 작업/옛 기획.md").read_text(encoding="utf-8")
    assert "## 왜\n결제를 쉽게." in new
    assert (docs(repo) / "5. 기존 문서/old/기획서.md").exists()
    _, out = repo("check")
    assert "5. 기존 문서" not in out  # legacy originals are never checked


def test_doctor_reports(repo):
    code, out = repo("doctor", ok=False)
    assert code == 1 and "lantern.yaml이 없습니다" in out
    repo("install")
    init_project(repo)
    repo("hooks", "install")
    code, out = repo("doctor")
    assert "lantern upgrade" in out  # skills were rendered before the profile existed
    repo("upgrade")
    code, out = repo("doctor")
    assert "문서 저장 방식 shared — 구조가 맞음" in out and "스킬 13개 최신" in out


def test_h7_sync_nudge_once_per_work_and_h8_compact_roundtrip(repo):
    init_project(repo)
    repo("scaffold", "work", "작업")
    repo("scaffold", "doc", "W-001", "할 일")
    repo("task", "add", "W-001", "하나", "--size", "S")
    repo("scaffold", "doc", "W-001", "기록")
    rec = docs(repo) / "2. 작업/W-001 작업/기록.md"
    fill(rec, [("- 진행: {{진행 중}}", "- 진행: 로그인 버튼 붙이는 중")])
    repo.git("add", "-A")
    repo.git("commit", "-qm", "docs: 준비")
    (repo.root / "app.py").write_text("x = 1\n", encoding="utf-8")
    r = _hook(repo.root, "stop", {"session_id": "s1"})
    assert not r.stdout  # still in planning: no nudge
    repo("task", "start", "W-001-T01")  # → 구현, and 할 일.md changes (docs touched)
    repo.git("add", "docs")
    repo.git("commit", "-qm", "docs: 시작")
    r = _hook(repo.root, "stop", {"session_id": "s1"})
    assert "/l-sync" in json.loads(r.stdout)["systemMessage"]
    r = _hook(repo.root, "stop", {"session_id": "s1"})
    assert not r.stdout  # once per work
    _hook(repo.root, "pre-compact", {"session_id": "s1"})
    # before compaction: the script overwrites 기록.md "지금 상황" with the state; what was written there moves to "지난 기록"
    text = rec.read_text(encoding="utf-8")
    now = text.split("## 지금 상황", 1)[1].split("## 증거", 1)[0]
    history = text.split("## 지난 기록", 1)[1]
    assert "- 진행: 구현 · 할 일 0/1 · 하는 중 W-001-T01" in now and "- 다음: W-001-T01 하나 (하는 중)" in now
    assert "- 열린 질문:" not in now  # "❓ 확인 필요" in guide text doesn't count
    assert "로그인 버튼 붙이는 중" not in now and "로그인 버튼 붙이는 중" in history
    assert "> [!guide] **덮어쓰는 칸.**" in now  # the guide line stays
    r = _hook(repo.root, "session-start", {"session_id": "s1", "source": "compact"})
    assert "압축 전 진행 상황 — 문서에 저장됨" in r.stdout and "하는 중 W-001-T01" in r.stdout and "로그인 버튼 붙이는 중" in r.stdout
    r = _hook(repo.root, "session-start", {"session_id": "s1", "source": "startup"})
    assert "압축 전 진행 상황" not in r.stdout
    code, out = repo("check", ok=False)
    assert code == 0, out
    # a second compaction keeps one 지금 상황 and doesn't pile up identical history
    _hook(repo.root, "pre-compact", {"session_id": "s1"})
    assert rec.read_text(encoding="utf-8").count("로그인 버튼 붙이는 중") == 1


def test_h8_without_a_record_writes_a_session_doc(repo):
    init_project(repo)
    repo("scaffold", "work", "작업")  # in planning: no 기록.md yet
    _hook(repo.root, "pre-compact", {"session_id": "s2"})
    sessions = list((docs(repo) / "4. 운영 기록/세션").glob("*.md"))
    assert len(sessions) == 1
    text = sessions[0].read_text(encoding="utf-8")
    assert frontmatter.parse(text).meta["type"] == "session"
    assert "**W-001**" in text and "- 진행: 기획" in text
    r = _hook(repo.root, "session-start", {"session_id": "s2", "source": "compact"})
    assert "세션/" in r.stdout and "- 진행: 기획" in r.stdout
    code, out = repo("check", ok=False)
    assert code == 0, out


def test_mcp_server_and_install_registration(repo, vault):
    init_project(repo, vault=vault)
    msgs = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "search", "arguments": {"query": "JWT"}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "propose", "arguments": {"title": "CRDT"}}},
        {"jsonrpc": "2.0", "id": 5, "method": "nope"},
    ]
    r = subprocess.run(
        [sys.executable, "-m", "lanternspec", "mcp"],
        cwd=str(repo.root),
        input="\n".join(json.dumps(m) for m in msgs) + "\n",
        capture_output=True,
        text=True,
    )
    out = [json.loads(l) for l in r.stdout.splitlines()]
    assert [o["id"] for o in out] == [1, 2, 3, 4, 5]
    assert {t["name"] for t in out[1]["result"]["tools"]} == {"search", "read", "propose", "write"}
    assert '"title": "JWT"' in out[2]["result"]["content"][0]["text"]
    assert (docs(repo) / "📒 부채/노트 초안/CRDT.md").exists()
    assert out[4]["error"]["code"] == -32601
    repo("install", "--tools", "claude,codex,antigravity", "--mcp")
    assert json.loads((repo.root / ".mcp.json").read_text())["mcpServers"]["lantern-knowledge"]["args"] == ["mcp"]
    assert "[mcp_servers.lantern-knowledge]" in (repo.root / ".codex/config.toml").read_text()
    plugin = repo.root / ".agents/plugins/lanternspec"
    assert json.loads((plugin / "plugin.json").read_text())["name"] == "lanternspec"
    assert json.loads((plugin / "mcp_config.json").read_text())["mcpServers"]["lantern-knowledge"]["args"] == ["mcp"]
    repo("upgrade")  # keeps the MCP choice
    assert (repo.root / ".codex/config.toml").read_text().count("[mcp_servers.lantern-knowledge]") == 1


def test_install_explains_next_steps_and_other_ai_tools(repo, monkeypatch):
    found = {"claude": "/bin/claude", "codex": "/bin/codex"}  # pretend only Claude Code and Codex are on this computer
    monkeypatch.setattr("lanternspec.cli.tools.shutil.which", found.get)
    _, out = repo("install")
    assert "1. 이 폴더에서 Claude Code를 엽니다 — 터미널에 `claude` 입력" in out
    assert "2. 입력창에 `/l-init`을 입력합니다" in out
    assert "이 컴퓨터에 Codex도 있습니다. 함께 쓰려면: lantern install --tools claude,codex" in out
    assert "Antigravity" not in out  # tools that are not installed are not suggested
    _, out = repo("install", "--tools", "claude,codex")
    assert "Claude Code는 `claude`, Codex는 `codex`" in out and "(Codex는 `$l-init`)" in out
    assert "이 컴퓨터에" not in out  # once everything is set up, nothing more is suggested
    assert "H-" not in out  # internal spec numbers never reach the user
