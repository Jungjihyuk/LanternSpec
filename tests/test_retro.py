"""The AI retro: rows written by code when a loop ends, judged through a command that knows the lists, confirmed by a person."""

import re

import pytest

from conftest import docs
from lanternspec.core.enums import load
from lanternspec.core.names import load as load_names
from lanternspec.core.project import Project, today
from lanternspec.report import retro
from lanternspec.work import loop
from loop_support import commit as _commit
from loop_support import implement as _implement
from loop_support import lines as _lines


def _file(repo):
    return docs(repo) / "4. 운영 기록" / "AI 회고" / f"{today()[:7]}.md"


def _rows(repo):
    return retro.parse(_file(repo).read_text(encoding="utf-8"), load_names("ko"))


def _run_id(work_project):
    return loop.last_start(work_project, "W-001")["run"]


def _loop_with_one_slow_criterion(repo):
    """AC-1 fails twice and then passes, AC-2 passes at once: the loop ends passed."""
    repo("loop", "start", "W-001")
    repo("loop", "attempt", "W-001", "AC-1", ok=False)
    repo("loop", "attempt", "W-001", "AC-1", ok=False)
    _implement(repo, "login")
    _implement(repo, "logout")
    repo("loop", "attempt", "W-001", "AC-1")
    repo("loop", "attempt", "W-001", "AC-2")
    repo("loop", "finish", "W-001")


# --------------------------------------------------------------------------- when a row is made


def test_a_criterion_that_passed_on_its_first_try_leaves_no_row(repo, work):
    repo("loop", "start", "W-001")
    _implement(repo, "login")
    _implement(repo, "logout")
    repo("loop", "attempt", "W-001", "AC-1")
    repo("loop", "attempt", "W-001", "AC-2")
    repo("loop", "finish", "W-001")
    assert not _file(repo).exists()
    _, out = repo("retro", "add", "W-001")
    assert "더할 줄이 없습니다" in out


def test_a_criterion_that_passed_on_the_third_try_leaves_one_row(repo, work):
    _loop_with_one_slow_criterion(repo)
    (row,) = _rows(repo)
    assert (row.work, row.key, row.tries, row.result, row.run) == ("W-001", "AC-1", 3, "통과", _run_id(work))
    assert row.date == today() and not row.judged and not row.confirmed
    assert "[시도:: 3] [결과:: 통과]" in _file(repo).read_text(encoding="utf-8")


def test_a_criterion_the_loop_gave_up_on_leaves_a_stopped_row(repo, work):
    repo("loop", "start", "W-001")
    for _ in range(3):
        repo("loop", "attempt", "W-001", "AC-1", ok=False)
    (row,) = _rows(repo)  # written at once: the loop stopped, there is no later round
    assert (row.key, row.tries, row.result) == ("AC-1", 3, "중단")


def test_a_failed_whole_suite_leaves_a_check_row(repo, work):
    (repo.root / "tests" / "test_broken.py").write_text("# a test that fails until src/broken.txt exists", encoding="utf-8")
    _commit(repo, "a failing test outside the criteria")
    repo("loop", "start", "W-001")
    _implement(repo, "login")
    _implement(repo, "logout")
    repo("loop", "attempt", "W-001", "AC-1")
    repo("loop", "attempt", "W-001", "AC-2")
    repo("loop", "finish", "W-001", ok=False)
    assert not _file(repo).exists()  # the loop is not over: another round may follow
    _implement(repo, "broken")
    repo("loop", "finish", "W-001")
    (row,) = _rows(repo)
    assert (row.is_check, row.key, row.tries, row.result) == (True, "전체 테스트", 2, "통과")  # one failed round, then the pass
    assert "[검증:: 전체 테스트] [시도:: 2] [결과:: 통과]" in _file(repo).read_text(encoding="utf-8")


