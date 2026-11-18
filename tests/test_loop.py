"""The build loop's facts: who may loop, what a try and a round measure, what makes a pass invalid.

The loop runs real commands in a real git repository. A fake test tool stands in for pytest: a test file
`tests/test_X.py` passes once `src/X.txt` exists, so "implementing" is writing that file.
"""

import json

import pytest

from conftest import docs, fill, fill_plan, init_project, work_dir
from lanternspec.core.profile import DEFAULTS, Profile, _deep_merge
from lanternspec.core.project import Project
from lanternspec.report import build_mode
from lanternspec.tools import get
from lanternspec.tools.skills import generate
from lanternspec.work import loop

FAKE_TESTS = """import pathlib
import sys

# usage: fake_tests.py [tests/test_X.py[::name]] — one test, or every test file
root = pathlib.Path(".")


def passes(path):
    return (root / "src" / (pathlib.Path(path).stem.removeprefix("test_") + ".txt")).exists()


if sys.argv[1:]:
    path = sys.argv[1].split("::")[0]
    ok = passes(path)
    print("1 passed in 0.01s" if ok else "1 failed in 0.01s")
    sys.exit(0 if ok else 1)
files = sorted((root / "tests").glob("test_*.py"))
bad = [f for f in files if not passes(f)]
print(f"{len(files) - len(bad)} passed, {len(bad)} failed in 0.01s")
sys.exit(1 if bad else 0)
"""

TWO_ACS = (
    "- [ ] AC-1 상황: 로그인 화면에서 · 행동: 카카오 버튼을 누르면 · 결과: 2초 안에 홈이 열린다 "
    "[테스트:: tests/test_login.py::test_kakao]\n"
    "- [ ] AC-2 행동: 로그아웃을 누르면 · 결과: 로그인 화면으로 돌아간다 [테스트:: tests/test_logout.py]"
)


def _lines(project, kind=None):
    path = project.state / "runs.jsonl"
    rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []
    return [r for r in rows if kind is None or r["kind"] == kind]


def _commit(repo, message="commit"):
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", message)


def _implement(repo, name):
    (repo.root / "src").mkdir(exist_ok=True)
    (repo.root / "src" / f"{name}.txt").write_text("done", encoding="utf-8")


@pytest.fixture
def work(repo):
    """A work W-001 whose two criteria link two committed tests, in a project with the loop on."""
    init_project(repo)
    repo("scaffold", "work", "카카오 로그인")
    fill_plan(repo, "W-001", TWO_ACS)
    (repo.root / "fake_tests.py").write_text(FAKE_TESTS, encoding="utf-8")
    (repo.root / "tests").mkdir()
    for name in ("login", "logout", "other"):
        (repo.root / "tests" / f"test_{name}.py").write_text("# a test", encoding="utf-8")
    _implement(repo, "other")
    repo("profile", "set", "build.loop=on", "build.test=python3 fake_tests.py", "build.test_one=python3 fake_tests.py {test}")
    _commit(repo, "tests")
    return Project.load(repo.root)


# --------------------------------------------------------------------------- the pieces


def test_the_test_count_is_read_from_the_common_tools():
    assert loop.count_tests("2164 passed, 381 skipped in 20.1s") == 2164
    assert loop.count_tests("FAILED x\n== 1 failed, 2 passed, 1 error in 3.00s ==") == 4
    assert loop.count_tests(" Test Files  1 passed (1)\n      Tests  2 failed | 5 passed (7)\n") == 7
    assert loop.count_tests("Tests:       5 passed, 5 total") == 5
    assert loop.count_tests("Ran 3 tests in 0.001s\n\nOK") == 3
    assert loop.count_tests("a tool nobody knows") is None
    assert loop.count_tests("Ran 2 tests in 0.1s\n== 1 passed in 0.30s ==") == 1  # the pytest summary is the last word


def test_a_test_with_spaces_stays_one_word_in_the_command():
    assert loop.command_for("t {test} --x", "tests/a b.py::test_c") == "t 'tests/a b.py::test_c' --x"
    assert loop.command_for("t {test}", "tests/it's.py") == "t 'tests/it'\"'\"'s.py'"  # a quote in the path stays in the path


def test_the_test_field_can_sit_anywhere_in_the_line():
    from lanternspec.core.names import load
    from lanternspec.core.taskfile import parse_criteria

    (ac,) = parse_criteria("- [ ] AC-1 [테스트:: tests/a b.py::test_x] 행동: 누르면 · 결과: 열린다", load("ko"))
    assert (ac.test_file, ac.text) == ("tests/a b.py", "행동: 누르면 · 결과: 열린다")


