"""Antigravity CLI (`agy`, successor of Gemini CLI) — `.agents/skills`, AGENTS.md, hooks in `.agents/hooks.json`.

Checked against agy 1.4.7 (its built-in agy-customizations guide and a live run):
- skills: `.agents/skills/<name>/SKILL.md` (name · description), called `/l-…`
- rules: AGENTS.md / GEMINI.md read natively
- hooks: `{"<hook name>": {Event: [...]}}`, run with cwd = `.agents/`; payload keys are camelCase
  (conversationId · lastUserInput · toolCall{name,args} · invocationNum · terminationReason)
- PostToolUse can't talk back (it must print `{}`), so H-5 results wait for PostInvocation
- no compaction hook → H-8 is not available here
- MCP has no project file; a workspace plugin (`.agents/plugins/<name>/mcp_config.json`) carries it
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..core.project import Project, write
from .base import MCP_NAME, MCP_SERVER, HookInput, HookReply, HookResult, Tool, hook_state_dir, merge_json_file

HOOK_NAME = "lanternspec"
PLUGIN_DIR = ".agents/plugins/lanternspec"
PATH_ARGS = ("Path", "TargetFile", "AbsolutePath", "FilePath", "path", "file_path")


class Antigravity(Tool):
    name = "antigravity"
    label = "Antigravity CLI"
    skill_root = ".agents/skills"
    config_paths = (".agents/", "GEMINI.md")
    write_tools = frozenset(
        {"write_file", "edit_file", "create_file", "write_to_file", "replace_file_content", "multi_replace_file_content"}
    )

    # ---- config
    def hooks(self) -> dict[str, Any]:
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
        def merge(data: dict[str, Any]) -> dict[str, Any]:
            data[HOOK_NAME] = self.hooks()  # named hooks: ours is one key, the user's stay as they are
            return data

        merge_json_file(project.root / ".agents" / "hooks.json", merge)
        merged = [".agents/hooks.json (에이전트 hook — 압축 hook이 없어 압축 전 저장은 빠짐)"]
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
        )

    def written_paths(self, inp: HookInput) -> list[str]:
        return [str(inp.tool_input[k]) for k in PATH_ARGS if inp.tool_input.get(k)]

    def respond(self, project: Project, event: str, result: HookResult) -> HookReply:
        if event == "post-tool":
            self._hold(project, [m for m in (result.block, result.context) if m])
            return HookReply(stdout="{}")
        if event == "feedback":
            return _inject(self._release(project))
        if event == "stop" and result.notice:
            return HookReply(
                stdout=json.dumps(
                    {"decision": "continue", "reason": result.notice + " — 이 권유를 사용자에게 한 줄로 전하고 마친다."}, ensure_ascii=False
                )
            )
        return _inject(result.context)

    # H-5 results wait here between PostToolUse and PostInvocation
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
