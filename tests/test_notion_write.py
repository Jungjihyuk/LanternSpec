"""Writing to Notion: a page under a page, a row of a database, and never a second note with the same title by accident."""

import io
import json
import urllib.error
from typing import Any

import pytest

from conftest import docs, init_project
from lanternspec.core import frontmatter
from lanternspec.core import profile as pm
from lanternspec.learn.knowledge import Adapter, KnowledgeError, mcp_server
from lanternspec.learn.knowledge.notion import NotionAdapter, NotionError

PAGE = "124791d2c4e380b086defba8b13fd766"
DATABASE = "b914fca558014ec5883b3fa0f6b3d33b"


def _options(*names: str) -> dict[str, Any]:
    return {"options": [{"name": n} for n in names]}


SCHEMA: dict[str, Any] = {
    "제목": {"type": "title", "title": {}},
    "분류": {"type": "select", "select": _options("개발", "개인")},
    "유형": {"type": "multi_select", "multi_select": _options("FastAPI", "Python", "JWT")},
    "체크": {"type": "status", "status": _options("시작 전", "완료")},
    "날짜": {"type": "date", "date": {}},
    "목표량": {"type": "number", "number": {}},
    "끝남": {"type": "checkbox", "checkbox": {}},
    "메모": {"type": "rich_text", "rich_text": {}},
    "주소": {"type": "url", "url": {}},
    "진행률": {"type": "formula", "formula": {}},
    "파일": {"type": "files", "files": {}},
}


class FakeNotion:
    """A workspace with one page and one database; keeps every request it was asked."""

    def __init__(self, titles: tuple[str, ...] = (), fail: dict[str, tuple[int, str]] | None = None) -> None:
        self.titles = titles  # notes already there, in the page and in the database alike
        self.fail = fail or {}  # "METHOD /path" → (status, body)
        self.calls: list[tuple[str, str, Any]] = []

    def made(self) -> list[Any]:
        return [body for method, path, body in self.calls if (method, path) == ("POST", "/pages")]

    def _answer(self, method: str, path: str, body: Any, full: str) -> dict[str, Any]:
        if path == f"/databases/{DATABASE}":
            return {"object": "database", "title": [{"plain_text": "노트"}], "properties": SCHEMA}
        if path.startswith("/databases/") and method == "GET":
            message = b'{"message":"Provided ID is a page, not a database."}'
            raise urllib.error.HTTPError(path, 400, "bad", {}, io.BytesIO(message))  # type: ignore[arg-type]
        if path == f"/databases/{DATABASE}/query":
            wanted = body["filter"]["title"]["equals"].casefold()
            assert body["filter"]["property"] == "제목"
            return {"results": [{"id": "r", "url": "https://notion.so/r"} for t in self.titles if t.strip().casefold() == wanted]}
        if path == f"/blocks/{PAGE}/children":  # two pages of answers: the notes are on the second
            if "start_cursor" not in full:
                return {"results": [{"id": "x", "type": "paragraph", "paragraph": {}}], "has_more": True, "next_cursor": "c"}
            return {"results": [{"id": "r-1", "type": "child_page", "child_page": {"title": t}} for t in self.titles], "has_more": False}
        return {"id": "new", "url": "https://notion.so/new"}

    def __call__(self, req: Any) -> Any:
        full = req.full_url.split("notion.com/v1")[1]
        path, method = full.split("?")[0], req.get_method()
        body = json.loads(req.data.decode()) if req.data else None
        self.calls.append((method, path, body))
        if f"{method} {path}" in self.fail:
            status, text = self.fail[f"{method} {path}"]
            raise urllib.error.HTTPError(path, status, "bad", {}, io.BytesIO(text.encode()))  # type: ignore[arg-type]
        data = self._answer(method, path, body, full)

        class Resp:
            def read(self_inner) -> bytes:
                return json.dumps(data).encode()

            def __enter__(self_inner) -> "Resp":
                return self_inner

            def __exit__(self_inner, *a: Any) -> bool:
                return False

        return Resp()


def _adapter(parent: str, fake: FakeNotion) -> NotionAdapter:
    return NotionAdapter(parent, "secret", opener=fake)


# --------------------------------------------------------------------------- where a note goes


def test_a_note_becomes_a_page_under_a_page_and_a_row_of_a_database():
    page, row = FakeNotion(), FakeNotion()

    assert _adapter(PAGE, page).write("JWT.md", "# JWT\n") == "https://notion.so/new"
    assert _adapter(DATABASE, row).write("JWT.md", "# JWT\n") == "https://notion.so/new"

    assert page.made()[0]["parent"] == {"page_id": PAGE} and list(page.made()[0]["properties"]) == ["title"]
    assert row.made()[0]["parent"] == {"database_id": DATABASE}
    assert row.made()[0]["properties"]["제목"]["title"][0]["text"]["content"] == "JWT"  # the title column has its own name


