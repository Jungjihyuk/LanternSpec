"""`lantern check --epic` — 수락 기준 규칙 검사 (PL-02, /l-plan 5단계).

Two questions per criterion: does it mean one thing? can it be checked?
"""

from __future__ import annotations

import re
from pathlib import Path

from ..check.check_docs import Finding
from ..core import frontmatter
from ..core.project import Project, read
from ..core.taskfile import parse_criteria

# words that make a result impossible to check ("빠르게" ✕ → "2초 안에" ○)
VAGUE_WORDS = [
    "빠르게",
    "빠른",
    "신속",
    "느리지 않",
    "적절히",
    "적절한",
    "적당히",
    "쉽게",
    "쉬운",
    "편리",
    "편하게",
    "직관적",
    "효율적",
    "최적",
    "충분히",
    "충분한",
    "원활",
    "자연스럽",
    "깔끔",
    "보기 좋",
    "사용자 친화",
    "안정적",
    "많은",
    "적은",
    "대부분",
    "일반적으로",
    "가능한 한",
    "가급적",
    "등등",
    "잘 ",
    "좋게",
    "좋은",
    "향상",
    "개선된",
    "더 나은",
    "유연",
    "강력",
    "멋진",
    "합리적",
]
AMBIGUOUS = [" 또는 ", "혹은", "및/또는", "/또는", "필요하면", "경우에 따라", "상황에 따라", "등 "]


def check_criteria(project: Project, plan: Path) -> list[Finding]:
    rel = project.rel(plan)
    text = read(plan)
    meta = frontmatter.parse(text).meta
    fmt = project.profile.get("plan.ac_format") or "gwt"
    acs = parse_criteria(text)
    out: list[Finding] = []
    if not acs:
        return [Finding("warn", rel, "ac-none", "수락 기준(- [ ] AC-1 …)이 없습니다", hint="기획.md '## 수락 기준'에 한 줄에 하나씩")]
    seen = set()
    for i, ac in enumerate(acs, start=1):
        line = ac.line_no + 1
        if ac.id in seen:
            out.append(Finding("error", rel, "ac-dup", f"{ac.id} 번호가 겹칩니다", line))
        seen.add(ac.id)
        if int(ac.id.split("-")[1]) != i:
            out.append(Finding("info", rel, "ac-order", f"{ac.id}: 번호가 순서대로가 아닙니다 (기대 AC-{i})", line))
        body = ac.text
        if "{{" in body:
            out.append(Finding("warn", rel, "ac-blank", f"{ac.id}: 빈칸이 남아 있습니다", line))
            continue
        if fmt == "gwt":
            if not re.search(r"행동\s*:", body) or not re.search(r"결과\s*:", body):
                out.append(
                    Finding(
                        "warn",
                        rel,
                        "ac-format",
                        f"{ac.id}: 상황 · 행동 · 결과 형식이 아닙니다",
                        line,
                        "예: AC-1 상황: 로그인 화면에서 · 행동: 카카오 버튼을 누르면 · 결과: 2초 안에 홈이 열린다",
                    )
                )
            result = re.split(r"결과\s*:", body, maxsplit=1)[-1]
        else:
            if "면" not in body:
                out.append(Finding("warn", rel, "ac-format", f"{ac.id}: '~하면 ~된다' 형식이 아닙니다", line))
            result = body.split("면", 1)[-1]
        for word in VAGUE_WORDS:
            if word in body:
                out.append(
                    Finding(
                        "warn",
                        rel,
                        "ac-vague",
                        f"{ac.id}: 확인하기 어려운 말 '{word.strip()}'",
                        line,
                        '숫자 · 화면에 보이는 것 · 상태로 바꾸세요 ("빠르게" → "2초 안에")',
                    )
                )
                break
        for word in AMBIGUOUS:
            if word in f" {result} ":
                out.append(
                    Finding(
                        "warn",
                        rel,
                        "ac-ambiguous",
                        f"{ac.id}: 결과가 여러 뜻으로 읽힙니다 ('{word.strip()}')",
                        line,
                        "기준을 둘로 나누세요",
                    )
                )
                break
        if len(result.strip()) < 4:
            out.append(Finding("warn", rel, "ac-result", f"{ac.id}: 결과가 너무 짧습니다", line))
    # PL-04: screen work under ui_reference=required needs a "matches the mockup" criterion
    if project.profile.get("plan.ui_reference") == "required" and meta.get("ui") is True:
        if not any("시안" in ac.text for ac in acs):
            out.append(
                Finding(
                    "warn",
                    rel,
                    "ac-mockup",
                    "화면 작업인데 '화면이 시안과 같다' 수락 기준이 없습니다",
                    hint="예: AC-n 결과: 화면이 화면/로그인.png 시안과 같다",
                )
            )
        if not _has_mockup(plan.parent):
            out.append(
                Finding(
                    "warn",
                    rel,
                    "mockup-missing",
                    "화면 시안이 없습니다 (화면/ 아래 이미지 · HTML)",
                    hint="Claude Design에서 HTML로 내보내 화면/에 두세요",
                )
            )
    return out


MOCKUP_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".html", ".htm", ".pdf"}


def _has_mockup(work_dir: Path) -> bool:
    d = work_dir / "화면"
    return d.exists() and any(p.suffix.lower() in MOCKUP_EXT for p in d.rglob("*") if p.is_file())


def has_mockup(work_dir: Path) -> bool:
    return _has_mockup(work_dir)


def run(project: Project, work_id: str | None = None) -> list[Finding]:
    out: list[Finding] = []
    works = [project.find_work(work_id)] if work_id else project.work_dirs()
    for w in works:
        if w is None:
            raise ValueError(f"작업 {work_id}를 찾지 못했습니다")
        plan = w / "기획.md"
        if plan.exists():
            out += check_criteria(project, plan)
    return out
