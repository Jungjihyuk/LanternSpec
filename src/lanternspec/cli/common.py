"""Helpers every command module shares."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Iterable

from ..core.project import Project

Handler = Callable[[argparse.Namespace], int]  # a command: parsed arguments → exit code
Add = Callable[[str, Handler, str], argparse.ArgumentParser]  # add(name, handler, help) -> its parser


class CliError(Exception):
    r"""A command was used the wrong way; `main` prints the message as one "✖" line.

    Example:
        >>> str(CliError("--work W-012 또는 --none \"이유\" 중 하나"))
        '--work W-012 또는 --none "이유" 중 하나'
    """

    pass


def _p() -> Project:
    return Project.load()


def _print(lines: str | Iterable[str]) -> None:
    if isinstance(lines, str):
        print(lines)
    else:
        for line in lines:
            print(line)


def _csv(value: str | None) -> list[str]:
    return [x.strip() for x in (value or "").split(",") if x.strip()]
