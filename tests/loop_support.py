"""What the build-loop tests share: a fake test tool, and a work whose two acceptance criteria link two committed tests.

A test file `tests/test_X.py` passes once `src/X.txt` exists, so "implementing" is writing that file.
"""

import json

import pytest

from conftest import fill_plan, init_project
from lanternspec.core.project import Project

FAKE_TESTS = """import pathlib
import sys

# usage: fake_tests.py [tests/test_X.py[::name]] — one test, or every test file
root = pathlib.Path(".")


def passes(path):
    return (root / "src" / (pathlib.Path(path).stem.removeprefix("test_") + ".txt")).exists()


if sys.argv[1:]:
    path = sys.argv[1].split("::")[0]
    ok = passes(path)
    print("1 passed in 0.01s" if ok else "1 failed in 0.01s")
    sys.exit(0 if ok else 1)
files = sorted((root / "tests").glob("test_*.py"))
bad = [f for f in files if not passes(f)]
print(f"{len(files) - len(bad)} passed, {len(bad)} failed in 0.01s")
sys.exit(1 if bad else 0)
"""

TWO_ACS = (
    "- [ ] AC-1 상황: 로그인 화면에서 · 행동: 카카오 버튼을 누르면 · 결과: 2초 안에 홈이 열린다 "
    "[테스트:: tests/test_login.py::test_kakao]\n"
    "- [ ] AC-2 행동: 로그아웃을 누르면 · 결과: 로그인 화면으로 돌아간다 [테스트:: tests/test_logout.py]"
)


def lines(project, kind=None):
    path = project.state / "runs.jsonl"
    rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []
    return [r for r in rows if kind is None or r["kind"] == kind]


def commit(repo, message="commit"):
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", message)


def implement(repo, name):
    (repo.root / "src").mkdir(exist_ok=True)
    (repo.root / "src" / f"{name}.txt").write_text("done", encoding="utf-8")


@pytest.fixture
def work(repo):
    """A work W-001 whose two criteria link two committed tests, in a project with the loop on."""
    init_project(repo)
    repo("scaffold", "work", "카카오 로그인")
    fill_plan(repo, "W-001", TWO_ACS)
    (repo.root / "fake_tests.py").write_text(FAKE_TESTS, encoding="utf-8")
    (repo.root / "tests").mkdir()
    for name in ("login", "logout", "other"):
        (repo.root / "tests" / f"test_{name}.py").write_text("# a test", encoding="utf-8")
    implement(repo, "other")
    repo("profile", "set", "build.loop=on", "build.test=python3 fake_tests.py", "build.test_one=python3 fake_tests.py {test}")
    commit(repo, "tests")
    return Project.load(repo.root)
