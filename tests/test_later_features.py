"""Features added after the first version: tech-question and idea detection · Notion · competency debt · Figma/Canva ·
AI work evaluation · work-mode suggestion · [P] parallel tasks · due-date suggestions · mockup comparison · the big loop."""

import json
import struct
import subprocess
import sys
import zipfile
import zlib

import pytest

from conftest import docs, init_project, work_dir
from lanternspec import tools
from lanternspec.core import frontmatter
from lanternspec.core.profile import DEFAULTS, Profile, _deep_merge
from lanternspec.tools.skills import generate as _generate


def gen(profile, names):
    return _generate(profile, tools.resolve(names))


def _hook(root, name, payload):
    return subprocess.run(
        [sys.executable, "-m", "lanternspec", "hook", name], cwd=str(root), input=json.dumps(payload), capture_output=True, text=True
    )


def _ctx(r):
    return json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"] if r.stdout.strip() else ""


# --------------------------------------------------------------------------- tech-question · idea detection


def test_h9_learning_question_detection(repo, vault):
    init_project(repo, vault=vault)
    assert not _ctx(_hook(repo.root, "prompt", {"session_id": "s", "prompt": "JWT가 뭐야?"}))  # manual: never counts
    repo("profile", "set", "learn.detect=ask")
    assert "📒 부채로 남길까요?" in _ctx(_hook(repo.root, "prompt", {"session_id": "s", "prompt": "JWT가 뭐야?"}))
    repo("profile", "set", "learn.detect=auto")
    ctx = _ctx(_hook(repo.root, "prompt", {"session_id": "s", "prompt": "Optimistic Lock이 뭐예요?"}))
    assert "카드가 없습니다" in ctx
    assert not _ctx(_hook(repo.root, "prompt", {"session_id": "s", "prompt": "Optimistic Lock이 뭐예요?"}))  # once
    repo("debt", "new", "JWT", "--area", "backend", "--session", "s0")
    ctx = _ctx(_hook(repo.root, "prompt", {"session_id": "s1", "prompt": "what is JWT?"}))
    assert "물은 횟수를 셌습니다 (2번째" in ctx
    assert not _ctx(_hook(repo.root, "prompt", {"session_id": "s1", "prompt": "JWT가 뭐야"}))  # same conversation
    repo("debt", "known", "add", "React")
    assert not _ctx(_hook(repo.root, "prompt", {"session_id": "s2", "prompt": "React가 뭐야?"}))
    assert not _ctx(_hook(repo.root, "prompt", {"session_id": "s2", "prompt": "/l-learn Kafka가 뭐야"}))


def test_h10_idea_detection(repo):
    init_project(repo)
    say = {"session_id": "s", "prompt": "나중에 다크 모드도 있으면 좋겠다"}
    assert not _ctx(_hook(repo.root, "prompt", say))
    repo("profile", "set", "idea.capture=ask")
    assert "아이디어로 남길까요" in _ctx(_hook(repo.root, "prompt", say))
    assert not _ctx(_hook(repo.root, "prompt", say))  # once per conversation
    repo("profile", "set", "idea.capture=auto")
    assert "--auto" in _ctx(_hook(repo.root, "prompt", say))
    assert not _ctx(_hook(repo.root, "prompt", {"session_id": "s", "prompt": "로그인 버그 고쳐줘"}))


# --------------------------------------------------------------------------- knowledge adapters


class FakeNotion:
    def __init__(self):
        self.calls = []

    def __call__(self, req):
        body = json.loads(req.data.decode()) if req.data else None
        self.calls.append((req.get_method(), req.full_url, body))
        assert req.headers["Authorization"] == "Bearer secret"
        if req.full_url.endswith("/search"):
            data = {
                "results": [
                    {
                        "id": "p1",
                        "url": "https://notion.so/p1",
                        "last_edited_time": "2026-10-01T00:00:00Z",
                        "properties": {"Name": {"type": "title", "title": [{"plain_text": "JWT"}]}},
                    }
                ]
            }
        elif "/children" in req.full_url and req.get_method() == "GET":
            data = {
                "results": [
                    {"type": "heading_2", "heading_2": {"rich_text": [{"plain_text": "개요"}]}},
                    {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "서명된 토큰"}]}},
                ],
                "has_more": False,
            }
        else:
            data = {"id": "new", "url": "https://notion.so/new"}

        class Resp:
            def read(self_inner):
                return json.dumps(data).encode()

            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False

        return Resp()


