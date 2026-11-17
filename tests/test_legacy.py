"""`lantern legacy adopt` — what moves and what stays, preview first, one commit to undo."""

from conftest import docs, init_project, sh

LEGACY = "5. 기존 문서"


def _brownfield(repo):
    """A repository with documents and paths from before LanternSpec, all committed."""
    d = docs(repo)
    (d / "1. 기획").mkdir(parents=True)
    (d / "1. 기획" / "기획서.md").write_text("# 옛 기획\n", encoding="utf-8")
    (d / "updates").mkdir()
    (d / "updates" / "appcast.xml").write_text("<rss/>\n", encoding="utf-8")
    (d / "0. 템플릿").mkdir()
    (d / "0. 템플릿" / "옛 양식.md").write_text("# 옛 양식\n", encoding="utf-8")
    (d / "개발문서 MOC.md").write_text("---\ntitle: 개발문서 MOC\ntemplate: desktop-standard v2\n---\n# 옛 MOC\n", encoding="utf-8")
    (repo.root / "Scripts").mkdir()
    (repo.root / "Scripts" / "release.sh").write_text('APPCAST="docs/updates/appcast.xml"\n', encoding="utf-8")
    (repo.root / "README.md").write_text("[기획](docs/1. 기획/기획서.md)\n", encoding="utf-8")
    (repo.root / "Makefile").write_text("# 절차: docs/1. 기획/기획서.md 참고\n", encoding="utf-8")  # a link in a comment, not a use
    repo.git("add", "-A")
    repo.git("commit", "-qm", "old docs")
    repo("profile", "write", "--name", "앱", "--origin", "brownfield", "--team", "solo", "--clients", "desktop", "--design", "none")
    repo.git("add", "-A")
    repo.git("commit", "-qm", "lantern.yaml")


def _status(repo) -> str:
    return sh(repo.root, "git", "status", "--porcelain").stdout


def test_adopt_without_apply_only_shows_the_plan(repo):
    _brownfield(repo)
    _, out = repo("legacy", "adopt")
    assert _status(repo) == "" and not (docs(repo) / LEGACY).exists()
    assert "옮김  1. 기획/" in out
    assert "남김  updates/" in out and "Scripts/release.sh" in out  # a script reads this path
    assert "옮김  0. 템플릿/" in out and "옮김  개발문서 MOC.md" in out  # ours by name only
    assert "README.md → docs/1. 기획/" in out and "Makefile → docs/1. 기획/" in out  # links a person fixes after the move
    assert "--apply" in out


def test_adopt_apply_moves_in_one_commit_and_history_continues(repo):
    _brownfield(repo)
    before = int(sh(repo.root, "git", "rev-list", "--count", "HEAD").stdout)
    _, out = repo("legacy", "adopt", "--apply")
    d = docs(repo)
    assert (d / "updates" / "appcast.xml").exists()
    assert (d / LEGACY / "1. 기획" / "기획서.md").exists() and not (d / "1. 기획").exists()
    assert (d / LEGACY / "0. 템플릿" / "옛 양식.md").exists() and (d / LEGACY / "개발문서 MOC.md").exists()
    assert int(sh(repo.root, "git", "rev-list", "--count", "HEAD").stdout) == before + 1 and _status(repo) == ""
    log = sh(repo.root, "git", "log", "--follow", "--oneline", "--", f"docs/{LEGACY}/1. 기획/기획서.md").stdout
    assert len(log.splitlines()) == 2  # the move and the commit that first added it
    assert "git revert" in out
    _, out = repo("legacy", "adopt")  # nothing left to move; ours stays
    assert "옮김" not in out


def test_adopt_stops_when_the_documents_have_uncommitted_changes(repo):
    _brownfield(repo)
    (docs(repo) / "1. 기획" / "기획서.md").write_text("# 고치는 중\n", encoding="utf-8")
    code, out = repo("legacy", "adopt", "--apply", ok=False)
    assert code != 0 and "커밋" in out
    assert (docs(repo) / "1. 기획" / "기획서.md").exists() and not (docs(repo) / LEGACY).exists()


def test_adopt_leaves_what_docs_keep_lists(repo):
    _brownfield(repo)
    repo("profile", "set", "docs.keep=[1. 기획/]")
    repo.git("commit", "-qam", "keep")
    _, out = repo("legacy", "adopt", "--apply")
    assert "남김  1. 기획/" in out and "docs.keep" in out
    assert (docs(repo) / "1. 기획" / "기획서.md").exists()


def test_adopt_leaves_what_lantern_made(repo):
    init_project(repo)
    (docs(repo) / "wiki").mkdir()
    (docs(repo) / "wiki" / "메모.md").write_text("# 메모\n", encoding="utf-8")
    repo.git("add", "-A")
    repo.git("commit", "-qm", "docs")
    _, out = repo("legacy", "adopt", "--apply")
    d = docs(repo)
    assert (d / "0. 템플릿" / "_meta" / "enums.yaml").exists() and (d / "개발문서 MOC.md").exists() and (d / "3. 현재 상태").exists()
    assert (d / LEGACY / "wiki" / "메모.md").exists()


def test_adopt_says_when_git_does_not_track_what_moves(repo):
    _brownfield(repo)
    (repo.root / ".gitignore").write_text("docs/n*/\n", encoding="utf-8")
    repo.git("add", "-A")
    repo.git("commit", "-qm", "ignore")
    (docs(repo) / "notes").mkdir()
    (docs(repo) / "notes" / "메모.md").write_text("# 메모\n", encoding="utf-8")
    repo("profile", "set", "docs.keep=[1. 기획/, 0. 템플릿/, 개발문서 MOC.md]")
    repo.git("commit", "-qam", "keep")
    before = sh(repo.root, "git", "rev-parse", "HEAD").stdout
    _, out = repo("legacy", "adopt", "--apply")
    assert "git이 추적하지 않습니다" in out and "git revert" not in out.split("옮겼습니다")[1]
    assert (docs(repo) / LEGACY / "notes" / "메모.md").exists() and sh(repo.root, "git", "rev-parse", "HEAD").stdout == before


def test_repo_file_rules_list_ai_context_files(repo):
    init_project(repo)
    text = (docs(repo) / "3. 현재 상태/규칙/저장소 파일 규칙.md").read_text(encoding="utf-8")
    assert "## AI Context Files" in text and "### 표준" in text and "### LanternSpec" in text
    assert "LanternSpec 스킬 20개" in text and "`설계.md` (영문: `Design.md`)" in text
    assert "### 도입 전" not in text and "lantern:if" not in text  # nothing to compare with in a new project


def test_brownfield_repo_file_rules_ask_for_before_and_after(repo):
    init_project(repo, "--origin", "brownfield")
    text = (docs(repo) / "3. 현재 상태/규칙/저장소 파일 규칙.md").read_text(encoding="utf-8")
    assert "### 도입 전" in text and "### 도입 후" in text
    assert text.count("| {{파일}} | {{누가 정했나}} | {{무엇을 적나}} |") == 2
    repo("check")
