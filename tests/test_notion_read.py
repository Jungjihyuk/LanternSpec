"""Reading a Notion page: nested blocks, links, tables, subpages and the properties of a database row."""

import io
import json
import urllib.error
from typing import Any

from lanternspec.learn.knowledge.notion import MAX_DEPTH, MAX_REQUESTS, NotionAdapter, block_text, properties_text


def _rt(text: str) -> dict[str, Any]:
    return {"rich_text": [{"plain_text": text}]}


def _block(kind: str, text: str = "", block_id: str = "", children: bool = False, **extra: Any) -> dict[str, Any]:
    body = {**_rt(text), **extra}
    return {"id": block_id, "type": kind, "has_children": children, kind: body}


class FakeTree:
    """Answers Notion calls from a table: block id -> its children, page id -> its properties."""

    def __init__(
        self, children: dict[str, list[dict[str, Any]]], pages: dict[str, dict[str, Any]] | None = None, endless: bool = False
    ) -> None:
        self.children = children
        self.pages = pages or {}
        self.found: list[dict[str, Any]] = []  # what a search answers
        self.endless = endless
        self.asked: list[str] = []

    def __call__(self, req: Any) -> Any:
        assert req.headers["Authorization"] == "Bearer secret"
        path = req.full_url.split("notion.com/v1")[1].split("?")[0]
        if path.startswith("/blocks/") and path.endswith("/children"):
            block_id = path.split("/")[2]
            self.asked.append(block_id)
            if self.endless:
                data = {"results": [_block("paragraph", f"in {block_id}", block_id=block_id + "x", children=True)], "has_more": False}
            else:
                data = {"results": self.children.get(block_id, []), "has_more": False}
        elif path == "/search":
            data = {"results": self.found}
        elif path.startswith("/pages/"):
            page_id = path.split("/")[2]
            if page_id not in self.pages:
                raise urllib.error.HTTPError(req.full_url, 404, "not found", {}, io.BytesIO(b"{}"))  # type: ignore[arg-type]
            data = self.pages[page_id]
        else:
            raise AssertionError(path)

        class Resp:
            def read(self_inner) -> bytes:
                return json.dumps(data).encode()

            def __enter__(self_inner) -> "Resp":
                return self_inner

            def __exit__(self_inner, *a: Any) -> bool:
                return False

        return Resp()


def _adapter(fake: FakeTree) -> NotionAdapter:
    return NotionAdapter("parent", "secret", opener=fake)


def test_read_goes_into_blocks_that_have_children():
    fake = FakeTree(
        {
            "root": [_block("heading_2", "Pydantic", "h", children=True), _block("paragraph", "끝")],
            "h": [_block("paragraph", "데이터 검증"), _block("bulleted_list_item", "타입 힌트", "b", children=True)],
            "b": [_block("bulleted_list_item", "더 깊은 줄")],
        }
    )
    assert _adapter(fake).read("root") == "## Pydantic\n  데이터 검증\n  - 타입 힌트\n    - 더 깊은 줄\n끝"


def test_read_indents_every_line_of_a_nested_code_block():
    fake = FakeTree({"root": [_block("toggle", "예시", "t", children=True)], "t": [_block("code", "a = 1\nb = 2")]})
    assert _adapter(fake).read("root") == "- 예시\n  ```\n  a = 1\n  b = 2\n  ```"


def test_read_shows_a_bookmark_as_its_address_and_skips_the_table_of_contents():
    fake = FakeTree(
        {
            "root": [
                {"id": "c", "type": "table_of_contents", "has_children": False, "table_of_contents": {}},
                {"id": "k", "type": "bookmark", "has_children": False, "bookmark": {"url": "https://example.com/a", "caption": []}},
            ]
        }
    )
    assert _adapter(fake).read("root") == "[북마크] https://example.com/a"


def test_read_names_a_subpage_without_following_it():
    fake = FakeTree(
        {
            "root": [
                {"id": "sub", "type": "child_page", "has_children": True, "child_page": {"title": "하위 문서"}},
                {"id": "db", "type": "child_database", "has_children": False, "child_database": {"title": "표"}},
            ]
        }
    )
    assert _adapter(fake).read("root") == "- [하위 페이지] 하위 문서 (sub)\n- [데이터베이스] 표 (db)"
    assert fake.asked == ["root"]  # the subpage is its own document: found by search, read by its own id


def test_read_writes_table_rows_as_lines():
    row = {
        "id": "r1",
        "type": "table_row",
        "has_children": False,
        "table_row": {"cells": [[{"plain_text": "이름"}], [{"plain_text": "값"}]]},
    }
    fake = FakeTree({"root": [{"id": "tbl", "type": "table", "has_children": True, "table": {"table_width": 2}}], "tbl": [row]})
    assert _adapter(fake).read("root") == "  | 이름 | 값 |"


def test_read_puts_the_properties_of_a_database_row_first():
    page = {
        "properties": {
            "제목": {"type": "title", "title": [{"plain_text": "FastAPI"}]},
            "분류": {"type": "select", "select": {"name": "개발"}},
            "유형": {"type": "multi_select", "multi_select": [{"name": "공부"}, {"name": "프로젝트"}]},
            "날짜": {"type": "date", "date": {"start": "2025-10-07", "end": None}},
            "비어 있음": {"type": "select", "select": None},
        }
    }
    fake = FakeTree({"root": [_block("paragraph", "본문")]}, {"root": page})
    assert _adapter(fake).read("root") == "---\n분류: 개발\n유형: 공부, 프로젝트\n날짜: 2025-10-07\n---\n본문"


