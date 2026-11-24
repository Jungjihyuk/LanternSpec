"""Walk a person through connecting Notion as the knowledge store: the integration, the token, the page, the settings.

Responsibilities:
    - ask how notes reach Notion and tell which permissions of the integration that needs
    - guide making the integration and connecting pages (Notion's web pages cannot be driven from here)
    - get the token into the macOS Keychain without ever receiving it (the Keychain tool asks for it on the person's terminal);
      off a Mac, check the environment variable
    - check that Notion accepts the token, show how many pages the integration sees, and check the page or database new notes go in
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
import time
import webbrowser
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Protocol

from ...core import profile as pm
from ...core.messages import msg
from ...core.project import Project
from ...core.state import ensure_state_dir
from ...core.textwidth import cut
from . import KnowledgeError, keychain, notion_database
from .notion import NotionAdapter, notion_token, page_id, token_sources

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

    def sleep(self, seconds: float) -> None:
        """Wait."""
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

    def sleep(self, seconds: float) -> None:
        """Wait."""
        time.sleep(seconds)


def _yes(answer: str) -> bool:
    return answer.strip().lower() not in ("n", "no", "아니", "아니요")


STEPS = 4
WAIT_SECONDS = 5  # the pause before looking again for a page that was just connected
WAIT_TRIES = 6  # how many times it looks again before asking the person what to do
SHOWN_TITLES = 3  # how many recently edited pages are named after the check
TITLE_CELLS = 40  # a title wider than this many terminal columns is cut, so the line stays short


def _step(io: Io, n: int, title: str) -> None:
    io.say("")
    io.say(msg("[{n}/{total}] {title}", n=n, total=STEPS, title=title))


def _write_mode(io: Io) -> str:
    _step(io, 1, msg("How notes are written"))
    io.say(msg("How should new notes reach Notion?"))
    io.say(msg("  1) draft files only; you move them in yourself (a safe start)"))
    io.say(msg("  2) create a new page or row in Notion right after you approve (what exists is never changed)"))
    while True:
        answer = io.ask(msg("▶ Choose 1 or 2 [1]: ")).strip() or "1"
        if answer in WRITE_MODES:
            return WRITE_MODES[answer]


def _guide(io: Io, mode: str) -> None:
    on = msg("Read content · Insert content") if mode == "direct" else msg("Read content")
    off = (
        msg("Update content · comments · user information · agent features")
        if mode == "direct"
        else msg("Update content · Insert content · comments · user information · agent features")
    )
    _step(io, 2, msg("Make an integration in Notion"))
    io.say(msg("Your browser opens. Do these in order:"))
    io.say(msg("  ① Address: {url}", url=INTEGRATIONS_URL))
    io.say(msg('     → click "New integration"'))
    io.say(msg("     → give it a name (e.g. LanternSpec) and pick your workspace"))
    io.say(msg("        (you must be the workspace's owner)"))
    io.say(msg('  ② "Configuration" tab → capabilities'))
    io.say(msg("     turn ON:  {on}", on=on))
    io.say(msg("     turn OFF: {off}", off=off))
    io.say(msg("  ③ On the same tab, show the token and copy it"))
    io.say(msg("  ④ Open a page (or database) whose notes you want searched,"))
    io.say(msg('     then ••• → "Add connections" → pick your integration'))
    io.say(msg("     (only what you connect, and what is under it, can be read: connect only what you need)"))


def _get_token(io: Io, store: Any, env_name: str, env: Mapping[str, str], replace: bool = False) -> str | None:
    """Make sure a token exists and return it; None when it can't be had (a message says why)."""
    found = notion_token(env_name, store, env)
    if found and not replace:
        io.say(msg("A token for {env} is already stored.", env=env_name))
        if _yes(io.ask(msg("▶ Use it? [Y/n] (Y = keep it, n = enter a new one): "))):
            return found
    if not store.available():
        if env.get(env_name, "").strip() and not replace:
            return env[env_name].strip()
        io.say(msg("✖ No token found."))
        io.say(msg("Add this line to your shell settings, open a new terminal and run this again:"))
        io.say(f"    export {env_name}=<the token>")
        return None
    io.say(msg("Copy the token, then press Enter."))
    io.say(msg("The next prompt is the Keychain's."))
    io.say(msg("Paste the token there and press Enter (nothing is shown)."))
    io.ask(msg("▶ Press Enter when you have copied it: "))
    if not store.store(env_name):
        io.say(msg("✖ The Keychain tool did not save the token. Nothing was changed."))
        return None
    return store.read(env_name)  # the one just typed, not an older variable that would be looked at first


def _parent(io: Io, notion: Any, mode: str) -> str | None:
    """Ask for the page or database new notes go in; None when the person stops."""
    _step(io, 4, msg("Where new notes go"))
    io.say(msg("Pick one page or database where new notes will be made."))
    if mode == "direct":
        io.say(msg("  · A page: each note you approve becomes a new page under it."))
        io.say(msg("  · A database: each note you approve becomes a new row of it."))
        io.say(msg("  · Existing pages and rows are never changed."))
    else:
        io.say(msg("  · It isn't used while you only write drafts, but you'll"))
        io.say(msg("    need it when you switch to writing, so decide now."))
    io.say(msg("  · Anything the integration can see will do (it must be connected)."))
    io.say(msg("  · How: open it in Notion → Share → Copy link → paste it here."))
    while True:
        ref = io.ask(msg("▶ Page or database link: ")).strip()
        pid = page_id(ref)
        if not ref or not _ID.fullmatch(pid):
            io.say(msg("That doesn't look like a page link (it ends with 32 letters and digits)."))
            continue
        if notion.can_see(pid):
            return pid
        try:
            database = notion.database(pid)
        except KnowledgeError as e:
            io.say(f"✖ {cut(str(e), 100)}")
            continue
        if database:
            _tell_database(io, database)
            return pid
        io.say(msg("✖ The integration can't see it. Open it → ••• → Add connections → pick your integration."))
        if not _yes(io.ask(msg("▶ Try again? [Y/n]: "))):
            return None