# --------------------------------------------------------------------------- who may loop


def test_a_work_may_loop_when_every_criterion_has_a_committed_test(repo, work):
    elig = loop.eligibility(work, "W-001")
    assert elig.ok and elig.tests == {"AC-1": "tests/test_login.py::test_kakao", "AC-2": "tests/test_logout.py"}


def test_a_criterion_without_a_test_names_itself(repo, work):
    plan = work_dir(repo, "W-001") / "기획.md"
    fill(plan, [(" [테스트:: tests/test_logout.py]", "")])
    elig = loop.eligibility(work, "W-001")
    assert not elig.ok and elig.missing == ["AC-2"] and "AC-2" in elig.reasons[0]


def test_a_test_that_is_not_committed_yet_does_not_count(repo, work):
    (repo.root / "tests" / "test_login.py").write_text("# changed", encoding="utf-8")
    elig = loop.eligibility(work, "W-001")
    assert not elig.ok and "커밋하지 않은" in elig.reasons[0]
    (repo.root / "tests" / "test_logout.py").unlink()
    _commit(repo, "drop")
    assert any("커밋되지 않았습니다" in r for r in loop.eligibility(work, "W-001").reasons)


def test_a_project_without_a_test_command_may_not_loop(repo, work):
    repo("profile", "set", "build.test=")
    assert "테스트 명령" in " ".join(loop.eligibility(Project.load(repo.root), "W-001").reasons)


def test_the_test_field_is_checked_like_the_rest_of_the_criterion(repo, work):
    plan = work_dir(repo, "W-001") / "기획.md"
    fill(plan, [("[테스트:: tests/test_logout.py]", "[태스트:: tests/test_logout.py] [테스트:: ]")])
    _, out = repo("check", "--epic", "W-001", ok=False)
    assert "'태스트'" in out and "테스트 칸이 비어 있습니다" in out


# --------------------------------------------------------------------------- starting


def test_a_loop_starts_with_the_settings_and_the_base_it_will_be_judged_by(repo, work):
    _, out = repo("loop", "start", "W-001")
    (line,) = _lines(work, "loop")
    assert "✔" in out and line["event"] == "start" and line["mode"] == "loop" and line["work"] == "W-001"
    assert line["tests_before"] == 3 and line["base"] == repo.git("rev-parse", "HEAD").stdout.strip()
    assert sorted(line["files"]["tests"]) == ["tests/test_login.py", "tests/test_logout.py"]  # each with its fingerprint
    assert line["settings"]["same_ac_limit"] == 3 and line["settings"]["test_one"].endswith("{test}")


def test_a_work_that_may_not_loop_goes_on_with_a_check_after_each_task(repo, work):
    plan = work_dir(repo, "W-001") / "기획.md"
    fill(plan, [(" [테스트:: tests/test_logout.py]", "")])
    _, out = repo("loop", "start", "W-001")
    assert "ℹ" in out and "AC-2" in out and _lines(work, "loop")[0]["mode"] == "each"
    code, out = repo("loop", "attempt", "W-001", "AC-1", ok=False)  # nothing runs: the person checks each task
    assert code == 1 and "진행 중인 반복이 없습니다" in out and _lines(work, "attempt") == []


def test_no_loop_starts_when_the_setting_is_off(repo, work):
    repo("profile", "set", "build.loop=off")
    code, out = repo("loop", "start", "W-001", ok=False)
    assert code == 1 and "off" in out and _lines(work, "loop") == []


# --------------------------------------------------------------------------- a try


def test_a_try_is_judged_by_the_exit_code_and_written_by_lantern(repo, work):
    repo("loop", "start", "W-001")
    code, out = repo("loop", "attempt", "W-001", "AC-1", ok=False)
    assert code == 1 and "✖" in out and "연속 1/3" in out
    _implement(repo, "login")
    code, out = repo("loop", "attempt", "W-001", "ac-1")
    assert code == 0 and "✔" in out
    first, second = _lines(work, "attempt")
    assert (first["attempt"], first["result"], first["scope"]) == (1, "fail", "one") and "test_login.py" in first["failed_check"]
    assert (second["attempt"], second["result"], second["failed_check"]) == (2, "pass", "")
    assert first["work"] == "W-001" and first["run"] == second["run"] and first["source"] == "build"


