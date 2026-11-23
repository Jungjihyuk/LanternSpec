"""A report's Markdown tables drawn as aligned columns on a terminal, and left as Markdown everywhere else."""

import io
import json

from conftest import init_project
from lanternspec.cli import table
from lanternspec.core.project import Project

MARKDOWN = """실행 기록: 대화 턴 3개

**스킬별 비용**

| 스킬 | 턴 | 평균 토큰 |
|---|---|---|
| (스킬 없음) | 3 | 28740 |
| find-skills | 12 | — |

_MCP 도구 호출만 셉니다._"""


class _Tty(io.StringIO):
    def isatty(self) -> bool:
        return True


def test_a_table_is_drawn_with_each_column_as_wide_as_its_widest_cell_and_numbers_on_the_right():
    lines = table.render(MARKDOWN).splitlines()

    assert lines[4:8] == [
        "스킬        │ 턴 │ 평균 토큰",
        "────────────┼────┼──────────",
        "(스킬 없음) │  3 │     28740",
        "find-skills │ 12 │         —",
    ]


def test_the_marks_around_a_title_and_a_note_are_dropped():
    out = table.render(MARKDOWN)

    assert "스킬별 비용" in out and "**" not in out
    assert "MCP 도구 호출만 셉니다." in out and "_MCP" not in out and not out.rstrip().endswith("_")
    assert "실행 기록: 대화 턴 3개" in out  # other lines stay as they are


def test_text_without_a_table_is_unchanged_and_a_pipe_inside_prose_is_not_a_table():
    plain = "한 줄\n\n그냥 문장 | 가운데 막대\n"
    assert table.render(plain) == plain


def test_wide_letters_count_two_columns_and_combining_marks_none():
    assert table.cells("abc") == 3
    assert table.cells("한글") == 4
    assert table.cells("é") == 1  # e + a combining accent


def test_only_a_terminal_gets_the_drawn_table():
    assert "│" in table.for_terminal(MARKDOWN, _Tty())
    assert table.for_terminal(MARKDOWN, io.StringIO()) == MARKDOWN  # a pipe or a file keeps the Markdown


def test_lantern_eval_prints_markdown_when_it_is_not_a_terminal(repo):
    init_project(repo)
    project = Project.load(repo.root)
    project.state.mkdir(parents=True, exist_ok=True)
    records = [{"kind": "turn", "session": "s1", "start": "2026-11-23T10:00:00", "end": "2026-11-23T10:01:00", "tools": {"Read": 1}}]
    (project.state / "runs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")

    _, out = repo("eval")

    assert "|---|" in out and "│" not in out
