"""How long a task took: only what was recorded, to the second in the run log, and never a time made up for the chart."""

import datetime as dt
import json
import shutil
import subprocess

import pytest

from conftest import docs, init_project, work_dir
from lanternspec import resources
from lanternspec.core.project import Project
from lanternspec.report.evaluate import load_runs, task_durations
from lanternspec.tools import runlog, who_did


def _project(repo, *lines: str) -> Project:
    init_project(repo)
    repo("scaffold", "work", "작업")
    repo("scaffold", "doc", "W-001", "할 일")
    if lines:
        path = work_dir(repo, "W-001") / "할 일.md"
        head = path.read_text(encoding="utf-8").split("---\n")[1]  # the document's frontmatter stays, so it is checked as one
        path.write_text(f"---\n{head}---\n" + "\n".join(lines) + "\n", encoding="utf-8")
    return Project.load(repo.root)


def _log(project: Project, task: str, event: str, at: str) -> None:
    runlog.append(project, {"kind": "task", "source": "cli", "event": event, "task": task, "work": "W-001", "at": f"{at}+09:00"})


def _chart(repo, name: str) -> dict:
    plugin = docs(repo) / f".obsidian/plugins/{name}"
    plugin.mkdir(parents=True, exist_ok=True)
    (plugin / "main.js").write_text("", encoding="utf-8")
    (docs(repo) / ".obsidian/community-plugins.json").write_text(json.dumps([name]), encoding="utf-8")
    repo("report", "--views", "kanban,timeline")
    report = (docs(repo) / "4. 운영 기록/보고/현황.md").read_text(encoding="utf-8")
    return json.loads(report.split(f"```{name}\n")[1].split("\n```")[0])


SAME_MINUTE = "- [x] W-001-T01 하나 [크기:: 1h] [시작:: 2026-11-24 17:07] [완료:: 2026-11-24 17:07]"


# --------------------------------------------------------------------------- the run log


def test_start_and_done_leave_their_time_to_the_second(repo):
    project = _project(repo)
    repo("task", "add", "W-001", "하나", "--size", "1h")
    repo("task", "start", "W-001-T01")
    repo("task", "start", "W-001-T01")  # taken over: it has started already
    repo("task", "done", "W-001-T01")

    events = [r for r in load_runs(project) if r["kind"] == "task"]
    assert [(r["event"], r["task"], r["work"]) for r in events] == [("start", "W-001-T01", "W-001"), ("done", "W-001-T01", "W-001")]
    assert all(dt.datetime.fromisoformat(r["at"]).tzinfo and len(r["at"][11:19]) == 8 for r in events)
    line = (work_dir(repo, "W-001") / "할 일.md").read_text(encoding="utf-8")
    assert f"[시작:: {events[0]['at'][:16].replace('T', ' ')}]" in line  # the document keeps minutes


# --------------------------------------------------------------------------- the charts


def test_a_task_that_ends_in_the_minute_it_began_gets_no_time_made_up(repo):
    _project(repo, SAME_MINUTE)
    (task,) = _chart(repo, "lantern-timeline")["works"][0]["tasks"]
    assert (task["start"], task["end"], task["seconds"]) == ("2026-11-24 17:07", "2026-11-24 17:07", 0)


def test_the_run_log_says_the_seconds_when_it_agrees_with_the_document(repo):
    project = _project(
        repo, SAME_MINUTE, "- [x] W-001-T02 둘 [크기:: 1h] [시작:: 2026-11-24 17:07] [완료:: 2026-11-24 17:08]",
        "- [x] W-001-T03 셋 [크기:: 1h] [시작:: 2026-11-24 10:00] [완료:: 2026-11-24 11:00]",
    )  # fmt: skip
    for task, start, done in (("T01", "17:07:01", "17:07:43"), ("T02", "17:07:43", "17:08:14"), ("T03", "17:00:00", "17:01:00")):
        _log(project, f"W-001-{task}", "start", f"2026-11-24T{start}")
        _log(project, f"W-001-{task}", "done", f"2026-11-24T{done}")

    tasks = _chart(repo, "lantern-timeline")["works"][0]["tasks"]
    assert [t["seconds"] for t in tasks] == [42, 31, 3600]  # T03's line was changed by hand: the document is what is shown


def test_a_task_never_started_or_dated_by_the_day_has_no_length(repo):
    project = _project(
        repo, SAME_MINUTE, "- [x] W-001-T02 둘 [시작:: 2026-11-24] [완료:: 2026-11-24]",
        "- [x] W-001-T03 셋 [시작:: 2026-11-24 18:00] [완료:: 2026-11-24 17:00]",
    )  # fmt: skip
    _log(project, "W-001-T01", "done", "2026-11-24T17:07:43")  # only `done` was run, which stamps both times

    tasks = _chart(repo, "lantern-timeline")["works"][0]["tasks"]
    assert all("seconds" not in t for t in tasks)
    assert tasks[2]["end"] == "2026-11-24 17:00"  # as recorded, however odd: lantern check says so


def test_the_kanban_adds_up_the_same_times(repo):
    project = _project(repo, SAME_MINUTE)
    work = _chart(repo, "lantern-kanban")["works"][0]
    assert work["worked"] == 0 and work["under_minute"] is True
    _log(project, "W-001-T01", "start", "2026-11-24T17:07:01")
    _log(project, "W-001-T01", "done", "2026-11-24T17:07:43")
    assert _chart(repo, "lantern-kanban")["works"][0]["under_minute"] is True