def test_notion_adapter_contract():
    from lanternspec.learn.knowledge import KnowledgeError
    from lanternspec.learn.knowledge.notion import NotionAdapter, markdown_to_blocks

    with pytest.raises(KnowledgeError):
        NotionAdapter("parent", None)
    fake = FakeNotion()
    n = NotionAdapter("abc-def", "secret", opener=fake)
    hits = n.search("JWT")
    assert hits[0].title == "JWT" and hits[0].path == "p1"
    assert n.read("p1") == "## 개요\n서명된 토큰"
    url = n.write("2. Study/CRDT.md", "# CRDT\n- 충돌 없는 복제\n" + "\n".join(f"줄 {i}" for i in range(120)))
    assert url == "https://notion.so/new"
    create = next(c for c in fake.calls if c[1].endswith("/pages"))
    assert create[2]["parent"] == {"page_id": "abcdef"} and len(create[2]["children"]) == 100
    assert any(c[0] == "PATCH" for c in fake.calls)  # the rest in a second request
    kinds = [b["type"] for b in markdown_to_blocks("# A\n- b\n> c\n```\nx\n```\nd")]
    assert kinds == ["heading_1", "bulleted_list_item", "quote", "code", "paragraph"]


# --------------------------------------------------------------------------- competency debt


def test_competency_debt_flow(repo, vault):
    init_project(repo, vault=vault)
    repo("debt", "new", "JWT", "--area", "backend")
    code, out = repo("debt", "promote", "D-001", ok=False)
    assert code == 1 and "이해가 먼저" in out
    repo("debt", "resolve", "D-001")
    repo("debt", "promote", "JWT")
    card = next((docs(repo) / "📒 부채/카드").glob("D-002 *"))
    meta = frontmatter.parse(card.read_text(encoding="utf-8")).meta
    assert meta["kind"] == "역량" and meta["from"] == "D-001" and meta["status"] == "처음"
    code, _ = repo("debt", "promote", "D-001", ok=False)
    assert code == 1
    repo("debt", "practice", "D-002", "토큰 발급 API를 만들어 봄")
    text = card.read_text(encoding="utf-8")
    assert "토큰 발급 API를 만들어 봄" in text and frontmatter.parse(text).meta["status"] == "연습 중"
    repo("debt", "new", "레거시 결제 모듈", "--kind", "기술", "--area", "backend")
    repo("debt", "status")
    status = (docs(repo) / "📒 부채/부채 현황.md").read_text(encoding="utf-8")
    assert "| 🛠 역량 | 1 |" in status and "| 🧱 기술 | 1 |" in status and "✍️ 연습 중 1" in status
    _, out = repo("check")
    assert "✖" not in out


# --------------------------------------------------------------------------- Figma · Canva · screens


def test_figma_and_canva_reach_the_skills(repo):
    for tool, word in (("figma", "Figma MCP"), ("canva", "Canva MCP")):
        files = gen(Profile(data=_deep_merge(DEFAULTS, {"design": {"tool": tool}})), ["claude"])
        assert word in files[".claude/skills/l-design/SKILL.md"]
        assert "Claude Design으로 시안을 만든다" not in files[".claude/skills/l-design/SKILL.md"]
    init_project(repo, "--design", "figma")
    assert "| 디자인 도구 | Figma (MCP) |" in (docs(repo) / "3. 현재 상태/프로젝트 정의서.md").read_text(encoding="utf-8")


