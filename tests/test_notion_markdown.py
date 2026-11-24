"""A note's Markdown as Notion's own blocks — and the same note untouched in Obsidian."""

import json
from typing import Any

import pytest

from lanternspec.learn.knowledge.notion_markdown import ALIASES, CALLOUTS, LANGUAGES, markdown_to_blocks, requests, rich_text, without_title


def _look(obj: dict[str, Any]) -> Any:
    """A text object as (text, looks…), to read tests at a glance."""
    if obj["type"] == "equation":
        return (obj["equation"]["expression"], "formula")
    marks = [k if v is True else v for k, v in (obj.get("annotations") or {}).items()]
    link = obj["text"].get("link")
    return (obj["text"]["content"], *marks, *([link["url"]] if link else []))


def _line(md: str) -> list[Any]:
    return [x[0] if len(x) == 1 else x for x in map(_look, rich_text(md))]


def _tree(blocks: list[dict[str, Any]]) -> list[Any]:
    """Blocks as [kind, text, children]."""
    out = []
    for b in blocks:
        body = b[b["type"]]
        text = "".join(_look(t)[0] for t in body.get("rich_text") or [])
        children = _tree(body.get("children") or [])
        out.append([b["type"], text, children] if children else [b["type"], text])
    return out


SERDE = """# Serde

> [!abstract] 한 줄 요약
> Rust 데이터 구조를 변환하는 프레임워크다.

## 왜 쓰나
- **포맷 독립성**: `serde`가 공통 인터페이스를 제공한다.
- **제로 카피 역직렬화(Zero-copy)**: 입력 버퍼를 빌려(`&'a str`) 쓴다.

## 어떻게 동작하나
```rust
#[derive(Deserialize)]
struct LogEntry {
    level: LogLevel,
}
```
1. `#[derive(Deserialize)]`를 붙이면 코드를 만든다.
2. `serde_json::from_str::<LogEntry>(line)`을 호출한다.
"""


def test_a_learning_note_comes_out_in_notions_own_forms():
    blocks = markdown_to_blocks(SERDE)

    assert [b["type"] for b in blocks] == [
        "heading_1", "callout", "heading_2", "bulleted_list_item", "bulleted_list_item",
        "heading_2", "code", "numbered_list_item", "numbered_list_item",
    ]  # fmt: skip
    callout = blocks[1]["callout"]
    assert callout["icon"]["emoji"] == "📋" and _look(callout["rich_text"][0]) == ("한 줄 요약", "bold")
    assert _tree(callout["children"]) == [["paragraph", "Rust 데이터 구조를 변환하는 프레임워크다."]]
    assert [_look(t) for t in blocks[3]["bulleted_list_item"]["rich_text"]][:3] == [("포맷 독립성", "bold"), (": ",), ("serde", "code")]
    assert blocks[6]["code"]["language"] == "rust" and "\n    level: LogLevel,\n" in blocks[6]["code"]["rich_text"][0]["text"]["content"]
    sent = json.dumps(blocks, ensure_ascii=False)
    assert "**" not in sent and "`" not in sent and "[!" not in sent  # no Markdown mark is left as text


# --------------------------------------------------------------------------- inside a line


@pytest.mark.parametrize(
    ("md", "expected"),
    [
        ("**Ser**ialization", [("Ser", "bold"), "ialization"]),
        ("**역직렬화(Zero-copy)**는", [("역직렬화(Zero-copy)", "bold"), "는"]),  # strict Markdown would not see this one end
        ("*기울임* _기울임_ ***둘 다***", [("기울임", "italic"), " ", ("기울임", "italic"), " ", ("둘 다", "bold", "italic")]),
        ("**굵은 *안쪽* 글**", [("굵은 ", "bold"), ("안쪽", "bold", "italic"), (" 글", "bold")]),
        ("**`코드`와 글**", [("코드", "bold", "code"), ("와 글", "bold")]),
        ("~~취소~~ ==강조==", [("취소", "strikethrough"), " ", ("강조", "yellow_background")]),
        ("`**그대로**` ``a`b``", [("**그대로**", "code"), " ", ("a`b", "code")]),
        ("snake_case_name · 2 * 3 * 4 · a == b == c", ["snake_case_name · 2 * 3 * 4 · a == b == c"]),
        ("*.py 와 *.rs", ["*.py 와 *.rs"]),
        (r"\*별표\* 그대로", ["*별표* 그대로"]),
        ("`안 닫힘 **이것도", ["`안 닫힘 **이것도"]),
        ("[글](https://a.b/c_(d))", [("글", "https://a.b/c_(d)")]),
        ("[**굵은** 링크](https://a.b)", [("굵은", "bold", "https://a.b"), (" 링크", "https://a.b")]),
        ("[`코드`](https://a.b)", [("코드", "code", "https://a.b")]),
        ("[밖](https://a.b/x_y_z) [안](../노트.md)", [("밖", "https://a.b/x_y_z"), " 안"]),  # a place inside the vault: text
        ("https://a.b/c.를 보라", [("https://a.b/c", "https://a.b/c"), ".를 보라"]),
        ("(https://a.b/c) <https://d.e>", ["(", ("https://a.b/c", "https://a.b/c"), ") ", ("https://d.e", "https://d.e")]),
        ("**https://a.b**", [("https://a.b", "bold", "https://a.b")]),
        ("[[JWT]] [[폴더/JWT|토큰]] [[JWT#서명]] ![[그림.png]]", ["JWT 토큰 JWT › 서명 그림.png"]),
        ("$E=mc^2$ 값은 $5 와 $6", [("E=mc^2", "formula"), " 값은 $5 와 $6"]),
        ("보임 %%숨김%%끝<!-- 숨김 -->", ["보임 끝"]),
        ("첫 줄<br>둘째", ["첫 줄\n둘째"]),
        ("", []),
    ],
)
def test_marks_inside_a_line(md, expected):
    assert _line(md) == expected


