"""`lantern guard` — start an AI tool inside an OS sandbox that keeps it out of the closed knowledge store folders.

The tool's own settings are not trusted with this: the whole process is started under the
sandbox, so its file tools, shell commands, hooks and the servers it launches are all held
by the operating system, and nothing inside can loosen the rules.

Responsibilities:
    - turn the closed folders into the rules of this OS's sandbox (macOS sandbox-exec · Linux bubblewrap)
    - replace this process with the AI tool running under those rules

Not here:
    - which folders are open (knowledge.allow · knowledge.deny) → learn/knowledge/access.py
    - the options a tool needs to run inside the sandbox → tools/<tool>.py (guarded_command)
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from ..core.messages import msg
from ..core.profile import PROFILE_FILE
from ..core.project import Project, nfc

MACOS_SANDBOX = "sandbox-exec"
LINUX_SANDBOX = "bwrap"  # bubblewrap


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


def bwrap_args(guard: Guard) -> list[str]:
    r"""Write the bubblewrap options for one guarded run on Linux.

    The whole file system stays as it is, and the closed parts are covered: a closed folder by an
    empty folder nobody may open or write, a closed file by an empty one, a locked file by a
    read-only copy of itself. With allow set the store is covered and the open folders are put back.
    A later mount lies on top of an earlier one, so the order is the same as on macOS.

    Args:
        guard: What to close.

    Returns:
        The options to put between `bwrap` and `--`.

    Example:
        >>> guard = Guard(Path("/v"), allow=(Path("/v/2. Study"),), closed=(Path("/v/2. Study/Exam"),), locked=(Path("/p/lantern.yaml"),))
        >>> print(shlex.join(bwrap_args(guard)).replace(" --", "\n--"))
        --dev-bind / /
        --tmpfs /v
        --bind '/v/2. Study' '/v/2. Study'
        --chmod 0111 /v
        --remount-ro /v
        --tmpfs '/v/2. Study/Exam'
        --chmod 0000 '/v/2. Study/Exam'
        --remount-ro '/v/2. Study/Exam'
        --ro-bind /p/lantern.yaml /p/lantern.yaml
    """
    args = ["--dev-bind", "/", "/"]
    closed = guard.closed
    if guard.allow:
        vault = str(guard.vault)
        args += ["--tmpfs", vault]
        for path in map(str, guard.allow):
            args += ["--bind", path, path]
        args += ["--chmod", "0111", vault, "--remount-ro", vault]  # the open folders can be reached, the store can't be listed
        closed = tuple(p for p in closed if any(p.is_relative_to(a) for a in guard.allow))  # the rest is covered already
    for path in closed:
        if path.is_file():
            args += ["--ro-bind", "/dev/null", str(path)]
        else:
            args += ["--tmpfs", str(path), "--chmod", "0000", str(path), "--remount-ro", str(path)]
    for path in map(str, guard.locked):
        args += ["--ro-bind", path, path]
    return args


def launcher(guard: Guard, platform: str = sys.platform) -> list[str]:
    """Build the command that starts a program inside this OS's sandbox; the program follows it.

    Args:
        guard: What to close.
        platform: `sys.platform` of the computer.

    Returns:
        The sandbox program and its options.

    Raises:
        GuardError: The OS has no sandbox the guard knows.

    Example:
        >>> launcher(Guard(Path("/v"), closed=(Path("/v/4. Work"),)), "linux")[:4]
        ['bwrap', '--dev-bind', '/', '/']
        >>> launcher(Guard(Path("/v")), "darwin")[:2]
        ['sandbox-exec', '-p']
    """
    if platform == "darwin":
        return [MACOS_SANDBOX, "-p", sandbox_profile(guard)]
    if platform.startswith("linux"):
        return [LINUX_SANDBOX, *bwrap_args(guard), "--"]
    raise GuardError(msg("lantern guard works on macOS and Linux only"))


def nests(platform: str = sys.platform) -> bool:
    """Tell whether a tool can start its own sandbox inside this OS's guard.

    macOS can't put a sandbox inside another; Linux namespaces can be nested.

    Args:
        platform: `sys.platform` of the computer.

    Returns:
        True on Linux.

    Example:
        >>> nests("darwin"), nests("linux")
        (False, True)
    """
    return platform != "darwin"


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


def describe(guard: Guard, command: list[str], started: list[str] | None = None, nested: bool = False) -> list[str]:
    """Say what a guarded run opens and closes, for the person starting it.

    Args:
        guard: What the run closes.
        command: The tool's command line as typed.
        started: The command line actually started, when the tool's adapter added options to it.
        nested: Whether the tool's own sandbox can run inside the guard (see nests).

    Returns:
        Lines to print before the tool starts.

    Example:
        >>> describe(Guard(Path("/v"), closed=(Path("/v/4. Work"),)), ["claude"])[2]
        '   닫힘: 4. Work'
        >>> describe(Guard(Path("/v")), ["codex"], ["codex", "--no-daemon"])[-1]
        '   codex에 더한 옵션: --no-daemon (OS 샌드박스 안에서 돌게)'
    """

    def names(paths: tuple[Path, ...]) -> str:
        return " · ".join(nfc(str(p.relative_to(guard.vault))) for p in paths)

    rest = msg("everything else")
    closed = " · ".join(x for x in (names(guard.closed), rest if guard.allow else "") if x)
    added = [arg for arg in (started or command)[1:] if arg not in command[1:]]
    lines = [
        msg("🔒 {command} starts inside the OS sandbox — knowledge store {vault}", command=command[0], vault=guard.vault),
        msg("   open: {items}", items=names(guard.allow) if guard.allow else rest),
        msg("   closed: {items}", items=closed),
        msg("   {profile_file} can't be changed in this session", profile_file=PROFILE_FILE),
    ]
    if added:
        lines.append(
            msg("   Options added to {command}: {options} (to run inside the OS sandbox)", command=command[0], options=shlex.join(added))
        )
    elif not nested:
        lines.append(msg("   Turn the tool's own sandbox off: macOS can't put a sandbox inside another"))
    return lines


def adapted(command: list[str], nested: bool) -> list[str]:
    """Let the AI tool the command starts adjust it for the sandbox; other commands run as typed.

    Args:
        command: The tool's command line, e.g. ["codex"].
        nested: Whether the tool's own sandbox can run inside the guard (see nests).

    Returns:
        The command line to start.

    Example:
        >>> adapted(["codex"], nested=False)
        ['codex', '--no-daemon', '--sandbox', 'danger-full-access']
        >>> adapted(["/bin/sh", "-c", "true"], nested=False)
        ['/bin/sh', '-c', 'true']
    """
    from . import REGISTRY

    name = Path(command[0]).name
    tool = next((t for t in REGISTRY.values() if t.launch == name), None)
    return tool.guarded_command(command, nested) if tool else command


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
    if not shutil.which(command[0]):
        raise GuardError(msg("Command not found: {command}", command=command[0]))
    guard = plan(project)
    sandbox = launcher(guard)
    if not shutil.which(sandbox[0]):
        raise GuardError(msg("lantern guard needs {program}, which is not installed (Linux: the bubblewrap package)", program=sandbox[0]))
    # try the sandbox first: when it can't start, say why instead of leaving the person with its own error
    trial = subprocess.run([*sandbox, "true"], capture_output=True, text=True)
    if trial.returncode != 0:
        raise GuardError(
            msg("The OS sandbox did not start, so {command} was not started: {error}", command=command[0], error=trial.stderr.strip())
        )
    started = adapted(command, nests())
    print("\n".join(describe(guard, command, started, nests())), file=sys.stderr)
    sys.stderr.flush()
    os.execvp(sandbox[0], [*sandbox, *started])
