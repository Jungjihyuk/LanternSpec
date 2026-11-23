"""Searching a Notion workspace by title and by properties, from a list of all the pages that is kept for a while.

Notion's own search looks at titles only, so the list of pages (with their properties) is fetched whole and searched here.
"""

import json
import urllib.error
from pathlib import Path
from typing import Any

from conftest import init_project
from lanternspec.core.project import Project
from lanternspec.core.state import IGNORED
from lanternspec.learn.knowledge import adapter_for
from lanternspec.learn.knowledge.notion import CACHE_SECONDS, NotionAdapter, match


def _page(pid: str, title: str, **props: Any) -> dict[str, Any]:
    """A page as Notion's search lists it: `props` maps a property name to ("select" | "multi_select" | "rich_text", value)."""
    out: dict[str, Any] = {"제목": {"type": "title", "title": [{"plain_text": title}]}}
    for name, (kind, value) in props.items():
        if kind == "multi_select":
            out[name] = {"type": kind, kind: [{"name": v} for v in value]}
        elif kind == "rich_text":
            out[name] = {"type": kind, kind: [{"plain_text": value}]}
        else:
            out[name] = {"type": kind, kind: {"name": value}}
    return {"id": pid, "url": f"https://www.notion.so/{pid}", "last_edited_time": "2026-11-20T00:00:00.000Z", "properties": out}


class FakeWorkspace:
    """Answers `/search` listings in pages of `size`; counts how many times it was asked."""

    def __init__(self, pages: list[dict[str, Any]], size: int = 100) -> None:
        self.pages = pages
        self.size = size
        self.asked = 0

    def __call__(self, req: Any) -> Any:
        assert req.full_url.endswith("/search"), req.full_url
        self.asked += 1
        body = json.loads(req.data.decode())
        assert body["page_size"] == 100 and body["filter"] == {"property": "object", "value": "page"}
        start = int(body.get("start_cursor") or 0)
        chunk = self.pages[start : start + self.size]
        more = start + self.size < len(self.pages)
        data = {"results": chunk, "has_more": more, "next_cursor": str(start + self.size) if more else None}

        class Resp:
            def read(self_inner) -> bytes:
                return json.dumps(data).encode()

            def __enter__(self_inner) -> "Resp":
                return self_inner

            def __exit__(self_inner, *a: Any) -> bool:
                return False

        return Resp()


WORKSPACE = [
    _page("p1", "FastAPI", 유형=("multi_select", ["FastAPI"])),
    _page("p2", "모니터링", 유형=("multi_select", ["Monitoring", "Grafana", "Prometheus"]), 분류=("select", "개인")),
    _page("p3", "Kubernetes"),
    _page("p4", "회고 메모", 메모=("rich_text", "Prometheus 알림을 정리함")),
]


def _adapter(pages: list[dict[str, Any]] | None = None, state: Path | None = None, size: int = 100) -> tuple[NotionAdapter, FakeWorkspace]:
    fake = FakeWorkspace(pages if pages is not None else WORKSPACE, size)
    return NotionAdapter("parent", "secret", opener=fake, state_dir=state), fake


# --------------------------------------------------------------------------- what is found


def test_a_word_that_is_only_in_a_property_is_found_and_the_result_says_where():
    adapter, _ = _adapter()

    (hit,) = adapter.search("Grafana")

    assert hit.title == "모니터링" and hit.path == "https://www.notion.so/p2"
    assert hit.summary == "유형: Grafana"  # why this note came up


def test_a_title_beats_a_property_and_an_exact_property_value_beats_a_mention():
    adapter, _ = _adapter()

    titles = [h.title for h in adapter.search("Prometheus")]

    assert titles == ["모니터링", "회고 메모"]  # the tag is exactly "Prometheus"; the memo only mentions it
    assert [h.title for h in adapter.search("Kubernetes")] == ["Kubernetes"]
    assert (
        adapter.search("FastAPI")[0].score == 100 and adapter.search("FastAPI")[0].summary == ""
    )  # found by its title: nothing to explain


def test_an_alias_is_found_in_a_property_too_and_the_first_name_ranks_above_an_alias():
    adapter, _ = _adapter()

    hits = adapter.search("Kubernetes", aliases=["Grafana"])

    assert [h.title for h in hits] == ["Kubernetes", "모니터링"]
    assert hits[0].score > hits[1].score


def test_a_word_only_the_body_has_is_still_not_found():
    adapter, _ = _adapter()
    assert adapter.search("Pydantic") == []  # headings inside a note are the body: a later step


def test_blank_names_are_ignored_and_an_untitled_page_can_still_be_found_by_a_property():
    pages = [_page("u1", "", 유형=("select", "Redis"))]
    adapter, _ = _adapter(pages)

    assert adapter.search("", aliases=["  "]) == []
    (hit,) = adapter.search("Redis")
    assert hit.summary == "유형: Redis"


def test_match_is_a_plain_function_of_the_listed_pages():
    listed = [
        {"id": "a", "title": "JWT", "url": "u1", "edited": "2026-01-01", "props": {}},
        {"id": "b", "title": "인증", "url": "u2", "edited": "2026-01-02", "props": {"유형": ["JWT 토큰"]}},
    ]
    assert [(h.title, h.score) for h in match(listed, ["JWT"], 5)] == [("JWT", 100), ("인증", 30)]
    assert match(listed, ["JWT"], 1)[0].title == "JWT"


