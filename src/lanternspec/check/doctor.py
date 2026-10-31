"""`lantern doctor` — does the project's real structure match lantern.yaml? One look at everything.

Checks lantern.yaml, the `lantern` command, git and its hooks, the docs storage mode, templates,
enums.yaml, the MOC, the knowledge store, installed skills, AGENTS.md, the code size and, for each
installed AI tool, its version and whether its hooks still run (tools/health.py).

Not here:
    - fixing anything — each row names the command that fixes it
"""

from __future__ import annotations

import shutil

from ..core import profile as profile_mod
from ..core import state
from ..core.messages import msg
from ..core.project import Project, git, git_version, read
from ..tools.rules import AGENTS_START
from ..tools.skills import SKILL_NAMES
from . import githooks

OK, INFO, WARN, BAD = "✔", "ℹ", "⚠", "✖"
LEVELS = {"ok": OK, "info": INFO, "warn": WARN, "bad": BAD}  # Tool.check_config levels → icons


def run(project: Project) -> list[tuple[str, str]]:
    """Check the project and return one row per check.

    Args:
        project: The project.

    Returns:
        (icon, message) rows; the icon is OK, WARN or BAD.

    Example:
        >>> run(project)[0]  # doctest: +SKIP
        ('✔', 'lantern.yaml 형식')
    """
    out: list[tuple[str, str]] = []
    p = project.profile
    if not p.exists:
        out.append((BAD, msg("No lantern.yaml — set up the project with /l-init")))
    else:
        problems = profile_mod.validate(p.data)
        out += [(BAD, f"lantern.yaml: {x}") for x in problems] or [(OK, msg("lantern.yaml format"))]
    if shutil.which("lantern"):
        out.append((OK, msg("lantern command is on PATH")))
    else:
        out.append((WARN, msg("lantern command is not on PATH — agent hooks · git hooks are skipped (uv tool install lanternspec)")))
    is_git = git(["rev-parse", "--git-dir"], project.root).returncode == 0
    if not is_git:
        out.append((WARN, msg("Not a git repository — hooks · commit links · sync won't work")))
    else:
        ver = git_version(project.root)
        if p.remote == "local" and ver < (2, 42, 0):
            out.append((BAD, msg("The local mode needs git 2.42 or later (now {items})", items=".".join(map(str, ver)))))
        structural = githooks.structure_problems(project)
        out += [(BAD, msg("Document storage ({remote}): {x}", remote=p.remote, x=x)) for x in structural] or [
            (OK, msg("Document storage {remote} — the layout is right", remote=p.remote))
        ]
        hooks = githooks.status(project)
        missing = [n for n, ok in hooks if not ok]
        if missing:
            level = BAD if p.remote == "local" and "pre-push" in missing else WARN
            out.append((level, msg("git hooks not installed: {items} — lantern hooks install", items=", ".join(missing))))
        else:
            out.append((OK, msg("git hooks installed (content check: {get})", get=p.get("git.hooks"))))
        if p.get("project.kind"):
            out.append(_code_size_row(project))
    if p.exists:
        out.append(
            (OK, msg("Templates folder exists"))
            if project.templates_dir.exists()
            else (BAD, msg("No templates folder — lantern scaffold init"))
        )
        out.append((OK, msg("enums.yaml exists")) if project.enums_file.exists() else (WARN, msg("No enums.yaml — using the defaults")))
        out += [(BAD, x) for x in project.enums.problems()]
        out.append((OK, msg("Docs MOC exists")) if project.moc.exists() else (WARN, msg("No MOC — lantern map")))
    k = p.knowledge
    if k:
        from pathlib import Path

        if k["type"] == "notion":
            import os

            env = str(k.get("token_env") or "NOTION_TOKEN")
            out.append(
                (OK, msg("Notion token {env} is set", env=env))
                if os.environ.get(env)
                else (WARN, msg("No Notion token — environment variable {env}", env=env))
            )
        else:
            path = Path(str(k["path"])).expanduser()
            out.append(
                (OK, msg("Knowledge store {path} ({type})", path=path, type=k["type"]))
                if path.exists()
                else (BAD, msg("Knowledge store path doesn't exist: {path}", path=path))
            )
    st = state.load(project)
    if not st.get("version"):
        out.append((WARN, msg("Skills are not installed — lantern install")))
    else:
        from ..tools.install import drift

        d = drift(project)
        if d["missing"]:
            out.append((WARN, msg("{count} skill files missing — lantern upgrade", count=len(d["missing"]))))
        if d["stale"]:
            out.append(
                (WARN, msg("{count} skills differ from lantern.yaml values (e.g. idea.capture) — lantern upgrade", count=len(d["stale"])))
            )
        if d["modified"]:
            out.append(
                (
                    WARN,
                    msg("{count} skills edited by the user (upgrade skips them): ", count=len(d["modified"]))
                    + ", ".join(d["modified"][:3]),
                )
            )
        if not any(d.values()):
            out.append((OK, msg("{count} skills up to date ({items})", count=len(SKILL_NAMES), items=", ".join(st.get("tools") or []))))
        agents = project.root / "AGENTS.md"
        if not agents.exists() or AGENTS_START not in read(agents):
            out.append((WARN, msg("AGENTS.md has no LanternSpec rules — lantern upgrade")))
        out += _part_rows(project)
        out += _budget_rows(project, list(st.get("tools") or []))
        out += _tool_rows(project, list(st.get("tools") or []))
    return out


