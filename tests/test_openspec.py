"""`lantern migrate openspec` — OpenSpec changes become works and ideas, the originals are kept, one commit to undo."""

import pytest

from conftest import docs, init_project, sh
from lanternspec import resources
from lanternspec.check import openspec
from lanternspec.check.templates import parse_sections

LEGACY = "5. 기존 문서"

PROPOSAL = """## Why

로그인 문구에 변수 이름이 그대로 보인다.

## What Changes

- 문구에 실제 숫자를 넣는다.

## Impact

- 로그인 화면
"""
DESIGN = """## Context

문구를 만드는 함수가 값을 받지만 쓰지 않는다. 배경은 [제안](proposal.md)에 있다.

## Goals / Non-Goals

**Goals:**

- 숫자를 보여 준다.

**Non-Goals:**

- 계산 규칙 변경

## Decisions

문자열 보간으로 바꾼다.

## Risks / Trade-offs

- 문구가 바뀌면 테스트가 깨진다.
"""
TASKS = """## 1. 문구

- [x] 1.1 문구를 고친다
- [{box}] 1.2 테스트를 더한다
"""
SPEC = """## ADDED Requirements

### Requirement: 숫자를 보여 준다

#### Scenario: 조건 미충족

- **WHEN** 할 일이 모자라면
- **THEN** 필요한 개수를 숫자로 보여 준다
"""


def _change(folder, box="x", design=True):
    (folder / "specs" / "login-message").mkdir(parents=True)
    (folder / "proposal.md").write_text(PROPOSAL, encoding="utf-8")
    (folder / "tasks.md").write_text(TASKS.format(box=box), encoding="utf-8")
    (folder / "specs" / "login-message" / "spec.md").write_text(SPEC, encoding="utf-8")
    (folder / ".openspec.yaml").write_text("schema: spec-driven\ncreated: 2026-09-16\n", encoding="utf-8")
    if design:
        (folder / "design.md").write_text(DESIGN, encoding="utf-8")


def _project(repo):
    """A LanternSpec project with an OpenSpec folder: one archived change, one in progress, one note."""
    init_project(repo, "--origin", "brownfield")
    changes = repo.root / "openspec" / "changes"
    _change(changes / "archive" / "2026-09-17-fix-login-message")
    _change(changes / "add-dark-mode", box=" ")
    (changes / "try-voice-input").mkdir()
    (changes / "try-voice-input" / "README.md").write_text("# try-voice-input\n\n말로 할 일을 적는다.\n", encoding="utf-8")
    spec = repo.root / "openspec" / "specs" / "login-message"
    spec.mkdir(parents=True)
    (spec / "spec.md").write_text("## Purpose\n\n로그인 문구가 실제 값을 보여 준다.\n\n## Requirements\n", encoding="utf-8")
    repo.git("add", "-A")
    repo.git("commit", "-qm", "project")


@pytest.mark.parametrize("language", ["ko", "en"])
def test_our_section_titles_are_the_ones_in_the_templates(language):
    template_of = {"what": "plan", "why": "plan", "criteria": "plan", "out_of_scope": "plan", "structure": "design", "tasks": "tasks"}
    names = {"plan": {"ko": "기획", "en": "Plan"}, "design": {"ko": "설계", "en": "Design"}, "tasks": {"ko": "할 일", "en": "Tasks"}}
    for key, role in template_of.items():
        text = resources.read_text(f"locales/{language}/templates/{names[role][language]}.md")
        assert openspec.heading(key, language) in [title for title, _ in parse_sections(text).sections], key
    features = resources.read_text(f"locales/{language}/templates/{'기능 목록' if language == 'ko' else 'Feature List'}.md")
    assert openspec.heading("features", language) in [title for title, _ in parse_sections(features).sections]


def test_preview_shows_where_each_change_goes_and_changes_nothing(repo):
    _project(repo)
    _, out = repo("migrate", "openspec")
    assert "2. 작업/보관/W-001 fix-login-message  (2026-09-17 끝남)" in out
    assert "2. 작업/W-002 add-dark-mode  (할 일 1/2)" in out
    assert "1. 아이디어/ try-voice-input" in out and "기능마다 한 줄 (1개)" in out
    assert "--apply" in out
    assert sh(repo.root, "git", "status", "--porcelain").stdout == "" and (repo.root / "openspec").exists()


