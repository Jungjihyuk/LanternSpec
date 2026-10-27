"""`lantern doctor` — does the project's real structure match lantern.yaml? One look at everything."""

from __future__ import annotations

import shutil

from ..core import profile as profile_mod
from ..core import state
from ..core.project import Project, git, git_version, read
from ..tools.rules import AGENTS_START
from ..tools.skills import SKILL_NAMES
from . import githooks

OK, WARN, BAD = "✔", "⚠", "✖"


def run(project: Project) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    p = project.profile
    if not p.exists:
        out.append((BAD, "lantern.yaml이 없습니다 — /l-init 으로 프로젝트를 준비하세요"))
    else:
        problems = profile_mod.validate(p.data)
        out += [(BAD, f"lantern.yaml: {x}") for x in problems] or [(OK, "lantern.yaml 형식")]
    if shutil.which("lantern"):
        out.append((OK, "lantern 명령이 PATH에 있음"))
    else:
        out.append((WARN, "lantern 명령이 PATH에 없습니다 — 에이전트 hook · git hook이 건너뜁니다 (uv tool install <lanternspec 경로>)"))
    is_git = git(["rev-parse", "--git-dir"], project.root).returncode == 0
    if not is_git:
        out.append((WARN, "git 저장소가 아닙니다 — hook · 커밋 연결 · sync가 동작하지 않습니다"))
    else:
        ver = git_version(project.root)
        if p.remote == "local" and ver < (2, 42, 0):
            out.append((BAD, f"local 방식은 git 2.42 이상 필요 (지금 {'.'.join(map(str, ver))})"))
        structural = githooks.structure_problems(project)
        out += [(BAD, f"문서 저장 방식({p.remote}): {x}") for x in structural] or [(OK, f"문서 저장 방식 {p.remote} — 구조가 맞음")]
        hooks = githooks.status(project)
        missing = [n for n, ok in hooks if not ok]
        if missing:
            level = BAD if p.remote == "local" and "pre-push" in missing else WARN
            out.append((level, f"git hook 미설치: {', '.join(missing)} — lantern hooks install"))
        else:
            out.append((OK, f"git hook 설치됨 (내용 검사: {p.get('git.hooks')})"))
        if p.get("project.kind"):
            out.append(_code_size_row(project))
    if p.exists:
        out.append(
            (OK, "docs/0. 템플릿 있음") if project.templates_dir.exists() else (BAD, "docs/0. 템플릿이 없습니다 — lantern scaffold init")
        )
        out.append((OK, "enums.yaml 있음") if project.enums_file.exists() else (WARN, "enums.yaml이 없습니다 — 기본값을 씁니다"))
        out += [(BAD, x) for x in project.enums.problems()]
        out.append((OK, "개발문서 MOC 있음") if project.moc.exists() else (WARN, "MOC가 없습니다 — lantern map"))
    k = p.knowledge
    if k:
        from pathlib import Path

        if k["type"] == "notion":
            import os

            env = str(k.get("token_env") or "NOTION_TOKEN")
            out.append((OK, f"Notion 토큰 {env} 있음") if os.environ.get(env) else (WARN, f"Notion 토큰이 없습니다 — 환경 변수 {env}"))
        else:
            path = Path(str(k["path"])).expanduser()
            out.append((OK, f"지식 저장소 {path} ({k['type']})") if path.exists() else (BAD, f"지식 저장소 경로가 없습니다: {path}"))
    st = state.load(project)
    if not st.get("version"):
        out.append((WARN, "스킬이 설치되지 않았습니다 — lantern install"))
    else:
        from ..tools.install import drift

        d = drift(project)
        if d["missing"]:
            out.append((WARN, f"빠진 스킬 파일 {len(d['missing'])}개 — lantern upgrade"))
        if d["stale"]:
            out.append((WARN, f"lantern.yaml 값(예: idea.capture)과 스킬이 다릅니다 {len(d['stale'])}개 — lantern upgrade"))
        if d["modified"]:
            out.append((WARN, f"사용자가 고친 스킬 {len(d['modified'])}개 (upgrade가 건너뜀): " + ", ".join(d["modified"][:3])))
        if not any(d.values()):
            out.append((OK, f"스킬 {len(SKILL_NAMES)}개 최신 ({', '.join(st.get('tools') or [])})"))
        agents = project.root / "AGENTS.md"
        if not agents.exists() or AGENTS_START not in read(agents):
            out.append((WARN, "AGENTS.md에 LanternSpec 규칙이 없습니다 — lantern upgrade"))
        if "claude" in (st.get("tools") or []):
            cm = project.root / "CLAUDE.md"
            if not cm.exists() or "@AGENTS.md" not in read(cm):
                out.append((WARN, "CLAUDE.md가 @AGENTS.md를 불러오지 않습니다"))
    return out


def _code_size_row(project: Project) -> tuple[str, str]:
    """코드가 자라 기록한 규모의 경계를 넘었으면 원칙을 한 단계 올릴지 묻는다 (줄면 그대로 둔다)."""
    from ..core import principles
    from ..report.harness import code_lines

    lines = code_lines(project, tests=False)
    now, recorded = principles.code_size(lines), str(project.profile.get("project.code_size") or principles.SIZES[0])
    label = principles.table()["sizes"]["code"]
    if principles.SIZES.index(now) > principles.SIZES.index(recorded):
        return (
            WARN,
            f"코드가 {lines:,}줄로 자라 규모가 {label[recorded]['label']} → {label[now]['label']}이 됐습니다 — 원칙을 한 단계 올릴까요? "
            f"→ lantern profile set project.code_size={now} && lantern upgrade",
        )
    return OK, f"개발 원칙 규모: 코드 {label[recorded]['label']} ({lines:,}줄)"


def format_result(rows: list[tuple[str, str]]) -> str:
    bad = sum(1 for r in rows if r[0] == BAD)
    warn = sum(1 for r in rows if r[0] == WARN)
    lines = [f"{icon} {msg}" for icon, msg in rows]
    lines.append("" if not rows else ("✔ 모두 정상" if not bad and not warn else f"✖ {bad}개 · ⚠ {warn}개"))
    return "\n".join(lines).rstrip()