def test_without_a_one_test_command_nothing_is_judged_per_criterion(repo, work):
    repo("profile", "set", "build.test_one=")
    repo("loop", "start", "W-001")
    for _ in range(4):  # the suite fails because AC-2 is not built yet — that is no failure of AC-1, and no limit
        code, out = repo("loop", "attempt", "W-001", "AC-1", ok=False)
        assert code == 1 and "전체 테스트가 통과하지 못했습니다" in out
    assert {r["scope"] for r in _lines(work, "attempt")} == {"all"} and {r["result"] for r in _lines(work, "attempt")} == {"fail"}
    _implement(repo, "login")
    _implement(repo, "logout")
    _, out = repo("loop", "finish", "W-001")  # the whole suite is the judge
    assert "✔" in out


def test_a_criterion_that_fails_too_often_in_a_row_is_not_run_again(repo, work):
    repo("loop", "start", "W-001")
    for _ in range(3):
        repo("loop", "attempt", "W-001", "AC-1", ok=False)
    _implement(repo, "login")  # fixed too late: the loop has to stop and hand it to the person anyway
    code, out = repo("loop", "attempt", "W-001", "AC-1", ok=False)
    assert code == 1 and "⛔" in out
    for command in (("attempt", "W-001", "AC-2"), ("attempt", "W-001", "AC-1"), ("finish", "W-001")):
        code, out = repo("loop", *command, ok=False)
        assert code == 1 and "멈췄습니다" in out  # the loop has stopped: nothing more runs
    results = [r["result"] for r in _lines(work, "attempt")]
    assert results == ["fail", "fail", "fail", "limit"]  # the refusal is written once, and nothing ran


def test_a_criterion_outside_the_loop_is_refused(repo, work):
    repo("loop", "start", "W-001")
    code, out = repo("loop", "attempt", "W-001", "AC-9", ok=False)
    assert code == 1 and "AC-9" in out


# --------------------------------------------------------------------------- a round


def _loop_to_the_end(repo):
    repo("loop", "start", "W-001")
    _implement(repo, "login")
    _implement(repo, "logout")
    repo("loop", "attempt", "W-001", "AC-1")
    repo("loop", "attempt", "W-001", "AC-2")


def test_a_round_passes_when_the_criteria_and_the_suite_pass(repo, work):
    _loop_to_the_end(repo)
    _, out = repo("loop", "finish", "W-001")
    end = _lines(work, "loop")[-1]
    assert "✔" in out and (end["event"], end["result"], end["round"], end["tests_after"]) == ("end", "passed", 1, 3)


def test_new_tests_do_not_invalidate_a_pass(repo, work):
    _loop_to_the_end(repo)
    (repo.root / "tests" / "test_extra.py").write_text("# new", encoding="utf-8")
    _implement(repo, "extra")
    _commit(repo, "impl")
    _, out = repo("loop", "finish", "W-001")
    assert "✔" in out


def test_a_round_fails_when_a_criterion_has_no_passing_try(repo, work):
    repo("loop", "start", "W-001")
    _implement(repo, "login")
    repo("loop", "attempt", "W-001", "AC-1")
    code, out = repo("loop", "finish", "W-001", ok=False)
    assert code == 1 and "✖" in out and "AC-2" in out


def test_the_round_limit_hands_the_work_to_the_person(repo, work):
    repo("loop", "start", "W-001")
    for _ in range(3):
        _, out = repo("loop", "finish", "W-001", ok=False)
    assert "한도" in out
    assert [r["round"] for r in _lines(work, "loop") if r["event"] == "end"] == [1, 2, 3]


@pytest.mark.parametrize(
    ("change", "kind"),
    [
        (lambda r: (r.root / "tests" / "test_login.py").write_text("# weakened", encoding="utf-8"), "연결된 테스트가 바뀌었습니다"),
        (lambda r: (r.root / "pytest.ini").write_text("[pytest]", encoding="utf-8"), "테스트 설정 파일이 바뀌었습니다"),
        (lambda r: (r.root / "tests" / "test_other.py").unlink(), "실행된 테스트가 줄었습니다"),
    ],
    ids=["a linked test edited", "a test settings file changed", "fewer tests ran"],
)
def test_a_pass_is_invalid_when_the_tests_that_judge_it_changed(repo, work, change, kind):
    repo("profile", "set", "build.test_config=[pytest.ini]")
    _commit(repo, "settings")
    _loop_to_the_end(repo)
    change(repo)
    code, out = repo("loop", "finish", "W-001", ok=False)
    assert code == 1 and "⛔" in out and kind in out
    end = _lines(work, "loop")[-1]
    assert end["result"] == "invalid" and end["violations"]


