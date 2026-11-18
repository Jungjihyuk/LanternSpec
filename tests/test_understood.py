"""The understanding mark: asked where approval is already asked, kept on the document, paid back as debt.

Approval (may it go on?) and understanding (did I follow it?) are different questions; a work approved
without understanding and built in an automatic loop leaves one understanding-debt card. Whether a loop built
it is read from the run log, not from the `build.loop` setting.
"""

import pytest

from conftest import docs, fill, init_project, work_dir
from lanternspec.core import frontmatter
from lanternspec.core.project import Project
from lanternspec.learn import debt
from lanternspec.tools import runlog
from lanternspec.work import stages


def _meta(path):
    return frontmatter.parse(path.read_text(encoding="utf-8")).meta


def _work(repo, loop="off", vault=None):
    """A work with a plan and a design, in a project whose build loop is `loop`."""
    init_project(repo, vault=vault)  # a debt ledger exists once the project has a knowledge store
    repo("profile", "set", f"build.loop={loop}")
    repo("scaffold", "work", "카카오 로그인")
    repo("scaffold", "doc", "W-001", "설계")
    folder = work_dir(repo, "W-001")
    return folder / "기획.md", folder / "설계.md"


def _looped(repo):
    """What the run log holds once a build loop started for W-001 and tried a criterion."""
    project = Project.load(repo.root)
    runlog.loop_event(project, "start", "r1", "W-001", mode="loop")
    runlog.loop_attempt(project, "r1", "W-001-T01", "AC-1", 1, "pass", work="W-001")


def _cards(repo):
    return sorted((docs(repo) / "📒 부채/카드").glob("D-* *.md"))


# --------------------------------------------------------------------------- writing the mark


def test_design_approval_records_understood_or_delegated(repo):
    _, design = _work(repo)
    repo("design", "approve", "W-001", "--by", "지혁", "--understood")
    assert _meta(design)["understood"] == "yes" and _meta(design)["approved"].endswith("지혁")
    repo("design", "approve", "W-001", "--by", "지혁", "--delegated")
    assert _meta(design)["understood"] == "no"


def test_design_approval_without_a_choice_changes_nothing_else(repo):
    _, design = _work(repo)
    repo("design", "approve", "W-001", "--by", "지혁")
    assert "understood" not in _meta(design) and _meta(design)["approved"]


def test_one_approval_cannot_be_both_understood_and_delegated(repo):
    _work(repo)
    with pytest.raises(SystemExit):
        repo("design", "approve", "W-001", "--by", "지혁", "--understood", "--delegated")


def test_the_plan_is_marked_when_planning_ends(repo):
    plan, _ = _work(repo)
    repo("plan", "understand", "W-001", "--delegated")
    assert _meta(plan)["understood"] == "no"
    repo("plan", "understand", "W-001", "--understood")
    assert _meta(plan)["understood"] == "yes"
    code, _ = repo("plan", "understand", "W-009", "--understood", ok=False)
    assert code == 1  # no such work
    with pytest.raises(SystemExit):
        repo("plan", "understand", "W-001")  # one of the two is needed


def test_a_marked_document_still_passes_the_format_check(repo):
    plan, design = _work(repo)
    repo("plan", "understand", "W-001", "--understood")
    repo("design", "approve", "W-001", "--by", "지혁", "--delegated")
    _, out = repo("check", str(plan), str(design))
    assert "understood" not in out and "✖" not in out


# --------------------------------------------------------------------------- reading it back


def test_the_design_mark_wins_and_a_skipped_design_follows_the_plan(repo):
    plan, design = _work(repo)
    project = Project.load(repo.root)
    assert stages.understood(project, "W-001") is None  # never asked
    repo("plan", "understand", "W-001", "--understood")
    assert stages.understood(project, "W-001") is True  # no design mark yet: the plan's
    repo("design", "approve", "W-001", "--by", "auto")  # a small design that passed without asking
    assert stages.understood(project, "W-001") is True
    repo("design", "approve", "W-001", "--by", "지혁", "--delegated")  # asked at the design: the later answer
    assert stages.understood(project, "W-001") is False


def test_a_hand_written_yes_or_no_reads_too(repo):
    plan, _ = _work(repo)
    fill(plan, [("\ntemplate:", "\nunderstood: yes\ntemplate:")])  # YAML reads a bare yes as true
    assert stages.understood(Project.load(repo.root), "W-001") is True
    fill(plan, [("understood: yes", "understood: no")])
    assert stages.understood(Project.load(repo.root), "W-001") is False


# --------------------------------------------------------------------------- the debt card


def test_a_work_built_by_the_loop_without_understanding_leaves_one_card(repo, vault):
    _work(repo, loop="on", vault=vault)
    _looped(repo)
    repo("plan", "understand", "W-001", "--delegated")
    _, out = repo("work", "archive", "W-001")
    (card,) = _cards(repo)
    meta = _meta(card)
    assert meta["kind"] == "이해" and "W-001" in str(meta["work"]) and "이해 부채" in out and "W-001" in card.name
    assert "이해하지 않은 채 자율 구현됨" in card.read_text(encoding="utf-8")


def test_the_card_is_made_once_per_work(repo, vault):
    _work(repo, loop="on", vault=vault)
    _looped(repo)
    repo("plan", "understand", "W-001", "--delegated")
    project = Project.load(repo.root)
    first = debt.understanding_debt(project, "W-001")
    assert first is not None and debt.understanding_debt(project, "W-001") is None
    assert len(_cards(repo)) == 1


@pytest.mark.parametrize(
    ("looped", "mark"),
    [(False, "--delegated"), (True, "--understood"), (True, None)],
    ids=["not built by the loop", "understood", "never asked"],
)
def test_no_card_when_it_does_not_apply(repo, vault, looped, mark):
    _work(repo, loop="on", vault=vault)  # the setting is on in every case: only the run log says who looped
    if looped:
        _looped(repo)
    if mark:
        repo("plan", "understand", "W-001", mark)
    repo("work", "archive", "W-001")
    assert _cards(repo) == []


def test_a_project_without_a_debt_ledger_just_skips_the_card(repo):
    _work(repo, loop="on")
    _looped(repo)
    repo("plan", "understand", "W-001", "--delegated")
    assert not (docs(repo) / "📒 부채").exists()
    _, out = repo("work", "archive", "W-001")
    assert "보관" in out and not (docs(repo) / "📒 부채").exists()


def test_an_archive_that_waits_and_runs_again_still_leaves_one_card(repo, vault, monkeypatch):
    from lanternspec.work import branches

    _work(repo, loop="on", vault=vault)
    _looped(repo)
    repo("plan", "understand", "W-001", "--delegated")
    waiting = iter([["W-002"]])  # a running work links to it the first time only
    monkeypatch.setattr(branches, "archive_waits_for", lambda project, work_id: next(waiting, []))
    _, out = repo("work", "archive", "W-001")
    assert "⏸" in out and len(_cards(repo)) == 1
    _, out = repo("work", "archive", "W-001", "--now")
    assert "✔ 보관" in out and len(_cards(repo)) == 1 and "이해 부채" not in out


def test_a_broken_debt_ledger_does_not_stop_the_archive(repo, vault, monkeypatch):
    _work(repo, loop="on", vault=vault)
    _looped(repo)
    repo("plan", "understand", "W-001", "--delegated")

    def broken(project, work_id):
        raise ValueError("깨진 카드")

    monkeypatch.setattr(debt, "understanding_debt", broken)
    _, out = repo("work", "archive", "W-001")
    assert "⚠" in out and "깨진 카드" in out and "✔ 보관" in out
