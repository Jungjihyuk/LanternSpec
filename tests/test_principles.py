"""Design principles and code conventions are chosen from the tables and written into AGENTS.md and the design-principles document."""

import copy

import yaml

from conftest import init_project
from lanternspec.core import principles
from lanternspec.core.profile import DEFAULTS, Profile


def _profile(**project):
    data = copy.deepcopy(DEFAULTS)
    data["project"].update(project)
    return Profile(data)


def _levels(**project):
    sel = principles.select(_profile(**project))
    return {p.id: p.level for p in sel.principles}


def test_levels_follow_kind_external_and_size():
    assert principles.select(_profile()) is None  # nothing is chosen before the kind is set
    script = _levels(kind="script")
    assert [k for k, v in script.items() if v == "must"] == ["simplicity"]
    assert _levels(kind="cli", external=True)["extension_points"] == "must"
    assert _levels(kind="cli", external=False)["extension_points"] == "skip"
    # size adjustment: from medium signals up, should → must; observability is at least should for large code
    assert _levels(kind="cli")["dependency_direction"] == "should"
    assert _levels(kind="cli", code_size="medium")["dependency_direction"] == "must"
    assert _levels(kind="cli", team="team", members=["가", "나"])["public_interface"] == "must"
    assert _levels(kind="cli")["observability"] == "skip"
    assert _levels(kind="cli", code_size="large")["observability"] == "should"
    assert _levels(kind="script", code_size="large")["single_responsibility"] == "skip"  # a skip in the table is never raised by size


def test_conventions_by_language_and_size_library_docs_are_large():
    small = principles.select(_profile(kind="cli", languages=["python"])).conventions[0]
    assert small.rules["typecheck"] == "pyright basic" and small.tools["lint"] == ("ruff", "uv run ruff check .")
    medium = principles.select(_profile(kind="cli", languages=["python"], code_size="medium")).conventions[0]
    assert medium.rules["typecheck"] == "pyright standard"
    lib = principles.select(_profile(kind="library", languages=["python"])).conventions[0]
    assert lib.rules["typecheck"] == "pyright basic" and "doctest" in lib.rules["docs"]  # only the doc-comment rule is "large"


