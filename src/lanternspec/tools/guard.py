"""`lantern guard` — start an AI tool inside an OS sandbox that keeps it out of the closed knowledge store folders.

The tool's own settings are not trusted with this: the whole process is started under the
sandbox, so its file tools, shell commands, hooks and the servers it launches are all held
by the operating system, and nothing inside can loosen the rules.

Responsibilities:
    - turn the closed folders into a macOS sandbox profile
    - replace this process with the AI tool running under that profile

Not here:
    - which folders are open (knowledge.allow · knowledge.deny) → learn/knowledge/access.py
    - what each AI tool's own settings look like → tools/<tool>.py
"""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

from ..core.messages import msg
from ..core.profile import PROFILE_FILE
from ..core.project import Project, nfc

SANDBOX = "sandbox-exec"  # macOS only; Linux needs its own launcher (bubblewrap)


class GuardError(RuntimeError):
    """The guard could not be set up, so the tool was not started; the message says why.

    Example:
        >>> str(GuardError("macOS에서만 됩니다"))
        'macOS에서만 됩니다'
    """


@dataclass(frozen=True)
class Guard:
    """What one guarded run closes, as absolute paths spelled the way the disk spells them.

    Attributes:
        vault: The knowledge store folder.
        allow: Open folders; when not empty the rest of the store is closed.
        closed: Closed folders and files (knowledge.deny, and the store's hidden entries).
        locked: Files that may be read but not changed (lantern.yaml).

    Example:
        >>> Guard(Path("/v"), closed=(Path("/v/4. Work"),)).allow
        ()
    """

    vault: Path
    allow: tuple[Path, ...] = ()
    closed: tuple[Path, ...] = ()
    locked: tuple[Path, ...] = field(default=())


def _quote(path: Path) -> str:
    """A path as a string literal of the sandbox profile language."""
    return '"' + str(path).replace("\\", "\\\\").replace('"', '\\"') + '"'


def sandbox_profile(guard: Guard) -> str:
    r"""Write the macOS sandbox profile for one guarded run.

    Everything stays allowed except the closed parts of the store. A later rule wins over an
    earlier one, so the order is: close the store, open the allowed folders, close the denied ones.

    Args:
        guard: What to close.

    Returns:
        The profile text for `sandbox-exec -p`.

    Example:
        >>> guard = Guard(Path("/v"), allow=(Path("/v/2. Study"),), closed=(Path("/v/2. Study/Exam"),), locked=(Path("/p/lantern.yaml"),))
        >>> print(sandbox_profile(guard))
        (version 1)
        (allow default)
        (deny file-read* file-write* (subpath "/v"))
        (allow file-read* file-write* (subpath "/v/2. Study"))
        (deny file-read* file-write* (subpath "/v/2. Study/Exam"))
        (deny file-write* (literal "/p/lantern.yaml"))
    """
    rules = ["(version 1)", "(allow default)"]
    if guard.allow:
        rules.append(f"(deny file-read* file-write* (subpath {_quote(guard.vault)}))")
        rules += [f"(allow file-read* file-write* (subpath {_quote(p)}))" for p in guard.allow]
    rules += [f"(deny file-read* file-write* (subpath {_quote(p)}))" for p in guard.closed]
    rules += [f"(deny file-write* (literal {_quote(p)}))" for p in guard.locked]
    return "\n".join(rules)


def plan(project: Project) -> Guard:
    """Work out what a guarded run of this project closes.

    A folder written in lantern.yaml that is not in the store stops the run: a misspelled
    name would otherwise leave that folder open without anyone noticing.

    Args:
        project: The project.

    Returns:
        The paths to close, to open and to lock.

    Raises:
        GuardError: No folder store is set up, nothing is closed, or a listed folder is missing.

    Example:
        >>> plan(project).closed  # doctest: +SKIP
        (PosixPath('/Users/me/vault/4. Work'), PosixPath('/Users/me/vault/.git'))
    """
    from ..learn.knowledge.access import Access
    from ..learn.knowledge.obsidian import on_disk

    k = project.profile.knowledge
    if not k or k["type"] not in ("obsidian", "folder"):
        raise GuardError(msg("lantern guard needs a knowledge store that is a folder (knowledge.type: obsidian | folder)"))
    access = Access.from_config(k)
    if not access.restricted:
        raise GuardError(
            msg(
                "Nothing to guard — list the folders in knowledge.allow or knowledge.deny first ({profile_file})", profile_file=PROFILE_FILE
            )
        )
    vault = Path(str(k["path"])).expanduser().resolve()
    found: dict[str, list[Path]] = {"allow": [], "deny": []}
    for key, folders in (("allow", access.allow), ("deny", access.deny)):
        for folder in folders:
            path = on_disk(vault, folder)
            if path is None:
                raise GuardError(
                    msg("knowledge.{key}: '{folder}' is not in the knowledge store ({vault})", key=key, folder=folder, vault=vault)
                )
            found[key].append(path)
    # hidden entries (.git · .obsidian …) often hold copies of the closed notes; with allow set the whole root is closed anyway
    hidden = [] if found["allow"] else sorted(vault / n for n in os.listdir(vault) if n.startswith("."))
    return Guard(
        vault=vault,
        allow=tuple(found["allow"]),
        closed=(*found["deny"], *hidden),
        locked=((project.root / PROFILE_FILE).resolve(),),
    )


def describe(guard: Guard, command: list[str]) -> list[str]:
    """Say what a guarded run opens and closes, for the person starting it.

    Args:
        guard: What the run closes.
        command: The tool's command line.

    Returns:
        Lines to print before the tool starts.

    Example:
        >>> describe(Guard(Path("/v"), closed=(Path("/v/4. Work"),)), ["claude"])[2]
        '   닫힘: 4. Work'
    """

    def names(paths: tuple[Path, ...]) -> str:
        return " · ".join(nfc(str(p.relative_to(guard.vault))) for p in paths)

    rest = msg("everything else")
    closed = " · ".join(x for x in (names(guard.closed), rest if guard.allow else "") if x)
    return [
        msg("🔒 {command} starts inside the OS sandbox — knowledge store {vault}", command=command[0], vault=guard.vault),
        msg("   open: {items}", items=names(guard.allow) if guard.allow else rest),
        msg("   closed: {items}", items=closed),
        msg("   {profile_file} can't be changed in this session", profile_file=PROFILE_FILE),
        msg("   Turn the tool's own sandbox off: macOS can't put a sandbox inside another"),
    ]


def run(project: Project, command: list[str]) -> int:
    """Replace this process with the AI tool, held by the sandbox for as long as it runs.

    Args:
        project: The project.
        command: The tool's command line, e.g. ["claude"].

    Returns:
        Never returns when the tool starts (the process becomes the tool).

    Raises:
        GuardError: The guard cannot be set up; the tool is not started unguarded.

    Example:
        >>> run(project, ["claude"])  # doctest: +SKIP
    """
    if not command:
        raise GuardError(msg("Say which tool to start: lantern guard -- claude"))
    if sys.platform != "darwin" or not shutil.which(SANDBOX):
        raise GuardError(msg("lantern guard works on macOS only for now (it uses sandbox-exec)"))
    if not shutil.which(command[0]):
        raise GuardError(msg("Command not found: {command}", command=command[0]))
    guard = plan(project)
    print("\n".join(describe(guard, command)), file=sys.stderr)
    sys.stderr.flush()
    os.execvp(SANDBOX, [SANDBOX, "-p", sandbox_profile(guard), *command])
