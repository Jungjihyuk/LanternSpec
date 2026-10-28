"""Language packs (resources/locales/<language>) and protected sections.

Code and skills find every name by role, so a language pack must give each role a name, and
the names must never be spelled in code. Protected sections may be renamed or removed by a
person: lantern then asks instead of breaking or re-adding them.
"""

import ast
import json
import re
from pathlib import Path

import pytest
import yaml

from conftest import docs, fill, init_project, work_dir
from lanternspec import resources
from lanternspec.core import names as names_mod
from lanternspec.core import sections
from lanternspec.core.project import Project
from lanternspec.tools.skills import SKILL_NAMES

SRC = Path(__file__).resolve().parents[1] / "src" / "lanternspec"
LANGUAGES = names_mod.languages()


def _code_lines():
    """(file, line number, line) of every Python line that is neither a docstring nor a comment."""
    for p in sorted(SRC.rglob("*.py")):
        src = p.read_text(encoding="utf-8")
        docs_lines: set[int] = set()
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and ast.get_docstring(node):
                first = node.body[0]
                docs_lines |= set(range(first.lineno, (first.end_lineno or first.lineno) + 1))
        for i, line in enumerate(src.split("\n"), start=1):
            if i not in docs_lines and not line.strip().startswith("#"):
                yield p, i, line.split("  # ")[0]


def _roles_used_in_code():
    """Every role the code looks up, by kind of name."""
    calls = {
        "folders": r"\.folder\(\"([a-z_]+)\"\)",
        "docs": r"\.(?:doc|file)\(\"([a-z_]+)\"\)|doc_path\([^)]*?, \"([a-z_]+)\"\)",
        "task_attrs": r"\.attr\(\"([a-z_]+)\"\)|\(\"([a-z_]+)\", (?:owner|screen|start_plan|due_plan)\)",
        "markers": r"\.marker\(\"([a-z_]+)\"\)",
        "acceptance": r"\.acceptance\(\"([a-z_]+)\"\)",
        "sections": r"\.(?:section|title|titles|is_unused)\(\"([a-z_]+)\"\)",
    }
    found: dict[str, set[str]] = {k: set() for k in calls}
    for _, _, line in _code_lines():
        for kind, pat in calls.items():
            for m in re.finditer(pat, line):
                found[kind] |= {g for g in m.groups() if g}
    return found


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_role_the_code_uses_has_a_name(language):
    table = names_mod.load(language).table
    used = _roles_used_in_code()
    assert used["folders"] and used["docs"] and used["sections"]
    for kind, roles in used.items():
        missing = sorted(roles - set(table[kind]))
        assert not missing, f"{language} names.yaml {kind}: {missing}"


def test_every_name_has_every_language():
    raw = yaml.safe_load(resources.read_text("names.yaml"))
    for kind in ("folders", "docs", "task_attrs", "markers", "acceptance", "sections"):
        for key, value in raw[kind].items():
            missing = [lang for lang in LANGUAGES if lang not in value]
            assert not missing, f"names.yaml {kind}.{key}: {missing}"


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_name_token_in_skills_and_rules_resolves(language):
    ctx = names_mod.load(language).context()
    sources = [f"skills/{n}/SKILL.md" for n in SKILL_NAMES] + ["agents/AGENTS.md"]
    for rel in sources:
        text = resources.read_text(f"locales/{language}/{rel}")
        for key in re.findall(r"<<((?:folder|doc|file|attr|marker|section)\.[a-z_]+)>>", text):
            assert key in ctx, f"{language} {rel}: <<{key}>>"


@pytest.mark.parametrize("language", LANGUAGES)
def test_templates_carry_their_protected_sections(language):
    n = names_mod.load(language)
    for s in n.sections():
        for role in s.docs:
            text = resources.read_text(f"locales/{language}/templates/{n.file(role)}")
            assert sections.has(text, [s.title]), f"{language} {n.file(role)}: ## {s.title}"


def test_code_never_spells_a_name_from_names_yaml():
    table = names_mod.load("ko").table
    literals = {f'"{v}"' for v in table["folders"].values()}
    literals |= {f"{v}.md" for v in table["docs"].values()}
    literals |= {f"[{v}::" for v in table["task_attrs"].values()}
    literals |= {str(table["markers"]["unknown"]), str(table["markers"]["required"])}
    heading = re.compile("|".join(rf"## {re.escape(s['title'])}(?=[\"'\\\\]|$)" for s in table["sections"].values()))
    hits = [
        f"{p.relative_to(SRC)}:{i}: {line.strip()}"
        for p, i, line in _code_lines()
        if any(lit in line for lit in literals) or heading.search(line)
    ]
    assert not hits, "names written in code instead of looked up:\n" + "\n".join(hits)


