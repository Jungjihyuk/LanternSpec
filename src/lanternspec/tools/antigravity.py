"""Antigravity CLI (`agy`, successor of Gemini CLI) — `.agents/skills`, AGENTS.md, hooks in `.agents/hooks.json`.

Checked against agy 1.4.7 (its built-in agy-customizations guide and a live run), hooks rechecked on 1.4.10:
- skills: `.agents/skills/<name>/SKILL.md` (name · description), called `/l-…`
- rules: AGENTS.md / GEMINI.md read natively
- hooks: `{"<hook name>": {Event: [...]}}`, run with cwd = `.agents/`; payload keys are camelCase
  (conversationId · lastUserInput · toolCall{name,args} · invocationNum · terminationReason)
- PostToolUse can't talk back (it must print `{}`), so document-check results wait for PostInvocation
- no compaction hook → saving progress before compaction is not available here
- MCP has no project file; a workspace plugin (`.agents/plugins/<name>/mcp_config.json`) carries it
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..core.messages import msg
from ..core.project import Project, write
from .base import MCP_NAME, MCP_SERVER, HookInput, HookReply, HookResult, Tool, Turn, hook_state_dir, jsonl_records, merge_json_file

HOOK_NAME = "lanternspec"
PLUGIN_DIR = ".agents/plugins/lanternspec"
USER_REQUEST = re.compile(r"</?USER_REQUEST>")  # agy wraps what the user wrote in these tags
PATH_ARGS = ("Path", "TargetFile", "AbsolutePath", "FilePath", "path", "file_path")


class Antigravity(Tool):
    """The Antigravity CLI adapter.

    Example:
        >>> Antigravity().launch
        'agy'
    """

    name = "antigravity"
    label = "Antigravity CLI"
    launch = "agy"
    skill_root = ".agents/skills"
    config_paths = (".agents/", "GEMINI.md")
    write_tools = frozenset(
        {"write_file", "edit_file", "create_file", "write_to_file", "replace_file_content", "multi_replace_file_content"}
    )
    verified_version = "1.4.10"
    rules_max_bytes = 24_000  # its guide: each rules file is cut at 24,000 bytes

    # ---- config
    def hooks(self) -> dict[str, Any]:
        """Build our named hook block for `.agents/hooks.json`.

        Returns:
            Antigravity event → handlers.

        Example:
            >>> sorted(Antigravity().hooks())
            ['PostInvocation', 'PostToolUse', 'PreInvocation', 'SessionStart', 'Stop']
        """

        def handler(event: str, timeout: int) -> dict[str, Any]:
            return {"type": "command", "command": self.hook_command(event), "timeout": timeout}

        return {
            "SessionStart": [handler("session-start", 10)],
            "PreInvocation": [handler("prompt", 10)],
            "PostToolUse": [{"matcher": "*", "hooks": [handler("post-tool", 30)]}],
            "PostInvocation": [handler("feedback", 10)],
            "Stop": [handler("stop", 10)],
        }

    def install_config(self, project: Project, mcp: bool) -> list[str]:
        """Implement Tool.install_config for Antigravity.

        Our hooks are one named key in `.agents/hooks.json`; the MCP server (when asked) goes into a workspace plugin.

        Args:
            project: The project.
            mcp: Also register the knowledge MCP server.

        Returns:
            What was merged.

        Example:
            >>> Antigravity().install_config(project, mcp=False)  # doctest: +SKIP
            ['.agents/hooks.json (에이전트 hook — 압축 hook이 없어 압축 전 저장은 빠짐)']
        """

        def merge(data: dict[str, Any]) -> dict[str, Any]:
            data[HOOK_NAME] = self.hooks()  # named hooks: ours is one key, the user's stay as they are
            return data

        merge_json_file(project.root / ".agents" / "hooks.json", merge)
        merged = [msg(".agents/hooks.json (agent hooks — no compaction hook, so saving before compaction is left out)")]
        if mcp:
            write(project.root / PLUGIN_DIR / "plugin.json", json.dumps({"name": "lanternspec"}, indent=2) + "\n")
            merge_json_file(
                project.root / PLUGIN_DIR / "mcp_config.json",
                lambda d: {**d, "mcpServers": {**d.get("mcpServers", {}), MCP_NAME: dict(MCP_SERVER)}},
            )
            merged.append(f"{PLUGIN_DIR}/ (MCP {MCP_NAME})")
        return merged

    # ---- hooks
    def parse_hook(self, event: str, data: dict[str, Any]) -> HookInput:
        """Implement Tool.parse_hook for Antigravity's camelCase payload.

        PreInvocation fires before every model call; only call 0 starts a turn.

        Args:
            event: Our hook event.
            data: The JSON agy sent on stdin.

        Returns:
            The call in LanternSpec's words.

        Example:
            >>> Antigravity().parse_hook("prompt", {"conversationId": "c1", "invocationNum": 2}).turn_start
            False
        """
        call = data.get("toolCall")
        call = call if isinstance(call, dict) else {}
        args = call.get("args")
        args = args if isinstance(args, dict) else {}
        workspaces = data.get("workspacePaths") or []
        return HookInput(
            session=str(data.get("conversationId") or ""),
            model=str(data.get("modelName") or ""),
            prompt=str(data.get("lastUserInput") or ""),
            tool=str(call.get("name") or ""),
            tool_input=args,
            cwd=str(workspaces[0]) if workspaces else "",
            # PreInvocation fires before every model call; the turn starts at call 0
            turn_start=int(data.get("invocationNum") or 0) == 0,
            finished=str(data.get("terminationReason") or "NO_TOOL_CALL") == "NO_TOOL_CALL",
            transcript=str(data.get("transcriptPath") or ""),
        )

    def written_paths(self, inp: HookInput) -> list[str]:
        """Implement Tool.written_paths over the path arguments agy's file tools use.

        Args:
            inp: The hook call.

        Returns:
            The written paths.

        Example:
            >>> Antigravity().written_paths(HookInput(tool_input={"TargetFile": "docs/a.md"}))
            ['docs/a.md']
        """
        return [str(inp.tool_input[k]) for k in PATH_ARGS if inp.tool_input.get(k)]

    def read_transcript(self, path: Path) -> list[Turn] | None:
        """Implement Tool.read_transcript for agy's transcript steps (`USER_INPUT` · `PLANNER_RESPONSE`).

        The `<USER_REQUEST>` wrapper agy puts around what the user wrote is taken off.

        Args:
            path: The transcript file.

        Returns:
            The messages, oldest first.

        Example:
            >>> Antigravity().read_transcript(Path("…/transcript.jsonl"))[0].role  # doctest: +SKIP
            'user'
        """
        turns: list[Turn] = []
        for d in jsonl_records(path):
            at = str(d.get("created_at") or "")
            raw = d.get("content")
            content = raw if isinstance(raw, str) else ""
            if d.get("type") == "USER_INPUT" and content.strip():
                turns.append(Turn("user", USER_REQUEST.sub("", content).strip(), at=at))
            elif d.get("type") == "PLANNER_RESPONSE":
                calls = [c for c in d.get("tool_calls") or [] if isinstance(c, dict)]
                if not content.strip() and not calls:
                    continue
                files = [
                    f
                    for c in calls
                    if c.get("name") in self.write_tools
                    for f in self.written_paths(HookInput(tool_input=c.get("args") or {}))
                ]
                turns.append(Turn("assistant", content.strip(), [str(c.get("name")) for c in calls], files, at))
        return turns

    def respond(self, project: Project, event: str, result: HookResult) -> HookReply:
        """Implement Tool.respond for Antigravity.

        post-tool always prints `{}` and holds its messages until feedback (PostInvocation) injects them;
        a stop notice asks the agent to pass it on; context is injected as a system message.

        Args:
            project: The project.
            event: Our hook event.
            result: What the hook wants to say.

        Returns:
            What to print and the exit code.

        Example:
            >>> Antigravity().respond(project, "post-tool", HookResult(block="양식이 깨졌습니다")).stdout  # doctest: +SKIP
            '{}'
        """
        if event == "post-tool":
            self._hold(project, [m for m in (result.block, result.context) if m])
            return HookReply(stdout="{}")
        if event == "feedback":
            return _inject(self._release(project))
        if event == "stop" and result.notice:
            return HookReply(
                stdout=json.dumps(
                    {"decision": "continue", "reason": result.notice + msg(" — pass this suggestion to the user in one line and finish.")},
                    ensure_ascii=False,
                )
            )
        return _inject(result.context)

    # document-check results wait here between PostToolUse and PostInvocation
    def _pending(self, project: Project) -> Path:
        return hook_state_dir(project) / "antigravity-pending.json"

    def _hold(self, project: Project, messages: list[str]) -> None:
        if not messages:
            return
        f = self._pending(project)
        held = json.loads(f.read_text(encoding="utf-8")) if f.exists() else []
        f.write_text(json.dumps(held + messages, ensure_ascii=False), encoding="utf-8")

    def _release(self, project: Project) -> str:
        f = self._pending(project)
        if not f.exists():
            return ""
        held = json.loads(f.read_text(encoding="utf-8"))
        f.unlink()
        return "\n".join(held)


def _inject(text: str) -> HookReply:
    if not text:
        return HookReply(stdout="{}")
    return HookReply(stdout=json.dumps({"injectSteps": [{"systemMessage": {"systemMessage": text}}]}, ensure_ascii=False))
