"""Parse and edit the task lines of `할 일.md` and the acceptance criteria of `기획.md`.

Task line (TA-01):
    - [ ] W-012-T02 무엇 [크기:: M] [기준:: AC-1] [먼저:: T01] [담당:: 이름]
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
        return self.id.rsplit("-T", 1)[0]

    def list_attr(self, key: str) -> list[str]:
        return [x.strip() for x in re.split(r"[,\s]+", self.attrs.get(key, "")) if x.strip()]

    @property
    def deps(self) -> list[str]:
        out = []
        for d in self.list_attr("먼저"):
            d = d.upper()
            if re.fullmatch(r"T\d+", d):
                d = f"{self.work_id}-T{int(d[1:]):02d}"
            out.append(d)
        return out

    @property
    def criteria(self) -> list[str]:
        return [c.upper() for c in self.list_attr("기준") if re.fullmatch(r"(?i)AC-\d+", c)]

    @property
    def size(self) -> str:
        return self.attrs.get("크기", "")

    @property
    def started(self) -> str:
        return self.attrs.get("시작", "")

    @property
    def finished(self) -> str:
        return self.attrs.get("완료", "")

    @property
    def screen(self) -> str:
        return self.attrs.get("화면", "")


@dataclass
class Criterion:
    id: str
    text: str
    done: bool
    line_no: int


def parse_tasks(text: str) -> list[Task]:
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
    return re.sub(r"^(\s*- \[)( |x|X)(\])", lambda m: m.group(1) + ("x" if checked else " ") + m.group(3), line, count=1)


def find_task(tasks: list[Task], task_id: str) -> Task | None:
    task_id = task_id.upper()
    for t in tasks:
        if t.id == task_id:
            return t
    return None


@dataclass
class TaskGraph:
    tasks: list[Task] = field(default_factory=list)

    def by_id(self) -> dict[str, Task]:
        return {t.id: t for t in self.tasks}

    def blocked_reason(self, task: Task) -> str | None:
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
