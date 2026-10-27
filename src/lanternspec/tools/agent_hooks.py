"""Agent hooks — 있으면 더 편한 것. Without them the skills' common close (P4) does the same.

What each hook does, for every tool alike (a tool adapter only reads its payload and writes the answer):

session-start  H-4  지금 상황 3줄을 대화에 넣는다 (압축 직후면 H-8 저장본도)
prompt         H-6  어떤 스킬로 시작했나 · H-9 기술 질문 감지 · H-10 아이디어 감지
post-tool      H-5  docs/ 문서를 쓰면 바로 양식 검사 → 깨졌으면 그 자리에서 고치게
               H-6  도구 호출 수 세기
feedback       (Antigravity) post-tool이 바로 말할 수 없어 미뤄 둔 H-5 결과를 전한다
stop           H-6  한 번 답을 마칠 때마다 실행 기록 한 줄
               H-7  코드는 바뀌었는데 작업 문서는 그대로면 /l-sync 권유 (작업당 한 번, 강제 없음)
pre-compact    H-8  압축 직전 진행 상황을 기록.md(없으면 세션 문서)의 "지금 상황"에 저장 → 압축 직후 session-start가 다시 넣어 준다
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path

from ..core.project import Project
from . import runlog
from .base import HookInput, HookReply, HookResult, Tool, hook_state_dir

STRUCTURE_CODES = {"frontmatter", "common-fields", "enum", "broken-link", "dup-id", "task-dup", "task-cycle", "template-structure"}


def run(project: Project, event: str, tool: Tool, raw: str) -> HookReply:
    try:
        data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        data = {}
    if event not in HANDLERS:
        raise ValueError(f"알 수 없는 hook: {event}")
    inp = tool.parse_hook(event, data if isinstance(data, dict) else {})
    return tool.respond(project, event, HANDLERS[event](project, tool, inp))


# --------------------------------------------------------------------------- H-4 · H-8


def session_start(project: Project, tool: Tool, inp: HookInput) -> HookResult:
    runlog.session_start(project, inp.session, inp.model or None, inp.source)
    if not project.profile.exists:
        return HookResult(context="[LanternSpec] 아직 프로젝트 준비 전입니다 — /l-init 으로 시작하세요.")
    from ..report.status import lines

    out = ["[LanternSpec 지금 상황]", *lines(project), "(자세한 내용은 해당 작업 폴더의 기록.md · 할 일.md를 필요할 때만 연다)"]
    if inp.source == "compact":
        out += _saved_progress(project, inp.session)
    return HookResult(context="\n".join(out))


def _compact_file(project: Project, session: str) -> Path:
    safe = re.sub(r"[^\w.-]", "_", session or "unknown")[:80]
    return hook_state_dir(project) / f"compact-{safe}.json"


def pre_compact(project: Project, tool: Tool, inp: HookInput) -> HookResult:
    """H-8: 진행 상황을 문서의 "지금 상황"에 저장하고, 압축 뒤 다시 넣을 문서 목록을 기억한다."""
    from ..work.progress import save_before_compact

    saved = save_before_compact(project)
    pointer = [{"path": project.rel(p), "before": before} for p, before in saved.items()]
    _compact_file(project, inp.session).write_text(json.dumps(pointer, ensure_ascii=False), encoding="utf-8")
    return HookResult()


def _saved_progress(project: Project, session: str) -> list[str]:
    """압축 직전에 저장한 문서들의 "지금 상황"(과 그때 밀려난 옛 내용)을 다시 넣을 줄로 만든다."""
    from ..core.project import read
    from ..work.progress import NOW, section_body

    f = _compact_file(project, session)
    if not f.exists():
        return []
    out = ["", "[LanternSpec 압축 전 진행 상황 (H-8) — 문서에 저장됨]"]
    for item in json.loads(f.read_text(encoding="utf-8")):
        path = project.root / item["path"]
        if not path.exists():
            continue
        out += [f"{item['path']} · {NOW}:", section_body(read(path), NOW)]
        if item.get("before"):
            out += ["(압축 직전에 적혀 있던 내용 — 지난 기록으로 옮김)", item["before"]]
    out.append("→ 필요하면 이 문서의 '## 지금 상황'에 진행 맥락을 보탠다 (요약만).")
    return out


# --------------------------------------------------------------------------- H-5 · H-6


def post_tool(project: Project, tool: Tool, inp: HookInput) -> HookResult:
    runlog.tool(project, inp.session, inp.tool, inp.tool_input)
    if inp.tool not in tool.write_tools:
        return HookResult()
    from ..check import check_docs

    hard_msgs: list[str] = []
    soft_msgs: list[str] = []
    for fp in dict.fromkeys(tool.written_paths(inp)):
        path = Path(fp)
        if not path.is_absolute():
            path = Path(inp.cwd or project.root) / path
        try:
            path.resolve().relative_to(project.docs.resolve())
        except ValueError:
            continue
        if path.suffix != ".md" or not path.exists():
            continue
        findings = check_docs.run(project, [path]).findings
        hard = [f for f in findings if f.level == "error" or f.code in STRUCTURE_CODES]
        soft = [f for f in findings if f not in hard and f.level == "warn"]
        rel = project.rel(path)
        if hard:
            hard_msgs.append(f"LanternSpec H-5: {rel} 양식이 깨졌습니다 — 지금 고치세요 (템플릿 구조는 바꾸지 않는다):")
            hard_msgs += [f"- {f.message}" + (f" (줄 {f.line})" if f.line else "") + (f" → {f.hint}" if f.hint else "") for f in hard]
        if soft:
            soft_msgs.append(f"LanternSpec 참고 ({rel}): " + " · ".join(f.message for f in soft[:5]))
    return HookResult(block="\n".join(hard_msgs), context="" if hard_msgs else "\n".join(soft_msgs))


def feedback(project: Project, tool: Tool, inp: HookInput) -> HookResult:
    return HookResult()  # the tool adapter delivers what post-tool held back


# --------------------------------------------------------------------------- H-6 · H-9 · H-10


def prompt(project: Project, tool: Tool, inp: HookInput) -> HookResult:
    if not inp.turn_start:
        return HookResult()
    runlog.prompt(project, inp.session, inp.prompt)
    if not project.profile.exists or inp.prompt.lstrip().startswith(("/", "$")):
        return HookResult()  # explicit commands are handled by their skill
    notes = [n for n in (learn_detect(project, inp.session, inp.prompt), idea_detect(project, inp.session, inp.prompt)) if n]
    return HookResult(context="\n".join(notes))


_PARTICLE = r"(?:이|가|은|는|이란|란|라는\s*게|란\s*게)?"
TECH_Q = [
    re.compile(
        r"^\s*(?P<t>[\w.+#/\- ]{1,40}?)\s*" + _PARTICLE + r"\s*(?:뭐야|뭐예요|뭐에요|뭔가요|뭐지|뭐임|뭔데|무엇인가요|무엇이야|뭐하는\s*거)"
    ),
    re.compile(r"^\s*(?P<t>[\w.+#/\- ]{1,40}?)\s*" + _PARTICLE + r"\s*(?:어떻게\s*동작|설명해\s*(?:줘|주세요))"),
    re.compile(r"(?i)^\s*what\s+(?:is|are)\s+(?:an?\s+|the\s+)?(?P<t>[\w.+#/\- ]{1,40}?)\s*\??\s*$"),
]
IDEA_HINT = re.compile(
    r"(?:(?:으)?면\s*좋겠|있으면\s*좋|하고\s*싶|나중에\s*\S+\s*(?:하자|해야|추가|넣)|아이디어가?\s*있|would be nice|it'd be nice)", re.I
)


def tech_term(text: str) -> str:
    for line in text.strip().split("\n")[:2]:
        for pat in TECH_Q:
            m = pat.search(line.strip())
            if m:
                term = re.sub(r"\s+", " ", m.group("t")).strip(" ?.")
                if 1 <= len(term) <= 40:
                    return term
    return ""


def _once(project: Project, key: str) -> bool:
    """True the first time a key is seen (per conversation reminders)."""
    f = hook_state_dir(project) / "once.json"
    try:
        seen = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        seen = {}
    if seen.get(key):
        return False
    seen[key] = True
    f.write_text(json.dumps(seen, ensure_ascii=False), encoding="utf-8")
    return True


def learn_detect(project: Project, session: str, text: str) -> str:
    """H-9 (LE-01 대화 중 질문 감지): manual 안 셈 · ask 묻기 · auto 카드 있으면 바로 셈."""
    mode = project.profile.get("learn.detect")
    if mode == "manual" or not project.profile.knowledge:
        return ""
    term = tech_term(text)
    if not term:
        return ""
    from ..learn import debt

    if debt.is_known(project, term):
        return ""
    card = debt.find(project, term)
    if mode == "ask":
        return (
            f"LanternSpec H-9: 사용자가 기술 '{term}'을(를) 물었습니다. 답한 뒤 한 줄로 \"📒 부채로 남길까요?\"라고 묻고, "
            f"남기면 /l-learn {term}"
            + (f" (카드 {card.id} 있음 — {project.enums.value('debt_status', 'asked_again')}으로 셈)" if card else "")
        )
    if card:  # auto + card → count without asking
        r = debt.ask(project, term, session=session, context="대화 중 질문 (H-9 자동)")
        if not r.counted:
            return ""
        return (
            f"LanternSpec H-9: '{term}'은(는) 부채 카드 {card.id}에 있어 물은 횟수를 셌습니다 ({r.ask_count}번째"
            + (f", {project.enums.value('debt_status', 'resolved')} → 다시 열림" if r.reopened else "")
            + "). 답할 때 지난 노트 · 카드를 링크해 복습을 돕는다."
        )
    if not _once(project, f"learn:{session}:{debt.norm(term)}"):
        return ""
    return f"LanternSpec H-9: '{term}' 카드가 없습니다. 답한 뒤 한 줄로 \"📒 부채 카드를 만들까요?\"라고 제안하세요 (/l-learn {term})."


def idea_detect(project: Project, session: str, text: str) -> str:
    """H-10 (ID-03): ask 대화당 한 번 묻기 · auto 바로 기록."""
    mode = project.profile.get("idea.capture")
    if mode == "manual" or not IDEA_HINT.search(text) or tech_term(text):
        return ""
    if mode == "ask":
        if not _once(project, f"idea:{session}"):
            return ""
        return (
            "LanternSpec H-10: 아이디어 같은 말이 있습니다. "
            '하던 일을 마친 뒤 한 줄로 "💡 이거 아이디어로 남길까요?"라고 한 번만 묻는다 (남기면 /l-idea).'
        )
    return (
        "LanternSpec H-10: 아이디어 같은 말이 있습니다. 하던 일은 멈추지 말고 /l-idea 규칙대로 바로 기록한다: "
        'lantern scaffold idea "<제목>" --kind <유형> --raw "<원문>" --auto → 한 줄로만 알림.'
    )


# --------------------------------------------------------------------------- H-6 · H-7


def stop(project: Project, tool: Tool, inp: HookInput) -> HookResult:
    runlog.stop(project, inp.session, model=inp.model or None)
    return HookResult(notice=sync_nudge(project, inp.session) if inp.finished else "")


def sync_nudge(project: Project, session: str) -> str:
    """H-7: uncommitted code changes while the in-progress work's docs are untouched → suggest /l-sync once."""
    from ..core import frontmatter
    from ..core.project import git_out, nfc, read, work_id_of
    from ..report.scan import is_doc_path

    if not project.profile.exists:
        return ""
    works = [
        w
        for w in project.work_dirs()
        if (w / "기획.md").exists()
        and frontmatter.parse(read(w / "기획.md")).meta.get("status") == project.enums.value("work_status", "build")
    ]
    if not works:
        return ""
    status = git_out(["status", "--porcelain", "--untracked-files=all"], project.root)
    changed = [nfc(l[3:].strip().strip('"')) for l in status.splitlines() if l.strip()]
    code = [f for f in changed if not is_doc_path(project, f)]
    if not code:
        return ""
    docs_changed = set(changed)
    if project.is_local_mode() and (project.docs / ".git").exists():
        docs_changed |= {
            project.profile.docs_root.rstrip("/") + "/" + nfc(l[3:].strip().strip('"'))
            for l in git_out(["status", "--porcelain"], project.docs).splitlines()
        }
    seen_file = hook_state_dir(project) / "sync-nudged.json"
    try:
        seen = json.loads(seen_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        seen = {}
    for w in works:
        wid = work_id_of(w)
        rel = project.rel(w) + "/"
        if any(f.startswith(rel) for f in docs_changed):
            continue
        key = f"{session}:{wid}"
        if seen.get(key):
            continue
        seen[key] = True
        seen_file.write_text(json.dumps(seen, ensure_ascii=False), encoding="utf-8")
        return (
            f"LanternSpec: 코드 {len(code)}개 파일이 바뀌었는데 진행 중 작업 {wid}의 문서는 그대로예요. "
            f"필요하면 /l-sync 로 맞추세요 (권유만 — 이 작업에서는 다시 묻지 않아요)."
        )
    return ""


HANDLERS: dict[str, Callable[[Project, Tool, HookInput], HookResult]] = {
    "session-start": session_start,
    "prompt": prompt,
    "post-tool": post_tool,
    "feedback": feedback,
    "stop": stop,
    "pre-compact": pre_compact,
}
