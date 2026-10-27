"""Claude Code — `.claude/skills`, CLAUDE.md → `@AGENTS.md`, hooks in `.claude/settings.json`, MCP in `.mcp.json`."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..core.project import Project, read, write
from .base import HOOK_COMMAND, MCP_NAME, MCP_SERVER, HookInput, HookReply, HookResult, Tool, merge_json_file, replace_hook_entries

if TYPE_CHECKING:
    from ..core.profile import Profile
    from .skills import SkillSource


class ClaudeHooks:
    """Claude Code's hook payload and answers. Codex adopted the same schema, so it reuses this."""

    # the event name Claude Code expects back in hookSpecificOutput
    EVENT_NAMES = {"session-start": "SessionStart", "prompt": "UserPromptSubmit", "post-tool": "PostToolUse"}

    def parse_hook(self, event: str, data: dict[str, Any]) -> HookInput:
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
        )

    def written_paths(self, inp: HookInput) -> list[str]:
        return [str(inp.tool_input[k]) for k in ("file_path", "notebook_path") if inp.tool_input.get(k)]

    def session_context_reply(self, text: str) -> HookReply:
        return HookReply(stdout=text)  # Claude Code adds SessionStart stdout to the context

    def respond(self, project: Project, event: str, result: HookResult) -> HookReply:
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
    name = "claude"
    label = "Claude Code"
    skill_root = ".claude/skills"
    session_expr = "${CLAUDE_SESSION_ID}"
    expands_arguments = True
    config_paths = (".claude/", "CLAUDE.md", ".mcp.json")
    write_tools = frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit"})

    def skill_meta(self, src: SkillSource, profile: Profile, prefix: str) -> dict[str, Any]:
        meta: dict[str, Any] = {"name": src.name, "description": src.description}
        if src.argument_hint:
            meta["argument-hint"] = src.argument_hint
        if src.manual_only(profile):
            meta["disable-model-invocation"] = True
        meta["allowed-tools"] = "Bash(lantern:*)"
        return meta

    def hook_command(self, event: str) -> str:
        return HOOK_COMMAND.format(event=event, agent="")  # Claude Code is the default agent

    def hooks(self) -> dict[str, list[dict[str, Any]]]:
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
        }

    def install_config(self, project: Project, mcp: bool) -> list[str]:
        merged = []
        claude_md = project.root / "CLAUDE.md"
        text = read(claude_md) if claude_md.exists() else ""
        if "@AGENTS.md" not in text:
            write(claude_md, ("@AGENTS.md\n\n" + text) if text.strip() else "@AGENTS.md\n")
            merged.append("CLAUDE.md (@AGENTS.md)")
        merge_json_file(project.root / ".claude" / "settings.json", lambda d: replace_hook_entries(d, self.hooks()))
        merged.append(".claude/settings.json (에이전트 hook)")
        if mcp:
            merge_json_file(project.root / ".mcp.json", add_mcp_server)
            merged.append(f".mcp.json (MCP {MCP_NAME})")
        return merged


def hook_specific_output(event: str, text: str) -> str:
    return json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}, ensure_ascii=False)


def add_mcp_server(data: dict[str, Any]) -> dict[str, Any]:
    data.setdefault("mcpServers", {})[MCP_NAME] = dict(MCP_SERVER)
    return data


def model_from_transcript(path: str) -> str:
    """Headless sessions don't send the model at SessionStart; the last assistant message has it."""
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