def _part_rows(project: Project) -> list[tuple[str, str]]:
    """Ask about undecided part candidates, and point out folder AGENTS.md files some tools never get."""
    from ..tools import REGISTRY
    from ..tools.parts import statuses, unseen_rules

    out = []
    found = statuses(project)
    open_ = [s.path for s in found if s.state == "new"]
    if open_ and sum(1 for s in found if s.state in ("added", "new")) >= 2:
        out.append(
            (
                WARN,
                msg(
                    "Sub-projects that could get their own rules (parts), not decided yet: {items} — lantern parts", items=", ".join(open_)
                ),
            )
        )
    tools = [REGISTRY[n] for n in state.load(project).get("tools") or [] if n in REGISTRY]
    unseen, blind = unseen_rules(project, tools)
    if unseen:
        out.append((WARN, unseen_note(unseen, blind)))
    return out


def unseen_note(files: list[str], tools: list[str]) -> str:
    """Say which folder AGENTS.md files some tools never get, and where to put what matters.

    Args:
        files: The AGENTS.md files.
        tools: The tools that won't get them.

    Returns:
        One line.

    Example:
        >>> unseen_note(["backend/app/AGENTS.md"], ["Codex"]).split(":")[0]
        'backend/app/AGENTS.md'
    """
    return msg(
        "{items}: not handed to {tools} — only the AGENTS.md right in a part's folder is; move what matters there (lantern parts)",
        items=", ".join(files),
        tools=" · ".join(tools),
    )


def _budget_rows(project: Project, names: list[str]) -> list[tuple[str, str]]:
    """Check the root and every folder's AGENTS.md against the budget the installed AI tools allow."""
    from ..tools import REGISTRY
    from ..tools.rules import AGENTS_END, nested_agents
    from .budget import check, folder_budget, root_budget

    tools = [REGISTRY[n] for n in names if n in REGISTRY]
    files = [("AGENTS.md", root_budget(tools))] + [(rel, folder_budget(tools)) for rel in nested_agents(project)]
    out = []
    for rel, budget in files:
        path = project.root / rel
        if path.exists():
            level, text = check(rel, read(path), budget, AGENTS_START, AGENTS_END)
            out.append((LEVELS[level], text))
    return out