def test_an_invalid_round_stops_the_loop_and_a_restart_needs_the_persons_word(repo, work):
    _loop_to_the_end(repo)
    (repo.root / "tests" / "test_login.py").write_text("# weakened", encoding="utf-8")
    repo("loop", "finish", "W-001", ok=False)
    for command in (("attempt", "W-001", "AC-1"), ("finish", "W-001")):
        code, out = repo("loop", *command, ok=False)
        assert code == 1 and "멈췄습니다" in out
    code, out = repo("loop", "start", "W-001", ok=False)  # starting over would forget the failures and the fingerprints
    assert code == 1 and "--again" in out and len(_lines(work, "loop")) == 2


def test_a_second_loop_started_with_the_persons_word_is_warned_about_at_archive(repo, work):
    repo("loop", "start", "W-001")
    repo("loop", "start", "W-001", "--again")
    _implement(repo, "login")
    repo("loop", "attempt", "W-001", "AC-1")
    _, out = repo("work", "archive", "W-001")
    assert "2번 시작했습니다" in out


def test_a_restart_after_a_work_that_could_not_loop_needs_no_word(repo, work):
    plan = work_dir(repo, "W-001") / "기획.md"
    fill(plan, [(" [테스트:: tests/test_logout.py]", "")])
    repo("loop", "start", "W-001")  # not eligible: goes on with a check after each task
    fill(plan, [("로그인 화면으로 돌아간다", "로그인 화면으로 돌아간다 [테스트:: tests/test_logout.py]")])
    _, out = repo("loop", "start", "W-001")
    assert "✔" in out


def test_a_failing_run_is_not_judged_by_how_many_tests_it_ran(repo, work):
    _loop_to_the_end(repo)
    (repo.root / "tests" / "test_other.py").unlink()  # fewer tests, but the suite fails too: a failed round, not an invalid one
    (repo.root / "src" / "logout.txt").unlink()
    _, out = repo("loop", "finish", "W-001", ok=False)
    assert "✖" in out and _lines(work, "loop")[-1]["result"] == "failed"


def test_the_change_is_caught_even_when_committed(repo, work):
    _loop_to_the_end(repo)
    (repo.root / "tests" / "test_login.py").write_text("# weakened", encoding="utf-8")
    _commit(repo, "weaken the test")
    code, out = repo("loop", "finish", "W-001", ok=False)
    assert code == 1 and "연결된 테스트가 바뀌었습니다: tests/test_login.py" in out


def test_a_settings_file_made_later_is_caught_even_when_git_ignores_it(repo, work):
    (repo.root / ".gitignore").write_text("pytest.ini\n", encoding="utf-8")
    repo("profile", "set", "build.test_config=[pytest.ini]")
    _commit(repo, "ignore")
    _loop_to_the_end(repo)
    (repo.root / "pytest.ini").write_text("[pytest]", encoding="utf-8")
    code, out = repo("loop", "finish", "W-001", ok=False)
    assert code == 1 and "테스트 설정 파일이 바뀌었습니다: pytest.ini" in out


def test_a_settings_pattern_catches_a_conftest_made_later(repo, work):
    repo("profile", "set", "build.test_config=['tests/**/conftest.py']")
    _commit(repo, "settings")
    _loop_to_the_end(repo)
    (repo.root / "tests" / "conftest.py").write_text("# a hook that bends the results", encoding="utf-8")
    code, out = repo("loop", "finish", "W-001", ok=False)
    assert code == 1 and "tests/conftest.py" in out


def test_a_moved_linked_test_is_caught(repo, work):
    _loop_to_the_end(repo)
    repo.git("mv", "tests/test_login.py", "tests/test_signin.py")
    code, out = repo("loop", "finish", "W-001", ok=False)
    assert code == 1 and "연결된 테스트가 바뀌었습니다: tests/test_login.py" in out


def test_a_test_tool_whose_output_cannot_be_counted_skips_only_that_check(repo, work):
    repo("profile", "set", "build.test=python3 fake_tests.py >/dev/null && echo fine")
    _loop_to_the_end(repo)
    _, out = repo("loop", "finish", "W-001")
    assert "✔" in out and "테스트 수를 읽지 못해" in out


# --------------------------------------------------------------------------- what later steps read


def test_the_wrap_up_warns_when_the_loop_is_on_but_nothing_looped(repo, work):
    _, out = repo("work", "archive", "W-001")
    assert "⚠" in out and "반복이 없습니다" in out


def test_the_wrap_up_is_quiet_after_a_loop_that_passed(repo, work):
    _loop_to_the_end(repo)
    repo("loop", "finish", "W-001")
    _, out = repo("work", "archive", "W-001")
    assert "⚠" not in out


def test_the_wrap_up_warns_about_what_changed_after_the_pass(repo, work):
    _loop_to_the_end(repo)
    repo("loop", "finish", "W-001")
    (repo.root / "tests" / "test_login.py").write_text("# weakened later", encoding="utf-8")
    _, out = repo("work", "archive", "W-001")
    assert "⚠" in out and "연결된 테스트가 바뀌었습니다" in out


