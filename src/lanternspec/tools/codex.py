"""Codex — `.agents/skills` (called `$l-…`), hooks in `.codex/hooks.json`, MCP in `.codex/config.toml`.

Hook payloads and answers follow Claude Code's schema (checked against codex 0.164), so the
protocol comes from claude.ClaudeHooks; only what differs is written here.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..core.messages import msg
from ..core.project import Project, read, write
from .base import MCP_NAME, HookInput, HookReply, Tool, Turn, jsonl_records, merge_json_file, replace_hook_entries
from .claude import ClaudeHooks, hook_specific_output

if TYPE_CHECKING:
    from ..core.profile import Profile
    from .skills import SkillSource

PATCH_FILE = re.compile(r"^\*\*\* (?:Add|Update) File: (.+)$", re.M)
INJECTED = ("# AGENTS.md", "<")  # starts of text Codex adds to user messages itself (AGENTS.md, environment context)


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

        def entry(event: str, timeout: int) -> dict[str, Any]:
            return {"hooks": [{"type": "command", "command": self.hook_command(event), "timeout": timeout}]}

        return {
            "SessionStart": [entry("session-start", 10)],
            "UserPromptSubmit": [entry("prompt", 10)],
            "PostToolUse": [entry("post-tool", 30)],
            "PreCompact": [entry("pre-compact", 10)],
            "Stop": [entry("stop", 10)],
        }

    def install_config(self, project: Project, mcp: bool) -> list[str]:
        """Implement Tool.install_config: hooks go into `.codex/hooks.json`, the MCP server (when asked) into `.codex/config.toml`.

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
        merged = [msg(".codex/hooks.json (agent hooks — Codex asks whether to trust them on first run)")]
        if mcp:
            path = project.root / ".codex" / "config.toml"
            write(path, add_mcp_server_toml(read(path) if path.exists() else ""))
            merged.append(f".codex/config.toml (MCP {MCP_NAME})")
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
