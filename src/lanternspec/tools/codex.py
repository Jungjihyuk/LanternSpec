"""Codex — `.agents/skills` (called `$l-…`), hooks in `.codex/hooks.json`, permissions and MCP in `.codex/config.toml`.

Hook payloads and answers follow Claude Code's schema (checked against codex 0.164), so the
protocol comes from claude.ClaudeHooks; only what differs is written here.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..core.messages import msg
from ..core.project import Project, git_out, read, write
from .base import MCP_NAME, HookInput, HookReply, Tool, Turn, jsonl_records, merge_json_file, replace_hook_entries
from .claude import ClaudeHooks, hook_specific_output

if TYPE_CHECKING:
    from ..core.profile import Profile
    from .skills import SkillSource

PATCH_FILE = re.compile(r"^\*\*\* (?:Add|Update) File: (.+)$", re.M)
INJECTED = ("# AGENTS.md", "<")  # starts of text Codex adds to user messages itself (AGENTS.md, environment context)
WORKTREE_PROFILE = "lantern-worktree"
PROJECT_PROFILE = "lantern"
# what a session may do with a repository's git folder: commit and merge, but not change its hooks or settings
GIT_ACCESS = {"": "write", "hooks": "read", "config": "read"}


def git_access(git_dir: str) -> dict[str, str]:
    """Map a git folder and its protected parts to the access our permission profiles give them.

    Args:
        git_dir: The git folder, absolute (`/repo/.git`) or relative to the project root (`.git`).

    Returns:
        Path → "write" or "read".

    Example:
        >>> git_access(".git")
        {'.git': 'write', '.git/hooks': 'read', '.git/config': 'read'}
    """
    return {f"{git_dir}/{part}" if part else git_dir: level for part, level in GIT_ACCESS.items()}


class Codex(ClaudeHooks, Tool):
    """The Codex adapter.

    Manual-only skills get `agents/openai.yaml` that turns off implicit invocation;
    files written by `apply_patch` are read from the patch text.

    Example:
        >>> Codex().command_prefix
        '$'
    """

    name = "codex"
    label = "Codex"
    launch = "codex"
    skill_root = ".agents/skills"
    command_prefix = "$"
    config_paths = (".agents/", ".codex/")
    write_tools = frozenset({"apply_patch"})
    verified_version = "0.164.0"
    rules_chain_max_bytes = 32 * 1024  # project_doc_max_bytes: the AGENTS.md files from root to working folder together
    hook_context_max_tokens = 8000  # we set additionalContextLimit (its default 2500 would cut a folder's rules)
    restores_after_compaction = True  # SessionStart with source compact
    model_prefixes = ("gpt-", "codex", "o3", "o4")

    def skill_extras(self, src: SkillSource, profile: Profile) -> dict[str, str]:
        r"""Implement Tool.skill_extras: keep manual-only skills out of implicit (model-chosen) invocation.

        Args:
            src: The skill source.
            profile: The project's settings.

        Returns:
            `agents/openai.yaml` for manual-only skills; nothing otherwise.

        Example:
            >>> Codex().skill_extras(src, profile)  # doctest: +SKIP
            {'agents/openai.yaml': 'policy:\n  allow_implicit_invocation: false\n'}
        """
        if src.manual_only(profile):  # keep the skill out of implicit (model-chosen) invocation
            return {"agents/openai.yaml": "policy:\n  allow_implicit_invocation: false\n"}
        return {}

    def written_paths(self, inp: HookInput) -> list[str]:
        r"""Implement Tool.written_paths, adding the files named in an `apply_patch` patch.

        Args:
            inp: The hook call.

        Returns:
            The written paths.

        Example:
            >>> Codex().written_paths(HookInput(tool_input={"input": "*** Update File: docs/a.md\n"}))
            ['docs/a.md']
        """
        paths = super().written_paths(inp)
        for v in inp.tool_input.values():  # apply_patch carries the patch text
            if isinstance(v, str) and "*** " in v:
                paths += [m.strip() for m in PATCH_FILE.findall(v)]
        return paths

    def read_transcript(self, path: Path) -> list[Turn] | None:
        r"""Implement Tool.read_transcript for Codex's rollout JSON lines (`response_item` · `event_msg`).

        Codex shares Claude Code's hook payload but not its transcript. Text Codex adds to user
        messages itself (AGENTS.md, environment context) is left out. User messages were seen in a
        real rollout; assistant messages and tool calls follow Codex's documented item types
        (`message` · `function_call` · `custom_tool_call`), and the final answer of a turn
        (`task_complete`) fills in when no assistant message was kept.

        Args:
            path: The transcript file.

        Returns:
            The messages, oldest first.

        Example:
            >>> Codex().read_transcript(Path("…/rollout-….jsonl"))[0].role  # doctest: +SKIP
            'user'
        """
        turns: list[Turn] = []
        for d in jsonl_records(path):
            item = d.get("payload")
            item = item if isinstance(item, dict) else {}
            kind, at = item.get("type"), str(d.get("timestamp") or "")
            if d.get("type") == "response_item" and kind == "message" and item.get("role") in ("user", "assistant"):
                raw_parts = item.get("content")
                parts = raw_parts if isinstance(raw_parts, list) else []
                texts = [str(c.get("text") or "") for c in parts if isinstance(c, dict)]
                texts = [t for t in texts if t.strip() and not (item.get("role") == "user" and t.lstrip().startswith(INJECTED))]
                if texts:
                    turns.append(Turn(str(item["role"]), "\n".join(texts).strip(), at=at))
            elif d.get("type") == "response_item" and kind in ("function_call", "custom_tool_call", "local_shell_call"):
                raw = item.get("input") or item.get("arguments") or ""
                name = str(item.get("name") or kind)
                if not turns or turns[-1].role != "assistant":
                    turns.append(Turn("assistant", "", at=at))
                turns[-1].tools.append(name)
                if isinstance(raw, str):
                    turns[-1].files += [m.strip() for m in PATCH_FILE.findall(raw)]
            elif d.get("type") == "event_msg" and kind == "task_complete" and isinstance(item.get("last_agent_message"), str):
                if not turns or turns[-1].role != "assistant" or not turns[-1].text:
                    turns.append(Turn("assistant", item["last_agent_message"].strip(), at=at))
        return turns

    def session_context_reply(self, text: str) -> HookReply:
        """Answer session-start in hookSpecificOutput form (Codex does not take plain stdout as context).

        Args:
            text: The text to add.

        Returns:
            The reply.

        Example:
            >>> "SessionStart" in Codex().session_context_reply("안내").stdout
            True
        """
        return HookReply(stdout=hook_specific_output("SessionStart", text))

    def hooks(self) -> dict[str, list[dict[str, Any]]]:
        """Build our hook entries for `.codex/hooks.json`, with timeouts.

        Returns:
            Codex event → entries.

        Example:
            >>> Codex().hooks()["PostToolUse"][0]["hooks"][0]["timeout"]
            30
        """

        def entry(event: str, timeout: int, context: bool = False) -> dict[str, Any]:
            handler: dict[str, Any] = {"type": "command", "command": self.hook_command(event), "timeout": timeout}
            if context:  # only events that can add context take the limit (others make Codex warn)
                handler["additionalContextLimit"] = self.hook_context_max_tokens
            return {"hooks": [handler]}

        return {
            "SessionStart": [entry("session-start", 10, context=True)],
            "UserPromptSubmit": [entry("prompt", 10, context=True)],
            "PreToolUse": [entry("pre-tool", 10, context=True)],  # a part's rules before its first edit
            "PostToolUse": [entry("post-tool", 30, context=True)],
            "PreCompact": [entry("pre-compact", 10)],
            "Stop": [entry("stop", 10)],
        }

    def worktree_command(self, path: Path, work_id: str, merge_folder: Path) -> str:
        r"""Implement Tool.worktree_command: open Codex with a permission profile that lets git work from a worktree.

        Codex keeps a linked worktree's git folder read-only, so commits fail there. For this one
        session the profile opens what committing and merging write, and keeps the sandbox on: git
        hooks and `.git/config` stay read-only, so settings kept there can't change from inside it.

        Args:
            path: The work's worktree.
            work_id: The work, e.g. "W-012".
            merge_folder: The folder where the branch it merges into is open.

        Returns:
            The command, quoted for a shell.

        Example:
            >>> Codex().worktree_command(Path("../app-W-012"), "W-012", Path("../app"))  # doctest: +SKIP
            "codex -c 'permissions.lantern-worktree={…}' -c 'default_permissions=\"lantern-worktree\"' '$l-build W-012'"
        """

        def git_path(folder: Path, what: str) -> str:
            return git_out(["rev-parse", "--path-format=absolute", what], folder)

        access = {
            **git_access(git_path(path, "--git-common-dir")),
            git_path(path, "--git-dir"): "write",
            git_path(merge_folder, "--git-dir"): "write",
            str(merge_folder.resolve()): "write",
        }
        rules = ",".join(f"{json.dumps(k, ensure_ascii=False)}={json.dumps(v)}" for k, v in access.items())
        return shlex.join(
            [
                self.launch,
                "-c",
                f'permissions.{WORKTREE_PROFILE}={{extends=":workspace",filesystem={{{rules}}}}}',
                "-c",
                f'default_permissions="{WORKTREE_PROFILE}"',
                f"{self.command_prefix}l-build {work_id}",
            ]
        )

    def guarded_command(self, command: list[str], nested: bool) -> list[str]:
        """Implement Tool.guarded_command: run without the shared background server, and on macOS without Codex's own sandbox.

        A running Codex connects to a shared server that was started outside the guard, and its
        commands would run there unguarded. On macOS Codex's own sandbox is the system's too, which
        can't start inside another, so every shell command would fail. Options already typed are kept.

        Args:
            command: The command line as typed.
            nested: Whether Codex's own sandbox can run inside the guard's.

        Returns:
            The command line with the missing options right after `codex`.

        Example:
            >>> Codex().guarded_command(["codex", "exec", "hi"], nested=False)
            ['codex', '--no-daemon', '--sandbox', 'danger-full-access', 'exec', 'hi']
            >>> Codex().guarded_command(["codex", "-s", "read-only"], nested=False)
            ['codex', '--no-daemon', '-s', 'read-only']
            >>> Codex().guarded_command(["codex"], nested=True)
            ['codex', '--no-daemon']
        """
        typed = {arg.split("=", 1)[0] for arg in command[1:]}
        added = [] if "--no-daemon" in typed else ["--no-daemon"]
        if not nested and not typed & {"-s", "--sandbox", "--dangerously-bypass-approvals-and-sandbox"}:
            added += ["--sandbox", "danger-full-access"]
        return [command[0], *added, *command[1:]]

    def check_config(self, project: Project) -> list[tuple[str, str]]:
        """Implement Tool.check_config: warn when the user's own Codex settings turn our permission profile off.

        `sandbox_mode` in any settings file Codex loads makes it use the older sandbox settings and
        ignore `default_permissions`, so commits from a session would fail again.

        Args:
            project: The project.

        Returns:
            A warning row when the user's settings set `sandbox_mode`; nothing otherwise.

        Example:
            >>> Codex().check_config(project)  # doctest: +SKIP
            []
        """
        home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex") / "config.toml"
        try:
            data = tomllib.loads(read(home)) if home.exists() else {}
        except (tomllib.TOMLDecodeError, OSError):
            return []
        raw = data.get("profiles")
        profiles: dict[str, Any] = raw if isinstance(raw, dict) else {}
        if "sandbox_mode" in data or any(isinstance(p, dict) and "sandbox_mode" in p for p in profiles.values()):
            return [
                (
                    "warn",
                    msg(
                        "Codex: sandbox_mode in {path} makes Codex ignore the project's lantern permissions, "
                        "so commits fail — remove it to use them",
                        path=str(home),
                    ),
                )
            ]
        return []

    def install_config(self, project: Project, mcp: bool) -> list[str]:
        """Implement Tool.install_config: hooks into `.codex/hooks.json`; permissions and (when asked) MCP into `.codex/config.toml`.

        Args:
            project: The project.
            mcp: Also register the knowledge MCP server.

        Returns:
            What was merged.

        Example:
            >>> Codex().install_config(project, mcp=False)[0]  # doctest: +SKIP
            '.codex/hooks.json (에이전트 hook — Codex가 처음 실행할 때 신뢰 여부를 묻는다)'
        """
        merge_json_file(project.root / ".codex" / "hooks.json", lambda d: replace_hook_entries(d, self.hooks()))
        merged = [msg(".codex/hooks.json — agent hooks. Codex asks whether to trust them on first run")]
        path = project.root / ".codex" / "config.toml"
        text = add_permissions_toml(read(path) if path.exists() else "")
        if mcp:
            text = add_mcp_server_toml(text)
        write(path, text)
        merged.append(
            msg(
                ".codex/config.toml — permissions so a session can commit. "
                "Codex uses them only after you trust this project when it first asks"
            )
        )
        if mcp:
            merged.append(f".codex/config.toml — MCP {MCP_NAME}")
        return merged


def add_mcp_server_toml(existing_text: str) -> str:
    """Add our MCP server to `.codex/config.toml` text, unless it is already there.

    Args:
        existing_text: The current file text ("" when missing).

    Returns:
        The new text.

    Example:
        >>> print(add_mcp_server_toml(""), end="")
        [mcp_servers.lantern-knowledge]
        command = "lantern"
        args = ["mcp"]
    """
    header = f"[mcp_servers.{MCP_NAME}]"
    if header in existing_text:
        return existing_text
    block = f'{header}\ncommand = "lantern"\nargs = ["mcp"]\n'
    return (existing_text.rstrip() + "\n\n" if existing_text.strip() else "") + block


def add_permissions_toml(existing_text: str) -> str:
    r"""Add our permission profile to `.codex/config.toml` text, unless it is already there.

    Codex keeps `.git` read-only inside the project by default, so commits and merges fail. The
    profile opens `.git` and keeps its hooks and config read-only. A `default_permissions` the user
    already chose stays; the profile is then only added for them to pick.

    Args:
        existing_text: The current file text ("" when missing).

    Returns:
        The new text.

    Example:
        >>> text = add_permissions_toml("")
        >>> text.splitlines()[0]
        'default_permissions = "lantern"'
        >>> '".git" = "write"' in text and add_permissions_toml(text) == text
        True
    """
    header = f"[permissions.{PROJECT_PROFILE}]"
    text = existing_text
    if header not in text:
        block = (
            "# lantern: commits and merges write to .git; its hooks and config stay read-only\n"
            f"{header}\n"
            'extends = ":workspace"\n\n'
            f'[permissions.{PROJECT_PROFILE}.filesystem.":workspace_roots"]\n'
            + "".join(f'"{path}" = "{level}"\n' for path, level in git_access(".git").items())
        )
        text = (text.rstrip() + "\n\n" if text.strip() else "") + block
    if not re.search(r"(?m)^\s*default_permissions\s*=", text):
        text = f'default_permissions = "{PROJECT_PROFILE}"\n\n' + text  # a top-level key must come before any table
    return text