def _png(path, w, h, color_fn):
    raw = b"".join(b"\x00" + bytes(c for x in range(w) for c in color_fn(x, y)) for y in range(h))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def test_screen_import_and_compare(repo, tmp_path):
    init_project(repo)
    repo("scaffold", "work", "화면", "--ui")
    mock = tmp_path / "mock.png"
    _png(mock, 64, 64, lambda x, y: (255, 255, 255) if y > 16 else (0, 0, 255))
    same = tmp_path / "same.png"
    _png(same, 128, 128, lambda x, y: (255, 255, 255) if y > 32 else (0, 0, 250))
    diff = tmp_path / "diff.png"
    _png(diff, 64, 64, lambda x, y: (0, 0, 0))
    bundle = tmp_path / "handoff.zip"
    with zipfile.ZipFile(bundle, "w") as z:
        z.writestr("handoff/index.html", "<html></html>")
        z.writestr("handoff/../evil.html", "x")
        z.writestr("__MACOSX/x.png", "x")
    _, out = repo("screen", "import", "W-001", str(mock), str(bundle))
    screens = work_dir(repo, "W-001") / "화면"
    assert (screens / "mock.png").exists() and (screens / "handoff/handoff/index.html").exists()
    assert not (screens / "evil.html").exists() and not (screens / "handoff/__MACOSX").exists()
    code, _ = repo("screen", "import", "W-001", str(tmp_path / "x.exe"), ok=False)
    assert code == 1
    code, out = repo("screen", "compare", str(same), str(mock))
    assert code == 0 and "비슷함" in out
    code, out = repo("screen", "compare", str(diff), str(mock), ok=False)
    assert code == 1 and "다른 곳" in out


# --------------------------------------------------------------------------- eval · harness · [P] · estimate · loop


def test_eval_and_harness(repo):
    init_project(repo)
    _, out = repo("eval")
    assert "실행 기록이 아직 없습니다" in out
    for _ in range(2):
        repo("close", "l-plan")
    repo("profile", "set", "design.approval=auto")
    repo("close", "l-plan")
    turns = [
        {
            "kind": "turn",
            "skill": "l-build",
            "model": "m1",
            "start": "2026-10-27T10:00:00+09:00",
            "end": "2026-10-27T10:30:00+09:00",
            "tool_calls": 10,
            "tools": {"Edit": 10},
        }
    ]
    with (repo.root / ".lantern/runs.jsonl").open("a", encoding="utf-8") as f:
        f.write("\n".join(json.dumps(t) for t in turns) + "\n")
    _, out = repo("eval")
    assert "| l-build | 1 | 30.0 | 10.0 |" in out and "구성별 결과" in out and "design.approval=auto" in out
    repo("report", "--views", "eval")
    assert "📊 AI 작업 평가" in (docs(repo) / "4. 운영 기록/보고/현황.md").read_text(encoding="utf-8")
    _, out = repo("harness", "suggest")
    assert "하네스 (작은 반복)" in out
    repo("profile", "set", 'build.test="pytest"', "project.team=team", "project.members=[a, b]")
    for name in ("하나", "둘"):
        repo("scaffold", "work", name)
    _, out = repo("harness", "suggest", "--apply")
    assert "그래프 (병렬)" in out
    prof = (repo.root / "lantern.yaml").read_text(encoding="utf-8")
    assert "loop: 'on'" in prof and "report_cycle: criterion" in prof


def test_parallel_tasks_and_estimates(repo):
    init_project(repo)
    repo("scaffold", "work", "작업")
    repo("scaffold", "doc", "W-001", "할 일")
    repo("task", "add", "W-001", "바탕", "--size", "S")
    repo("task", "add", "W-001", "목록 화면", "--size", "M", "--parallel", "--after", "T01")
    repo("task", "add", "W-001", "설정 화면", "--size", "L", "--parallel", "--after", "T01")
    tf = work_dir(repo, "W-001") / "할 일.md"
    assert "- [ ] W-001-T02 [P] 목록 화면 [크기:: M]" in tf.read_text(encoding="utf-8")
    _, out = repo("task", "next", "W-001", "--all")
    assert "W-001-T01" in out and "T02" not in out
    repo("task", "done", "W-001-T01")
    _, out = repo("task", "next", "W-001", "--all", "--json")
    ready = json.loads(out)
    assert [t["id"] for t in ready] == ["W-001-T02", "W-001-T03"] and all(t["parallel"] for t in ready)
    _, out = repo("task", "estimate", "W-001", "--from", "2026-11-02")
    assert "W-001-T02 목록 화면 [M] → 2026-11-02 ~ 2026-11-02" in out and "(기본값)" in out
    assert "[시작 예정:: 2026-11-02]" not in tf.read_text(encoding="utf-8")
    repo("task", "estimate", "W-001", "--from", "2026-11-02", "--apply")
    text = tf.read_text(encoding="utf-8")
    assert "[시작 예정:: 2026-11-02]" in text and "[마감 예정:: 2026-11-03]" in text


