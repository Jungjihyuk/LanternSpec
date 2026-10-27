"""`lantern` — the deterministic half of LanternSpec (P1: AI는 내용, 스크립트는 형식).

Each command group registers its own commands (cli/<group>.py, same groups as the package);
this file only assembles the parser and runs the chosen handler.
"""

from __future__ import annotations

import argparse
import sys

from .. import __version__
from . import check, core, learn, report, tools, work
from .common import CliError, Handler

GROUPS = (tools, core, work, learn, report, check)  # order of the help list


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="lantern", description="LanternSpec — 모르는 것은 밝히고, 걸어온 길은 보여 준다.")
    ap.add_argument("--version", action="version", version=f"lanternspec {__version__}")
    sub = ap.add_subparsers(dest="command", metavar="<명령>")

    def add(name: str, fn: Handler, help_: str) -> argparse.ArgumentParser:
        # internal commands (hook · task-add) stay out of the help list
        p = sub.add_parser(name) if help_ == argparse.SUPPRESS else sub.add_parser(name, help=help_, description=help_)
        p.set_defaults(fn=fn)
        return p

    for group in GROUPS:
        group.register(add)
    return ap


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # `lantern task add …` reads better than a separate command name
    if len(argv) >= 2 and argv[0] == "task" and argv[1] == "add":
        argv = ["task-add", *argv[2:]]
    parser = build_parser()
    a = parser.parse_args(argv)
    if not getattr(a, "fn", None):
        parser.print_help()
        return 0
    try:
        return a.fn(a) or 0
    except (CliError, ValueError, FileNotFoundError, FileExistsError, LookupError, RuntimeError) as e:
        print(f"✖ {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