def test_a_line_full_of_marks_is_read_to_its_end():
    assert len(rich_text("**a** b " * 40)) == 80
    assert "".join(t["text"]["content"] for t in rich_text("**a** " * 3000)).count("a") == 3000


def test_something_that_only_looks_like_an_address_is_text():
    assert _line("http://[a 와 [글](http://[b)") == ["http://[a 와 글"]


def test_text_past_the_limits_is_kept():
    long = "가" * 4500
    assert "".join(t["text"]["content"] for t in rich_text(long)) == long
    assert all(len(t["text"]["content"].encode("utf-16-le")) // 2 <= 2000 for t in rich_text("😀" * 3000))  # an emoji counts as two
    many = " ".join(f"`c{i}`" for i in range(200))
    made = rich_text(many)
    assert len(made) <= 100 and "".join(t["text"]["content"] for t in made) == many.replace("`", "")


# --------------------------------------------------------------------------- blocks


def test_lists_keep_their_nesting_checks_and_what_is_under_an_item():
    md = "- 하나\n  - 둘\n    - 셋\n- [ ] 할 일\n- [x] 끝남\n\n1. 첫째\n   ```sh\n   ls\n   ```\n2. 둘째\n   이어지는 줄\n"
    assert _tree(markdown_to_blocks(md)) == [
        ["bulleted_list_item", "하나", [["bulleted_list_item", "둘", [["bulleted_list_item", "셋"]]]]],
        ["to_do", "할 일"],
        ["to_do", "끝남"],
        ["numbered_list_item", "첫째", [["code", "ls"]]],
        ["numbered_list_item", "둘째\n이어지는 줄"],
    ]
    assert [b["to_do"]["checked"] for b in markdown_to_blocks(md) if b["type"] == "to_do"] == [False, True]


def test_a_shallow_indent_under_a_number_is_still_under_it():
    assert _tree(markdown_to_blocks("1. 첫째\n  - 안쪽\n2. 둘째")) == [
        ["numbered_list_item", "첫째", [["bulleted_list_item", "안쪽"]]],
        ["numbered_list_item", "둘째"],
    ]


def test_a_number_notion_would_count_from_one_again_stays_as_text():
    assert _tree(markdown_to_blocks("1. 첫째\n\n```\n코드\n```\n2. 둘째\n3. 셋째")) == [
        ["numbered_list_item", "첫째"],
        ["code", "코드"],
        ["paragraph", "2. 둘째"],
        ["paragraph", "3. 셋째"],
    ]
    assert _tree(markdown_to_blocks("그해는\n2024. 봄이다")) == [["paragraph", "그해는\n2024. 봄이다"]]


def test_a_list_goes_on_over_blank_lines():
    assert [b["type"] for b in markdown_to_blocks("1. 하나\n\n2. 둘\n\n   이어짐\n\n3. 셋")] == ["numbered_list_item"] * 3


def test_lines_of_a_paragraph_stay_in_one_block_and_a_blank_line_starts_another():
    assert _tree(markdown_to_blocks("첫 줄\n둘째 줄\n\n다음 문단")) == [["paragraph", "첫 줄\n둘째 줄"], ["paragraph", "다음 문단"]]


def test_quotes_and_callouts_hold_what_is_in_them():
    assert _tree(markdown_to_blocks("> 인용\n> 둘째 줄\n>\n> - 목록\n\n> 다른 인용")) == [
        ["quote", "인용\n둘째 줄", [["bulleted_list_item", "목록"]]],
        ["quote", "다른 인용"],
    ]
    warning, plain, unknown = markdown_to_blocks(
        "> [!warning]- 주의 **꼭**\n> ```py\n> x\n> ```\n\n> [!note]\n> 제목 없음\n\n> [!처음] 보는 것".replace("처음", "my-kind")
    )
    assert warning["callout"]["icon"]["emoji"] == "⚠️" and warning["callout"]["children"][0]["code"]["language"] == "python"
    assert _tree([plain]) == [["callout", "제목 없음"]]  # no title: the text itself, and not the word "note"
    assert unknown["callout"]["icon"]["emoji"] == "📌"
    assert all(len(look) == 2 for look in CALLOUTS.values())


@pytest.mark.parametrize(
    ("info", "language"),
    [("rs", "rust"), ("rust,ignore", "rust"), ("toml", "toml"), ("TypeScript", "typescript"), ("py title='a'", "python"),
     ("{.python}", "python"), ("", "plain text"), ("없는언어", "plain text"), ("mermaid", "mermaid")],
)  # fmt: skip
def test_code_says_its_language_only_when_notion_knows_it(info, language):
    assert markdown_to_blocks(f"```{info}\nx\n```")[0]["code"]["language"] == language
    assert set(ALIASES.values()) <= LANGUAGES | {"plain text"}


def test_code_is_kept_as_written_even_when_never_closed():
    md = "~~~\n# 제목 아님\n\n```\n- 목록 아님\n~~~\n뒤"
    assert _tree(markdown_to_blocks(md)) == [["code", "# 제목 아님\n\n```\n- 목록 아님"], ["paragraph", "뒤"]]
    assert _tree(markdown_to_blocks("```\n안 닫힘")) == [["code", "안 닫힘"]]
    long = "\n".join("x" * 99 for _ in range(1200))
    blocks = markdown_to_blocks(f"```\n{long}\n```")
    assert len(blocks) > 1 and "".join(t["text"]["content"] for b in blocks for t in b["code"]["rich_text"]) == long


def test_tables():
    (table,) = markdown_to_blocks("| 이름 | 값 |\n|---|:-:|\n| **a** | `x \\| y` |\n| b |")
    rows = table["table"]["children"]
    assert table["table"]["table_width"] == 2 and table["table"]["has_column_header"]
    assert [[[_look(t) for t in c] for c in r["table_row"]["cells"]] for r in rows] == [
        [[("이름",)], [("값",)]],
        [[("a", "bold")], [("x | y", "code")]],
        [[("b",)], []],
    ]
    assert _tree(markdown_to_blocks("A | B 중에서 고른다\n그냥 글")) == [["paragraph", "A | B 중에서 고른다\n그냥 글"]]
    long = markdown_to_blocks("| a |\n|---|\n" + "| 1 |\n" * 150)
    assert [len(t["table"]["children"]) for t in long] == [100, 52]  # each with the header


def test_the_rest_of_the_blocks():
    md = "#### 작은 제목 #\n\n---\n\n$$\na^2\n$$\n\n$$b$$\n\n%%\n숨김\n%%\n<!-- 숨김 -->\n![그림](https://a.b/c.png)\n\n제목\n===\n"
    blocks = markdown_to_blocks(md)
    assert [b["type"] for b in blocks] == ["heading_4", "divider", "equation", "equation", "image", "heading_1"]
    assert blocks[2]["equation"]["expression"] == "a^2"
    assert _tree(markdown_to_blocks("# C#\n###### 여섯"))[0] == ["heading_1", "C#"]
    assert markdown_to_blocks("![그림](그림.png)")[0]["type"] == "paragraph"  # a file of the vault has no place in Notion
    assert markdown_to_blocks("") == []


def _depth(b: dict[str, Any]) -> int:
    return max((1 + _depth(c) for c in b[b["type"]].get("children") or []), default=0)


def test_what_one_request_does_not_take_is_moved_out_and_never_dropped():
    deep = "\n".join("  " * i + f"- 단계{i}" for i in range(6))
    blocks = markdown_to_blocks(deep)
    assert max(map(_depth, blocks)) <= 2 and all(f"단계{i}" in json.dumps(blocks, ensure_ascii=False) for i in range(6))

    table = "- a\n  - b\n    - c\n\n      | 칸 |\n      |---|\n      | 값 |\n"
    blocks = markdown_to_blocks(table)
    assert max(map(_depth, blocks)) <= 2 and "값" in json.dumps(blocks, ensure_ascii=False)

    many = markdown_to_blocks("- 위\n" + "".join(f"  - {i}\n" for i in range(130)))
    assert len(many[0]["bulleted_list_item"]["children"]) == 100 and len(many) == 31

    groups = requests(markdown_to_blocks("".join(f"- {i}\n" + "  - x\n" * 30 for i in range(80))))
    assert all(len(g) <= 100 and sum(1 + len(b["bulleted_list_item"]["children"]) for b in g) <= 1000 for g in groups)
    assert sum(len(g) for g in groups) == 80 and requests([]) == [[]]


def test_a_first_heading_that_repeats_the_title_is_left_out():
    assert _tree(without_title(markdown_to_blocks("# Serde\n본문"), "serde ")) == [["paragraph", "본문"]]
    assert len(without_title(markdown_to_blocks("# 다른 제목\n본문"), "Serde")) == 2
    assert without_title([], "Serde") == []


# --------------------------------------------------------------------------- each store its own way


def test_obsidian_keeps_the_note_exactly_as_written(tmp_path):
    from lanternspec.learn.knowledge.obsidian import ObsidianAdapter

    ObsidianAdapter(tmp_path).write("Serde.md", SERDE)
    assert (tmp_path / "Serde.md").read_text(encoding="utf-8") == SERDE