def _tell_database(io: Io, database: dict[str, Any]) -> None:
    """Say which database it is, that notes become rows, and which properties can be filled."""
    title = "".join(str(r.get("plain_text") or "") for r in database.get("title") or []).strip() or msg("(untitled)")
    names = ", ".join(p.name for p in notion_database.fillable(database))
    io.say(msg("✔ Database “{title}”: each note becomes a new row.", title=cut(title, TITLE_CELLS)))
    if names:
        io.say(msg("   Properties that can be filled: {names}", names=cut(names, TITLE_CELLS)))


def _differs(store: Any, env_name: str, env: Mapping[str, str]) -> bool:
    """Whether the environment variable and the Keychain hold different tokens (the Keychain's is the one used)."""
    from_env, from_keychain = token_sources(env_name, store, env)
    return bool(from_env and from_keychain and from_env != from_keychain)


def _explain_rejection(io: Io, error: KnowledgeError) -> None:
    """Say in plain words why Notion refused, without its raw answer."""
    status = int(getattr(error, "status", 0))
    if status == 401:
        io.say(msg("✖ Notion did not accept the token ({status}).", status=status))
        io.say(msg("  · Check that the whole token was pasted."))
        io.say(msg("  · A token of an integration you deleted or remade no longer works."))
    elif status:
        io.say(msg("✖ Notion answered with an error ({status}).", status=status))
    else:
        io.say(msg("✖ Couldn't reach Notion: {error}", error=cut(str(error), 100)))


def _wait_for_a_page(io: Io, notion: Any) -> tuple[str, int, list[str]]:
    """Look again, with pauses, until the integration shows a page (a page just connected can take a while to be listed).

    Returns:
        ("found", page count, titles) once there is a page; ("skip", 0, []) when the person goes on without waiting;
        ("stop", 0, []) when the person stops.
    """
    io.say(msg("The token works, but no page shows up yet."))
    io.say(msg("A page you just connected can take a while to show up."))
    io.say(msg('   Not connected yet? Open a page → ••• → "Add connections" → pick your integration.'))
    while True:
        for i in range(1, WAIT_TRIES + 1):
            io.sleep(WAIT_SECONDS)
            io.say(msg("   Checking again… ({i}/{n})", i=i, n=WAIT_TRIES))
            count, titles = notion.overview(SHOWN_TITLES)
            if count:
                return "found", count, titles
        answer = io.ask(msg("▶ Keep waiting (Enter), go on without it (s), or stop (q): ")).strip().lower()
        if answer == "q":
            return "stop", 0, []
        if answer == "s":
            return "skip", 0, []


def _check_token(
    io: Io, token: str, store: Any, env_name: str, env: Mapping[str, str], make_adapter: Callable[..., Any], state: Path | None
) -> Any:
    """Return the Notion connection once it accepts the token and sees a page; None when the person stops."""
    notion = make_adapter(token, state)
    replaced = False
    while True:
        try:
            count, titles = notion.overview(SHOWN_TITLES)
        except KnowledgeError as e:
            _explain_rejection(io, e)
            if replaced or not store.available() or not _yes(io.ask(msg("▶ Enter a different token now? [Y/n]: "))):
                return None
            retyped = _get_token(io, store, env_name, env, replace=True)
            if not retyped:
                return None
            replaced = True
            notion = make_adapter(retyped, state)
            continue
        if count == 0:
            outcome, count, titles = _wait_for_a_page(io, notion)
            if outcome == "stop":
                return None
            if outcome == "skip":  # the person goes on without the list: the page given next is checked on its own
                io.say(msg("ℹ Skipping the list check: the page you give next is checked directly."))
                return notion
        io.say("")
        io.say(msg("✔ Notion accepted the token."))
        io.say(msg("   Pages the integration can see: {count}", count=count))
        io.say(msg("   Most recently edited:"))
        for title in titles:
            io.say(f"     · {cut(title, TITLE_CELLS)}")
        io.say(msg("   More than you meant? Connect fewer pages in Notion (••• → Add connections)."))
        io.say(msg("   This is only a check: you don't have to connect anything more to go on."))
        if _differs(store, env_name, env):
            io.say("")
            io.say(msg("ℹ The environment variable {env} holds another token.", env=env_name))
            io.say(msg("  lantern uses the Keychain's first, so that variable is ignored."))
            io.say(msg("  Its `export` line in your shell settings can be deleted."))
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
        io.say(msg("Notion setup — about 5 minutes."))
        io.say(
            msg("⚠ The token goes only into the Keychain prompt.")
            if store.available()
            else msg("⚠ The token goes in the environment variable {env}.", env=env_name)
        )
        io.say(msg("⚠ Never paste it into a chat."))
        mode = _write_mode(io)
        _guide(io, mode)
        if open_browser:
            io.open_url(INTEGRATIONS_URL)
        _step(io, 3, msg("Token"))
        token = _get_token(io, store, env_name, environment)
        if token is None:
            return 1
        state = ensure_state_dir(project) if project.profile.exists else None
        notion = _check_token(io, token, store, env_name, environment, maker, state)
        if notion is None:
            return 1
        parent = _parent(io, notion, mode)
        if parent is None:
            return 1
        io.say("")
        _save(io, project, parent, mode)
        titles = notion.overview(1)[1]
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
