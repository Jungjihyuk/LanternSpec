"""Claude Code — `.claude/skills`, AGENTS.md read natively (an existing CLAUDE.md gets `@AGENTS.md`), hooks · MCP.

Hooks go into `.claude/settings.json`, the MCP server into `.mcp.json`.

Not here:
    - what a hook does → tools/agent_hooks.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..core.messages import msg
from ..core.project import Project, read, write
from .base import (
    HOOK_COMMAND,
    MCP_NAME,
    MCP_SERVER,
    HookInput,
    HookReply,
    HookResult,
    Tool,
    Turn,
    as_count,
    jsonl_records,
    merge_json_file,
    replace_hook_entries,
)
from .rules import nested_agents

if TYPE_CHECKING:
    from ..core.enums import Enums
    from ..core.profile import Profile
    from .skills import SkillSource


class ClaudeHooks:
    """Claude Code's hook payload and answers. Codex adopted the same schema, so it reuses this.

    Attributes:
        EVENT_NAMES: Our hook event → the event name Claude Code expects back in hookSpecificOutput.

    Example:
        >>> ClaudeHooks().parse_hook("prompt", {"session_id": "s1", "prompt": "/l-build"}).prompt
        '/l-build'
    """

    # the event name Claude Code expects back in hookSpecificOutput
    EVENT_NAMES = {"session-start": "SessionStart", "prompt": "UserPromptSubmit", "pre-tool": "PreToolUse", "post-tool": "PostToolUse"}

    def parse_hook(self, event: str, data: dict[str, Any]) -> HookInput:
        """Implement Tool.parse_hook for Claude Code's payload (snake_case keys).

        At stop, a missing model is read from the transcript (headless sessions do not send it).

        Args:
            event: Our hook event.
            data: The JSON Claude Code sent on stdin.

        Returns:
            The call in LanternSpec's words.

        Example:
            >>> ClaudeHooks().parse_hook("post-tool", {"tool_name": "Write", "tool_input": {"file_path": "a.md"}}).tool
            'Write'
        """
        model = data.get("model")
        if isinstance(model, dict):
            model = model.get("id") or model.get("display_name")
        if not model and event == "stop" and data.get("transcript_path"):
            model = model_from_transcript(str(data["transcript_path"]))
        tool_input = data.get("tool_input")
        return HookInput(
            session=str(data.get("session_id") or ""),
            model=str(model or ""),
            source=str(data.get("source") or ""),
            prompt=str(data.get("prompt") or ""),
            tool=str(data.get("tool_name") or ""),
            tool_input=tool_input if isinstance(tool_input, dict) else {},
            cwd=str(data.get("cwd") or ""),
            transcript=str(data.get("transcript_path") or ""),
            agent_id=str(data.get("agent_id") or ""),
            agent_type=str(data.get("agent_type") or ""),
            agent_transcript=str(data.get("agent_transcript_path") or ""),
            last_message=str(data.get("last_assistant_message") or ""),
        )

    def written_paths(self, inp: HookInput) -> list[str]:
        """Implement Tool.written_paths: `file_path` or `notebook_path` of the tool input.

        Args:
            inp: The hook call.

        Returns:
            The written paths.

        Example:
            >>> ClaudeHooks().written_paths(HookInput(tool_input={"file_path": "docs/a.md"}))
            ['docs/a.md']
        """
        return [str(inp.tool_input[k]) for k in ("file_path", "notebook_path") if inp.tool_input.get(k)]

    def session_context_reply(self, text: str) -> HookReply:
        """Answer session-start with text for the context (Claude Code adds plain stdout to the context).

        Args:
            text: The text to add.

        Returns:
            The reply.

        Example:
            >>> ClaudeHooks().session_context_reply("📦 진행 중: 없음").stdout
            '📦 진행 중: 없음'
        """
        return HookReply(stdout=text)  # Claude Code adds SessionStart stdout to the context

    def respond(self, project: Project, event: str, result: HookResult) -> HookReply:
        """Implement Tool.respond for Claude Code.

        A block exits 2 (fed back to the model), context goes into hookSpecificOutput
        (plain stdout at session-start), and a notice becomes a systemMessage.

        Args:
            project: The project.
            event: Our hook event.
            result: What the hook wants to say.

        Returns:
            What to print and the exit code.

        Example:
            >>> ClaudeHooks().respond(None, "post-tool", HookResult(block="양식이 깨졌습니다")).code
            2
        """
        if result.block:
            return HookReply(stderr=result.block, code=2)  # exit 2 = fed back to the model
        if event == "session-start" and result.context:
            return self.session_context_reply(result.context)
        if result.context and event in self.EVENT_NAMES:
            return HookReply(stdout=hook_specific_output(self.EVENT_NAMES[event], result.context))
        if result.notice:
            return HookReply(stdout=json.dumps({"systemMessage": result.notice}, ensure_ascii=False))
        return HookReply()


class ClaudeCode(ClaudeHooks, Tool):
    """The Claude Code adapter.

    Skills get `argument-hint`, `allowed-tools: Bash(lantern:*)` and, for manual-only skills,
    `disable-model-invocation`. It is the default agent, so its hook commands carry no `--agent`.

    Example:
        >>> ClaudeCode().hook_command("stop")
        'if command -v lantern >/dev/null 2>&1; then lantern hook stop; fi'
    """

    name = "claude"
    label = "Claude Code"
    launch = "claude"
    skill_root = ".claude/skills"
    session_expr = "${CLAUDE_SESSION_ID}"
    expands_arguments = True
    config_paths = (".claude/", "CLAUDE.md", ".mcp.json")
    write_tools = frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit"})
    min_version = "2.1.277"  # reads AGENTS.md itself (no CLAUDE.md needed)
    verified_version = "2.1.308"
    rules_max_lines = 200  # its docs: keep each instruction file under 200 lines, longer ones are followed less
    reads_nested_rules = True  # a folder's AGENTS.md loads when it opens a file there (no CLAUDE.md in the project)
    restores_after_compaction = True  # SessionStart with source compact
    model_prefixes = ("claude-",)
    agent_root = ".claude/agents"

    def skill_meta(self, src: SkillSource, profile: Profile, prefix: str) -> dict[str, Any]:
        """Implement Tool.skill_meta with Claude Code's extra frontmatter keys.

        Args:
            src: The skill source.
            profile: The project's settings.
            prefix: The command prefix (not used: Claude Code calls skills with "/").

        Returns:
            Frontmatter keys and values.

        Example:
            >>> ClaudeCode().skill_meta(src, profile, "/")["allowed-tools"]  # doctest: +SKIP
            'Bash(lantern:*)'
        """
        meta: dict[str, Any] = {"name": src.name, "description": src.description}
        if src.argument_hint:
            meta["argument-hint"] = src.argument_hint
        if src.manual_only(profile):
            meta["disable-model-invocation"] = True
        meta["allowed-tools"] = "Bash(lantern:*)"
        return meta

    def hook_command(self, event: str) -> str:
        """Implement Tool.hook_command without `--agent` (Claude Code is the default agent).

        Args:
            event: Our hook event.

        Returns:
            The command.

        Example:
            >>> ClaudeCode().hook_command("prompt")
            'if command -v lantern >/dev/null 2>&1; then lantern hook prompt; fi'
        """
        return HOOK_COMMAND.format(event=event, agent="")  # Claude Code is the default agent

    def hooks(self) -> dict[str, list[dict[str, Any]]]:
        """Build our hook entries for `.claude/settings.json`.

        Returns:
            Claude Code event → entries.

        Example:
            >>> sorted(ClaudeCode().hooks())
            ['PostToolUse', 'PreCompact', 'SessionStart', 'Stop', 'SubagentStart', 'SubagentStop', 'UserPromptSubmit']
        """

        def entry(event: str, matcher: str = "") -> dict[str, Any]:
            e: dict[str, Any] = {"hooks": [{"type": "command", "command": self.hook_command(event)}]}
            if matcher:
                e["matcher"] = matcher
            return e

        return {
            "SessionStart": [entry("session-start")],
            "UserPromptSubmit": [entry("prompt")],
            "PostToolUse": [entry("post-tool", "*")],
            "Stop": [entry("stop")],
            "PreCompact": [entry("pre-compact")],
            "SubagentStart": [entry("subagent-start")],
            "SubagentStop": [entry("subagent-stop")],
        }

    def agent_files(self, profile: Profile, enums: Enums | None = None) -> dict[str, str]:
        """Implement Tool.agent_files: the reviewer's definition (`.claude/agents/lantern-reviewer.md`) while `build.review` is on.

        The model line comes from `build.review_model` and is left out when that is empty, so the reviewer runs on
        the tool's own default. The definition disallows Edit, Write and NotebookEdit; Bash stays (the reviewer
        runs `git diff` and the tests), so that it writes no file through the shell rests on its instructions.

        Args:
            profile: The project's settings.
            enums: The project's choice lists; the bundled ones when None.

        Returns:
            Path → text; empty while the review is off.

        Example:
            >>> from lanternspec.core.profile import Profile
            >>> ".claude/agents/lantern-reviewer.md" in ClaudeCode().agent_files(Profile(data={"build": {"review": "on"}}))
            True
        """
        from .. import resources
        from ..core import templating
        from ..work.review import REVIEWER
        from .skills import body_context, fill_tokens

        if profile.get("build.review") != "on":
            return {}
        ctx = body_context(profile, self.name, enums)
        text = resources.read_text(f"locales/{profile.language}/agents/{REVIEWER}.md")
        return {f"{self.agent_root}/{REVIEWER}.md": fill_tokens(templating.apply_conditions(text, ctx), ctx)}

    def agent_definitions(self, project: Project) -> list[Path]:
        """Implement Tool.agent_definitions: the project's `.claude/agents/*.md` and the person's own `~/.claude/agents/*.md`.

        Args:
            project: The project.

        Returns:
            The files, project ones first.

        Example:
            >>> ClaudeCode().agent_definitions(project)  # doctest: +SKIP
            [PosixPath('…/.claude/agents/lantern-reviewer.md')]
        """
        folders = [project.root / self.agent_root, Path.home() / ".claude" / "agents"]
        return [p for folder in folders if folder.is_dir() for p in sorted(folder.glob("*.md"))]

    def agent_usage(self, path: Path) -> tuple[str, dict[str, int]] | None:
        """Implement Tool.agent_usage: the model of the sub-agent's answers and the sum of their `usage`.

        Args:
            path: The sub-agent's own transcript.

        Returns:
            The model and the tokens (each response counted once); None when the file holds no answer.

        Example:
            >>> ClaudeCode().agent_usage(Path("…/agent-x.jsonl"))  # doctest: +SKIP
            ('claude-opus-5-5', {'input': 330, 'cached': 4500, 'output': 150})
        """
        usages: dict[str, dict[str, Any]] = {}
        model = ""
        for i, d in enumerate(jsonl_records(path)):
            message = d.get("message")
            if d.get("type") != "assistant" or not isinstance(message, dict):
                continue
            model = str(message.get("model") or model)
            if usage := _dict(message.get("usage")):
                usages[str(message.get("id") or f"line-{i}")] = usage
        return (model, _sum_usage(usages)) if usages else None

    def install_config(self, project: Project, mcp: bool) -> list[str]:
        """Implement Tool.install_config for Claude Code.

        Claude Code reads AGENTS.md on its own, so no CLAUDE.md is created. CLAUDE.md files that hold
        nothing but the import of AGENTS.md are deleted, since while one exists Claude reads only CLAUDE.md
        files and so misses the folders' AGENTS.md (kept when a CLAUDE.local.md needs them). Any other
        CLAUDE.md is kept, with the import at its top. Hooks go into `.claude/settings.json`, the MCP
        server (when asked) into `.mcp.json`.

        Args:
            project: The project.
            mcp: Also register the knowledge MCP server.

        Returns:
            What was merged.

        Example:
            >>> ClaudeCode().install_config(project, mcp=False)  # doctest: +SKIP
            ['.claude/settings.json (에이전트 hook)']
        """
        merged = []
        present = {rel: read(project.root / rel) for rel in CLAUDE_FILES if (project.root / rel).exists()}
        if present and not (project.root / "CLAUDE.local.md").exists() and all(t.strip() == CLAUDE_FILES[r] for r, t in present.items()):
            for rel in present:
                (project.root / rel).unlink()
                merged.append(msg("{file} deleted (it only imported AGENTS.md, which Claude Code reads itself)", file=rel))
        for rel, line in CLAUDE_FILES.items():
            path = project.root / rel
            if path.exists() and not imports_agents(read(path)):
                text = read(path)
                write(path, f"{line}\n\n{text}" if text.strip() else f"{line}\n")
                merged.append(f"{rel} — {line}")
        merge_json_file(project.root / ".claude" / "settings.json", lambda d: replace_hook_entries(d, self.hooks()))
        merged.append(msg(".claude/settings.json — agent hooks"))
        if mcp:
            merge_json_file(project.root / ".mcp.json", add_mcp_server)
            merged.append(f".mcp.json — MCP {MCP_NAME}")
        return merged

    def read_transcript(self, path: Path) -> list[Turn] | None:
        r"""Implement Tool.read_transcript for Claude Code's JSON lines (`type` user · assistant, `message.content`).

        Subagent lines and user lines that only carry tool results are left out.

        Args:
            path: The transcript file.

        Returns:
            The messages, oldest first.

        Example:
            >>> ClaudeCode().read_transcript(Path("…/s1.jsonl"))[0].text  # doctest: +SKIP
            '로그인 버튼 고쳐 줘'
        """
        turns: list[Turn] = []
        for d in jsonl_records(path):
            role = d.get("type")
            message = d.get("message")
            if role not in ("user", "assistant") or d.get("isSidechain") or not isinstance(message, dict):
                continue
            content = message.get("content")
            blocks = [{"type": "text", "text": content}] if isinstance(content, str) else content if isinstance(content, list) else []
            texts = [str(b.get("text") or "") for b in blocks if isinstance(b, dict) and b.get("type") == "text"]
            calls = [b for b in blocks if isinstance(b, dict) and b.get("type") == "tool_use"]
            if not any(t.strip() for t in texts) and not calls:
                continue  # tool results, thinking only
            files = [
                f
                for c in calls
                if c.get("name") in self.write_tools
                for f in self.written_paths(HookInput(tool_input=_dict(c.get("input"))))
            ]
            turns.append(
                Turn(str(role), "\n".join(texts).strip(), [str(c.get("name")) for c in calls], files, str(d.get("timestamp") or ""))
            )
        return turns

    def turn_tokens(self, path: Path) -> dict[str, int] | None:
        """Implement Tool.turn_tokens: add up `usage` of the answers written since the user's last message.

        Claude Code writes one response as several lines that share a message id and a `usage`, so each
        id counts once. Sub-agent lines are left out; their tokens are recorded on their own.

        Args:
            path: The transcript file.

        Returns:
            Fresh input (input plus cache writes), cached input and output tokens; None when no answer follows the last message.

        Example:
            >>> ClaudeCode().turn_tokens(Path("…/s1.jsonl"))  # doctest: +SKIP
            {'input': 330, 'cached': 4500, 'output': 150}
        """
        records = jsonl_records(path)
        start = max((i for i, d in enumerate(records) if _is_prompt(d)), default=-1)
        usages: dict[str, dict[str, Any]] = {}
        for i, d in enumerate(records[start + 1 :]):
            message, usage = d.get("message"), _dict(_dict(d.get("message")).get("usage"))
            if d.get("type") == "assistant" and not d.get("isSidechain") and isinstance(message, dict) and usage:
                usages[str(message.get("id") or f"line-{i}")] = usage
        return _sum_usage(usages) if usages else None

    def check_config(self, project: Project) -> list[tuple[str, str]]:
        """Implement Tool.check_config: does Claude Code read the root and the nested AGENTS.md?

        Claude reads AGENTS.md itself only while no CLAUDE.md or CLAUDE.local.md exists in the project;
        otherwise it reads CLAUDE.md files only (the root AGENTS.md through their import, nested ones never).

        Args:
            project: The project.

        Returns:
            (level, message) rows.

        Example:
            >>> ClaudeCode().check_config(project)  # doctest: +SKIP
            [('ok', 'Claude Code가 AGENTS.md를 직접 읽습니다')]
        """
        rows: list[tuple[str, str]] = []
        present = {rel: read(project.root / rel) for rel in CLAUDE_FILES if (project.root / rel).exists()}
        only_import = [rel for rel, text in present.items() if text.strip() == CLAUDE_FILES[rel]]
        for rel, text in present.items():
            if not imports_agents(text):
                rows.append(("warn", msg("Claude Code doesn't read AGENTS.md: {file} doesn't import it — lantern upgrade", file=rel)))
        nested = nested_agents(project)
        if present and nested:
            items = ", ".join(nested[:3]) + (" …" if len(nested) > 3 else "")
            files = ", ".join(present)
            if len(only_import) == len(present):  # nothing of their own: deleting them is enough
                fix = msg("delete {file} (it only imports AGENTS.md)", file=files)
            else:
                fix = msg("move the text of {file} into AGENTS.md and delete it", file=files)
            rows.append(("warn", msg("Claude Code doesn't read {items} while a CLAUDE.md exists — {fix}", items=items, fix=fix)))
        elif only_import:
            rows.append(
                (
                    "info",
                    msg("You can delete {file}: it only imports AGENTS.md, which Claude Code reads itself", file=", ".join(only_import)),
                )
            )
        if (project.root / "CLAUDE.local.md").exists():
            rows.append(
                (
                    "warn",
                    msg(
                        "CLAUDE.local.md keeps Claude Code from reading AGENTS.md — set Project instructions to "
                        "claude-md-and-agents-md in /config (or ~/.claude/settings.json)"
                    ),
                )
            )
        if not any(level == "warn" for level, _ in rows):
            ok = (
                msg("Claude Code reads AGENTS.md through the import in {file}", file=", ".join(present))
                if present
                else msg("Claude Code reads AGENTS.md itself")
            )
            rows.insert(0, ("ok", ok))
        return rows


def _sum_usage(usages: dict[str, dict[str, Any]]) -> dict[str, int]:
    """Add up the `usage` of responses (one entry per response): fresh input with the cache writes, cached input, output."""
    return {
        "input": sum(as_count(u.get("input_tokens")) + as_count(u.get("cache_creation_input_tokens")) for u in usages.values()),
        "cached": sum(as_count(u.get("cache_read_input_tokens")) for u in usages.values()),
        "output": sum(as_count(u.get("output_tokens")) for u in usages.values()),
    }


CLAUDE_FILES = {"CLAUDE.md": "@AGENTS.md", ".claude/CLAUDE.md": "@../AGENTS.md"}  # file → the import that reaches the root AGENTS.md


def imports_agents(text: str) -> bool:
    r"""Tell whether a CLAUDE.md text imports the root AGENTS.md.

    Args:
        text: The CLAUDE.md text.

    Returns:
        True when a line starts with `@AGENTS.md` or `@../AGENTS.md`.

    Example:
        >>> imports_agents("@AGENTS.md\n\n# 메모"), imports_agents("AGENTS.md를 읽어라")
        (True, False)
    """
    return re.search(r"^@(\.\./)?AGENTS\.md\b", text, re.M) is not None


def hook_specific_output(event: str, text: str) -> str:
    """Write context for the model in Claude Code's hookSpecificOutput form.

    Args:
        event: Claude Code's event name, e.g. "UserPromptSubmit".
        text: The context to add.

    Returns:
        The JSON text.

    Example:
        >>> hook_specific_output("UserPromptSubmit", "안내")
        '{"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": "안내"}}'
    """
    return json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}, ensure_ascii=False)


def add_mcp_server(data: dict[str, Any]) -> dict[str, Any]:
    """Add our MCP server to `.mcp.json` data.

    Args:
        data: The current data, changed in place.

    Returns:
        The data.

    Example:
        >>> add_mcp_server({})
        {'mcpServers': {'lantern-knowledge': {'command': 'lantern', 'args': ['mcp']}}}
    """
    data.setdefault("mcpServers", {})[MCP_NAME] = dict(MCP_SERVER)
    return data


def model_from_transcript(path: str) -> str:
    """Read the model from a session transcript — headless sessions don't send it at SessionStart.

    Args:
        path: The transcript file (JSON lines).

    Returns:
        The model of the last assistant message; "" when none is found or the file cannot be read.

    Example:
        >>> model_from_transcript("no-such-file.jsonl")
        ''
    """
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return ""
    for line in reversed(lines[-400:]):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        msg = entry.get("message") if isinstance(entry, dict) else None
        if entry.get("type") == "assistant" and isinstance(msg, dict) and msg.get("model"):
            return str(msg["model"])
    return ""


def _is_prompt(record: dict[str, Any]) -> bool:
    """Whether a transcript line is something the user wrote (not a tool result, a skill's text or a compaction summary)."""
    message = record.get("message")
    if record.get("type") != "user" or record.get("isSidechain") or record.get("isMeta") or record.get("isCompactSummary"):
        return False
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str):
        return bool(content.strip())
    return isinstance(content, list) and any(isinstance(b, dict) and b.get("type") == "text" for b in content)


def _dict(value: Any) -> dict[str, Any]:
    """The value when it is a mapping, else an empty one (a transcript is not checked input)."""
    return value if isinstance(value, dict) else {}