def test_an_invalid_pass_leaves_a_stopped_check_row(repo, work):
    repo("loop", "start", "W-001")
    _implement(repo, "login")
    _implement(repo, "logout")
    repo("loop", "attempt", "W-001", "AC-1")
    repo("loop", "attempt", "W-001", "AC-2")
    (repo.root / "tests" / "test_login.py").write_text("# weakened", encoding="utf-8")
    repo("loop", "finish", "W-001", ok=False)
    (row,) = _rows(repo)
    assert (row.key, row.result) == ("통과 무효", "중단")


def test_without_a_one_test_command_there_is_no_row_per_criterion(repo, work):
    repo("profile", "set", "build.test_one=")
    repo("loop", "start", "W-001")
    repo("loop", "attempt", "W-001", "AC-1", ok=False)  # the whole suite stands in: this says nothing about AC-1
    _implement(repo, "login")
    _implement(repo, "logout")
    repo("loop", "attempt", "W-001", "AC-1")
    repo("loop", "finish", "W-001")
    assert not _file(repo).exists()


def test_a_loop_that_has_not_ended_leaves_nothing_and_a_second_add_adds_nothing(repo, work):
    repo("loop", "start", "W-001")
    repo("loop", "attempt", "W-001", "AC-1", ok=False)
    _, out = repo("retro", "add", "W-001")
    assert "더할 줄이 없습니다" in out and not _file(repo).exists()
    _implement(repo, "login")
    _implement(repo, "logout")
    repo("loop", "attempt", "W-001", "AC-1")
    repo("loop", "attempt", "W-001", "AC-2")
    repo("loop", "finish", "W-001")
    _, out = repo("retro", "add", "W-001")  # finish already added the row
    assert "더할 줄이 없습니다" in out and len(_rows(repo)) == 1


@pytest.mark.parametrize("error", [OSError("disk full"), TypeError("a template went wrong"), KeyError("run")])
def test_a_retro_that_cannot_be_written_never_stops_the_loop(repo, work, monkeypatch, capsys, error):
    def broken(project, work_id):
        raise error

    monkeypatch.setattr(retro, "record", broken)
    repo("loop", "start", "W-001")
    _implement(repo, "login")
    _implement(repo, "logout")
    repo("loop", "attempt", "W-001", "AC-1")
    repo("loop", "attempt", "W-001", "AC-2")
    _, out = repo("loop", "finish", "W-001")
    assert "✔" in out and "AI 회고를 쓰지 못했습니다" in out  # one line says so, and the round is written
    assert _lines(work, "loop")[-1]["result"] == "passed"


def test_the_rows_of_a_run_are_worked_out_from_its_lines_alone():
    enums = load()
    at = "2026-11-20T09:31:00+09:00"
    tries = [{"kind": "attempt", "ac": "AC-1", "result": r, "scope": "one", "at": at} for r in ("fail", "fail", "pass")]
    start = {"kind": "loop", "event": "start", "work": "W-001", "run": "r1"}
    ended = {"kind": "loop", "event": "end", "result": "passed", "at": "2026-11-20T10:00:00+09:00"}
    (row,) = retro.rows_from_run([start, *tries, ended], enums)
    assert (row.date, row.time, row.tries, row.run) == ("2026-11-20", "09:31", 3, "r1")
    assert retro.rows_from_run([start, *tries], enums) == []  # still going
    kept_then_lost = [{**t, "result": r} for t, r in zip(tries, ("pass", "fail", "fail"), strict=True)]
    (row,) = retro.rows_from_run([start, *kept_then_lost, {"kind": "attempt", "ac": "AC-1", "result": "limit", "at": at}], enums)
    assert (row.tries, row.result) == (3, "중단")  # passed at once, but did not stay passed and the loop gave up