def test_quick_tasks_count_when_sizes_are_measured(repo):
    project = _project(repo, SAME_MINUTE, "- [x] W-001-T02 둘 [크기:: 1h] [시작:: 2026-11-24 10:00] [완료:: 2026-11-24 11:00]")
    _log(project, "W-001-T01", "start", "2026-11-24T17:07:00")
    _log(project, "W-001-T01", "done", "2026-11-24T17:07:36")
    assert task_durations(project)["1h"] == [0.01, 1.0]


def test_a_length_that_was_never_measured_is_no_size(repo):
    """Without a run log (it isn't shared) a task only finished looks like one that took no time at all."""
    project = _project(repo, SAME_MINUTE, "- [x] W-001-T02 둘 [크기:: 1h] [시작:: 2026-11-24 10:00] [완료:: 2026-11-24 11:00]")
    assert task_durations(project)["1h"] == [1.0]


@pytest.mark.skipif(shutil.which("node") is None, reason="node draws nothing here, it only runs the plugin's own functions")
def test_the_timeline_plugin_says_under_a_minute():
    code = dict(resources.iter_files("obsidian/lantern-timeline"))["main.js"].read_text(encoding="utf-8")
    head = code[: code.index("class ")].replace(
        'require("obsidian")', "{MarkdownRenderChild: class {}, Notice: class {}, Plugin: class {}}"
    )
    script = (
        head
        + """
const L = { minutes: "{n}분", hours: "{n}시간", under_minute: "1분 미만" };
const at = (end, more) => ({ state: "done", basis: "actual", start: "2026-11-24 17:07", end: `2026-11-24 ${end}`, ...more });
console.log(JSON.stringify([
  took(at("17:07", { seconds: 0 })), took(at("17:08", { seconds: 31 })), took(at("17:08", { seconds: 60 })), took(at("17:07")),
  took(at("18:07")), took(at("18:07", { seconds: 3599 })),
].map((s) => s === null ? null : lasted(s, L))));
console.log(JSON.stringify(recorded(at("17:07", { seconds: 0 })).map(stamp)));
"""
    )
    done = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    lengths, span = map(json.loads, done.stdout.splitlines())
    assert lengths == ["1분 미만", "1분 미만", "1분", None, "1시간", "1시간"]  # the fourth: no seconds, so nothing is said
    assert span == ["2026-11-24 17:07", "2026-11-24 17:07"]


# --------------------------------------------------------------------------- names


def test_a_model_name_may_hold_spaces(repo):
    _project(repo)
    repo("task", "add", "W-001", "하나", "--size", "1h")
    repo("task", "start", "W-001-T01", "--by", "Gemini 4 Neon")
    repo("task", "done", "W-001-T01", "--by", "Gemini 4 Neon, 지혁")

    assert "[한 사람:: Gemini 4 Neon, 지혁]" in (work_dir(repo, "W-001") / "할 일.md").read_text(encoding="utf-8")
    (task,) = _chart(repo, "lantern-kanban")["works"][0]["tasks"]
    assert task["by"] == ["Gemini 4 Neon", "지혁"] and task["who"] == "both"
    models = ("Gemini 4 Neon", "gemini-4-neon", "Claude Opus 5.5", "GPT 5.1 Codex")
    assert {who_did([n]) for n in models} == {"ai"} and who_did(["홍 길동"]) == "human"


# --------------------------------------------------------------------------- times that can't be


def _time_findings(repo) -> list[str]:
    _, out = repo("check", ok=False)
    return [line for line in out.splitlines() if "task-time" in line or "미래" in line or "완료가 시작보다" in line]


def test_check_finds_times_that_cannot_be(repo):
    future = (dt.datetime.now() + dt.timedelta(days=2)).strftime("%Y-%m-%d %H:%M")
    _project(
        repo,
        "- [x] W-001-T01 하나 [크기:: 1h] [시작:: 2020-11-24 18:00] [완료:: 2020-11-24 17:00]",
        f"- [x] W-001-T02 둘 [크기:: 1h] [시작:: 2020-11-24 17:00] [완료:: {future}]",
        SAME_MINUTE.replace("T01", "T03").replace("2026", "2020"),
        "- [x] W-001-T04 넷 [크기:: 1h] [시작:: 2020-11-24 17:00] [완료:: 2020-11-24]",
    )
    text = "\n".join(_time_findings(repo))
    assert "W-001-T01" in text and "W-001-T02" in text and "W-001-T03" not in text and "W-001-T04" not in text


@pytest.mark.parametrize("team", [False, True])
def test_a_time_written_in_another_time_zone_is_not_in_the_future(repo, team):
    later = (dt.datetime.now() + dt.timedelta(hours=9)).strftime("%Y-%m-%d %H:%M")  # e.g. written in Seoul, checked by CI in UTC
    _project(repo, f"- [x] W-001-T01 하나 [크기:: 1h] [담당:: 지혁] [시작:: 2020-11-24 17:00] [완료:: {later}]")
    if team:
        repo("profile", "set", "project.team=team", "project.members=[지혁, 민수]")
    assert not _time_findings(repo)