# --------------------------------------------------------------------------- the list of pages


def test_a_list_longer_than_a_hundred_pages_is_read_to_its_end():
    pages = [_page(f"x{i}", f"노트 {i}") for i in range(250)] + [_page("last", "마지막", 유형=("select", "Zebra"))]
    adapter, fake = _adapter(pages)

    (hit,) = adapter.search("Zebra")

    assert hit.title == "마지막" and fake.asked == 3  # 251 pages: three requests


def test_the_list_is_fetched_once_for_all_the_names_of_one_search_and_for_later_searches_in_the_same_run():
    adapter, fake = _adapter()

    adapter.search("Kubernetes", aliases=["FastAPI", "Grafana"])
    adapter.search("Kubernetes")

    assert fake.asked == 1


# --------------------------------------------------------------------------- the file that keeps it for a while


def test_a_new_run_within_the_time_limit_uses_the_kept_list_and_a_later_one_asks_again(tmp_path, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr("lanternspec.learn.knowledge.notion.time.time", lambda: clock[0])
    first, fake = _adapter(state=tmp_path)
    first.search("Kubernetes")
    assert fake.asked == 1 and (tmp_path / "knowledge-notion.json").exists()

    clock[0] += CACHE_SECONDS - 1
    second, fake2 = _adapter(state=tmp_path)
    assert [h.title for h in second.search("Kubernetes")] == ["Kubernetes"] and fake2.asked == 0

    clock[0] += 2
    third, fake3 = _adapter(state=tmp_path)
    third.search("Kubernetes")
    assert fake3.asked == 1


def test_a_search_with_no_result_asks_once_more_in_case_the_kept_list_is_old(tmp_path, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr("lanternspec.learn.knowledge.notion.time.time", lambda: clock[0])
    old, _ = _adapter([_page("p3", "Kubernetes")], state=tmp_path)
    old.search("Kubernetes")  # the list kept now has one page

    clock[0] = 1100.0  # a note was added since
    fresh, fake = _adapter(WORKSPACE, state=tmp_path)
    hits = fresh.search("Grafana")
    assert [h.title for h in hits] == ["모니터링"] and fake.asked == 1  # found after the one extra look

    clock[0] = 1200.0
    later, fake2 = _adapter(WORKSPACE, state=tmp_path)
    assert later.search("Pydantic") == [] and fake2.asked == 1  # nothing anywhere: one extra look, not a loop


def test_a_list_fetched_a_moment_ago_is_not_fetched_again_for_each_search_that_finds_nothing(tmp_path, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr("lanternspec.learn.knowledge.notion.time.time", lambda: clock[0])
    adapter, fake = _adapter(state=tmp_path)
    adapter.search("Kubernetes")

    clock[0] += 10  # several terms in a row that have no note: only the first may be worth another look
    other, fake2 = _adapter(state=tmp_path)
    assert other.search("Pydantic") == [] and other.search("Starlette") == [] and fake2.asked == 0


def test_a_search_that_just_fetched_the_list_does_not_fetch_it_again_for_no_result():
    adapter, fake = _adapter()
    assert adapter.search("Pydantic") == [] and fake.asked == 1


def test_a_broken_or_unwritable_kept_list_never_stops_a_search(tmp_path):
    (tmp_path / "knowledge-notion.json").write_text("{broken", encoding="utf-8")
    adapter, _ = _adapter(state=tmp_path)
    assert [h.title for h in adapter.search("Kubernetes")] == ["Kubernetes"]

    blocked = tmp_path / "blocked"
    blocked.write_text("a file where a folder should be", encoding="utf-8")
    adapter, _ = _adapter(state=blocked / "inside")
    assert [h.title for h in adapter.search("Kubernetes")] == ["Kubernetes"]


def test_a_failed_request_is_an_error_not_an_empty_answer(tmp_path):
    def broken(req: Any) -> Any:
        raise urllib.error.HTTPError(req.full_url, 500, "boom", {}, None)  # type: ignore[arg-type]

    import pytest

    from lanternspec.learn.knowledge import KnowledgeError

    with pytest.raises(KnowledgeError, match="500"):
        NotionAdapter("parent", "secret", opener=broken, state_dir=tmp_path).search("x")


# --------------------------------------------------------------------------- where it is kept


def test_the_kept_list_goes_in_the_project_state_folder_and_git_never_gets_it(repo, monkeypatch):
    from lanternspec.core import profile as pm

    init_project(repo)
    data = pm.load(repo.root).data
    data["knowledge"] = {"type": "notion", "path": "abc", "token_env": "NOTION_TEST_TOKEN", "write": "direct"}
    pm.save(repo.root, data)
    monkeypatch.setenv("NOTION_TEST_TOKEN", "secret")
    project = Project.load(repo.root)

    adapter = adapter_for(project)

    assert "knowledge-notion.json" in IGNORED
    assert adapter.state_dir == project.state  # type: ignore[attr-defined]
    assert "knowledge-notion.json" in (project.state / ".gitignore").read_text(encoding="utf-8").splitlines()