def _synthetic_run(repo, work_id, at, results=("fail", "pass")):
    """Write the run-log lines of a finished loop at a given time, so the retro can be made for any day."""
    from lanternspec.tools import runlog

    project = Project.load(repo.root)
    runlog.append(project, {"kind": "loop", "event": "start", "work": work_id, "run": f"r-{work_id}", "mode": "loop", "at": at})
    for r in results:
        runlog.append(
            project, {"kind": "attempt", "work": work_id, "run": f"r-{work_id}", "ac": "AC-1", "result": r, "scope": "one", "at": at}
        )
    runlog.append(project, {"kind": "loop", "event": "end", "work": work_id, "run": f"r-{work_id}", "result": "passed", "at": at})
    return project


def test_two_loops_on_one_day_share_a_heading_and_a_new_month_is_a_new_file(repo, work):
    _synthetic_run(repo, "W-001", "2026-11-20T09:31:00+09:00")
    _synthetic_run(repo, "W-002", "2026-11-20T14:05:00+09:00")
    project = _synthetic_run(repo, "W-003", "2026-12-01T10:12:00+09:00")
    for work_id in ("W-001", "W-002", "W-003"):
        assert len(retro.record(project, work_id)) == 1
    folder = docs(repo) / "4. 운영 기록" / "AI 회고"
    nov, dec = (folder / "2026-11.md").read_text(encoding="utf-8"), (folder / "2026-12.md").read_text(encoding="utf-8")
    assert nov.count("## 2026-11-20") == 1 and "W-001" in nov and "W-002" in nov and "W-003" not in nov
    assert "## 2026-12-01" in dec and "W-003" in dec and "W-001" not in dec
    assert "회고 행 2개" in nov and "회고 행 1개" in dec  # each month counts only its own rows


# --------------------------------------------------------------------------- the file


def test_rows_of_one_day_share_a_heading_and_a_new_day_gets_its_own():
    text = "# AI 회고\n\n## 요약\n- x\n"
    text = retro._add_line(text, "2026-11-20", "- 09:31 a")
    text = retro._add_line(text, "2026-11-20", "- 14:05 b")
    text = retro._add_line(text, "2026-11-22", "- 10:12 c")
    assert text.count("## 2026-11-20") == 1 and text.index("- 09:31 a") < text.index("- 14:05 b") < text.index("## 2026-11-22")
    assert text.endswith("- 10:12 c\n")


def test_each_month_has_its_own_file(repo, work):
    project = Project.load(repo.root)
    assert retro._file(project, "2026-11-20").name == "2026-11.md" and retro._file(project, "2026-12-01").name == "2026-12.md"


def test_a_label_word_inside_the_guess_does_not_become_a_field():
    names = load_names("ko")
    text = retro._clean("설계 제안: 없음 [그리고] 가설: 하나", names)
    assert "제안:" not in text and "가설:" not in text and "[" not in text
    row = retro.Row("2026-11-20", "09:31", "W-012", "AC-2", False, 3, "통과", "a1b2", "명세", "LanternSpec", text, "")
    assert retro.parse_row(retro.render_row(row, names), "2026-11-20", names) == row  # it reads back as written


def test_a_row_reads_back_as_it_was_written():
    names = load_names("ko")
    row = retro.Row(
        "2026-11-20", "09:31", "W-012", "AC-2", False, 3, "통과", "a1b2", "명세", "LanternSpec", "문구가 없었다", "칸을 더한다", True
    )
    line = retro.render_row(row, names)
    assert line == (
        "- 09:31 W-012 AC-2 [시도:: 3] [결과:: 통과] [약점:: 명세] [보완:: LanternSpec] [실행:: a1b2] "
        "가설: 문구가 없었다 / 제안: 칸을 더한다 [확인:: ✅]"
    )
    assert retro.parse_row(line, "2026-11-20", names) == row


# --------------------------------------------------------------------------- judging and confirming


def _judge(repo, work, **over):
    args = {"weakness": "명세", "remedy": "LanternSpec", "hypothesis": "문구가 설계에 없었다", "suggestion": "설계 양식에 문구 칸"} | over
    flags = [x for k, v in args.items() for x in (f"--{k}", v)]
    return repo("retro", "judge", _run_id(work), "AC-1", *flags, ok=False)


