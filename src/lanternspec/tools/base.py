"""What every AI tool adapter provides — the contract the rest of LanternSpec talks to.

A tool adapter answers three questions only, each in that tool's own format:
  1. skills  — where a skill goes and what its frontmatter looks like
  2. config  — which settings files carry our rules, hooks and MCP server
  3. hooks   — how its hook payload reads (parse_hook) and how an answer is written back (respond)

What a hook *does* lives in agent_hooks.py and never looks at a tool's format.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from ..core.project import Project, read, write

if TYPE_CHECKING:
    from ..core.enums import Enums
    from ..core.profile import Profile
    from .skills import SkillSource

HOOK_COMMAND = "if command -v lantern >/dev/null 2>&1; then lantern hook {event}{agent}; fi"
MCP_NAME = "lantern-knowledge"
MCP_SERVER = {"command": "lantern", "args": ["mcp"]}


@dataclass
class HookInput:
    """One hook call, in LanternSpec's words (each tool maps its own payload onto this).

    Attributes:
        session: The conversation's ID.
        model: The model in use.
        source: For session-start: "startup", "resume" or "compact".
        prompt: For prompt: what the user wrote.
        tool: For post-tool: the tool that ran.
        tool_input: For post-tool: the tool's input.
        cwd: The folder the agent works in.
        turn_start: For prompt: whether this is the first model call of a user turn.
        finished: For stop: whether the turn ended normally (not an error or a cancel).

    Example:
        >>> HookInput(session="s1", prompt="/l-build W-012").prompt
        '/l-build W-012'
    """

    session: str = ""
    model: str = ""
    source: str = ""  # session-start: startup | resume | compact
    prompt: str = ""
    tool: str = ""
    tool_input: dict[str, Any] = field(default_factory=dict)
    cwd: str = ""
    turn_start: bool = True  # prompt: the first model call of a user turn
    finished: bool = True  # stop: the turn ended normally (not an error or a cancel)


@dataclass
class HookResult:
    """What a hook wants to say — each tool decides how to deliver it.

    Attributes:
        context: Text to add to the model's context (status, notes, detected questions or ideas).
        block: The document just written is broken — the agent must fix it now.
        notice: A one-line suggestion when the turn ends.

    Example:
        >>> HookResult(notice="/l-sync 할까요?").block
        ''
    """

    context: str = ""
    block: str = ""
    notice: str = ""


@dataclass
class HookReply:
    """What the hook process prints and returns, in the tool's own format.

    Attributes:
        stdout: Text for standard output.
        stderr: Text for standard error.
        code: The exit code.

    Example:
        >>> HookReply(stdout="{}").code
        0
    """

    stdout: str = ""
    stderr: str = ""
    code: int = 0


class Tool:
    """The contract of an AI tool adapter.

    Shared code knows only this class; each tool overrides what its format needs.
    Methods with a default (skill_meta, skill_extras, install_config, check_config, hooks, written_paths) are
    overridden only by tools that need them.

    Attributes:
        name: Key used on the command line and in installed.json, e.g. "claude".
        label: Display name, e.g. "Claude Code".
        launch: The terminal command that opens this tool (claude · codex · agy).
        skill_root: Folder that holds `<skill>/SKILL.md`.
        command_prefix: How a user calls a skill: "/" (/l-build) or "$" ($l-build).
        session_expr: Shell expression a skill passes as `--session`.
        expands_arguments: Whether the tool substitutes `$ARGUMENTS` in a skill body.
        config_paths: Files and folders this tool owns (not project code).
        write_tools: Tool names that write files (checked after they run).
        min_version: The oldest version with every feature we rely on ("" = not known, not checked).
        verified_version: The newest version whose formats were checked against its docs ("" = not checked).

    Example:
        >>> from lanternspec.tools import get
        >>> get("claude").skill_root
        '.claude/skills'
    """

    name = ""
    label = ""
    launch = ""  # the terminal command that opens this tool (claude · codex · agy)
    skill_root = ""  # folder that holds <skill>/SKILL.md
    command_prefix = "/"  # how a user calls a skill: /l-build · $l-build
    session_expr = "$(date +%Y-%m-%d)"  # shell expression a skill passes as --session
    expands_arguments = False  # does the tool substitute $ARGUMENTS in a skill body?
    config_paths: tuple[str, ...] = ()  # files · folders this tool owns (not project code)
    write_tools: frozenset[str] = frozenset()  # tool names that write files (checked right after)
    min_version = ""  # oldest version with every feature we rely on; "" = not known
    verified_version = ""  # newest version checked against its docs; "" = not checked

    # ---- skills
    def skill_meta(self, src: SkillSource, profile: Profile, prefix: str) -> dict[str, Any]:
        """Build the frontmatter of an installed skill.

        Args:
            src: The skill source.
            profile: The project's settings.
            prefix: The tool's command prefix, used to rewrite skill names in the description.

        Returns:
            Frontmatter keys and values (name and description by default).

        Example:
            >>> get("codex").skill_meta(src, profile, "$")["name"]  # doctest: +SKIP
            'l-build'
        """
        from .skills import rewrite_commands

        return {"name": src.name, "description": rewrite_commands(src.description, prefix)}

    def skill_extras(self, src: SkillSource, profile: Profile) -> dict[str, str]:
        """Return tool-only files to put next to SKILL.md.

        Args:
            src: The skill source.
            profile: The project's settings.

        Returns:
            Path relative to the skill folder → text; none by default.

        Example:
            >>> get("claude").skill_extras(src, profile)  # doctest: +SKIP
            {}
        """
        return {}

    def skill_files(self, src: SkillSource, profile: Profile, prefix: str, enums: Enums | None = None) -> dict[str, str]:
        """Build every file of one installed skill: SKILL.md (frontmatter + generated note + body) and its extra files.

        Args:
            src: The skill source.
            profile: The project's settings (fill `<<…>>` values).
            prefix: The tool's command prefix.
            enums: The project's choice lists; the bundled ones when None.

        Returns:
            Path relative to the project root → text.

        Example:
            >>> list(get("claude").skill_files(src, profile, "/"))[0]  # doctest: +SKIP
            '.claude/skills/l-build/SKILL.md'
        """
        from dataclasses import replace

        from .skills import body_context, fill_tokens, render_body, rewrite_commands

        base = f"{self.skill_root}/{src.name}"
        note = f"<!-- {profile.names.marker('generated_skill')} -->\n"
        body = render_body(src, profile, self, prefix, enums)
        src = replace(src, description=fill_tokens(src.description, body_context(profile, self.name, enums)))
        files = {f"{base}/SKILL.md": yaml_front(self.skill_meta(src, profile, prefix)) + note + "\n" + body}
        for rel, text in src.extra.items():
            files[f"{base}/{rel}"] = rewrite_commands(text, prefix)
        for rel, text in self.skill_extras(src, profile).items():
            files[f"{base}/{rel}"] = text
        return files

    def owns_skill_file(self, rel: str) -> bool:
        """Tell whether an installed file is one of this tool's skill files.

        Args:
            rel: Path relative to the project root.

        Returns:
            True when it lies under skill_root.

        Example:
            >>> from lanternspec.tools import get
            >>> get("claude").owns_skill_file(".claude/skills/l-build/SKILL.md")
            True
        """
        return rel.startswith(self.skill_root + "/")

    # ---- project config (rules · hooks · MCP); returns what was merged, for the install report
    def install_config(self, project: Project, mcp: bool) -> list[str]:
        """Merge our rules, hooks and MCP server into the tool's settings files, keeping the user's own entries.

        Args:
            project: The project.
            mcp: Also register the knowledge MCP server.

        Returns:
            What was merged, for the install report; nothing by default.

        Example:
            >>> get("claude").install_config(project, mcp=False)  # doctest: +SKIP
            ['.claude/settings.json (hooks)']
        """
        return []

    def check_config(self, project: Project) -> list[tuple[str, str]]:
        """Check that the tool will actually read our rules in this project (for `lantern doctor`).

        Args:
            project: The project.

        Returns:
            (level, message) rows; level is "ok", "info", "warn" or "bad". Nothing to check by default.

        Example:
            >>> get("codex").check_config(project)  # doctest: +SKIP
            []
        """
        return []

    # ---- hooks
    def hooks(self) -> dict[str, Any]:
        """Build our hook entries in the tool's settings format.

        Returns:
            The tool's event name → its entries; none by default.

        Example:
            >>> from lanternspec.tools import get
            >>> sorted(get("codex").hooks())
            ['PostToolUse', 'PreCompact', 'SessionStart', 'Stop', 'UserPromptSubmit']
        """
        return {}

    def hook_events(self) -> list[str]:
        """List our hook events this tool calls, read from the commands in hooks().

        Returns:
            Our event names, e.g. "session-start", sorted.

        Example:
            >>> from lanternspec.tools import get
            >>> get("antigravity").hook_events()
            ['feedback', 'post-tool', 'prompt', 'session-start', 'stop']
        """
        return sorted(set(re.findall(r"lantern hook ([a-z-]+)", json.dumps(self.hooks()))))

    def hook_command(self, event: str) -> str:
        """Return the shell command a hook entry runs (it does nothing when `lantern` is missing).

        Args:
            event: Our hook event, e.g. "session-start".

        Returns:
            The command.

        Example:
            >>> from lanternspec.tools import get
            >>> get("codex").hook_command("stop")
            'if command -v lantern >/dev/null 2>&1; then lantern hook stop --agent codex; fi'
        """
        return HOOK_COMMAND.format(event=event, agent=f" --agent {self.name}")

    def parse_hook(self, event: str, data: dict[str, Any]) -> HookInput:
        """Read the tool's hook payload.

        Args:
            event: Our hook event.
            data: The JSON the tool sent on stdin.

        Returns:
            The call in LanternSpec's words.

        Example:
            >>> get("claude").parse_hook("prompt", {"session_id": "s1", "prompt": "hi"}).session  # doctest: +SKIP
            's1'
        """
        raise NotImplementedError

    def written_paths(self, inp: HookInput) -> list[str]:
        """Return the files a post-tool call wrote (so they can be checked right away).

        Args:
            inp: The hook call.

        Returns:
            Written paths; none by default.

        Example:
            >>> get("claude").written_paths(HookInput(tool="Write", tool_input={"file_path": "docs/a.md"}))  # doctest: +SKIP
            ['docs/a.md']
        """
        return []

    def respond(self, project: Project, event: str, result: HookResult) -> HookReply:
        """Write a hook result back in the form the tool accepts. Must work for any result, even an empty one.

        Args:
            project: The project.
            event: Our hook event.
            result: What the hook wants to say.

        Returns:
            What to print and the exit code.

        Example:
            >>> get("antigravity").respond(project, "post-tool", HookResult()).stdout  # doctest: +SKIP
            '{}'
        """
        raise NotImplementedError


# --------------------------------------------------------------------------- helpers for adapters


def yaml_front(meta: dict[str, Any]) -> str:
    """Write a mapping as a YAML frontmatter block.

    Args:
        meta: Keys and values, in order.

    Returns:
        The block, between `---` lines.

    Example:
        >>> print(yaml_front({"name": "l-build", "description": "구현"}), end="")
        ---
        name: l-build
        description: 구현
        ---
    """
    return "---\n" + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False, width=10_000) + "---\n"


def merge_json_file(path: Path, merge: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
    """Change a JSON settings file through a merge function (a missing or empty file starts as {}).

    Args:
        path: The JSON file.
        merge: Takes the current data and returns the new data.

    Example:
        >>> merge_json_file(Path(".claude/settings.json"), lambda d: {**d, "x": 1})  # doctest: +SKIP
    """
    data = json.loads(read(path)) if path.exists() and read(path).strip() else {}
    write(path, json.dumps(merge(data), ensure_ascii=False, indent=2) + "\n")


def is_our_hook(entry: dict[str, Any]) -> bool:
    """Tell whether a hook entry is ours (its command calls `lantern hook`).

    Args:
        entry: A hook entry, with a command or a list of hooks with commands.

    Returns:
        True for LanternSpec's entries.

    Example:
        >>> is_our_hook({"hooks": [{"command": "lantern hook stop"}]}), is_our_hook({"command": "echo hi"})
        (True, False)
    """
    cmds = [entry.get("command", "")] + [h.get("command", "") for h in entry.get("hooks", [])]
    return any("lantern hook" in c for c in cmds)


def replace_hook_entries(data: dict[str, Any], ours: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Replace our hook entries in Claude-style settings (`hooks: {Event: [entries]}`), keeping the user's.

    Args:
        data: The settings, changed in place.
        ours: Event → our new entries.

    Returns:
        The settings.

    Example:
        >>> data = {"hooks": {"Stop": [{"command": "echo hi"}, {"command": "lantern hook stop"}]}}
        >>> replace_hook_entries(data, {"Stop": [{"command": "lantern hook stop --agent claude"}]})["hooks"]["Stop"]
        [{'command': 'echo hi'}, {'command': 'lantern hook stop --agent claude'}]
    """
    hooks = data.setdefault("hooks", {})
    for event, entries in ours.items():
        hooks[event] = [e for e in hooks.get(event, []) if not is_our_hook(e)] + entries
    return data


def hook_state_dir(project: Project) -> Path:
    """Return the folder where hooks keep state between calls (created when missing).

    Args:
        project: The project.

    Returns:
        `.lantern/hook-state`.

    Example:
        >>> hook_state_dir(project).name  # doctest: +SKIP
        'hook-state'
    """
    p = project.state / "hook-state"
    p.mkdir(parents=True, exist_ok=True)
    return p
