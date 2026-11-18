"""The review after a build: a pack for a reviewer in a fresh context, the verdict it gives, and how many rounds it gets.

The reviewer is a soft evaluator, so what it says is kept as it said it: the verdict is read from its own text
by code (`parse_verdict`) and written to the run log, never retold by the agent that built. The pack holds only
documents and the diff — not the conversation that built the work, nor its tries — so the reviewer does not share
the builder's blind spots. The number of rounds is counted here, not trusted to the agent.

Responsibilities:
    - build the review pack from the work's documents, the rules, the diff since the work started and the test result
    - read a verdict (one `[verdict] item` line each) out of a reviewer's text
    - write each round to the run log, and count rounds against `build.review_limit`
    - warn at archive when a build that asked for a review was not reviewed, or was left with issues

Not here:
    - who runs the reviewer and with which model → tools/<tool>.py (agent files · `review_command`)
    - catching the reviewer's report when it stops → tools/agent_hooks.py
    - turning issues into retro rows → report/retro.py
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..core.enums import Enums
from ..core.messages import msg
from ..core.project import Project, git_out, read, write
from ..core.taskfile import parse_criteria
from . import loop
from .pack import strip_guides

REVIEWER = "lantern-reviewer"  # the name of the reviewer's agent definition
PACK_FOLDER = "review"  # under .lantern/
DOC_LIMIT = 20_000  # characters of one document put in the pack
DIFF_LIMIT = 120_000  # characters of diff put in the pack; the rest is named, and the reviewer reads those files itself
ITEM = re.compile(r"^\s*[-*]\s*\[([^\[\]]+)\]\s*(.*)$")
WORK = re.compile(r"W-\d{3,}")
EVIDENCE = re.compile(r"[\w./\\-]+\.\w+:\d+")  # `path/to/file.py:12`


@dataclass
class Item:
    """One line of a verdict.

    Attributes:
        verdict: "pass" or "issue" (the role).
        text: What the reviewer wrote after the verdict.

    Example:
        >>> Item("issue", "R2 — tests/test_a.py:12 — no expected value").verdict
        'issue'
    """

    verdict: str
    text: str


@dataclass
class Verdict:
    """What a reviewer's text says.

    Attributes:
        work: The work it names (the first W-NNN in the text); "" when none.
        items: The `[verdict] item` lines, in order.

    Example:
        >>> Verdict("W-012", [Item("pass", "R1")]).work
        'W-012'
    """

    work: str
    items: list[Item] = field(default_factory=list)

    @property
    def issues(self) -> list[Item]:
        """The items the reviewer found fault with."""
        return [i for i in self.items if i.verdict == "issue"]


@dataclass
class Round:
    """One review round, as the run log holds it.

    Attributes:
        n: Which round, from 1.
        at: When it was written.
        model: The reviewer's model; "" when unknown.
        items: How many items were judged.
        issues: How many were found fault with.
        unsupported: Issues without a `path:line` as their ground.
        issue_list: What the issues said.
        run: The run the round belongs to (the loop run, else the review's own).
        source: "hook" (caught when the reviewer stopped) or "cli".

    Example:
        >>> Round(1, "", "opus", 5, 0, 0, [], "a1", "hook").issues
        0
    """

    n: int
    at: str
    model: str
    items: int
    issues: int
    unsupported: int
    issue_list: list[str]
    run: str
    source: str


def parse_verdict(text: str, enums: Enums) -> Verdict | None:
    r"""Read a reviewer's verdict out of its text.

    Items are the lines that begin with `- [<verdict>]`; the verdict word is one of `review_verdict` in enums.yaml
    (or the role, `pass` · `issue`). The work is the first W-NNN in the text. The reviewer's closing line is not
    read: the count comes from the items.

    Args:
        text: What the reviewer answered.
        enums: The project's lists (the verdict words).

    Returns:
        The verdict; None when the text names no work or has no item.

    Example:
        >>> from lanternspec.core.enums import load
        >>> v = parse_verdict("검토: W-012\n- [통과] R1 AC-1\n- [지적] R2 — tests/a.py:3 — 기대값 없음", load())
        >>> v.work, [i.verdict for i in v.items], len(v.issues)
        ('W-012', ['pass', 'issue'], 1)
    """
    found = WORK.search(text)
    words = enums["review_verdict"]
    items = []
    for line in text.splitlines():
        m = ITEM.match(line)
        if not m:
            continue
        role = words.role_of(m.group(1).strip()) or (m.group(1).strip().lower() if m.group(1).strip().lower() in ("pass", "issue") else "")
        if role:
            items.append(Item(role, m.group(2).strip()))
    return Verdict(found.group(0) if found else "", items) if found and items else None


# --------------------------------------------------------------------------- the rounds


def rounds(project: Project, work_id: str) -> list[Round]:
    """Read a work's review rounds from the run log, oldest first.

    Args:
        project: The project.
        work_id: E.g. "W-012".

    Returns:
        The rounds.

    Example:
        >>> [r.issues for r in rounds(project, "W-012")]  # doctest: +SKIP
        [2, 0]
    """
    from ..report.evaluate import load_runs

    out = []
    for r in load_runs(project):
        if r.get("kind") == "review" and r.get("work") == work_id:
            out.append(
                Round(
                    len(out) + 1,
                    str(r.get("at") or ""),
                    str(r.get("review_model") or ""),
                    int(r.get("items") or 0),
                    int(r.get("issues") or 0),
                    int(r.get("unsupported") or 0),
                    list(r.get("issue_list") or []),
                    str(r.get("run") or ""),
                    str(r.get("source") or ""),
                )
            )
    return out


def review_limit(project: Project) -> int:
    """How many times the build is fixed and reviewed again after the first review (`build.review_limit`).

    Args:
        project: The project.

    Returns:
        The limit; 1 when unset.

    Example:
        >>> review_limit(project)  # doctest: +SKIP
        1
    """
    return int(project.profile.get("build.review_limit") or 1)


def standing(project: Project, work_id: str) -> str:
    """Say where a work's review stands, from the rounds the run log holds.

    Args:
        project: The project.
        work_id: E.g. "W-012".

    Returns:
        "none" (not reviewed), "clean" (the last round found nothing), "open" (issues left, rounds remain) or
        "limit" (issues left and no round remains: the person decides).

    Example:
        >>> standing(project, "W-012")  # doctest: +SKIP
        'open'
    """
    done = rounds(project, work_id)
    if not done:
        return "none"
    if not done[-1].issues:
        return "clean"
    return "limit" if len(done) >= 1 + review_limit(project) else "open"


def open_pack(project: Project, work_id: str) -> dict[str, Any] | None:
    """Find the pack a reviewer is still to answer: a pack was made after the last round was recorded.

    Args:
        project: The project.
        work_id: E.g. "W-012".

    Returns:
        The latest pack line (with the number of `items` it asks about); None when no pack waits for an answer.

    Example:
        >>> open_pack(project, "W-012")["items"]  # doctest: +SKIP
        5
    """
    from ..report.evaluate import load_runs

    packs = [r for r in load_runs(project) if r.get("kind") == "review_pack" and r.get("work") == work_id]
    return packs[-1] if len(packs) > len(rounds(project, work_id)) else None


def _run_id(project: Project, work_id: str) -> str:
    start = loop.last_start(project, work_id)
    if start:
        return str(start["run"])
    done = rounds(project, work_id)
    return done[-1].run if done else uuid.uuid4().hex[:8]


def record(project: Project, text: str, model: str = "", source: str = "cli", work_id: str = "") -> Round | None:
    r"""Write a reviewer's verdict to the run log as one round, and let the retro know when the review is over.

    Args:
        project: The project.
        text: The reviewer's own text.
        model: The reviewer's model, when known.
        source: "hook" or "cli".
        work_id: The work, when the caller knows it; else the one the text names.

    Returns:
        The round; None when the text holds no verdict (or names no work).

    Raises:
        ValueError: The text names another work than `work_id`; `build.review` is off; the review is over (clean, or no
            round left); no pack waits for an answer; or the verdict judges fewer items than the pack asked about.

    Example:
        >>> record(project, "검토: W-012\\n- [통과] R1", "opus").issues  # doctest: +SKIP
        0
    """
    from ..tools import runlog

    verdict = parse_verdict(text, project.enums)
    if verdict is None:
        return None
    if work_id and verdict.work != work_id.upper():
        raise ValueError(msg("The verdict names {named}, not {work_id}", named=verdict.work, work_id=work_id.upper()))
    work = verdict.work
    if project.profile.get("build.review") != "on":
        raise ValueError(msg("build.review is off, so no round is recorded"))
    if standing(project, work) in ("clean", "limit"):
        raise ValueError(msg("The review of {work_id} is over: no more rounds are recorded", work_id=work))
    waiting = open_pack(project, work)
    if waiting is None:
        raise ValueError(msg("No review pack waits for an answer for {work_id}: make one first (lantern review pack)", work_id=work))
    if len(verdict.items) < int(waiting.get("items") or 0):
        raise ValueError(
            msg(
                "The verdict judges {found} of the {expected} items: ask the reviewer to answer every item",
                found=len(verdict.items),
                expected=waiting.get("items"),
            )
        )
    run = _run_id(project, work)
    issues = [i.text for i in verdict.issues]
    runlog.review(
        project,
        work,
        run,
        model or str(project.profile.get("build.review_model") or ""),
        len(verdict.items),
        issues,
        sum(not EVIDENCE.search(t) for t in issues),
        source,
    )
    done = rounds(project, work)
    if standing(project, work) in ("clean", "limit"):
        _retro(project, work)
    return done[-1]


def _retro(project: Project, work_id: str) -> None:
    """Ask for the retro row of a review that ended; the retro is optional, so nothing in it stops the review."""
    import sys

    from ..report import retro

    try:
        retro.record(project, work_id)
    except Exception as e:  # noqa: BLE001  the retro is optional: whatever goes wrong in it, the review goes on
        print(msg("⚠ The AI retro could not be written: {problem}", problem=e), file=sys.stderr)


def doubts(project: Project, work_id: str) -> list[str]:
    """Say at archive where a work that asked for a review was not reviewed, or was left with issues.

    Args:
        project: The project.
        work_id: E.g. "W-012".

    Returns:
        Warning lines; empty when `build.review` is off or the review is clean.

    Example:
        >>> doubts(project, "W-012")  # doctest: +SKIP
        ['⚠ build.review is on but nobody reviewed W-012']
    """
    if project.profile.get("build.review") != "on":
        return []
    state = standing(project, work_id)
    out: list[str] = []
    if state == "none":
        return [msg("⚠ build.review is on but nobody reviewed {work_id}", work_id=work_id)]
    if state in ("open", "limit"):
        out.append(msg("⚠ The review of {work_id} left {count} issues", work_id=work_id, count=rounds(project, work_id)[-1].issues))
    if any(r.source == "cli" for r in rounds(project, work_id)) and _has_reviewer_file(project):
        out.append(msg("⚠ A round of {work_id} was recorded by hand although the reviewer's hook was installed", work_id=work_id))
    return out


def _has_reviewer_file(project: Project) -> bool:
    """Whether a tool of this project got the reviewer's definition, so that its hook could have recorded the rounds."""
    from ..tools import REGISTRY

    return any((project.root / rel).exists() for tool in REGISTRY.values() for rel in tool.agent_files(project.profile))


# --------------------------------------------------------------------------- the pack


def _base(project: Project, work_id: str) -> str:
    """Where the work started: the commit its loop started from, else where the branch left the base branch."""
    start = loop.last_start(project, work_id)
    if start and start.get("base"):
        return str(start["base"])
    return git_out(["merge-base", "HEAD", str(project.profile.get("git.base") or "main")], project.root)


def _diff(project: Project, base: str) -> str:
    """The code changes since the base: the stat, then the diff up to DIFF_LIMIT; files beyond it are only named."""
    skip = [f":(exclude){project.rel(project.docs)}", ":(exclude).lantern"]
    stat = git_out(["diff", "--stat", base, "--", ".", *skip], project.root)
    new = git_out(["ls-files", "--others", "--exclude-standard", "--", ".", *skip], project.root).splitlines()
    if not stat and not new:
        return ""
    names = git_out(["diff", "--name-only", base, "--", ".", *skip], project.root).splitlines()
    shown, left = [], []
    size = 0
    for name in names:
        piece = git_out(["diff", base, "--", name], project.root)
        if size + len(piece) > DIFF_LIMIT:  # even the first file is cut: one huge file (a lock file) must not empty the limit
            left.append(name)
            piece = piece[: max(DIFF_LIMIT - size, 0)] if not shown else ""
        if piece:
            shown.append(piece)
            size += len(piece)
    text = (f"```\n{stat}\n```\n\n```diff\n" + "\n".join(shown) + "\n```") if stat else ""
    if left:
        text += "\n\n" + msg("The diff is too big to put here. Read these files yourself (`git diff {base} -- <file>`):", base=base)
        text += "\n" + "\n".join(f"- {n}" for n in left)
    if new:
        text += "\n\n" + msg("These new files are not added to git yet, so they are not in the diff. Read them yourself:")
        text += "\n" + "\n".join(f"- {n}" for n in new)
    return text.strip()


def _doc(path: Path) -> str:
    return strip_guides(read(path))[:DOC_LIMIT] if path.exists() else ""


def _test_result(project: Project, work_id: str) -> str:
    """The test result the pack carries: the last round of the work's loop, else a run of `build.test` now."""
    ends = [r for r in loop.last_run(project, work_id) if r.get("event") == "end"]
    if ends:
        r = ends[-1]
        return msg(
            "The last round of the loop: {result} (the whole suite exited {code}; {count} tests ran)",
            result=r.get("result"),
            code=r.get("exit"),
            count=r.get("tests_after") if r.get("tests_after") is not None else "?",
        )
    cmd = project.profile.get("build.test")
    if not cmd:
        return msg("There is no test command (build.test), so no test result")
    code, out = loop.run_command(project, str(cmd))
    return msg("`{cmd}` exited {code}", cmd=cmd, code=code) + "\n\n```\n" + "\n".join(out.strip().split("\n")[-15:]) + "\n```"


def build_pack(project: Project, work_id: str) -> tuple[str, int]:
    """Write the text of a review pack: the items to judge, the documents they come from, the diff and the test result.

    Items come from the documents; an item whose document is missing is left out. The pack carries neither the
    conversation that built the work nor its tries.

    Args:
        project: The project.
        work_id: A work in progress, e.g. "W-012".

    Returns:
        The pack as Markdown, and how many items it asks the reviewer to judge.

    Raises:
        ValueError: The work is not in progress, or nothing changed since it started.

    Example:
        >>> build_pack(project, "W-012")[0].splitlines()[0]  # doctest: +SKIP
        '# Review pack — W-012'
    """
    folder = project.find_work(work_id, include_archive=False)
    if folder is None:
        raise ValueError(msg("Work in progress {work_id} not found", work_id=work_id))
    base = _base(project, work_id)
    diff = _diff(project, base) if base else ""
    if not diff:
        raise ValueError(msg("Nothing changed in the code since {work_id} started, so there is nothing to review", work_id=work_id))
    from ..report.principles_doc import doc_path as principles_doc_path

    plan, design = _doc(project.doc_path(folder, "plan")), _doc(project.doc_path(folder, "design"))
    principles = _doc(principles_doc_path(project))
    repo_files = _doc(project.folder("rules") / project.names.file("repo_files"))
    pass_word, issue_word = project.enums.value("review_verdict", "pass"), project.enums.value("review_verdict", "issue")
    items: list[str] = []
    for ac in parse_criteria(plan, project.names) if plan else []:
        test = f" ({msg('test')}: `{ac.test}`)" if ac.test else ""
        items.append(msg("Does the build satisfy {ac}: {text}", ac=ac.id, text=ac.text) + test)
    if plan:
        items.append(
            msg(
                "Does each test really check its criterion? Are the expected values concrete, "
                "with no skipped test and no assertion that always passes?"
            )
        )
    if design:
        items.append(msg("Is it built as the design says (structure, data, screens)?"))
    if principles:
        items.append(msg("Does it keep the development principles and the code conventions?"))
    if repo_files:
        items.append(msg("Are the files where the repository file rules put them?"))
    out = [
        msg("# Review pack — {work_id}", work_id=work_id),
        "",
        msg(
            "You did not make this change and you do not see the conversation that made it. Judge only from this pack and the files "
            "it points to. Do not edit anything."
        ),
        "",
        msg("## How to answer"),
        "",
        msg(
            "Start with `Review: {work_id}`. Then one line for every item below, in this form, and nothing else after them:",
            work_id=work_id,
        ),
        "",
        f"- [{pass_word}] R1 — {msg('what you checked')}",
        f"- [{issue_word}] R2 — path/to/file.py:12 — {msg('what is wrong')}",
        "",
        msg("Every {issue} needs the file and line it rests on (`path:line`).", issue=issue_word),
        msg(
            "An item you could not check is an {issue} too: write what you could not check where the file and line would go. "
            "It goes to the person.",
            issue=issue_word,
        ),
        "",
        msg("## Items"),
        "",
        *[f"- R{i}: {text}" for i, text in enumerate(items, start=1)],
    ]
    for title, body in (
        (msg("## Plan"), plan),
        (msg("## Design"), design),
        (msg("## Development principles"), principles),
        (msg("## Repository file rules"), repo_files),
    ):
        if body:
            out += ["", title, "", body]
    out += [
        "",
        msg("## Test result"),
        "",
        _test_result(project, work_id),
        "",
        msg("## Changes since the work started ({base})", base=base[:10]),
        "",
        diff,
    ]
    return "\n".join(out) + "\n", len(items)


def pack(project: Project, work_id: str) -> Path:
    """Write the review pack of a work (`.lantern/review/W-012.md`), if the review may go on.

    Args:
        project: The project.
        work_id: A work in progress, e.g. "W-012".

    Returns:
        The pack's path.

    Raises:
        ValueError: `build.review` is off, the work was already reviewed clean, the review has no round left
            (the person decides), or there is nothing to review.

    Example:
        >>> pack(project, "W-012").name  # doctest: +SKIP
        'W-012.md'
    """
    work_id = work_id.upper()
    if project.profile.get("build.review") != "on":
        raise ValueError(msg("build.review is off, so no review is made (lantern build-mode suggest)"))
    state = standing(project, work_id)
    if state == "clean":
        raise ValueError(msg("{work_id} was reviewed and the last round found nothing", work_id=work_id))
    if state == "limit":
        raise ValueError(
            msg("{work_id} has no review round left (build.review_limit): hand the remaining issues to the person", work_id=work_id)
        )
    text, count = build_pack(project, work_id)
    path = project.state / PACK_FOLDER / f"{work_id}.md"
    write(path, text)
    if open_pack(project, work_id) is None:  # a pack asked for twice before the answer is still one round
        from ..tools import runlog

        runlog.review_pack(project, work_id, count)
    return path
