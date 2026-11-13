"""Open and closed knowledge store folders: the adapter's own check and the OS sandbox of `lantern guard`."""

import shutil
import subprocess
import sys
import unicodedata

import pytest

from conftest import init_project, sh
from lanternspec.core.project import Project
from lanternspec.tools import guard


@pytest.fixture
def store(repo, vault):
    """A project whose store has a work folder (to close) and a project folder next to the study notes."""
    (vault / "4. Work").mkdir()
    (vault / "4. Work" / "연봉.md").write_text("# 연봉\n\nJWT 관련 업무 메모\n", encoding="utf-8")
    (vault / "3. Projects").mkdir()
    (vault / "3. Projects" / "앱.md").write_text("# 앱\n\nJWT로 로그인\n", encoding="utf-8")
    (vault / ".git").mkdir()
    (vault / ".git" / "연봉.md").write_text("# 연봉 (사본)\n", encoding="utf-8")
    init_project(repo, vault=vault)
    return vault


def test_denied_folder_is_not_searched_read_or_written(repo, store):
    repo("profile", "set", "knowledge.deny=[4. Work]")
    _, out = repo("knowledge", "search", "JWT", "--json")
    assert "2. Study/Backend/JWT.md" in out and "3. Projects/앱.md" in out and "4. Work" not in out
    code, out = repo("knowledge", "read", "4. Work/연봉.md", ok=False)
    assert code == 1 and "닫힌 곳" in out
    code, out = repo("knowledge", "read", ".git/연봉.md", ok=False)  # hidden folders hold copies
    assert code == 1 and "닫힌 곳" in out
    _, out = repo("knowledge", "read", "3. Projects/앱.md")
    assert "로그인" in out
    assert "deny: [4. Work]" in (repo.root / "lantern.yaml").read_text(encoding="utf-8")


def test_only_allowed_folders_are_open(repo, store):
    repo("profile", "set", "knowledge.allow=[2. study]")  # names compare without case
    _, out = repo("knowledge", "search", "JWT", "--json")
    assert "2. Study/Backend/JWT.md" in out and "3. Projects" not in out and "4. Work" not in out
    code, out = repo("knowledge", "read", "3. Projects/앱.md", ok=False)
    assert code == 1 and "닫힌 곳" in out
    (store / "2. Study" / "바로가기.md").symlink_to(store / "4. Work" / "연봉.md")  # a link into a closed folder
    code, out = repo("knowledge", "read", "2. Study/바로가기.md", ok=False)
    assert code == 1 and "닫힌 곳" in out


def test_access_lists_must_be_folders_inside_the_store(repo, store):
    code, out = repo("profile", "set", "knowledge.deny=[../밖]", ok=False)
    assert code == 1 and "knowledge.deny" in out
    code, out = repo("profile", "set", "knowledge.allow=2. Study", ok=False)
    assert code == 1 and "knowledge.allow" in out


def test_plan_closes_denied_and_hidden_and_locks_the_profile(repo, store):
    repo("profile", "set", "knowledge.deny=[4. work]")
    plan = guard.plan(Project.load(repo.root))
    assert [p.name for p in plan.closed] == ["4. Work", ".git", ".obsidian"]  # spelled as on disk
    assert plan.allow == () and [p.name for p in plan.locked] == ["lantern.yaml"]
    assert "닫힘: 4. Work · .git · .obsidian" in "\n".join(guard.describe(plan, ["claude"]))


def test_plan_finds_names_the_disk_spells_in_another_unicode_form(repo, store):
    (store / unicodedata.normalize("NFD", "회사")).mkdir()
    repo("profile", "set", "knowledge.deny=[회사]")
    assert unicodedata.normalize("NFC", guard.plan(Project.load(repo.root)).closed[0].name) == "회사"