def test_a_row_body_has_no_frontmatter_lines():
    fake = FakeNotion()
    _adapter(DATABASE, fake).write("JWT.md", "---\ncreated: 2026-11-24\n---\n\n# JWT\n본문\n")

    assert [b["type"] for b in fake.made()[0]["children"]] == ["heading_1", "paragraph"]


def test_a_failure_that_is_not_about_the_kind_is_not_taken_for_a_page():
    fake = FakeNotion(fail={f"GET /databases/{DATABASE}": (500, "boom")})

    with pytest.raises(NotionError, match="500"):
        _adapter(DATABASE, fake).write("JWT.md", "x")
    assert not fake.made()


def test_a_database_with_several_sources_is_refused_in_plain_words():
    fake = FakeNotion(fail={f"GET /databases/{DATABASE}": (400, "This database has multiple data sources")})

    with pytest.raises(KnowledgeError, match="데이터 소스"):
        _adapter(DATABASE, fake).write("JWT.md", "x")


# --------------------------------------------------------------------------- the same title


@pytest.mark.parametrize("parent", [PAGE, DATABASE])
def test_a_note_with_the_same_title_is_not_made_again_and_another_title_is(parent):
    fake = FakeNotion(titles=("jwt ",))  # Notion titles often end in a space, and case does not make another note
    adapter = _adapter(parent, fake)

    with pytest.raises(KnowledgeError) as refused:
        adapter.write("JWT.md", "x")
    assert "notion.so/r" in str(refused.value) and "--target" in str(refused.value)  # which page it is, and what to do
    assert not fake.made()

    adapter.write("JWT 복습.md", "x")
    assert len(fake.made()) == 1


@pytest.mark.parametrize("parent", [PAGE, DATABASE])
def test_writing_only_ever_adds(parent):
    fake = FakeNotion(titles=("다른 노트",))
    _adapter(parent, fake).write("JWT.md", "\n".join(f"줄 {i}" for i in range(150)))

    changed = [(m, p) for m, p, _ in fake.calls if m not in ("GET",) and not p.endswith("/query")]
    assert changed == [("POST", "/pages"), ("PATCH", "/blocks/new/children")]  # the new page, and the rest of its own text


def test_a_page_whose_text_was_cut_short_is_named():
    fake = FakeNotion(fail={"PATCH /blocks/new/children": (500, "boom")})

    with pytest.raises(KnowledgeError, match="https://notion.so/new"):
        _adapter(PAGE, fake).write("JWT.md", "\n".join(f"줄 {i}" for i in range(150)))


# --------------------------------------------------------------------------- the properties of a row


def test_the_properties_that_can_be_filled_are_listed_with_their_choices():
    found = {p.name: p for p in _adapter(DATABASE, FakeNotion()).properties()}

    assert found["분류"].kind == "select" and found["분류"].options == ["개발", "개인"]
    assert "제목" not in found and "진행률" not in found and "파일" not in found  # the note's title; computed; not text
    assert _adapter(PAGE, FakeNotion()).properties() == []
    assert Adapter().properties() == []


def test_every_kind_is_written_the_way_notion_takes_it():
    fake = FakeNotion()
    _adapter(DATABASE, fake).write(
        "JWT.md",
        "x",
        {
            "분류": "개발",
            "유형": "jwt, Python",  # a comma list, and a choice found whatever its case
            "체크": "시작 전",
            "날짜": "2026-11-24",
            "목표량": "3",
            "끝남": "true",
            "메모": "한 줄",
            "주소": "https://a.b",
        },
    )

    props = fake.made()[0]["properties"]
    assert props["분류"] == {"select": {"name": "개발"}}
    assert props["유형"] == {"multi_select": [{"name": "JWT"}, {"name": "Python"}]}
    assert props["체크"] == {"status": {"name": "시작 전"}}
    assert props["날짜"] == {"date": {"start": "2026-11-24"}}
    assert props["목표량"] == {"number": 3} and props["끝남"] == {"checkbox": True}
    assert props["메모"]["rich_text"][0]["text"]["content"] == "한 줄" and props["주소"] == {"url": "https://a.b"}


def test_a_property_left_empty_is_not_sent():
    fake = FakeNotion()
    _adapter(DATABASE, fake).write("JWT.md", "x", {"분류": "", "유형": [], "메모": None})
    assert list(fake.made()[0]["properties"]) == ["제목"]


@pytest.mark.parametrize(
    ("values", "said"),
    [
        ({"분류": "없는 값"}, "개인"),  # Notion would add the choice: the choices there are named instead
        ({"유형": ["JWT", "Rust"]}, "Rust"),
        ({"없는 속성": "x"}, "없는 속성"),
        ({"진행률": "50"}, "진행률"),
        ({"제목": "다른 제목"}, "제목"),
        ({"목표량": "많이"}, "목표량"),
        ({"날짜": "내일"}, "날짜"),
        ({"끝남": "글쎄"}, "끝남"),
        ({"분류": ["개발", "개인"]}, "분류"),
    ],
)
def test_a_value_the_database_does_not_have_stops_the_write_before_anything_is_made(values, said):
    fake = FakeNotion()
    with pytest.raises(KnowledgeError, match=said):
        _adapter(DATABASE, fake).write("JWT.md", "x", values)
    assert not fake.made()