def test_the_judgment_takes_only_the_values_of_the_lists(repo, work):
    _loop_with_one_slow_criterion(repo)
    code, out = _judge(repo, work, weakness="너무 어려움")
    assert code == 1 and "목록에 없습니다" in out and "명세" in out  # it names what is allowed
    code, out = _judge(repo, work, remedy="")
    assert code == 1 and "필요합니다" in out
    assert not _rows(repo)[0].judged  # nothing was written


def test_a_judged_row_carries_the_judgment_and_the_summary_counts_it(repo, work):
    _loop_with_one_slow_criterion(repo)
    code, out = _judge(repo, work, hypothesis="문구가 [AC에만] 있었다 / 설계엔 없었다")
    assert code == 0
    (row,) = _rows(repo)
    assert (row.weakness, row.remedy, row.judged) == ("명세", "LanternSpec", True)
    assert "[" not in row.hypothesis and " / " not in row.hypothesis  # nothing in the guess can read as a field
    text = _file(repo).read_text(encoding="utf-8")
    assert "- 회고 행 1개 · 확인 0개 · 미확인 1개" in text and "- 약점: 명세 1" in text and "- 보완: LanternSpec 1" in text


def test_a_row_is_confirmed_by_a_person_after_it_is_judged(repo, work):
    _loop_with_one_slow_criterion(repo)
    run = _run_id(work)
    code, out = repo("retro", "confirm", run, "AC-1", ok=False)
    assert code == 1 and "먼저 판단" in out
    _judge(repo, work)
    _, out = repo("retro", "review")
    assert "1개" in out and run in out
    repo("retro", "confirm", run, "AC-1")
    assert "[확인:: ✅]" in _file(repo).read_text(encoding="utf-8") and "확인 1개 · 미확인 0개" in _file(repo).read_text(encoding="utf-8")
    _, out = repo("retro", "review")
    assert "확인할 줄이 없습니다" in out


def test_a_confirmation_typed_by_hand_counts_at_the_next_review(repo, work):
    _loop_with_one_slow_criterion(repo)
    _judge(repo, work)
    path = _file(repo)
    path.write_text(re.sub(r"(AC-1 .*)", r"\1 [확인:: ✅]", path.read_text(encoding="utf-8")), encoding="utf-8")
    assert "미확인 1개" in path.read_text(encoding="utf-8")  # the summary is stale until something rewrites it
    _, out = repo("retro", "review")
    assert "확인할 줄이 없습니다" in out and "확인 1개 · 미확인 0개" in path.read_text(encoding="utf-8")


def test_judging_again_asks_for_a_new_confirmation(repo, work):
    _loop_with_one_slow_criterion(repo)
    _judge(repo, work)
    repo("retro", "confirm", _run_id(work), "AC-1")
    _judge(repo, work, weakness="컨텍스트")
    assert not _rows(repo)[0].confirmed


def test_a_check_row_is_found_by_its_role_too(repo, work):
    (repo.root / "tests" / "test_broken.py").write_text("# fails until src/broken.txt exists", encoding="utf-8")
    _commit(repo, "broken")
    repo("loop", "start", "W-001")
    _implement(repo, "login")
    _implement(repo, "logout")
    repo("loop", "attempt", "W-001", "AC-1")
    repo("loop", "attempt", "W-001", "AC-2")
    repo("loop", "finish", "W-001", ok=False)
    _implement(repo, "broken")
    repo("loop", "finish", "W-001")
    repo("retro", "judge", _run_id(work), "suite", "--weakness", "환경", "--remedy", "하네스 설정", "--hypothesis", "테스트 환경이 달랐다")
    assert _rows(repo)[0].weakness == "환경"


