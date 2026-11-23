"""Walk a person through connecting Notion as the knowledge store: the integration, the token, the page, the settings.

Responsibilities:
    - ask how notes reach Notion and tell which permissions of the integration that needs
    - guide making the integration and connecting pages (Notion's web pages cannot be driven from here)
    - get the token into the macOS Keychain without ever receiving it (the Keychain tool asks for it on the person's terminal);
      off a Mac, check the environment variable
    - check that Notion accepts the token, show how many pages the integration sees, and check the page new notes go under
    - write the `knowledge` block of lantern.yaml, or print the values for /l-init when there is no lantern.yaml yet

Not here:
    - finding the token later and searching → learn/knowledge/notion.py
    - the Keychain commands → learn/knowledge/keychain.py
    - refusing to run without a terminal → cli/learn.py

The terminal, the Keychain, the browser and Notion are passed in, so the steps are tested without any of them.
"""

from __future__ import annotations

import os
import re
import webbrowser
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Protocol

from ...core import profile as pm
from ...core.messages import msg
from ...core.project import Project
from ...core.state import ensure_state_dir
from . import KnowledgeError, keychain
from .notion import NotionAdapter, notion_token, page_id

INTEGRATIONS_URL = "https://app.notion.com/developers/connections"  # where integrations are made (from Notion's docs)
WRITE_MODES = {"1": "propose_only", "2": "direct"}
_ID = re.compile(r"[0-9a-fA-F]{32}")


class Io(Protocol):
    """What the wizard needs of a terminal and a browser."""

    def ask(self, prompt: str) -> str:
        """Show a prompt and return the line typed."""
        ...

    def say(self, text: str) -> None:
        """Print a line."""
        ...

    def open_url(self, url: str) -> object:
        """Open an address in the browser."""
        ...


class TerminalIo:
    """The real terminal and browser.

    Example:
        >>> TerminalIo().say("안녕")
        안녕
    """

    def ask(self, prompt: str) -> str:
        """Show a prompt and return the line typed."""
        return input(prompt)

    def say(self, text: str) -> None:
        """Print a line."""
        print(text)

    def open_url(self, url: str) -> object:
        """Open an address in the browser."""
        return webbrowser.open(url)


def _yes(answer: str) -> bool:
    return answer.strip().lower() not in ("n", "no", "아니", "아니요")


def _write_mode(io: Io) -> str:
    io.say(msg("How should new notes reach Notion?"))
    io.say(msg("  1) draft files only, and you move them in yourself (a safe start)"))
    io.say(msg("  2) written to Notion right after you approve them"))
    while True:
        answer = io.ask(msg("Choose 1 or 2 [1]: ")).strip() or "1"
        if answer in WRITE_MODES:
            return WRITE_MODES[answer]


def _guide(io: Io, mode: str) -> None:
    caps = msg("Read content · Insert content") if mode == "direct" else msg("Read content")
    io.say("")
    io.say(msg("Do this in Notion (it opens in your browser):"))
    io.say(
        msg(
            "  1. {url} → New integration. Name it (for example LanternSpec) and pick your workspace (you must be its owner).",
            url=INTEGRATIONS_URL,
        )
    )
    io.say(
        msg(
            "  2. Configuration tab → capabilities: turn on only {caps}. "
            "Turn off the rest (update content · comments · user information · agent).",
            caps=caps,
        )
    )
    io.say(msg("  3. On the same tab, show the token and copy it."))
    io.say(msg("  4. Open the page or database whose notes should be searched → ••• → Add connections → pick your integration."))
    io.say(msg("     Only what you connect, and what is under it, can be seen. Connect as little as you need."))
    io.say("")


def _get_token(io: Io, store: Any, env_name: str, env: Mapping[str, str], replace: bool = False) -> str | None:
    """Make sure a token exists and return it; None when it can't be had (a message says why)."""
    found = notion_token(env_name, store, env)
    if found and not replace:
        if _yes(io.ask(msg("A token for {env} is already there. Use it? [Y/n]: ", env=env_name))):
            return found
    if not store.available():
        if env.get(env_name, "").strip() and not replace:
            return env[env_name].strip()
        io.say(msg("✖ No token found. Add it to your shell settings, open a new terminal and run this again:"))
        io.say(f"    export {env_name}=<the token>")
        return None
    io.ask(msg("Press Enter when you have copied the token. The next prompt is the Keychain's: paste the token there (nothing is shown): "))
    if not store.store(env_name):
        io.say(msg("✖ The Keychain tool did not save the token. Nothing was changed."))
        return None
    return notion_token(env_name, store, env)