def test_apply_writes_works_and_ideas_keeps_the_originals_and_commits_once(repo):
    _project(repo)
    before = int(sh(repo.root, "git", "rev-list", "--count", "HEAD").stdout)
    _, out = repo("migrate", "openspec", "--apply")
    d = docs(repo)
    assert "작업 2개(그중 보관 1개) · 아이디어 1개" in out and "git revert" in out
    assert not (repo.root / "openspec").exists() and (d / LEGACY / "openspec/changes/add-dark-mode/proposal.md").exists()
    assert int(sh(repo.root, "git", "rev-list", "--count", "HEAD").stdout) == before + 1
    assert sh(repo.root, "git", "status", "--porcelain").stdout == ""

    done = d / "2. 작업/보관/W-001 fix-login-message"
    plan = (done / "기획.md").read_text(encoding="utf-8")
    assert "status: 완료" in plan and "created: 2026-09-16" in plan
    assert "## 왜\n로그인 문구에 변수 이름이 그대로 보인다." in plan and "## 무엇을\n- 문구에 실제 숫자를 넣는다." in plan
    assert "- [x] AC-1 행동: 할 일이 모자라면 · 결과: 필요한 개수를 숫자로 보여 준다" in plan
    assert "## 범위 밖\n- 계산 규칙 변경" in plan  # the design's non-goals are what the plan leaves out
    assert "## 📦 옮기지 못한 내용" in plan and "### Impact\n- 로그인 화면" in plan  # no section of ours: kept, not dropped
    assert "(필수)" not in plan  # nobody fills the blanks of a finished work

    design = (done / "설계.md").read_text(encoding="utf-8")
    assert "**Context**" in design and "**Decisions**\n\n문자열 보간으로 바꾼다." in design
    assert "### Goals / Non-Goals\n**Goals:**" in design and "### Risks / Trade-offs" in design
    assert "openspec/changes/archive/2026-09-17-fix-login-message/proposal.md)" in design  # the link follows the original

    tasks = (done / "할 일.md").read_text(encoding="utf-8")
    assert "### 1. 문구\n\n- [x] W-001-T01 문구를 고친다\n- [x] W-001-T02 테스트를 더한다" in tasks
    assert "OpenSpec 변경 `fix-login-message`에서 옮김 — 2026-09-17 끝남" in (done / "기록.md").read_text(encoding="utf-8")

    running = d / "2. 작업/W-002 add-dark-mode"
    assert "status: 구현" in (running / "기획.md").read_text(encoding="utf-8")
    assert "- [ ] AC-1 행동:" in (running / "기획.md").read_text(encoding="utf-8")
    assert "- [ ] W-002-T02 테스트를 더한다" in (running / "할 일.md").read_text(encoding="utf-8")

    idea = next((d / "1. 아이디어").glob("IDEA-* try-voice-input.md")).read_text(encoding="utf-8")
    assert "> 말로 할 일을 적는다." in idea and "openspec/changes/try-voice-input/README]]" in idea
    assert "| login-message |  | 로그인 문구가 실제 값을 보여 준다. |" in (d / "3. 현재 상태/기능 목록.md").read_text(encoding="utf-8")
    legacy_map = (d / LEGACY / "기존 문서 지도.md").read_text(encoding="utf-8")
    assert legacy_map.count("openspec") == 2  # one row for the folder (link and name), not one per file

    _, out = repo("check")
    errors = [line for line in out.splitlines() if line.lstrip().startswith("✖")]
    assert not errors, errors  # nothing broken
    assert "W-001-T01" not in out and "AC-1에 연결된" not in out.split("W-002")[0]  # a finished work is asked nothing
    assert "W-002-T02에 크기가 없습니다" in out  # a work in progress still has to be planned our way


def test_the_person_decides_where_an_open_change_goes(repo):
    _project(repo)
    _, out = repo("migrate", "openspec", "--idea", "add-dark-mode", "--work", "try-voice-input")
    assert "1. 아이디어/ add-dark-mode" in out and "2. 작업/W-002 try-voice-input  (할 일 없음)" in out
    code, out = repo("migrate", "openspec", "--idea", "no-such-change", ok=False)
    assert code == 1 and "no-such-change" in out


def test_apply_stops_when_the_documents_have_uncommitted_changes(repo):
    _project(repo)
    (repo.root / "openspec" / "changes" / "add-dark-mode" / "proposal.md").write_text("## Why\n\n고치는 중\n", encoding="utf-8")
    code, out = repo("migrate", "openspec", "--apply", ok=False)
    assert code == 1 and "커밋하지 않은 변경" in out and (repo.root / "openspec").exists()
    code, out = repo("migrate", "openspec", ok=False)
    assert code == 0  # the preview still works
