from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from lanternspec.cli import main


@pytest.fixture(autouse=True)
def _isolated_git(monkeypatch, tmp_path_factory):
    """Tests never read the developer's git config (hooksPath, signing …)."""
    home = tmp_path_factory.mktemp("home")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(home / ".gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for k, v in {
        "GIT_AUTHOR_NAME": "테스트",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "테스트",
        "GIT_COMMITTER_EMAIL": "t@example.com",
    }.items():
        monkeypatch.setenv(k, v)
    # git hooks call `lantern` — make this interpreter's scripts reachable
    monkeypatch.setenv("PATH", str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", ""))
    monkeypatch.delenv("LANTERN_SKIP_HOOKS", raising=False)


def sh(cwd: Path, *args: str, check: bool = True, input: str = None) -> subprocess.CompletedProcess:
    r = subprocess.run(list(args), cwd=str(cwd), capture_output=True, text=True, input=input)
    if check and r.returncode != 0:
        raise AssertionError(f"{args} failed ({r.returncode}):\n{r.stdout}\n{r.stderr}")
    return r


class Runner:
    def __init__(self, root: Path, capsys):
        self.root = root
        self.capsys = capsys

    def __call__(self, *args: str, ok: bool = True) -> tuple[int, str]:
        self.capsys.readouterr()
        code = main(list(args))
        out = self.capsys.readouterr()
        text = out.out + out.err
        if ok and code != 0:
            raise AssertionError(f"lantern {' '.join(args)} → {code}\n{text}")
        return code, text

    def git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        return sh(self.root, "git", *args, check=check)


@pytest.fixture
def repo(tmp_path, monkeypatch, capsys) -> Runner:
    root = tmp_path / "proj"
    root.mkdir()
    sh(root, "git", "init", "-q", "-b", "main")
    sh(root, "git", "commit", "-q", "--allow-empty", "-m", "init")
    monkeypatch.chdir(root)
    return Runner(root, capsys)


@pytest.fixture
def vault(tmp_path) -> Path:
    v = tmp_path / "vault"
    (v / "2. Study" / "Backend").mkdir(parents=True)
    (v / "2. Study" / "AI Engineering").mkdir(parents=True)
    (v / "2. Study" / "Backend" / "JWT.md").write_text(
        "---\naliases: [JSON Web Token]\n---\n# JWT\n\nJSON Web Token은 서명된 토큰이다.\n", encoding="utf-8"
    )
    (v / ".obsidian").mkdir()
    (v / ".obsidian" / "JWT.md").write_text("# JWT 설정 파일", encoding="utf-8")
    return v


def init_project(r: Runner, *extra: str, vault: Path = None) -> None:
    args = [
        "profile",
        "write",
        "--name",
        "소셜 가계부",
        "--origin",
        "greenfield",
        "--team",
        "solo",
        "--clients",
        "mobile",
        "--server",
        "external",
        "--design",
        "claude-design",
        "--base",
        "main",
    ]
    if vault is not None:
        args += ["--knowledge", str(vault), "--areas-from", "2. Study"]
    r(*args, *extra)
    r("scaffold", "init")


def fill(path: Path, replacements: list[tuple[str, str]]) -> None:
    text = path.read_text(encoding="utf-8")
    for a, b in replacements:
        assert a in text, f"{a!r} not in {path.name}"
        text = text.replace(a, b)
    path.write_text(text, encoding="utf-8")


def docs(r: Runner) -> Path:
    return r.root / "docs"


def work_dir(r: Runner, wid: str) -> Path:
    base = docs(r) / "2. 작업"
    for p in list(base.iterdir()) + (list((base / "보관").iterdir()) if (base / "보관").exists() else []):
        if p.name.startswith(wid + " "):
            return p
    raise AssertionError(f"{wid} not found")


def fill_plan(r: Runner, wid: str, ac_lines: str = None) -> Path:
    p = work_dir(r, wid) / "기획.md"
    fill(
        p,
        [
            ("{{한눈에 보기 (필수)}}", "카카오 계정으로 로그인한다"),
            ("{{무엇을 (필수)}}", "로그인 화면에 카카오 버튼"),
            ("{{왜 (필수)}}", "가입이 귀찮다"),
            ("{{시나리오 (필수)}}", "카카오 버튼을 누른다"),
            ('"{{도메인}}"', "인증"),
            (
                "- [ ] AC-1 상황: {{상황}} · 행동: {{행동 (필수)}} · 결과: {{결과 (필수)}}",
                ac_lines
                or "- [ ] AC-1 상황: 로그인 화면에서 · 행동: 카카오 버튼을 누르면 · 결과: 2초 안에 홈이 열린다\n"
                "- [ ] AC-2 행동: 로그아웃을 누르면 · 결과: 로그인 화면으로 돌아간다",
            ),
            ("- {{범위 밖}}", "- 애플 로그인"),
        ],
    )
    return p