def test_add_lists_the_rows_to_judge_with_the_allowed_values(repo, work):
    repo("loop", "start", "W-001")
    for _ in range(3):
        repo("loop", "attempt", "W-001", "AC-1", ok=False)
    _, out = repo("retro", "add", "W-001")
    assert _run_id(work) in out and "AC-1" in out and "명세 | 컨텍스트" in out and "LanternSpec | 하네스 설정" in out


# --------------------------------------------------------------------------- the check


def test_check_catches_what_the_lists_and_names_do_not_know(repo, work):
    _loop_with_one_slow_criterion(repo)
    path = _file(repo)
    path.write_text(re.sub(r"(AC-1 .*)", r"\1 [약점:: 너무 어려움] [메모:: 하나]", path.read_text(encoding="utf-8")), encoding="utf-8")
    _, out = repo("check", str(path), ok=False)
    assert "'너무 어려움'은(는) 약점 목록에 없습니다" in out and "[메모:: 하나]" in out and "약점과 보완은 함께" in out


def test_a_clean_month_passes_the_check(repo, work):
    _loop_with_one_slow_criterion(repo)
    _judge(repo, work)
    repo("retro", "confirm", _run_id(work), "AC-1")
    _, out = repo("check", str(_file(repo)))
    assert "✖" not in out and "retro-" not in out


def test_a_summary_heading_a_person_removed_is_asked_about_and_does_not_break_the_retro(repo, work):
    _loop_with_one_slow_criterion(repo)
    path = _file(repo)
    path.write_text(path.read_text(encoding="utf-8").replace("## 요약", "## 한눈에"), encoding="utf-8")
    _, out = repo("check", str(path))
    assert "'요약' 칸이 없습니다" in out and "일부러 바꾸셨나요?" in out  # the check asks, as it does for every protected section
    _judge(repo, work)  # the rows still work; only the summary is left alone
    assert _rows(repo)[0].judged


@pytest.mark.parametrize("language", ["ko", "en"])
def test_both_languages_have_the_lists_and_the_names(language):
    enums, names = load(language=language), load_names(language)
    for name in ("retro_result", "retro_check", "retro_weakness", "retro_remedy"):
        assert enums.values(name)
    assert enums.value("retro_result", "passed") and enums.value("retro_check", "suite")
    assert {names.retro_attr(r) for r in names.table["retro_attrs"]} and names.folder("retro").endswith(names.doc("retro"))


def test_the_build_skill_tells_the_ai_to_judge_inside_the_lists_and_not_to_confirm():
    from lanternspec.core.profile import DEFAULTS, Profile, _deep_merge
    from lanternspec.tools import get
    from lanternspec.tools.skills import generate

    on = generate(Profile(data=_deep_merge(DEFAULTS, {"build": {"loop": "on", "test": "pytest"}})), [get("claude")])
    body = on[".claude/skills/l-build/SKILL.md"]
    assert "lantern retro add W-012" in body and "--weakness 명세 --remedy LanternSpec" in body
    assert "[실행:: 실행 ID]" in body and "[확인:: ✅]" in body and "네가 확인하지 않는다" in body
    off = generate(Profile(data=_deep_merge(DEFAULTS, {})), [get("claude")])
    body = off[".claude/skills/l-build/SKILL.md"]
    assert "lantern retro add" not in body and "lantern retro judge" not in body  # the loop's part
    assert "lantern retro note W-012-T03" in body and "부채 카드로 만들지 않는다" in body  # what it got stuck on: always


# --------------------------------------------------------------------------- what the AI got stuck on (no loop needed)


@pytest.fixture
def built(repo, work):
    """The work with one task."""
    repo("scaffold", "doc", "W-001", "할 일")
    repo("task", "add", "W-001", "로그인 버튼", "--size", "S")
    return work


