"""배우는 선로: 지식 연결기(search · read · propose · write) + 부채 장부."""

from conftest import docs, init_project
from lanternspec.core import frontmatter


def card_meta(r, debt_id):
    p = next((docs(r) / "📒 부채/카드").glob(f"{debt_id} *"))
    return frontmatter.parse(p.read_text(encoding="utf-8")).meta


def test_knowledge_search_read_and_areas(repo, vault):
    init_project(repo, vault=vault)
    _, out = repo("knowledge", "search", "json web token", "--json")
    assert '"title": "JWT"' in out and ".obsidian" not in out
    _, out = repo("knowledge", "search", "Optimistic Lock")
    assert "🔴" in out
    _, out = repo("knowledge", "read", "2. Study/Backend/JWT.md")
    assert "서명된 토큰" in out
    code, out = repo("knowledge", "read", "../../etc/passwd", ok=False)
    assert code == 1
    _, out = repo("knowledge", "areas")
    assert "· 있음  Backend" in out and "✚ 제안  AI Engineering" in out


def test_propose_then_write_respects_write_mode(repo, vault):
    init_project(repo, vault=vault)
    repo("knowledge", "propose", "Optimistic Lock", "--area", "data")
    draft = docs(repo) / "📒 부채/노트 초안/Optimistic Lock.md"
    assert frontmatter.parse(draft.read_text(encoding="utf-8")).meta["status"] == "승인 대기"
    code, out = repo("knowledge", "write", str(draft), ok=False)
    assert code == 1 and "빈칸" in out
    draft.write_text(draft.read_text(encoding="utf-8").replace("{{한 줄 요약}}", "버전으로 충돌을 감지"), encoding="utf-8")
    repo("knowledge", "write", str(draft))
    written = vault / "2. Study" / "Optimistic Lock.md"
    assert "버전으로 충돌을 감지" in written.read_text(encoding="utf-8")
    assert frontmatter.parse(draft.read_text(encoding="utf-8")).meta["status"] == "반영됨"
    # never overwrite the other store
    repo("knowledge", "propose", "JWT", "--target", "2. Study/Backend/JWT.md", "--file", str(draft))
    code, out = repo("knowledge", "write", str(docs(repo) / "📒 부채/노트 초안/JWT.md"), ok=False)
    assert code == 1 and "덮어쓰지 않음" in out
    # propose_only: drafts only
    repo("profile", "set", "knowledge.write=propose_only")
    repo("knowledge", "propose", "CRDT", "--file", str(draft))
    code, out = repo("knowledge", "write", str(docs(repo) / "📒 부채/노트 초안/CRDT.md"), ok=False)
    assert code == 1 and "propose_only" in out


def test_debt_counting_once_per_conversation_and_reopen(repo, vault):
    init_project(repo, vault=vault)
    repo("scaffold", "work", "로그인")
    repo(
        "debt",
        "new",
        "JWT 갱신",
        "--area",
        "backend",
        "--alias",
        "JWT",
        "--alias",
        "JSON Web Token",
        "--work",
        "W-001",
        "--session",
        "s1",
        "--context",
        "토큰 만료",
    )
    m = card_meta(repo, "D-001")
    assert m["status"] == "처음" and m["ask_count"] == 1 and m["area"] == "backend"
    code, out = repo("debt", "new", "jwt", "--area", "backend", ok=False)
    assert code == 1 and "이미 카드가 있습니다" in out
    _, out = repo("debt", "ask", "JSON web-token", "--session", "s1")
    assert "이미 셌습니다" in out
    repo("debt", "ask", "JWT", "--session", "s2", "--work", "W-001")
    m = card_meta(repo, "D-001")
    assert m["status"] == "되물음" and m["ask_count"] == 2 and len(m["work"]) == 1
    repo("debt", "resolve", "D-001")
    assert card_meta(repo, "D-001")["status"] == "해결"
    _, out = repo("debt", "ask", "D-001", "--session", "s3")
    assert "다시 열림" in out
    m = card_meta(repo, "D-001")
    assert m["status"] == "되물음" and m["ask_count"] == 3 and m["resolved"] == ""
    code, out = repo("debt", "new", "CRDT", "--area", "quantum", ok=False)
    assert code == 1 and "영역" in out
    # status page
    repo("debt", "status")
    status = (docs(repo) / "📒 부채/부채 현황.md").read_text(encoding="utf-8")
    assert "열린 부채 1개" in status and "| 🧠 이해 | 1 |" in status and "D-001 JWT 갱신" in status


def test_known_tech_is_never_asked_again(repo, vault):
    init_project(repo, vault=vault)
    repo("debt", "known", "add", "React", "--alias", "ReactJS")
    repo("debt", "known", "add", "react")  # duplicate is ignored
    _, out = repo("debt", "find", "reactjs")
    assert "아는 기술" in out
    _, out = repo("debt", "known", "list")
    assert out.strip() == "React · ReactJS"


def test_learning_line_off_without_store(repo):
    init_project(repo)
    code, out = repo("knowledge", "search", "JWT", ok=False)
    assert code == 1 and "지식 저장소" in out