def test_guard_refuses_to_start_when_it_would_close_nothing(repo, store):
    code, out = repo("guard", "--", "true", ok=False)
    assert code == 1 and "knowledge.allow" in out
    repo("profile", "set", "knowledge.deny=[4. Wrok]")  # a misspelled folder would stay open unnoticed
    code, out = repo("guard", "--", "true", ok=False)
    assert code == 1 and "4. Wrok" in out


def _sandbox_works() -> bool:
    """False off macOS, and inside another sandbox (macOS can't nest them)."""
    if sys.platform != "darwin" or not shutil.which("sandbox-exec"):
        return False
    return subprocess.run(["sandbox-exec", "-p", "(version 1)(allow default)", "/usr/bin/true"], capture_output=True).returncode == 0


needs_sandbox = pytest.mark.skipif(not _sandbox_works(), reason="needs macOS sandbox-exec, outside any sandbox")


def _guarded(repo, script: str) -> subprocess.CompletedProcess:
    return sh(repo.root, "lantern", "guard", "--", "/bin/sh", "-c", script, check=False)


@needs_sandbox
def test_guarded_tool_cannot_open_denied_folders(repo, store):
    repo("profile", "set", "knowledge.deny=[4. Work]")
    r = _guarded(repo, f"cat '{store}/2. Study/Backend/JWT.md' && cat '{store}/4. Work/연봉.md'")
    assert "서명된 토큰" in r.stdout and "업무 메모" not in r.stdout and r.returncode != 0
    assert "닫힘: 4. Work" in r.stderr
    for script in (
        f"{sys.executable} -c \"print(open('{store}/4. Work/연봉.md').read())\"",  # a script that opens the file itself
        f"cat '{store}/.git/연봉.md'",  # the copy in a hidden folder
        f"echo x > '{store}/4. Work/연봉.md'",
        "echo 'knowledge: null' > lantern.yaml",  # the rules can't be loosened for the next run
    ):
        assert _guarded(repo, script).returncode != 0, script
    assert "업무 메모" in (store / "4. Work" / "연봉.md").read_text(encoding="utf-8")
    assert "deny: [4. Work]" in (repo.root / "lantern.yaml").read_text(encoding="utf-8")


@needs_sandbox
def test_guarded_tool_opens_only_allowed_folders_and_lantern_still_searches(repo, store):
    repo("profile", "set", "knowledge.allow=[2. Study]", "knowledge.deny=[2. Study/AI Engineering]")
    (store / "2. Study" / "AI Engineering" / "RAG.md").write_text("# RAG\n\nJWT 언급\n", encoding="utf-8")
    assert _guarded(repo, f"cat '{store}/2. Study/Backend/JWT.md'").returncode == 0
    for closed in ("3. Projects/앱.md", "4. Work/연봉.md", "2. Study/AI Engineering/RAG.md"):
        assert _guarded(repo, f"cat '{store}/{closed}'").returncode != 0, closed
    assert _guarded(repo, f"ls '{store}'").returncode != 0  # the store root itself is closed
    r = _guarded(repo, "lantern knowledge search JWT --json")  # lantern, started by the tool, walks from the open folders
    assert r.returncode == 0 and "2. Study/Backend/JWT.md" in r.stdout and "RAG" not in r.stdout and "앱" not in r.stdout


def test_codex_starts_without_its_shared_server_and_own_sandbox():
    assert guard.adapted(["codex", "resume"]) == ["codex", "--no-daemon", "--sandbox", "danger-full-access", "resume"]
    assert guard.adapted(["/opt/homebrew/bin/codex", "--sandbox=read-only", "--no-daemon"]) == [
        "/opt/homebrew/bin/codex",
        "--sandbox=read-only",
        "--no-daemon",
    ]  # options already typed are kept, never doubled
    assert guard.adapted(["claude"]) == ["claude"] and guard.adapted(["agy", "-c"]) == ["agy", "-c"]
    lines = "\n".join(guard.describe(guard.Guard(guard.Path("/v")), ["codex"], guard.adapted(["codex"])))
    assert "--no-daemon --sandbox danger-full-access" in lines and "꺼 두세요" not in lines