def test_a_place_without_properties_refuses_them_instead_of_dropping_them(tmp_path):
    from lanternspec.learn.knowledge.obsidian import ObsidianAdapter

    fake = FakeNotion()
    with pytest.raises(KnowledgeError, match="속성"):
        _adapter(PAGE, fake).write("JWT.md", "x", {"분류": "개발"})
    with pytest.raises(KnowledgeError, match="속성"):
        ObsidianAdapter(tmp_path).write("JWT.md", "x", {"분류": "개발"})
    assert not fake.made() and not list(tmp_path.iterdir())


# --------------------------------------------------------------------------- from the draft to the row


@pytest.fixture
def notion_project(repo, monkeypatch):
    init_project(repo)
    data = pm.load(repo.root).data
    data["knowledge"] = {"type": "notion", "path": DATABASE, "write": "direct"}
    pm.save(repo.root, data)
    fake = FakeNotion(titles=("OAuth",))
    monkeypatch.setattr("lanternspec.learn.knowledge.notion.from_config", lambda k, state: _adapter(str(k["path"]), fake))
    return repo, fake


def test_the_values_wait_in_the_draft_for_approval_and_go_into_the_row(notion_project, tmp_path):
    repo, fake = notion_project
    text = tmp_path / "n.md"
    text.write_text("# JWT\n본문\n", encoding="utf-8")

    _, listed = repo("knowledge", "properties")
    assert "분류" in listed and "개발" in listed
    repo("knowledge", "propose", "JWT", "--file", str(text), "--property", "분류=개발", "--property", "유형=JWT, Python")
    draft = docs(repo) / "📒 부채/노트 초안/JWT.md"
    assert frontmatter.parse(draft.read_text(encoding="utf-8")).meta["properties"] == {"분류": "개발", "유형": "JWT, Python"}
    assert not fake.made()  # nothing is made before the person approves

    repo("knowledge", "write", str(draft))
    assert fake.made()[0]["properties"]["분류"] == {"select": {"name": "개발"}}


def test_a_wrong_value_is_caught_when_the_draft_is_made(notion_project):
    repo, _ = notion_project
    code, out = repo("knowledge", "propose", "JWT", "--property", "분류=없는 값", ok=False)
    assert code != 0 and "개발" in out
    code, out = repo("knowledge", "propose", "JWT", "--property", "분류", ok=False)
    assert code != 0 and "--property" in out
    assert not (docs(repo) / "📒 부채/노트 초안/JWT.md").exists()


def test_the_same_title_is_refused_and_another_target_title_is_written(notion_project, tmp_path):
    repo, fake = notion_project
    text = tmp_path / "n.md"
    text.write_text("본문\n", encoding="utf-8")
    repo("knowledge", "propose", "OAuth", "--file", str(text))
    draft = str(docs(repo) / "📒 부채/노트 초안/OAuth.md")

    code, out = repo("knowledge", "write", draft, ok=False)
    assert code != 0 and "OAuth" in out and not fake.made()

    repo("knowledge", "write", draft, "--target", "OAuth 흐름.md")
    assert fake.made()[0]["properties"]["제목"]["title"][0]["text"]["content"] == "OAuth 흐름"


def test_a_store_without_properties_says_so(repo):
    init_project(repo)
    data = pm.load(repo.root).data
    data["knowledge"] = {"type": "folder", "path": str(repo.root), "write": "direct"}
    pm.save(repo.root, data)
    _, out = repo("knowledge", "properties")
    assert "속성" in out


def test_the_mcp_server_offers_the_properties_too(notion_project):
    from lanternspec.core.project import Project

    repo, _ = notion_project
    project = Project.load(repo.root)
    assert {"name": "분류", "kind": "select", "options": ["개발", "개인"]} in mcp_server.call(project, "properties", {})
    mcp_server.call(project, "propose", {"title": "JWT", "properties": {"분류": "개발"}})
    with pytest.raises(KnowledgeError):
        mcp_server.call(project, "propose", {"title": "CRDT", "properties": {"분류": "없는 값"}})


@pytest.mark.parametrize("language", ["ko", "en"])
def test_the_learning_skill_asks_for_properties_only_with_notion(language):
    from lanternspec.core.profile import Profile
    from lanternspec.core.templating import apply_conditions
    from lanternspec.tools.skills import body_context, load_sources

    body = next(s for s in load_sources(language) if s.name == "l-learn").body
    for kind, asked in (("notion", True), ("obsidian", False)):
        ctx = body_context(Profile(data={"knowledge": {"type": kind, "path": "x"}}), "claude")
        text = apply_conditions(body, ctx)
        assert ("lantern knowledge properties" in text) is asked and "--target" in text
