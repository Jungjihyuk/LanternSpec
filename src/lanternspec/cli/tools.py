"""AI-tool commands: install · upgrade · build-adapters · docs-mode · hook · close."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from ..core.messages import msg
from ..core.names import languages
from .common import Add, CliError, _csv, _p, _print

if TYPE_CHECKING:
    from ..core.project import Project


def cmd_install(a: argparse.Namespace) -> int:
    """`lantern install` — install skills, rules and hooks for the chosen AI tools, then show the next steps."""
    from ..tools.install import install

    project = _p()
    rep = install(
        project,
        _csv(a.tools) or None,
        force=a.force,
        mcp=True if a.mcp else None,
        ci=True if a.ci else False if a.no_ci else None,
        language=a.language,
    )
    _print(rep.lines())
    _print(_next_steps(project))
    return 0


def _next_steps(project: Project) -> list[str]:
    """What to do after installing — the command that opens each configured tool and how to call the skill."""
    from ..core import state
    from ..tools import REGISTRY, resolve

    tools = resolve(state.load(project).get("tools") or ["claude"])
    # AI tools on this computer but not set up for this project — suggest only, the person decides
    missing = [t for t in REGISTRY.values() if t not in tools and shutil.which(t.launch)]
    hint = (
        [
            "",
            msg(
                "ℹ This computer also has {items}. To use them too: lantern install --tools {items2}",
                items=" · ".join(t.label for t in missing),
                items2=",".join(t.name for t in tools + missing),
            ),
        ]
        if missing
        else []
    )
    if project.profile.exists:
        return ["", msg("Next: carry on in the AI tool (where things stand: lantern status)"), *hint]
    if len(tools) == 1:
        opens = msg("open {label} — type `{launch}` in a terminal", label=tools[0].label, launch=tools[0].launch)
    else:
        opens = msg("Open the AI tool — ") + ", ".join(msg("{label}: `{launch}`", label=t.label, launch=t.launch) for t in tools)
    others = [
        msg("in {label}, `{command_prefix}l-init`", label=t.label, command_prefix=t.command_prefix)
        for t in tools
        if t.command_prefix != "/"
    ]
    return [
        "",
        msg("Next steps"),
        msg("  1. In this folder, {opens}", opens=opens),
        msg("  2. Type `/l-init` in the prompt")
        + (f" ({', '.join(others)})" if others else "")
        + msg(" — answer a few questions and the document layout and settings are made"),
        *hint,
    ]


def cmd_upgrade(a: argparse.Namespace) -> int:
    """`lantern upgrade` — refresh what install wrote and unedited template copies; move documents to the current layout (--apply)."""
    from ..check.layout import LayoutError
    from ..tools.install import upgrade

    try:
        _print(upgrade(_p(), force=a.force, apply=a.apply).lines())
    except LayoutError as e:
        raise CliError(str(e)) from e
    return 0


def cmd_build_adapters(a: argparse.Namespace) -> int:
    """`lantern build-adapters` — write every tool's skill files into a folder, without installing."""
    from ..core.project import write
    from ..tools import NAMES, resolve
    from ..tools.skills import generate

    project = _p()
    files = generate(project.profile, resolve(_csv(a.tools) or NAMES), project.enums)
    out = Path(a.out)
    for rel, text in files.items():
        write(out / rel, text)
    print(msg("✔ Created {count} files in {out} (install with lantern install)", count=len(files), out=out))
    return 0


def cmd_docs_mode(a: argparse.Namespace) -> int:
    """`lantern docs-mode local|shared` — switch how documents are stored."""
    from ..tools import docs_mode

    project = _p()
    fn = docs_mode.to_local if a.mode == "local" else docs_mode.to_shared
    _print(fn(project, commit=not a.no_commit))
    return 0


def cmd_hook(a: argparse.Namespace) -> int:
    """`lantern hook <event>` (internal) — handle an agent or git hook; never stops the agent."""
    from ..check import githooks
    from ..tools import agent_hooks, get

    project = _p()
    name = a.name
    if name == "git-commit-msg":
        return githooks.commit_msg(project, a.args[0])
    if name == "git-pre-commit":
        return githooks.pre_commit(project)
    if name == "git-pre-push":
        return githooks.pre_push(project, a.args[0] if a.args else "", a.args[1] if len(a.args) > 1 else "", sys.stdin.read())
    if name not in agent_hooks.HANDLERS:
        raise CliError(msg("Unknown hook: {name}", name=name))
    tool = get(a.agent)
    try:
        reply = agent_hooks.run(project, name, tool, sys.stdin.read() if not sys.stdin.isatty() else "")
    except Exception as e:  # an agent hook must never break the agent
        print(msg("LanternSpec hook {name} error: {e}", name=name, e=e), file=sys.stderr)
        return 0
    if reply.stdout:
        print(reply.stdout)
    if reply.stderr:
        print(reply.stderr, file=sys.stderr)
    return reply.code


def cmd_close(a: argparse.Namespace) -> int:
    """`lantern close <skill>` — every skill's common close: check → map → debt status → run record."""
    from ..tools import close

    _print(close.close(_p(), a.skill, work=a.work, start=a.start, model=a.model, check=not a.no_check, do_map=not a.no_map))
    return 0


def register(add: Add) -> None:
    """Register the AI-tool commands."""
    p = add("install", cmd_install, msg("Install skills · rules · agent hooks into the AI tool folders (before /l-init)"))
    p.add_argument("--tools", help=msg("claude,codex,antigravity (default claude)"))
    p.add_argument("--force", action="store_true", help=msg("Overwrite files the user edited too"))
    p.add_argument("--mcp", action="store_true", help=msg("Also register the knowledge connector MCP server (lantern mcp)"))
    p.add_argument("--language", choices=languages(), help=msg("Language of skills · rules · documents (first install only, default ko)"))
    ci = p.add_mutually_exclusive_group()
    ci.add_argument(
        "--ci",
        action="store_true",
        help=msg("Also check in GitHub Actions: formats · lint · type check · acceptance tests (with project tool setup)"),
    )
    ci.add_argument("--no-ci", action="store_true", help=msg("Turn off the GitHub Actions check (removes the workflow file if unedited)"))
    p = add("upgrade", cmd_upgrade, msg("Regenerate for a new version · a changed lantern.yaml (edited files are skipped)"))
    p.add_argument("--force", action="store_true")
    p.add_argument("--apply", action="store_true", help=msg("Move documents to the current layout (git mv · links · one commit)"))
    p = add("build-adapters", cmd_build_adapters, msg("Only write each tool's skill files to a folder (preview)"))
    p.add_argument("--out", required=True)
    p.add_argument("--tools")
    p = add("docs-mode", cmd_docs_mode, msg("Change document storage (shared ↔ local)"))
    p.add_argument("mode", choices=["local", "shared"])
    p.add_argument("--no-commit", action="store_true")
    p = add("hook", cmd_hook, argparse.SUPPRESS)
    p.add_argument("name")
    p.add_argument("args", nargs="*")
    p.add_argument("--agent", default="claude", help="claude | codex | antigravity")
    p = add("close", cmd_close, msg("Common skill wrap-up: check → map → run record"))
    p.add_argument("skill")
    p.add_argument("--work")
    p.add_argument("--start")
    p.add_argument("--model")
    p.add_argument("--no-check", action="store_true")
    p.add_argument("--no-map", action="store_true")
