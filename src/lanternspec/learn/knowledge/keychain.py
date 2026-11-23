"""Read, store and delete one password in the macOS Keychain through the `security` command.

Responsibilities:
    - read the token a person stored (service = the name of its environment variable, account = the user)
    - store a token by letting `security` ask for it on the person's own terminal, so the token never passes through lantern
    - delete it

Not here:
    - which service name a store uses and where else a token can come from → learn/knowledge/notion.py (notion_token)
    - walking a person through getting a token → learn/knowledge/notion_setup.py

Off a Mac every call does nothing (`available()` is False), so the callers fall back to the environment variable.
"""

from __future__ import annotations

import getpass
import shutil
import subprocess
import sys

TOOL = "security"
TIMEOUT = 10  # seconds a read waits for the Keychain


def available() -> bool:
    """Say whether the macOS Keychain tool can be used here.

    Returns:
        True on macOS when the `security` command exists.

    Example:
        >>> isinstance(available(), bool)
        True
    """
    return sys.platform == "darwin" and shutil.which(TOOL) is not None


def account() -> str:
    """The Keychain account items are stored under: the user's login name.

    Returns:
        The login name.

    Example:
        >>> isinstance(account(), str)
        True
    """
    return getpass.getuser()


def read(service: str) -> str | None:
    """Read the stored password of a service.

    Args:
        service: The Keychain service name (the name of the token's environment variable).

    Returns:
        The password; None when there is none, the tool is missing, it fails or it takes too long.

    Example:
        >>> read("NO_SUCH_SERVICE")  # doctest: +SKIP
    """
    if not available():
        return None
    try:
        done = subprocess.run(
            [TOOL, "find-generic-password", "-a", account(), "-s", service, "-w"], capture_output=True, text=True, timeout=TIMEOUT
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = done.stdout.strip()
    return value if done.returncode == 0 and value else None


def store(service: str) -> bool:
    """Store a password by letting the `security` tool ask for it on the terminal (an existing item is updated).

    `-w` comes last with no value, which makes the tool prompt, so the password is neither an argument of a command nor
    ever read by this program.

    Args:
        service: The Keychain service name.

    Returns:
        True when the item was stored.

    Example:
        >>> store("X")  # doctest: +SKIP
        True
    """
    if not available():
        return False
    try:
        return subprocess.run([TOOL, "add-generic-password", "-U", "-a", account(), "-s", service, "-w"]).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def delete(service: str) -> bool:
    """Delete the stored password of a service.

    Args:
        service: The Keychain service name.

    Returns:
        True when an item was deleted.

    Example:
        >>> delete("NO_SUCH_SERVICE")  # doctest: +SKIP
    """
    if not available():
        return False
    try:
        done = subprocess.run([TOOL, "delete-generic-password", "-a", account(), "-s", service], capture_output=True, text=True)
    except (OSError, subprocess.SubprocessError):
        return False
    return done.returncode == 0