# --------------------------------------------------------------------------- protected sections


def _record(repo):
    repo("scaffold", "work", "로그인")
    repo("scaffold", "doc", "W-001", "기록")
    return work_dir(repo, "W-001") / "기록.md"


def test_renamed_section_is_asked_about_then_followed(repo):
    init_project(repo)
    record = _record(repo)
    fill(record, [("## 지금 상황", "## 오늘 한 일")])
    _, out = repo("check", str(record))
    assert "'지금 상황' 칸이 없습니다" in out and "일부러 바꾸셨나요?" in out
    assert "lantern sections rename now" in out and "lantern sections off now" in out

    # before the answer, saving progress leaves the document alone instead of adding a second section
    before = record.read_text(encoding="utf-8")
    from lanternspec.work.progress import save_before_compact

    assert save_before_compact(Project.load(repo.root)) == {}
    assert record.read_text(encoding="utf-8") == before

    repo("sections", "rename", "now", "오늘 한 일")
    _, out = repo("check", str(record))
    assert "칸이 없습니다" not in out
    saved = save_before_compact(Project.load(repo.root))
    assert record in saved
    text = record.read_text(encoding="utf-8")
    assert text.count("## 오늘 한 일") == 1 and "## 지금 상황" not in text and "- 진행:" in text

    page = (docs(repo) / "0. 템플릿/_meta/보호 칸.md").read_text(encoding="utf-8")
    assert "`## 오늘 한 일` (예전 이름: 지금 상황)" in page


def test_section_turned_off_is_skipped_silently(repo):
    init_project(repo)
    record = _record(repo)
    fill(record, [("## 지금 상황", "## 메모")])
    repo("sections", "off", "now")
    _, out = repo("check", str(record))
    assert "칸이 없습니다" not in out
    assert yaml.safe_load((repo.root / "lantern.yaml").read_text(encoding="utf-8"))["docs"]["unused_sections"] == ["now"]
    from lanternspec.work.progress import save_before_compact

    assert save_before_compact(Project.load(repo.root)) == {}
    repo("sections", "on", "now")
    assert not yaml.safe_load((repo.root / "lantern.yaml").read_text(encoding="utf-8"))["docs"]["unused_sections"]


def test_template_change_is_asked_once_not_per_document(repo):
    init_project(repo)
    record = _record(repo)
    template = docs(repo) / "0. 템플릿/기록.md"
    fill(template, [("## 스키마 변경", "## DB 메모")])
    fill(record, [("## 스키마 변경", "## DB 메모")])
    _, out = repo("check")
    assert out.count("'스키마 변경' 칸이 없습니다") == 1
    assert "0. 템플릿/기록.md" in out


def test_a_command_that_needs_a_missing_section_explains_instead_of_adding_it(repo):
    init_project(repo)
    unit = ["unit-log", "add", "--what", "W-001", "--recommended", "할 일 3개", "--chosen", "할 일 2개", "--reason", "버튼은 하나로"]
    repo(*unit)
    log = docs(repo) / "3. 현재 상태/규칙 · 결정 기록/작업 단위 기록.md"
    fill(log, [("## 기록", "## 결정")])
    before = log.read_text(encoding="utf-8")
    code, out = repo(*unit, ok=False)
    assert code == 1 and "'기록' 칸이 없어 기록하지 못했습니다" in out and "lantern sections off unit_log" in out
    assert log.read_text(encoding="utf-8") == before  # nothing added


def test_the_ai_hook_reports_a_missing_section_without_blocking(repo):
    init_project(repo)
    record = _record(repo)
    fill(record, [("## 지금 상황", "## 오늘 한 일")])
    from lanternspec.tools import agent_hooks, get

    payload = json.dumps({"session_id": "s", "tool_name": "Write", "tool_input": {"file_path": str(record)}})
    reply = agent_hooks.run(Project.load(repo.root), "post-tool", get("claude"), payload)
    assert reply.code == 0 and "지금 상황" in reply.stdout


def test_sections_list_and_bad_key(repo):
    init_project(repo)
    _, out = repo("sections", "list")
    assert "now" in out and "## 지금 상황" in out and "대화가 길어져" in out
    code, out = repo("sections", "off", "nope", ok=False)
    assert code == 1 and "보호 칸 키는" in out