def test_detect_records_existing_tools_without_touching_them(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n\n[tool.ruff]\nline-length = 100\n", encoding="utf-8")
    (tmp_path / "poetry.lock").write_text("", encoding="utf-8")
    (tmp_path / "package.json").write_text('{"name": "web"}', encoding="utf-8")
    (tmp_path / ".eslintrc.json").write_text("{}", encoding="utf-8")
    (tmp_path / "yarn.lock").write_text("", encoding="utf-8")
    before = {p.name: p.read_text(encoding="utf-8") for p in tmp_path.iterdir()}
    d = principles.detect(tmp_path)
    assert d.languages == ["python", "typescript"]
    assert d.existing["python"]["lint"] == ("ruff", "poetry run ruff check .", "pyproject.toml [tool.ruff")
    assert d.existing["typescript"]["lint"][:2] == ("ESLint", "yarn eslint .")
    assert "typecheck" not in d.existing["python"]  # tools without a config are not recorded
    brown = d.commands(fill_defaults=False)
    assert brown["lint"] == "poetry run ruff check . && yarn eslint ." and "typecheck" not in brown
    green = d.commands(fill_defaults=True)
    assert green["typecheck"] == "poetry run pyright && yarn tsc --noEmit"
    assert {p.name: p.read_text(encoding="utf-8") for p in tmp_path.iterdir()} == before


def test_init_to_agents_block_doc_lint_and_doctor(repo):
    (repo.root / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (repo.root / "uv.lock").write_text("", encoding="utf-8")
    init_project(repo)
    repo("profile", "set", "project.kind=cli", "project.external=true")
    code, out = repo("principles", "detect", "--write")
    assert "언어: python (pyproject.toml)" in out and "project.code_size=small" in out
    prof = yaml.safe_load((repo.root / "lantern.yaml").read_text(encoding="utf-8"))
    assert prof["project"]["languages"] == ["python"] and prof["build"]["lint"] == "uv run ruff check ."
    assert "— 설계 원칙을 고르는 기준" in (repo.root / "lantern.yaml").read_text(encoding="utf-8")  # comments stay
    repo("scaffold", "init")
    repo("install")
    agents = (repo.root / "AGENTS.md").read_text(encoding="utf-8")
    assert "### 개발 원칙 — CLI 도구 · 바깥 연결 · 코드 작음 · 1인" in agents
    assert "- **지킴:** 단순함 (KISS · YAGNI) · 단일 책임 (SRP)" in agents and "확장 지점" in agents
    assert "린트 `uv run ruff check .`" in agents and "<!-- lantern:principles -->" not in agents
    doc = repo.root / "docs/3. 현재 상태/규칙 · 결정 기록/개발 원칙.md"
    text = doc.read_text(encoding="utf-8")
    assert "## 코드 컨벤션 — Python" in text and "| 의존 방향 (DIP · 순수한 핵심) | 권장 | CLI 도구 → 권장 |" in text
    repo("upgrade")
    assert doc.read_text(encoding="utf-8") == text  # unchanged content is not rewritten
    code, out = repo("check", ok=False)
    assert "개발 원칙" not in out
    # lantern lint runs the recorded commands
    repo("profile", "set", "build.lint=exit 0", "build.typecheck=exit 1")
    code, out = repo("lint", ok=False)
    assert code == 1 and "✔ lint: `exit 0`" in out and "✖ typecheck: `exit 1`" in out
    # when the code grows past the boundary, doctor asks
    (repo.root / "app.py").write_text("x = 1\n" * 10_001, encoding="utf-8")
    (repo.root / "tests").mkdir()
    (repo.root / "tests/test_app.py").write_text("y = 1\n" * 60_000, encoding="utf-8")  # tests are not counted
    repo.git("add", "-A")
    code, out = repo("doctor", ok=False)
    assert "코드가 10,001줄로 자라 규모가 작음 → 중간이 됐습니다 — 원칙을 한 단계 올릴까요?" in out
    repo("profile", "set", "project.code_size=medium")
    repo("upgrade")
    assert "의존 방향 (DIP · 순수한 핵심) | 지킴" in doc.read_text(encoding="utf-8")


def test_without_kind_nothing_changes(repo):
    init_project(repo)
    repo("scaffold", "init")
    repo("install")
    agents = (repo.root / "AGENTS.md").read_text(encoding="utf-8")
    assert "### 개발 원칙" not in agents and "<!-- lantern:principles -->" not in agents
    assert not (repo.root / "docs/3. 현재 상태/규칙 · 결정 기록/개발 원칙.md").exists()
    code, out = repo("principles", "show", ok=False)
    assert code == 1 and "project.kind가 없습니다" in out


def test_comment_language_is_separate_from_document_language(repo):
    init_project(repo)
    repo("profile", "set", "project.kind=cli", "project.languages=[python]")
    repo("scaffold", "init")
    repo("install")
    agents = (repo.root / "AGENTS.md").read_text(encoding="utf-8")
    assert "문서 주석 (Google 스타일 docstring · 한국어)" in agents  # left empty, it follows the document language (ko)
    repo("profile", "set", "project.comment_language=en")
    repo("upgrade")
    agents = (repo.root / "AGENTS.md").read_text(encoding="utf-8")
    # the doc-comment style and example follow the comment language; the guidance stays in Korean
    assert "문서 주석 (Google-style docstrings · 영어)" in agents and "### 개발 원칙" in agents
    doc = (repo.root / "docs/3. 현재 상태/규칙 · 결정 기록/개발 원칙.md").read_text(encoding="utf-8")
    assert "문서 주석: Google-style docstrings · 영어" in doc and "Rename one value in the text of enums.yaml." in doc
    code, out = repo("profile", "set", "project.comment_language=jp", ok=False)
    assert code == 1 and "comment_language" in out