def _tool_rows(project: Project, names: list[str]) -> list[tuple[str, str]]:
    """Check each installed AI tool: it reads our rules, its version against the checked ones, its hooks still running, odd payloads."""
    from ..tools import REGISTRY, health

    beats, odd = health.heartbeat(project), health.unexpected(project)
    out: list[tuple[str, str]] = []
    for tool in (REGISTRY[n] for n in names if n in REGISTRY):
        out += [(LEVELS[level], text) for level, text in tool.check_config(project)]
        version = health.installed_version(tool)
        verdict = health.version_verdict(tool, version) if version else ""
        if version is None:
            out.append(
                (WARN, msg("{label}: the {launch} command isn't on PATH — can't check its version", label=tool.label, launch=tool.launch))
            )
        elif verdict == "old":
            out.append(
                (
                    BAD,
                    msg(
                        "{label} {version} is older than {min} — update it (some features won't work)",
                        label=tool.label,
                        version=version,
                        min=tool.min_version,
                    ),
                )
            )
        elif verdict == "new":
            out.append(
                (
                    WARN,
                    msg(
                        "{label} {version} is newer than the last checked {verified} — if hooks misbehave, the hook rows below show it",
                        label=tool.label,
                        version=version,
                        verified=tool.verified_version,
                    ),
                )
            )
        elif verdict == "ok":
            out.append(
                (
                    OK,
                    msg(
                        "{label} {version} (checked up to {verified})",
                        label=tool.label,
                        version=version,
                        verified=tool.verified_version or "-",
                    ),
                )
            )
        else:
            out.append((WARN, msg("{label}: couldn't read its version", label=tool.label)))
        mine = beats.get(tool.name)
        if not mine:
            out.append((WARN, msg("{label}: its hooks have never run in this project — open a session once to check", label=tool.label)))
        else:
            silent = health.silent_events(tool, mine)
            if silent:
                out.append(
                    (
                        WARN,
                        msg(
                            "{label}: hook {items} stopped running for {count} sessions — the tool may have "
                            "changed its hooks (lantern upgrade; if it stays, report it)",
                            label=tool.label,
                            items=", ".join(silent),
                            count=health.MISSED_STARTS,
                        ),
                    )
                )
            else:
                runs = sum(int(v.get("count") or 0) for v in (mine.get("events") or {}).values())
                out.append((OK, msg("{label}: hooks running ({count} runs)", label=tool.label, count=runs)))
        calls = [c for c in odd if c.get("tool") == tool.name]
        if calls:
            last = calls[-1]
            out.append(
                (
                    WARN,
                    msg(
                        "{label}: {count} hook calls came without {items} (latest {at}, {event}) — its payload format may have changed",
                        label=tool.label,
                        count=len(calls),
                        items=", ".join(last.get("missing") or []),
                        at=last.get("at", "?"),
                        event=last.get("event", "?"),
                    ),
                )
            )
    return out


def _code_size_row(project: Project) -> tuple[str, str]:
    """Ask whether to raise the principles one level when the code grew past the recorded size (never lower it)."""
    from ..core import principles
    from ..report.harness import code_lines

    lines = code_lines(project, tests=False)
    now, recorded = principles.code_size(lines), str(project.profile.get("project.code_size") or principles.SIZES[0])
    label = principles.table(project.profile.language)["sizes"]["code"]
    if principles.SIZES.index(now) > principles.SIZES.index(recorded):
        return (
            WARN,
            msg(
                "The code grew to {lines:,} lines, so its size went {label} → {label2} — raise the "
                "principles a level? → lantern profile set project.code_size={now} && lantern upgrade",
                lines=lines,
                label=label[recorded]["label"],
                label2=label[now]["label"],
                now=now,
            ),
        )
    return OK, msg("Principles size: code {label} ({lines:,} lines)", label=label[recorded]["label"], lines=lines)


def format_result(rows: list[tuple[str, str]]) -> str:
    """Write doctor rows as text with a closing summary line.

    Args:
        rows: (icon, message) rows from run.

    Returns:
        One line per row, then "all fine" or the counts of problems.

    Example:
        >>> print(format_result([(OK, "lantern.yaml 형식"), (WARN, "MOC가 없습니다 — lantern map")]))
        ✔ lantern.yaml 형식
        ⚠ MOC가 없습니다 — lantern map
        ✖ 0개 · ⚠ 1개
    """
    bad = sum(1 for r in rows if r[0] == BAD)
    warn = sum(1 for r in rows if r[0] == WARN)
    lines = [f"{icon} {text}" for icon, text in rows]
    lines.append("" if not rows else (msg("✔ All good") if not bad and not warn else msg("✖ {bad} · ⚠ {warn}", bad=bad, warn=warn)))
    return "\n".join(lines).rstrip()
