"""Parse and edit the task lines of `할 일.md` and the acceptance criteria of `기획.md`.

Task line:
    - [ ] W-012-T02 무엇 [크기:: M] [기준:: AC-1] [먼저:: T01] [담당:: 이름]

Responsibilities:
    - read task lines and acceptance-criteria lines (outside code fences)
    - change one attribute or the check box of a line
    - tell why a task cannot start yet

Not here:
    - the `lantern task` commands that use these → work/tasks.py
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

TASK_LINE = re.compile(r"^(\s*)- \[( |x|X)\] (W-\d{3,}-T\d{2,})\b\s*(.*)$")
ATTR = re.compile(r"\[([^\[\]:]+?)::\s*([^\[\]]*?)\s*\]")
AC_LINE = re.compile(r"^(\s*)- \[( |x|X)\] (AC-\d+)\b\s*(.*)$")
UNKNOWN = "❓ 확인 필요"


@dataclass
class Task:
    """One task line of `할 일.md`.

    Attributes:
        id: Task ID, e.g. "W-012-T02".
        title: The text of the task, without attributes and markers.
        done: Whether the box is checked.
        attrs: Attribute name → value, from the `[이름:: 값]` parts.
        line_no: The 0-based line in the file.
        raw: The line exactly as written.
        unknown: Whether the line carries the "❓ 확인 필요" marker.
        parallel: Whether the line carries `[P]` (can run alongside other `[P]` tasks).

    Example:
        >>> task = parse_tasks("- [ ] W-012-T02 버튼 [크기:: M] [먼저:: T01]")[0]
        >>> task.id, task.title, task.size, task.deps
        ('W-012-T02', '버튼', 'M', ['W-012-T01'])
    """

    id: str
    title: str
    done: bool
    attrs: dict[str, str]
    line_no: int  # 0-based
    raw: str
    unknown: bool = False
    parallel: bool = False  # [P] — can run alongside other [P] tasks (parallel agents)

    @property
    def work_id(self) -> str:
        """The work the task belongs to, e.g. "W-012"."""
        return self.id.rsplit("-T", 1)[0]

    def list_attr(self, key: str) -> list[str]:
        """Read an attribute that holds several values.

        Args:
            key: Attribute name, e.g. "먼저".

        Returns:
            The values split on commas and spaces; empty when the attribute is missing.

        Example:
            >>> parse_tasks("- [ ] W-012-T03 셋 [먼저:: T01, T02]")[0].list_attr("먼저")
            ['T01', 'T02']
        """
        return [x.strip() for x in re.split(r"[,\s]+", self.attrs.get(key, "")) if x.strip()]

    @property
    def deps(self) -> list[str]:
        """Task IDs that must finish first, with short forms (`T01`) expanded to full IDs."""
        out = []
        for d in self.list_attr("먼저"):
            d = d.upper()
            if re.fullmatch(r"T\d+", d):
                d = f"{self.work_id}-T{int(d[1:]):02d}"
            out.append(d)
        return out

    @property
    def criteria(self) -> list[str]:
        """Acceptance criteria the task serves (`[기준:: AC-1]`), upper-cased."""
        return [c.upper() for c in self.list_attr("기준") if re.fullmatch(r"(?i)AC-\d+", c)]

    @property
    def size(self) -> str:
        """The size attribute (S · M · L), or ""."""
        return self.attrs.get("크기", "")

    @property
    def started(self) -> str:
        """The start time attribute, or ""."""
        return self.attrs.get("시작", "")

    @property
    def finished(self) -> str:
        """The finish time attribute, or ""."""
        return self.attrs.get("완료", "")

    @property
    def screen(self) -> str:
        """The screen attribute (which mockup the task builds), or ""."""
        return self.attrs.get("화면", "")


@dataclass
class Criterion:
    """One acceptance-criterion line of `기획.md`.

    Attributes:
        id: Criterion ID, e.g. "AC-1".
        text: The text after the ID.
        done: Whether the box is checked.
        line_no: The 0-based line in the file.

    Example:
        >>> parse_criteria("- [x] AC-1 누르면 열린다")[0]
        Criterion(id='AC-1', text='누르면 열린다', done=True, line_no=0)
    """

    id: str
    text: str
    done: bool
    line_no: int


def parse_tasks(text: str) -> list[Task]:
    r"""Read every task line of a document (outside code fences).

    Args:
        text: The whole document.

    Returns:
        The tasks, in file order.

    Example:
        >>> text = "- [x] W-001-T01 하나 [크기:: S]\n- [ ] W-001-T02 둘 [P] ❓ 확인 필요"
        >>> [(t.id, t.done, t.parallel, t.unknown) for t in parse_tasks(text)]
        [('W-001-T01', True, False, False), ('W-001-T02', False, True, True)]
    """
    tasks: list[Task] = []
    in_fence = False
    for i, line in enumerate(text.split("\n")):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = TASK_LINE.match(line)
        if not m:
            continue
        rest = m.group(4)
        attrs = {k.strip(): v.strip() for k, v in ATTR.findall(rest)}
        title = ATTR.sub("", rest).replace(UNKNOWN, "").replace("[P]", "").strip()
        tasks.append(
            Task(
                id=m.group(3).upper(),
                title=re.sub(r"\s+", " ", title),
                done=m.group(2).lower() == "x",
                attrs=attrs,
                line_no=i,
                raw=line,
                unknown=UNKNOWN in rest,
                parallel="[P]" in rest,
            )
        )
    return tasks


def parse_criteria(text: str) -> list[Criterion]:
    r"""Read every acceptance-criterion line of a document (outside code fences).

    Args:
        text: The whole document.

    Returns:
        The criteria, in file order.

    Example:
        >>> [c.id for c in parse_criteria("- [ ] AC-1 하나\n- [ ] AC-2 둘")]
        ['AC-1', 'AC-2']
    """
    out: list[Criterion] = []
    in_fence = False
    for i, line in enumerate(text.split("\n")):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = AC_LINE.match(line)
        if m:
            out.append(Criterion(id=m.group(3).upper(), text=m.group(4).strip(), done=m.group(2).lower() == "x", line_no=i))
    return out


def set_attr(line: str, key: str, value: str) -> str:
    """Set one `[key:: value]` attribute on a line, replacing it when present.

    A trailing "❓ 확인 필요" marker stays at the very end.

    Args:
        line: A task line.
        key: Attribute name.
        value: New value.

    Returns:
        The changed line.

    Example:
        >>> set_attr("- [ ] W-001-T01 하나 [크기:: S]", "크기", "M")
        '- [ ] W-001-T01 하나 [크기:: M]'
        >>> set_attr("- [ ] W-001-T01 하나 ❓ 확인 필요", "시작", "09:00")
        '- [ ] W-001-T01 하나 [시작:: 09:00] ❓ 확인 필요'
    """
    pat = re.compile(r"\[" + re.escape(key) + r"::\s*[^\[\]]*?\s*\]")
    new = f"[{key}:: {value}]"
    if pat.search(line):
        return pat.sub(new, line, count=1)
    # keep a trailing ❓ marker at the very end
    if line.rstrip().endswith(UNKNOWN):
        base = line.rstrip()[: -len(UNKNOWN)].rstrip()
        return f"{base} {new} {UNKNOWN}"
    return f"{line.rstrip()} {new}"


def set_checked(line: str, checked: bool) -> str:
    """Check or uncheck the box of a list line.

    Args:
        line: A `- [ ]` line.
        checked: True to check, False to uncheck.

    Returns:
        The changed line (unchanged when it has no box).

    Example:
        >>> set_checked("- [ ] W-001-T01 하나", True)
        '- [x] W-001-T01 하나'
    """
    return re.sub(r"^(\s*- \[)( |x|X)(\])", lambda m: m.group(1) + ("x" if checked else " ") + m.group(3), line, count=1)


def find_task(tasks: list[Task], task_id: str) -> Task | None:
    """Find a task by ID.

    Args:
        tasks: Tasks from parse_tasks.
        task_id: Task ID (case does not matter).

    Returns:
        The task; None when it is not in the list.

    Example:
        >>> find_task(parse_tasks("- [ ] W-001-T01 하나"), "w-001-t01").title
        '하나'
    """
    task_id = task_id.upper()
    for t in tasks:
        if t.id == task_id:
            return t
    return None


@dataclass
class TaskGraph:
    r"""The tasks of one work, for dependency questions.

    Attributes:
        tasks: All tasks of the work.

    Example:
        >>> graph = TaskGraph(parse_tasks("- [ ] W-001-T01 하나\n- [ ] W-001-T02 둘 [먼저:: T01]"))
        >>> graph.blocked_reason(graph.tasks[1])
        'W-001-T01 먼저'
    """

    tasks: list[Task] = field(default_factory=list)

    def by_id(self) -> dict[str, Task]:
        """Index the tasks by ID.

        Returns:
            Task ID → task.

        Example:
            >>> list(TaskGraph(parse_tasks("- [ ] W-001-T01 하나")).by_id())
            ['W-001-T01']
        """
        return {t.id: t for t in self.tasks}

    def blocked_reason(self, task: Task) -> str | None:
        r"""Tell why a task cannot start now.

        Args:
            task: A task of this graph.

        Returns:
            The reason (already done, needs checking, or a dependency missing or unfinished);
            None when the task can start.

        Example:
            >>> graph = TaskGraph(parse_tasks("- [x] W-001-T01 하나\n- [ ] W-001-T02 둘 [먼저:: T01]"))
            >>> graph.blocked_reason(graph.tasks[1]) is None
            True
        """
        if task.done:
            return "이미 완료"
        if task.unknown:
            return "❓ 확인 필요"
        index = self.by_id()
        for dep in task.deps:
            d = index.get(dep)
            if d is None:
                return f"먼저 끝나야 할 일 {dep}이 목록에 없음"
            if not d.done:
                return f"{dep} 먼저"
        return None