def test_a_work_checked_task_by_task_is_not_warned_about(repo, work):
    plan = work_dir(repo, "W-001") / "기획.md"
    fill(plan, [(" [테스트:: tests/test_logout.py]", "")])
    repo("loop", "start", "W-001")
    _, out = repo("work", "archive", "W-001")
    assert "⚠" not in out


def test_a_work_with_the_loop_off_is_not_warned_about(repo, work):
    repo("profile", "set", "build.loop=off")
    _, out = repo("work", "archive", "W-001")
    assert "⚠" not in out


def test_the_status_says_who_may_loop_and_how_the_run_stands(repo, work):
    _, out = repo("loop", "status", "W-001")
    assert "반복해도 됩니다" in out
    _loop_to_the_end(repo)
    repo("loop", "finish", "W-001")
    _, out = repo("loop", "status", "W-001")
    assert "시도 2번" in out and "마지막 회차: 통과" in out and "loop" not in out


# --------------------------------------------------------------------------- build-mode with a work


def test_the_suggestion_for_a_work_that_may_not_loop_changes_no_setting(repo, work, monkeypatch):
    monkeypatch.setattr(
        build_mode,
        "facts",
        lambda p: {
            "has_test": True,
            "skill_runs": 9,
            "clean_rate": 90,
            "loc": 10,
            "active_works": 1,
            "waiting_works": [],
            "parallel_ready": 0,
            "team": False,
            "code_files": 1,
            "tasks": 0,
        },
    )
    assert build_mode.suggest(work, "W-001").settings["build.loop"] == "on"  # every criterion has a test: the loop may be suggested
    plan = work_dir(repo, "W-001") / "기획.md"
    fill(plan, [(" [테스트:: tests/test_logout.py]", "")])
    blocked = build_mode.suggest(work, "W-001")
    assert blocked.settings == {} and any("AC-2" in r for r in blocked.axes[0].reasons)
    assert build_mode.suggest(work).settings["build.loop"] == "on"  # without a work: the project's own suggestion


def test_a_damaged_loop_line_does_not_stop_the_archive(repo, work):
    with (work.state / "runs.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"kind": "loop", "event": "start", "work": "W-001", "mode": "loop"}) + "\n")
        f.write(json.dumps({"kind": "attempt", "run": "x", "work": "W-001"}) + "\n")
    _, out = repo("work", "archive", "W-001")
    assert "✔ 보관" in out


def test_the_build_skill_shows_the_loop_only_when_the_loop_is_on_and_only_once():
    off = generate(Profile(data=_deep_merge(DEFAULTS, {})), [get("claude")])[".claude/skills/l-build/SKILL.md"]
    assert "큰 반복" not in off and "lantern loop" not in off
    on = generate(Profile(data=_deep_merge(DEFAULTS, {"build": {"loop": "on", "test": "pytest"}})), [get("claude")])[
        ".claude/skills/l-build/SKILL.md"
    ]
    assert on.count("## 3½") == 1 and "큰 반복 n번째" not in on and "1단계부터 다시 돈다" not in on
    assert (
        "lantern:if" not in on and "lantern:endif" not in on and "build.test_one`이 비어 있어" in on
    )  # no test_one: the skill says nothing is judged per criterion
    one = generate(Profile(data=_deep_merge(DEFAULTS, {"build": {"loop": "on", "test_one": "pytest {test}"}})), [get("claude")])
    assert "AC별 판정은 하지 않는다" not in one[".claude/skills/l-build/SKILL.md"]


def test_one_setting_never_stands_in_for_the_record(repo, work):
    assert not loop.built_by_loop(work, "W-001")  # the loop is on, but nothing looped
    repo("loop", "start", "W-001")
    assert not loop.built_by_loop(work, "W-001")  # started, nothing tried
    _implement(repo, "login")
    repo("loop", "attempt", "W-001", "AC-1")
    assert loop.built_by_loop(work, "W-001")
    repo("profile", "set", "build.loop=off")
    assert loop.built_by_loop(Project.load(repo.root), "W-001")  # the record outlives the setting


def test_profile_set_accepts_a_bare_on_and_refuses_a_one_test_command_without_its_place(repo, work):
    repo("profile", "set", "build.loop=off")
    repo("profile", "set", "build.loop=on")
    assert Project.load(repo.root).profile.get("build.loop") == "on"
    code, out = repo("profile", "set", "build.test_one=python3 fake_tests.py", ok=False)
    assert code == 1 and "{test}" in out and docs(repo).exists()