def test_big_loop_reaches_the_build_skill():
    on = gen(Profile(data=_deep_merge(DEFAULTS, {"build": {"loop": "on", "loop_limit": 4, "test": "pytest"}})), ["claude"])
    body = on[".claude/skills/l-build/SKILL.md"]
    assert "큰 반복 (build.loop: on · 최대 4번)" in body and "`pytest`" in body
    off = gen(Profile(data=_deep_merge(DEFAULTS, {})), ["claude"])
    assert "큰 반복 (build.loop" not in off[".claude/skills/l-build/SKILL.md"]


def test_ci_workflow(repo):
    import yaml

    repo("install", "--ci")
    wf = repo.root / ".github/workflows/lanternspec.yml"
    data = yaml.safe_load(wf.read_text(encoding="utf-8"))
    runs = [s.get("run", "") for s in data["jobs"]["docs-and-acceptance"]["steps"]]
    assert "lantern scan --tests" in runs and "lantern check --quiet" in runs and "lantern lint" in runs
    repo("upgrade")
    assert wf.exists()
    # once a language is set, its runner's setup steps come before the checks (the runner comes from the lock file)
    (repo.root / "package.json").write_text("{}", encoding="utf-8")
    (repo.root / "yarn.lock").write_text("", encoding="utf-8")
    init_project(repo)
    repo("profile", "set", "project.kind=service", "project.languages=[python, typescript]")
    repo("upgrade")
    steps = yaml.safe_load(wf.read_text(encoding="utf-8"))["jobs"]["docs-and-acceptance"]["steps"]
    names = [s.get("name", "") for s in steps]
    assert (
        names.index("Python 도구 준비 (uv)")
        < names.index("TypeScript 도구 준비 (yarn)")
        < names.index("린트 · 타입 검사 (lantern lint — build.lint · build.typecheck)")
    )
    runs = [s.get("run") for s in steps]
    assert "uv sync" in runs and "npm install -g yarn && yarn install" in runs
    # turning it off: an unedited workflow is removed and does not come back on the next upgrade
    repo("install", "--no-ci")
    assert not wf.exists()
    repo("upgrade")
    assert not wf.exists()
    # an edited workflow is never removed, even when turned off
    repo("install", "--ci")
    wf.write_text(wf.read_text(encoding="utf-8") + "# 우리 팀 단계\n", encoding="utf-8")
    code, out = repo("install", "--no-ci")
    assert wf.exists() and "사용자가 고친 파일이라 지우지 않음" in out


def _hook_as(root, name, agent, payload, cwd=None):
    return subprocess.run(
        [sys.executable, "-m", "lanternspec", "hook", name, "--agent", agent],
        cwd=str(cwd or root),
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )


