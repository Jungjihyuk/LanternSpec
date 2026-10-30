"""Agent hooks — nice to have. Without them the skills' common close (`lantern close`) does the same.

What each hook does, for every tool alike (a tool adapter only reads its payload and writes the answer):

session-start  put the three-line status into the conversation (right after compaction, also the saved progress)
prompt         which skill started the turn (run log) · tech-question detection · idea detection
pre-tool       (Codex) before the first edit in a part, hand over that part's AGENTS.md
post-tool      check the format as soon as a docs/ document is written → fix it on the spot if broken
               (tools without pre-tool) hand over a part's AGENTS.md after its first edit
               count tool calls (run log)
feedback       (Antigravity) deliver the document-check result that post-tool could not say right away
stop           one run-log line per finished answer
               suggest /l-sync when code changed but the work documents did not (once per work item, never forced)
pre-compact    save progress into "지금 상황" of `기록.md` (or the session document) before compaction; session-start puts it back

Every handler takes (project, tool, hook call) and returns a HookResult; it never stops the agent.
Every call is also noted in the hook-run record (tools/health.py), so a hook that stops running shows up,
and in the conversation record (tools/sessions.py), so `lantern resume` can carry a conversation on in any tool.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path

from ..core.messages import msg
from ..core.project import Project, read
from . import health, runlog, sessions
from .base import HookInput, HookReply, HookResult, Tool, hook_state_dir

STRUCTURE_CODES = {"frontmatter", "common-fields", "enum", "broken-link", "dup-id", "task-dup", "task-cycle", "template-structure"}


def run(project: Project, event: str, tool: Tool, raw: str) -> HookReply:
    """Handle one hook call: read the payload, run the handler, answer in the tool's format.

    Args:
        project: The project.
        event: Our hook event, e.g. "post-tool".
        tool: The tool that called.
        raw: The payload text from stdin (empty or broken JSON is read as {}).

    Returns:
        What to print and the exit code.

    Raises:
        ValueError: The event is unknown.

    Example:
        >>> run(project, "stop", get("claude"), "{}").code  # doctest: +SKIP
        0
    """
    try:
        data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        data = {}
    if event not in HANDLERS:
        raise ValueError(msg("Unknown hook: {event}", event=event))
    data = data if isinstance(data, dict) else {}
    inp = tool.parse_hook(event, data)
    health.record(project, tool, event, inp, data)
    sessions.record(project, tool, event, inp)
    return tool.respond(project, event, HANDLERS[event](project, tool, inp))


# --------------------------------------------------------------------------- session start · compaction


def session_start(project: Project, tool: Tool, inp: HookInput) -> HookResult:
    """Put the three-line status into the conversation; after compaction, also the progress saved before it.

    Args:
        project: The project.
        tool: The tool that called.
        inp: The hook call.

    Returns:
        The status as context (a "run /l-init" note before the project is set up).

    Example:
        >>> session_start(project, tool, HookInput(source="startup")).context.splitlines()[0]  # doctest: +SKIP
        '[LanternSpec 지금 상황]'
    """
    runlog.session_start(project, inp.session, inp.model or None, inp.source)
    if not project.profile.exists:
        return HookResult(context=msg("[LanternSpec] The project isn't set up yet — start with /l-init."))
    from ..report.status import lines

    n = project.names
    out = [
        msg("[LanternSpec now]"),
        *lines(project),
        msg("(open {file} · {file2} in the work folder only when you need the details)", file=n.file("record"), file2=n.file("tasks")),
    ]
    if inp.source == "compact":
        out += _saved_progress(project, inp.session)
        out += [line for line in (_part_line(project, inp.session),) if line]
    return HookResult(context="\n".join(out))


def _compact_file(project: Project, session: str) -> Path:
    safe = re.sub(r"[^\w.-]", "_", session or "unknown")[:80]
    return hook_state_dir(project) / f"compact-{safe}.json"


def pre_compact(project: Project, tool: Tool, inp: HookInput) -> HookResult:
    """Save progress into the documents' "지금 상황" and remember which documents to put back after compaction.

    Args:
        project: The project.
        tool: The tool that called.
        inp: The hook call.

    Returns:
        An empty result (nothing to say).

    Example:
        >>> pre_compact(project, tool, HookInput(session="s1"))  # doctest: +SKIP
        HookResult(context='', block='', notice='', reminder='')
    """
    from ..work.progress import save_before_compact

    saved = save_before_compact(project)
    pointer = [{"path": project.rel(p), "before": before} for p, before in saved.items()]
    _compact_file(project, inp.session).write_text(json.dumps(pointer, ensure_ascii=False), encoding="utf-8")
    return HookResult()


def _saved_progress(project: Project, session: str) -> list[str]:
    """Build the lines that put back "지금 상황" of the documents saved before compaction (and what it replaced)."""
    from ..core import sections
    from ..core.project import read

    names = project.names
    now, past = names.title("now"), names.title("past")
    f = _compact_file(project, session)
    if not f.exists():
        return []
    out = ["", msg("[LanternSpec progress before compaction — saved to the documents]")]
    for item in json.loads(f.read_text(encoding="utf-8")):
        path = project.root / item["path"]
        if not path.exists():
            continue
        out += [f"{item['path']} · {now}:", sections.body(read(path), names.titles("now"))]
        if item.get("before"):
            out += [msg("(what was written just before compaction — moved to {past})", past=past), item["before"]]
    out.append(msg("→ If needed, add the context of the progress to '## {now}' in this document (a summary only).", now=now))
    return out


# --------------------------------------------------------------------------- document check · tool count


def post_tool(project: Project, tool: Tool, inp: HookInput) -> HookResult:
    """Count the tool call, and check any document the tool just wrote.

    Errors and structure problems block (the agent must fix them now); warnings are added as context.

    Args:
        project: The project.
        tool: The tool that called.
        inp: The hook call.

    Returns:
        block for broken documents, otherwise context for warnings; empty for other tools.

    Example:
        >>> post_tool(project, tool, HookInput(tool="Write", tool_input={"file_path": "docs/a.md"})).block  # doctest: +SKIP
        ''
    """
    runlog.tool(project, inp.session, inp.tool, inp.tool_input)
    if inp.tool not in tool.write_tools:
        return HookResult()
    rules = part_rules(project, tool, inp)  # tools without a pre-tool hook get a part's rules after its first edit
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
            hard_msgs.append(
                msg("LanternSpec document format: {rel} is broken — fix it now (don't change the template structure):", rel=rel)
            )
            hard_msgs += [
                f"- {f.message}" + (msg(" (line {line})", line=f.line) if f.line else "") + (f" → {f.hint}" if f.hint else "") for f in hard
            ]
        if soft:
            soft_msgs.append(msg("LanternSpec note ({rel}): ", rel=rel) + " · ".join(f.message for f in soft[:5]))
    return HookResult(block="\n".join(hard_msgs), context="\n\n".join(x for x in (rules, "" if hard_msgs else "\n".join(soft_msgs)) if x))


def feedback(project: Project, tool: Tool, inp: HookInput) -> HookResult:
    """Return nothing — the tool adapter delivers what post-tool held back (Antigravity).

    Args:
        project: The project.
        tool: The tool that called.
        inp: The hook call.

    Returns:
        An empty result.

    Example:
        >>> feedback(None, None, HookInput())
        HookResult(context='', block='', notice='', reminder='')
    """
    return HookResult()  # the tool adapter delivers what post-tool held back


# --------------------------------------------------------------------------- prompt: tech questions · ideas


def prompt(project: Project, tool: Tool, inp: HookInput) -> HookResult:
    """At the start of a user turn: log which skill started it, then look for a tech question or an idea.

    Explicit commands (`/…`, `$…`) are left to their skill.

    Args:
        project: The project.
        tool: The tool that called.
        inp: The hook call.

    Returns:
        Notes for the model as context; empty when there is nothing to say.

    Example:
        >>> prompt(project, tool, HookInput(prompt="JWT가 뭐야?")).context  # doctest: +SKIP
        "LanternSpec 기술 질문: 사용자가 기술 'JWT'을(를) 물었습니다. …"
    """
    reminder = "" if tool.restores_after_compaction else _reminder(project, inp.session)
    if not inp.turn_start:
        return HookResult(reminder=reminder)
    runlog.prompt(project, inp.session, inp.prompt)
    if not project.profile.exists or inp.prompt.lstrip().startswith(("/", "$")):
        return HookResult(reminder=reminder)  # explicit commands are handled by their skill
    notes = [n for n in (learn_detect(project, inp.session, inp.prompt), idea_detect(project, inp.session, inp.prompt)) if n]
    return HookResult(context="\n".join(notes), reminder=reminder)


_PARTICLE = r"(?:이|가|은|는|이란|란|라는\s*게|란\s*게)?"
TECH_Q = [
    re.compile(
        r"^\s*(?P<t>[\w.+#/\- ]{1,40}?)\s*" + _PARTICLE + r"\s*(?:뭐야|뭐예요|뭐에요|뭔가요|뭐지|뭐임|뭔데|무엇인가요|무엇이야|뭐하는\s*거)"
    ),
    re.compile(r"^\s*(?P<t>[\w.+#/\- ]{1,40}?)\s*" + _PARTICLE + r"\s*(?:어떻게\s*동작|설명해\s*(?:줘|주세요))"),
    re.compile(r"(?i)^\s*what\s+(?:is|are)\s+(?:an?\s+|the\s+)?(?P<t>[\w.+#/\- ]{1,40}?)\s*\??\s*$"),
    re.compile(r"(?i)^\s*how\s+(?:does|do)\s+(?:an?\s+|the\s+)?(?P<t>[\w.+#/\- ]{1,40}?)\s+work\s*\??\s*$"),
    re.compile(r"(?i)^\s*(?:please\s+)?explain\s+(?:an?\s+|the\s+)?(?P<t>[\w.+#/\- ]{1,40}?)\s*[.?!]?\s*$"),
]
IDEA_HINT = re.compile(
    r"(?:(?:으)?면\s*좋겠|있으면\s*좋|하고\s*싶|나중에\s*\S+\s*(?:하자|해야|추가|넣)|아이디어가?\s*있"
    r"|would be nice|it'd be nice|i'd like to|we could (?:also )?add|maybe (?:we|later)|later we)",
    re.I,
)


def tech_term(text: str) -> str:
    """Find the technology a message asks about ("X가 뭐야", "X 설명해 줘", "what is X").

    Only the first two lines are read.

    Args:
        text: The user's message.

    Returns:
        The term; "" when the message is not a tech question.

    Example:
        >>> tech_term("JWT가 뭐야?"), tech_term("What is a webhook?"), tech_term("버튼 색 바꿔 줘")
        ('JWT', 'webhook', '')
    """
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
    """React to a tech question according to `learn.detect`.

    manual: nothing · ask: suggest recording it as debt · auto: count the ask when a card exists,
    otherwise suggest a card once per conversation. Known terms and projects without a knowledge store are skipped.

    Args:
        project: The project.
        session: The conversation.
        text: The user's message.

    Returns:
        A note for the model; "" when there is nothing to say.

    Example:
        >>> learn_detect(project, "s1", "JWT가 뭐야?")  # doctest: +SKIP
        "LanternSpec 기술 질문: 'JWT'은(는) 부채 카드 D-007에 있어 물은 횟수를 셌습니다 (2번째). …"
    """
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
        return msg(
            "LanternSpec tech question: the user asked about the technology '{term}'. After answering, "
            'ask in one line "📒 Save it as debt?", and if yes, /l-learn {term}',
            term=term,
        ) + (
            msg(" (card {id} exists — counted as {value})", id=card.id, value=project.enums.value("debt_status", "asked_again"))
            if card
            else ""
        )
    if card:  # auto + card → count without asking
        r = debt.ask(project, term, session=session, context=msg("asked in conversation (detected automatically)"))
        if not r.counted:
            return ""
        return (
            msg(
                "LanternSpec tech question: '{term}' has debt card {id}, so the ask was counted (#{ask_count}",
                term=term,
                id=card.id,
                ask_count=r.ask_count,
            )
            + (msg(", {value} → reopened", value=project.enums.value("debt_status", "resolved")) if r.reopened else "")
            + msg("). When answering, link the earlier notes · card to help review.")
        )
    if not _once(project, f"learn:{session}:{debt.norm(term)}"):
        return ""
    return msg(
        "LanternSpec tech question: no card for '{term}'. After answering, suggest in one line \"📒 Make a debt card?\" (/l-learn {term}).",
        term=term,
    )


def idea_detect(project: Project, session: str, text: str) -> str:
    """React to idea-like words according to `idea.capture`.

    manual: nothing · ask: ask once per conversation whether to record it · auto: record it right away.

    Args:
        project: The project.
        session: The conversation.
        text: The user's message.

    Returns:
        A note for the model; "" when there is nothing to say.

    Example:
        >>> idea_detect(project, "s1", "다크 모드가 있으면 좋겠다")  # doctest: +SKIP
        'LanternSpec 아이디어: 아이디어 같은 말이 있습니다. …'
    """
    mode = project.profile.get("idea.capture")
    if mode == "manual" or not IDEA_HINT.search(text) or tech_term(text):
        return ""
    if mode == "ask":
        if not _once(project, f"idea:{session}"):
            return ""
        return msg(
            "LanternSpec idea: something sounds like an idea. After finishing the current work, ask "
            'once in one line "💡 Save this as an idea?" (if yes, /l-idea).'
        )
    return msg(
        "LanternSpec idea: something sounds like an idea. Without stopping the current work, "
        'record it right away by the /l-idea rules: lantern scaffold idea "<title>" --kind <kind> '
        '--raw "<original words>" --auto → mention it in one line only.'
    )


# --------------------------------------------------------------------------- stop: run log · sync suggestion


def stop(project: Project, tool: Tool, inp: HookInput) -> HookResult:
    """Write the turn's run-log line and, after a normal finish, maybe suggest /l-sync.

    Args:
        project: The project.
        tool: The tool that called.
        inp: The hook call.

    Returns:
        The suggestion as a notice, or an empty result.

    Example:
        >>> stop(project, tool, HookInput(session="s1")).notice  # doctest: +SKIP
        ''
    """
    runlog.stop(project, inp.session, model=inp.model or None)
    return HookResult(notice=sync_nudge(project, inp.session) if inp.finished else "")


def sync_nudge(project: Project, session: str) -> str:
    """Suggest /l-sync once when code changed but the work in the build stage left its documents untouched.

    Args:
        project: The project.
        session: The conversation (each work is suggested once per conversation).

    Returns:
        The suggestion; "" when there is nothing to suggest.

    Example:
        >>> sync_nudge(project, "s1")  # doctest: +SKIP
        'LanternSpec: 코드 2개 파일이 바뀌었는데 진행 중 작업 W-012의 문서는 그대로예요. …'
    """
    from ..core import frontmatter
    from ..core.project import git_out, nfc, read, work_id_of
    from ..report.scan import is_doc_path

    if not project.profile.exists:
        return ""
    works = [
        w
        for w in project.work_dirs()
        if project.doc_path(w, "plan").exists()
        and frontmatter.parse(read(project.doc_path(w, "plan"))).meta.get("status") == project.enums.value("work_status", "build")
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
        return msg(
            "LanternSpec: {count} code files changed, but the documents of work in progress {wid} "
            "didn't. If needed, align them with /l-sync (just a suggestion — not asked again for this "
            "work).",
            count=len(code),
            wid=wid,
        )
    return ""


# --------------------------------------------------------------------------- parts: each folder's rules


def pre_tool(project: Project, tool: Tool, inp: HookInput) -> HookResult:
    """Before a tool writes in a part for the first time in this conversation, hand over that part's AGENTS.md.

    Args:
        project: The project.
        tool: The tool that called.
        inp: The hook call.

    Returns:
        The part's rules as context; empty when there is nothing new to hand over.

    Example:
        >>> pre_tool(project, get("codex"), HookInput(session="s1", tool="apply_patch")).context  # doctest: +SKIP
        ''
    """
    return HookResult(context=part_rules(project, tool, inp) if inp.tool in tool.write_tools else "")


def part_rules(project: Project, tool: Tool, inp: HookInput) -> str:
    r"""Hand over the AGENTS.md of the part a tool call writes in — once per part and conversation, if the tool won't read it.

    A tool started inside the part's folder read it at the start, and a tool that reads a folder's
    AGENTS.md by itself needs nothing. The part is remembered for the reminder after compaction.

    Args:
        project: The project.
        tool: The tool that called.
        inp: The hook call.

    Returns:
        The part's AGENTS.md with a one-line heading; "" otherwise.

    Example:
        >>> part_rules(project, get("codex"), HookInput(session="s1", tool_input={"input": "*** Update File: api/x.py"}))  # doctest: +SKIP
        '[LanternSpec] api 영역의 규칙 (api/AGENTS.md):\n…'
    """
    from .parts import part_of

    found = [p for p in (part_of(project, f, inp.cwd) for f in tool.written_paths(inp)) if p]
    if not found:
        return ""
    part = found[0]
    state = _parts_state(project, inp.session)
    state["current"] = part
    rules_file = project.root / part / "AGENTS.md"
    started_inside = bool(inp.cwd) and part_of(project, inp.cwd) == part
    give = not tool.reads_nested_rules and not started_inside and part not in state["sent"] and rules_file.exists()
    if give:
        state["sent"].append(part)
    _save_parts_state(project, inp.session, state)
    if not give:
        return ""
    return msg("[LanternSpec] rules of part {part} ({file}):", part=part, file=project.rel(rules_file)) + "\n" + read(rules_file)


def _parts_file(project: Project, session: str) -> Path:
    return hook_state_dir(project) / f"parts-{re.sub(r'[^\w.-]', '_', session or 'unknown')[:80]}.json"


def _parts_state(project: Project, session: str) -> dict:
    path = _parts_file(project, session)
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, ValueError):
        data = {}
    return {"current": data.get("current") or "", "sent": list(data.get("sent") or [])}


def _save_parts_state(project: Project, session: str, state: dict) -> None:
    _parts_file(project, session).write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")


def _part_line(project: Project, session: str) -> str:
    """Which part the conversation was working in, for the note after compaction."""
    part = _parts_state(project, session)["current"]
    return msg("Part in progress: {part} — its rules are in {part}/AGENTS.md", part=part) if part else ""


def _reminder(project: Project, session: str) -> str:
    """A one- or two-line "where we are" note, for tools that can't restore it after compaction."""
    if not project.profile.exists:
        return ""
    from ..report.status import lines

    now = lines(project)[:1]
    part = _part_line(project, session)
    return "\n".join([msg("[LanternSpec now]"), *now, *([part] if part else [])])


HANDLERS: dict[str, Callable[[Project, Tool, HookInput], HookResult]] = {
    "session-start": session_start,
    "prompt": prompt,
    "pre-tool": pre_tool,
    "post-tool": post_tool,
    "feedback": feedback,
    "stop": stop,
    "pre-compact": pre_compact,
}