def test_read_still_works_when_the_properties_cannot_be_read():
    fake = FakeTree({"root": [_block("paragraph", "본문")]})  # no page entry: the properties call fails
    assert _adapter(fake).read("root") == "본문"


def test_read_stops_going_deeper_at_the_depth_limit():
    fake = FakeTree({}, endless=True)
    text = _adapter(fake).read("root")
    assert len(fake.asked) == MAX_DEPTH + 1
    assert text.count("in ") == MAX_DEPTH + 1


def test_read_stops_when_it_has_asked_too_many_times_and_says_so():
    many = [_block("paragraph", f"줄 {i}", f"b{i}", children=True) for i in range(MAX_REQUESTS * 2)]
    fake = FakeTree({"root": many})
    text = _adapter(fake).read("root")
    assert len(fake.asked) <= MAX_REQUESTS
    assert "일부만" in text


def test_properties_text_covers_the_simple_kinds_and_skips_the_rest():
    props = {
        "수량": {"type": "number", "number": 3},
        "끝남": {"type": "checkbox", "checkbox": True},
        "안 끝남": {"type": "checkbox", "checkbox": False},
        "메모": {"type": "rich_text", "rich_text": [{"plain_text": "한 줄"}]},
        "주소": {"type": "url", "url": "https://example.com"},
        "기간": {"type": "date", "date": {"start": "2025-01-01", "end": "2025-01-31"}},
        "수식": {"type": "formula", "formula": {"type": "number", "number": 7}},
    }
    assert (
        properties_text({"properties": props})
        == "---\n수량: 3\n끝남: ✔\n메모: 한 줄\n주소: https://example.com\n기간: 2025-01-01 → 2025-01-31\n---\n"
    )
    assert properties_text({"properties": {}}) == ""


def test_block_text_marks_a_toggle_as_a_bullet():
    assert block_text(_block("toggle", "접힘")) == "- 접힘"


class Flaky:
    """Answers 429 (with a Retry-After) a number of times, then a page's children."""

    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.calls = 0

    def __call__(self, req: Any) -> Any:
        self.calls += 1
        if self.calls <= self.failures:
            raise urllib.error.HTTPError(req.full_url, 429, "rate limited", {"Retry-After": "2"}, io.BytesIO(b"{}"))  # type: ignore[arg-type]
        data = {"results": [_block("paragraph", "다시 됨")], "has_more": False}

        class Resp:
            def read(self_inner) -> bytes:
                return json.dumps(data).encode()

            def __enter__(self_inner) -> "Resp":
                return self_inner

            def __exit__(self_inner, *a: Any) -> bool:
                return False

        return Resp()


def test_a_rate_limited_request_waits_as_told_and_tries_again(monkeypatch):
    waits: list[float] = []
    monkeypatch.setattr("lanternspec.learn.knowledge.notion.time.sleep", waits.append)
    flaky = Flaky(failures=2)
    assert NotionAdapter("parent", "secret", opener=flaky).read("root") == "다시 됨"
    assert waits == [2.0, 2.0]


def test_a_request_that_stays_rate_limited_gives_up_with_the_api_error(monkeypatch):
    import pytest

    from lanternspec.learn.knowledge import KnowledgeError

    monkeypatch.setattr("lanternspec.learn.knowledge.notion.time.sleep", lambda s: None)
    flaky = Flaky(failures=99)
    with pytest.raises(KnowledgeError, match="429"):
        NotionAdapter("parent", "secret", opener=flaky).read("root")
    assert flaky.calls == 4  # the first try and three more


PAGE = "124791d2c4e380b086defba8b13fd766"


def _found(title: str, url: str = f"https://app.notion.com/p/FastAPI-{PAGE}") -> dict[str, Any]:
    return {
        "id": "124791d2-c4e3-80b0-86de-fba8b13fd766",
        "url": url,
        "last_edited_time": "2025-10-07T00:00:00.000Z",
        "properties": {"제목": {"type": "title", "title": [{"plain_text": title}]}},
    }


def test_a_title_that_ends_in_a_space_still_matches_its_name_exactly():
    fake = FakeTree({})
    fake.found = [_found("FastAPI ")]  # Notion titles often end in a space

    (hit,) = _adapter(fake).search("FastAPI")

    assert hit.title == "FastAPI" and hit.score == 100


def test_a_hit_points_at_the_page_by_its_address_and_read_takes_that_address_back():
    fake = FakeTree({PAGE: [_block("paragraph", "본문")]})
    fake.found = [_found("FastAPI")]
    adapter = _adapter(fake)

    (hit,) = adapter.search("FastAPI")

    assert hit.path == f"https://app.notion.com/p/FastAPI-{PAGE}"  # a person can open it, and a debt card keeps it as its note
    assert adapter.read(hit.path) == "본문"
    assert fake.asked == [PAGE]  # the page ID is taken from the end of the address


def test_read_takes_an_id_with_or_without_dashes_a_query_and_a_bare_name():
    for ref in (PAGE, "124791d2-c4e3-80b0-86de-fba8b13fd766", f"https://www.notion.so/me/FastAPI-{PAGE}?pvs=4", f"https://x.so/{PAGE}#h"):
        fake = FakeTree({PAGE: [_block("paragraph", "본문")]})
        assert _adapter(fake).read(ref) == "본문" and fake.asked == [PAGE], ref
    fake = FakeTree({"p1": [_block("paragraph", "본문")]})
    assert _adapter(fake).read("p1") == "본문" and fake.asked == ["p1"]  # not an address or an ID: left as it is
