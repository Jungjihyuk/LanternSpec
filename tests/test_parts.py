"""Parts: folders with their own toolchain get their own AGENTS.md once there are two or more.

The candidates come from the files git knows (a folder with its own manifest); the person decides
with `lantern parts add|ignore`. The root AGENTS.md keeps the ways of working and a map of the parts.
"""

from pathlib import Path

import yaml

from conftest import init_project
from lanternspec.core.principles import part_candidates


def test_candidates_are_folders_with_their_own_manifest_and_workspace_members_win(tmp_path):
    (tmp_path / "frontend").mkdir()
    (tmp_path / "frontend/pnpm-workspace.yaml").write_text("packages: [apps/*]\n", encoding="utf-8")
    files = [
        "pyproject.toml",  # the root is never a part
        "backend/pyproject.toml",
        "frontend/package.json",  # a workspace root: its member is the part
        "frontend/pnpm-workspace.yaml",
        "frontend/apps/web/package.json",
        "frontend/apps/web/tsconfig.json",
        "ios/App.xcodeproj/project.pbxproj",  # a bundle folder counts for its parent
        "a/b/c/d/pyproject.toml",  # deeper than three folders
        "docs/README.md",
    ]
    found = [(c.path, c.languages, c.evidence) for c in part_candidates(tmp_path, files)]
    assert found == [
        ("backend", ["python"], ["pyproject.toml"]),
        ("frontend/apps/web", ["typescript"], ["package.json"]),
        ("ios", ["swift"], ["App.xcodeproj"]),
    ]


def _two_parts(repo):
    init_project(repo, "--kind", "service", "--external", "no", "--languages", "python,typescript")
    (repo.root / "backend").mkdir()
    (repo.root / "backend/pyproject.toml").write_text("[project]\nname='b'\n\n[tool.ruff]\nline-length = 100\n", encoding="utf-8")
    (repo.root / "backend/uv.lock").write_text("", encoding="utf-8")
    (repo.root / "web").mkdir()
    (repo.root / "web/package.json").write_text('{"name": "web"}\n', encoding="utf-8")
    (repo.root / "web/tsconfig.json").write_text("{}\n", encoding="utf-8")
    (repo.root / "analysis").mkdir()
    (repo.root / "analysis/requirements.txt").write_text("pandas\n", encoding="utf-8")
    repo("install")


def test_people_decide_which_candidates_are_parts(repo):
    _two_parts(repo)
    _, out = repo("parts")
    assert "backend  (python) · 정하지 않음 · pyproject.toml" in out and "lantern parts add" in out
    _, doctor = repo("doctor", ok=False)
    assert "영역 후보를 아직 정하지 않았습니다: analysis, backend, web" in doctor
    _, out = repo("parts", "add", "backend")
    assert "✔ 영역 backend (python)" in out
    repo("parts", "add", "web")
    repo("parts", "ignore", "analysis")
    code = yaml.safe_load((repo.root / "lantern.yaml").read_text(encoding="utf-8"))["code"]
    assert [p["path"] for p in code["parts"]] == ["backend", "web"] and code["ignored_parts"] == ["analysis"]
    assert code["parts"][0]["build"]["lint"] == "uv run ruff check ."  # the folder's configured tool, with its runner
    _, out = repo("parts")
    assert "analysis  (python) · 빼 둠" in out and "lantern parts add" not in out
    code, out = repo("parts", "add", "docs", ok=False)
    assert code != 0 and "매니페스트가 없습니다" in out


def test_two_parts_get_their_own_agents_md_and_the_root_keeps_a_map(repo):
    _two_parts(repo)
    (repo.root / "web/AGENTS.md").write_text("# 우리 웹 규칙\n- 상태 관리 라이브러리를 쓰지 않는다\n", encoding="utf-8")
    repo("parts", "add", "backend")
    repo("upgrade")
    assert not (repo.root / "backend/AGENTS.md").exists()  # one part is the whole project: nothing changes
    repo("parts", "add", "web")
    _, out = repo("upgrade")
    assert "backend/AGENTS.md" in out and "web/AGENTS.md" in out
    backend = (repo.root / "backend/AGENTS.md").read_text(encoding="utf-8")
    assert "## 영역 backend — 이 폴더의 규칙" in backend and "`uv run ruff check .`" in backend and "Python" in backend
    web = (repo.root / "web/AGENTS.md").read_text(encoding="utf-8")
    assert web.startswith("# 우리 웹 규칙\n- 상태 관리 라이브러리를 쓰지 않는다") and "## 영역 web" in web  # the person's text stays
    root = (repo.root / "AGENTS.md").read_text(encoding="utf-8")
    assert "### 영역 — 폴더마다 자기 규칙" in root and "| `backend` | Python | `backend/AGENTS.md` |" in root
    assert "### 코드 컨벤션" not in root  # conventions moved to the parts
    _, again = repo("upgrade")
    assert "backend/AGENTS.md" not in again  # unchanged files are left alone


def test_a_folder_that_stops_being_a_part_loses_only_our_block(repo):
    _two_parts(repo)
    (repo.root / "web/AGENTS.md").write_text("# 우리 웹 규칙\n", encoding="utf-8")
    for part in ("backend", "web", "analysis"):
        repo("parts", "add", part)
    repo("upgrade")
    repo("parts", "ignore", "web")
    repo("parts", "ignore", "analysis")
    repo("upgrade")
    assert (repo.root / "web/AGENTS.md").read_text(encoding="utf-8") == "# 우리 웹 규칙\n"
    assert not (repo.root / "analysis/AGENTS.md").exists()  # it held only our block
    assert not Path(repo.root / "backend/AGENTS.md").exists()  # one part left: back to the whole project
    assert "### 코드 컨벤션" in (repo.root / "AGENTS.md").read_text(encoding="utf-8")
