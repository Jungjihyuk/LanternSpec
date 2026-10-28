"""AI-tool commands: install · upgrade · build-adapters · docs-mode · hook · close."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from ..core.names import languages
from .common import Add, CliError, _csv, _p, _print

if TYPE_CHECKING:
    from ..core.project import Project


def cmd_install(a: argparse.Namespace) -> int:
    """`lantern install` — install skills, rules and hooks for the chosen AI tools, then show the next steps."""
    from ..tools.install import install

    project = _p()
    rep = install(
        project,
        _csv(a.tools) or None,
        force=a.force,
        mcp=True if a.mcp else None,
        ci=True if a.ci else False if a.no_ci else None,
        language=a.language,
    )
    _print(rep.lines())
    _print(_next_steps(project))
    return 0


def _next_steps(project: Project) -> list[str]:
    """What to do after installing — the command that opens each configured tool and how to call the skill."""
    from ..core import state
    from ..tools import REGISTRY, resolve

    tools = resolve(state.load(project).get("tools") or ["claude"])
    # AI tools on this computer but not set up for this project — suggest only, the person decides
    missing = [t for t in REGISTRY.values() if t not in tools and shutil.which(t.launch)]
    hint = (
        [
            "",
            f"ℹ 이 컴퓨터에 {' · '.join(t.label for t in missing)}도 있습니다. 함께 쓰려면: "
            f"lantern install --tools {','.join(t.name for t in tools + missing)}",
        ]
        if missing
        else []
    )
    if project.profile.exists:
        return ["", "다음 단계: AI 도구에서 하던 작업을 이어 갑니다 (지금 상황은 lantern status)", *hint]
    if len(tools) == 1:
        opens = f"{tools[0].label}를 엽니다 — 터미널에 `{tools[0].launch}` 입력"
    else:
        opens = "AI 도구를 엽니다 — " + ", ".join(f"{t.label}는 `{t.launch}`" for t in tools)
    others = [f"{t.label}는 `{t.command_prefix}l-init`" for t in tools if t.command_prefix != "/"]
    return [
        "",
        "다음 단계",
        f"  1. 이 폴더에서 {opens}",
        "  2. 입력창에 `/l-init`을 입력합니다"
        + (f" ({', '.join(others)})" if others else "")
        + " — 몇 가지 질문에 답하면 문서 구조와 설정이 만들어집니다",
        *hint,
    ]


def cmd_upgrade(a: argparse.Namespace) -> int:
    """`lantern upgrade` — refresh what install wrote, and template copies nobody edited."""
    from ..tools.install import upgrade

    _print(upgrade(_p(), force=a.force).lines())
    return 0


def cmd_build_adapters(a: argparse.Namespace) -> int:
    """`lantern build-adapters` — write every tool's skill files into a folder, without installing."""
    from ..core.project import write
    from ..tools import NAMES, resolve
    from ..tools.skills import generate

    project = _p()
    files = generate(project.profile, resolve(_csv(a.tools) or NAMES), project.enums)
    out = Path(a.out)
    for rel, text in files.items():
        write(out / rel, text)
    print(f"✔ {len(files)}개 파일을 {out}에 생성 (설치는 lantern install)")
    return 0


def cmd_docs_mode(a: argparse.Namespace) -> int:
    """`lantern docs-mode local|shared` — switch how documents are stored."""
    from ..tools import docs_mode

    project = _p()
    fn = docs_mode.to_local if a.mode == "local" else docs_mode.to_shared
    _print(fn(project, commit=not a.no_commit))
    return 0


def cmd_hook(a: argparse.Namespace) -> int:
    """`lantern hook <event>` (internal) — handle an agent or git hook; never stops the agent."""
    from ..check import githooks
    from ..tools import agent_hooks, get

    project = _p()
    name = a.name
    if name == "git-commit-msg":
        return githooks.commit_msg(project, a.args[0])
    if name == "git-pre-commit":
        return githooks.pre_commit(project)
    if name == "git-pre-push":
        return githooks.pre_push(project, a.args[0] if a.args else "", a.args[1] if len(a.args) > 1 else "", sys.stdin.read())
    if name not in agent_hooks.HANDLERS:
        raise CliError(f"알 수 없는 hook: {name}")
    tool = get(a.agent)
    try:
        reply = agent_hooks.run(project, name, tool, sys.stdin.read() if not sys.stdin.isatty() else "")
    except Exception as e:  # an agent hook must never break the agent
        print(f"LanternSpec hook {name} 오류: {e}", file=sys.stderr)
        return 0
    if reply.stdout:
        print(reply.stdout)
    if reply.stderr:
        print(reply.stderr, file=sys.stderr)
    return reply.code


def cmd_close(a: argparse.Namespace) -> int:
    """`lantern close <skill>` — every skill's common close: check → map → debt status → run record."""
    from ..tools import close

    _print(close.close(_p(), a.skill, work=a.work, start=a.start, model=a.model, check=not a.no_check, do_map=not a.no_map))
    return 0


def register(add: Add) -> None:
    """Register the AI-tool commands."""
    p = add("install", cmd_install, "스킬 · 규칙 · 에이전트 hook을 AI 도구 폴더에 설치 (/l-init 전에)")
    p.add_argument("--tools", help="claude,codex,antigravity (기본 claude)")
    p.add_argument("--force", action="store_true", help="사용자가 고친 파일도 덮어쓰기")
    p.add_argument("--mcp", action="store_true", help="지식 연결기 MCP 서버도 등록 (lantern mcp)")
    p.add_argument("--language", choices=languages(), help="스킬 · 규칙 · 문서의 언어 (처음 설치할 때만, 기본 ko)")
    ci = p.add_mutually_exclusive_group()
    ci.add_argument(
        "--ci", action="store_true", help="GitHub Actions에서도 검사: 양식 · 린트 · 타입 검사 · 수락 기준 테스트 (프로젝트 도구 준비 포함)"
    )
    ci.add_argument("--no-ci", action="store_true", help="GitHub Actions 검사 끄기 (고치지 않은 workflow 파일은 지움)")
    p = add("upgrade", cmd_upgrade, "새 버전 · 바뀐 lantern.yaml로 다시 생성 (고친 파일은 건너뜀)")
    p.add_argument("--force", action="store_true")
    p = add("build-adapters", cmd_build_adapters, "도구별 스킬 파일을 폴더에 생성만 (미리보기)")
    p.add_argument("--out", required=True)
    p.add_argument("--tools")
    p = add("docs-mode", cmd_docs_mode, "문서 저장 방식 바꾸기 (shared ↔ local)")
    p.add_argument("mode", choices=["local", "shared"])
    p.add_argument("--no-commit", action="store_true")
    p = add("hook", cmd_hook, argparse.SUPPRESS)
    p.add_argument("name")
    p.add_argument("args", nargs="*")
    p.add_argument("--agent", default="claude", help="claude | codex | antigravity")
    p = add("close", cmd_close, "스킬 공통 마무리: check → map → 실행 기록")
    p.add_argument("skill")
    p.add_argument("--work")
    p.add_argument("--start")
    p.add_argument("--model")
    p.add_argument("--no-check", action="store_true")
    p.add_argument("--no-map", action="store_true")