def _parent_page(io: Io, notion: Any) -> str | None:
    io.say(msg("Where should new notes be made? In Notion open that page, copy its link and paste it here (a link is not a secret)."))
    while True:
        ref = io.ask(msg("Page link: ")).strip()
        pid = page_id(ref)
        if not ref or not _ID.fullmatch(pid):
            io.say(msg("That doesn't look like a page link (it ends with 32 letters and digits)."))
            continue
        if notion.can_see(pid):
            return pid
        io.say(msg("✖ The integration can't see that page. Open it → ••• → Add connections → pick your integration."))
        if not _yes(io.ask(msg("Try again? [Y/n]: "))):
            return None


def _check_token(io: Io, store: Any, env_name: str, env: Mapping[str, str], make_adapter: Callable[..., Any], state: Path | None) -> Any:
    """Return the Notion connection once it accepts the token and sees a page; None when the person stops."""
    token = notion_token(env_name, store, env)
    if not token:
        return None
    notion = make_adapter(token, state)
    replaced = False
    while True:
        try:
            count, titles = notion.overview()
        except KnowledgeError as e:
            io.say(msg("✖ Notion did not accept the token ({error}).", error=str(e)))
            if replaced or not store.available() or not _yes(io.ask(msg("Enter a different token now? [Y/n]: "))):
                return None
            token, replaced = _get_token(io, store, env_name, env, replace=True), True
            if not token:
                return None
            notion = make_adapter(token, state)
            continue
        if count == 0:
            io.say(
                msg(
                    "The token works, but the integration can't see any page yet. "
                    "Open a page → ••• → Add connections → pick your integration."
                )
            )
            if io.ask(msg("Press Enter after connecting a page (q to stop): ")).strip().lower() == "q":
                return None
            continue
        io.say(
            msg(
                "✔ Notion accepts the token. The integration can see {count} page(s); the newest: {titles}",
                count=count,
                titles=" · ".join(titles),
            )
        )
        io.say(msg("  If that is more than you meant, connect fewer pages (••• → Add connections): what is connected is what can be read."))
        return notion


def run(
    project: Project,
    io: Io,
    *,
    store: Any = keychain,
    make_adapter: Callable[..., Any] | None = None,
    env: Mapping[str, str] | None = None,
    open_browser: bool = True,
) -> int:
    """Connect Notion: guide, get the token, check it, ask for the page, save the settings.

    Nothing is written to lantern.yaml until every step has worked, so stopping part way leaves it as it was.

    Args:
        project: The project.
        io: The terminal and browser.
        store: Where tokens are kept (the keychain module; tests pass a fake).
        make_adapter: Makes the Notion connection from a token and a folder for the kept list; the real adapter when None.
        env: The environment; the process's own when None.
        open_browser: Open the integrations page for the person.

    Returns:
        0 when Notion is connected; 1 when it stopped (a message says why).

    Example:
        >>> run(project, TerminalIo())  # doctest: +SKIP
        0
    """
    environment = os.environ if env is None else env
    maker = make_adapter or (lambda token, state: NotionAdapter("", token, state_dir=state))
    existing = project.profile.knowledge or {}
    env_name = str(existing.get("token_env") or "NOTION_TOKEN")
    try:
        io.say(
            msg("Notion setup — about 5 minutes. The token goes into the Keychain prompt, never into a chat.")
            if store.available()
            else msg(
                "Notion setup — about 5 minutes. On this computer the token goes in the environment variable {env}, never into a chat.",
                env=env_name,
            )
        )
        mode = _write_mode(io)
        _guide(io, mode)
        if open_browser:
            io.open_url(INTEGRATIONS_URL)
        if _get_token(io, store, env_name, environment) is None:
            return 1
        state = ensure_state_dir(project) if project.profile.exists else None
        notion = _check_token(io, store, env_name, environment, maker, state)
        if notion is None:
            return 1
        parent = _parent_page(io, notion)
        if parent is None:
            return 1
        _save(io, project, parent, mode)
        titles = notion.overview()[1]
        if titles:
            hits = notion.search(titles[0])
            io.say(msg("✔ Searching “{title}” works: {count} page(s) found.", title=titles[0], count=len(hits)))
        return 0
    except (KeyboardInterrupt, EOFError):
        io.say("")
        io.say(msg("Stopped. lantern.yaml was not changed."))
        return 1


def _save(io: Io, project: Project, parent: str, mode: str) -> None:
    """Write the `knowledge` block (other settings of it stay), or print the values when there is no lantern.yaml yet."""
    if not project.profile.exists:
        io.say(
            msg(
                "ℹ lantern.yaml isn't there yet. "
                "/l-init makes it with: --knowledge {page} --knowledge-type notion --knowledge-write {write}",
                page=parent,
                write=mode,
            )
        )
        return
    data = pm.load(project.root).data
    knowledge = dict(data.get("knowledge") or {})
    knowledge.update({"type": "notion", "path": parent, "write": mode})
    data["knowledge"] = knowledge
    pm.save(project.root, data)
    io.say(msg("✔ Saved the knowledge settings in lantern.yaml (notion · {write}).", write=mode))