def test_a_stuck_note_is_one_line_without_a_loop(repo, built):
    _, out = repo("retro", "note", "w-001-t01", "--stuck", "자동 커밋이 아니면 멈춘다", "--solved", "isolation_level=None")
    (row,) = _rows(repo)
    assert (row.work, row.task, row.stuck, row.solved) == ("W-001", "W-001-T01", "자동 커밋이 아니면 멈춘다", "isolation_level=None")
    assert row.run.startswith("n-") and not row.is_check and not row.judged and not row.confirmed
    line = retro.render_row(row, load_names("ko"))
    assert line in out and "[시도::" not in line and "[결과::" not in line  # nothing measured it
    assert "회고 행 1개" in _file(repo).read_text(encoding="utf-8")


def test_a_stuck_note_of_a_work_and_several_notes(repo, built):
    repo("retro", "note", "W-001", "--stuck", "하나")
    repo("retro", "note", "W-001", "--stuck", "둘")
    first, second = _rows(repo)
    assert (first.stuck, second.stuck, first.task, first.solved) == ("하나", "둘", "", "")
    assert first.run != second.run


def test_a_stuck_note_is_judged_and_confirmed_like_any_line(repo, built):
    repo("retro", "note", "W-001-T01", "--stuck", "막힘", "--solved", "풀이")
    (row,) = _rows(repo)
    repo("retro", "judge", row.run, "막힘", "--weakness", "환경", "--remedy", "연결 도구", "--hypothesis", "판이 달랐다")
    _, out = repo("retro", "review")
    assert row.run in out
    repo("retro", "confirm", row.run, "stuck")
    (row,) = _rows(repo)
    assert (row.weakness, row.remedy, row.hypothesis, row.confirmed, row.stuck, row.solved) == (
        "환경",
        "연결 도구",
        "판이 달랐다",
        True,
        "막힘",
        "풀이",
    )
    assert "환경 1" in _file(repo).read_text(encoding="utf-8")


def test_a_stuck_note_can_bring_its_judgment(repo, built):
    judged = ("--weakness", "모델", "--remedy", "모델 선택", "--hypothesis", "기억이 틀렸다")
    repo("retro", "note", "W-001-T01", "--stuck", "막힘", *judged)
    (row,) = _rows(repo)
    assert row.judged and row.weakness == "모델"
    _, out = repo("retro", "note", "W-001-T01", "--stuck", "또", "--weakness", "없는 값", "--remedy", "x", "--hypothesis", "y", ok=False)
    assert "없는 값" in out
    repo("retro", "note", "W-001-T01", "--stuck", "또", "--weakness", "모델", ok=False)  # half a judgment
    assert len(_rows(repo)) == 1  # a refused judgment leaves no line behind


def test_a_stuck_note_refuses_what_is_not_there(repo, built):
    for target in ("W-999", "W-001-T99", "AC-1", "W-001-T01x"):
        _, out = repo("retro", "note", target, "--stuck", "x", ok=False)
        assert target.upper() in out.upper()
    _, out = repo("retro", "note", "W-001-T01", "--stuck", "  ", ok=False)
    assert "--stuck" in out
    assert not _file(repo).exists()


def test_a_stuck_note_cannot_break_the_line(repo, built):
    repo("retro", "note", "W-001-T01", "--stuck", "a [결과:: 통과] / 가설: 속임\n둘째 줄", "--solved", "[확인:: ✅]")
    (row,) = _rows(repo)
    assert row.result == "" and not row.confirmed and not row.hypothesis and "둘째 줄" in row.stuck


def test_stuck_notes_pass_the_check_and_stay_with_loop_lines(repo, built):
    repo("retro", "note", "W-001-T01", "--stuck", "막힘", "--weakness", "환경", "--remedy", "연결 도구", "--hypothesis", "h")
    _loop_with_one_slow_criterion(repo)
    rows = _rows(repo)
    assert [r.key for r in rows] == ["막힘", "AC-1"] and rows[1].tries == 3
    assert retro.problems(built, _file(repo).read_text(encoding="utf-8")) == []