def test_codex_agent_hooks(repo, vault):
    repo("install", "--tools", "claude,codex")
    codex = json.loads((repo.root / ".codex/hooks.json").read_text(encoding="utf-8"))
    assert set(codex["hooks"]) == {"SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "PreCompact", "Stop"}
    assert "--agent codex" in codex["hooks"]["PostToolUse"][0]["hooks"][0]["command"]
    repo("install")  # idempotent: no duplicated lantern entries
    codex = json.loads((repo.root / ".codex/hooks.json").read_text(encoding="utf-8"))
    assert len(codex["hooks"]["PostToolUse"]) == 1

    init_project(repo, vault=vault)
    repo("scaffold", "work", "작업")
    # SessionStart: JSON additionalContext
    out = json.loads(_hook_as(repo.root, "session-start", "codex", {"session_id": "s", "source": "startup"}).stdout)
    assert out["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "W-001 작업" in out["hookSpecificOutput"]["additionalContext"]
    # apply_patch → the document check runs on the patched doc
    plan = docs(repo) / "2. 작업/W-001 작업/기획.md"
    plan.write_text(plan.read_text(encoding="utf-8").replace("## 왜", "## 이유"), encoding="utf-8")
    patch = f"*** Begin Patch\n*** Update File: {plan}\n@@\n-## 왜\n+## 이유\n*** End Patch\n"
    r = _hook_as(repo.root, "post-tool", "codex", {"session_id": "s", "tool_name": "apply_patch", "tool_input": {"command": patch}})
    assert r.returncode == 2 and "'## 왜'" in r.stderr


def test_antigravity_agent_hooks(repo, vault):
    """Payloads as agy 1.4.7 sends them (captured from a live run); hooks run with cwd = .agents/."""
    repo("install", "--tools", "antigravity")
    hooks = json.loads((repo.root / ".agents/hooks.json").read_text(encoding="utf-8"))["lanternspec"]
    assert "--agent antigravity" in hooks["PostToolUse"][0]["hooks"][0]["command"]
    assert "lantern hook feedback" in hooks["PostInvocation"][0]["command"]
    init_project(repo, vault=vault)
    repo("scaffold", "work", "작업")
    agents_dir = repo.root / ".agents"
    common = {
        "conversationId": "c1",
        "modelName": "gemini-4-argon-medium",
        "workspacePaths": [str(repo.root)],
        "lastUserInput": "/l-plan 작업",
    }

    def hook(name, **extra):
        return _hook_as(repo.root, name, "antigravity", {**common, **extra}, cwd=agents_dir)

    steps = json.loads(hook("session-start").stdout)["injectSteps"]
    assert "W-001 작업" in steps[0]["systemMessage"]["systemMessage"]
    hook("prompt", invocationNum=0, initialNumSteps=1)
    # write_file on a broken doc: PostToolUse must answer {} — the document-check result comes at PostInvocation
    plan = docs(repo) / "2. 작업/W-001 작업/기획.md"
    plan.write_text(plan.read_text(encoding="utf-8").replace("## 왜", "## 이유"), encoding="utf-8")
    r = hook("post-tool", stepIdx=2, toolCall={"name": "write_file", "args": {"Path": str(plan), "Content": "…"}})
    assert r.returncode == 0 and json.loads(r.stdout) == {}
    held = json.loads(hook("feedback", invocationNum=0).stdout)["injectSteps"][0]["systemMessage"]["systemMessage"]
    assert "LanternSpec 문서 양식" in held and "'## 왜'" in held
    assert json.loads(hook("feedback", invocationNum=1).stdout) == {}  # delivered once
    plan.write_text(plan.read_text(encoding="utf-8").replace("## 이유", "## 왜"), encoding="utf-8")
    hook("post-tool", stepIdx=4, toolCall={"name": "edit_file", "args": {"Path": str(plan), "Target": "a", "Replacement": "b"}})
    # later model calls in the same turn are not new prompts
    repo("profile", "set", "learn.detect=ask")
    later = json.loads(hook("prompt", invocationNum=1, lastUserInput="JWT가 뭐야?").stdout)["injectSteps"]
    assert later == [{"ephemeralMessage": "[LanternSpec 지금 상황]\n📦 진행 중: W-001 작업 (기획)"}]  # only the reminder, every call
    steps = json.loads(hook("prompt", invocationNum=0, lastUserInput="JWT가 뭐야?").stdout)["injectSteps"]
    assert "LanternSpec 기술 질문" in steps[0]["systemMessage"]["systemMessage"] and "ephemeralMessage" in steps[1]
    # sync suggestion at Stop: keep going once so the agent tells the user; never on errors
    repo("work", "stage", "W-001", "구현")
    repo.git("add", "-A")
    repo.git("commit", "-qm", "docs: 시작")
    (repo.root / "app.py").write_text("x = 1\n", encoding="utf-8")
    assert json.loads(hook("stop", terminationReason="ERROR").stdout) == {}
    out = json.loads(hook("stop", terminationReason="NO_TOOL_CALL", executionNum=0).stdout)
    assert out["decision"] == "continue" and "/l-sync" in out["reason"]
    assert json.loads(hook("stop", terminationReason="NO_TOOL_CALL").stdout) == {}  # once per work
    recs = [json.loads(l) for l in (repo.root / ".lantern/runs.jsonl").read_text(encoding="utf-8").splitlines()]
    turn = [r for r in recs if r.get("session") == "c1" and r.get("kind") == "turn"][0]
    assert turn["skill"] == "l-plan" and turn["model"] == "gemini-4-argon-medium"
    assert turn["tools"] == {"write_file": 1, "edit_file": 1}
