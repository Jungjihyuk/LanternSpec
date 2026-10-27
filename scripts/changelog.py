"""CHANGELOG.md · CHANGELOG.ko.md의 [Unreleased]를 새 버전 칸으로 옮긴다 — `make release`가 부른다.

책임:
    - [Unreleased] 내용을 "## [버전] - 날짜" 칸으로 옮기고 [Unreleased]는 비우기
    - 맨 아래 비교 링크 맞추기 ([Unreleased] → 새 버전, 새 버전 → 이전 버전과 비교)

하지 않는 일:
    - [Unreleased]에 무엇을 쓸지 정하기 → /release-notes 스킬
    - 버전 올리기 · 커밋 · 태그 · push → Makefile (release)
"""

from __future__ import annotations

import datetime
import re
import sys
from pathlib import Path

from packaging.version import Version

FILES = ("CHANGELOG.md", "CHANGELOG.ko.md")
REPO = "https://github.com/Jungjihyuk/LanternSpec"
UNRELEASED = "## [Unreleased]\n"
LINK = re.compile(r"^\[Unreleased\]: .*/compare/v(?P<prev>[^.\s]+(?:\.[^.\s]+)*)\.\.\.HEAD$", re.M)


def stamp(text: str, version: str, date: str) -> str:
    r"""CHANGELOG 글 하나의 [Unreleased]를 새 버전 칸으로 옮긴다.

    Args:
        text: CHANGELOG 전체 글.
        version: 새 버전. 예: "0.2.0".
        date: 배포 날짜. 예: "2026-10-28".

    Returns:
        버전을 찍은 CHANGELOG 글.

    Raises:
        SystemExit: [Unreleased] 칸이 없거나 비었을 때, 새 버전이 이전 버전보다 크지 않을 때.

    Example:
        >>> text = "## [Unreleased]\n\n- 새 기능\n\n## [0.1.0] - 2026-10-27\n\n[Unreleased]: x/compare/v0.1.0...HEAD\n"
        >>> print(stamp(text, "0.2.0", "2026-10-28").replace(REPO, "x"), end="")  # doctest: +NORMALIZE_WHITESPACE
        ## [Unreleased]
        <BLANKLINE>
        ## [0.2.0] - 2026-10-28
        <BLANKLINE>
        - 새 기능
        <BLANKLINE>
        ## [0.1.0] - 2026-10-27
        <BLANKLINE>
        [Unreleased]: x/compare/v0.2.0...HEAD
        [0.2.0]: x/compare/v0.1.0...v0.2.0
    """
    if UNRELEASED not in text:
        raise SystemExit("✖ '## [Unreleased]' 칸이 없습니다")
    start = text.index(UNRELEASED) + len(UNRELEASED)
    end = text.index("\n## [", start)
    body = text[start:end].strip()
    if not body:
        raise SystemExit("✖ [Unreleased]가 비어 있습니다 — 먼저 /release-notes로 바뀐 점을 정리하세요")
    link = LINK.search(text)
    if link is None:
        raise SystemExit("✖ 맨 아래 '[Unreleased]: …/compare/v이전버전...HEAD' 링크가 없습니다")
    prev = link.group("prev")
    if Version(version) <= Version(prev):
        raise SystemExit(f"✖ 새 버전 {version}이 이전 버전 {prev}보다 커야 합니다")
    text = text[:start] + f"\n## [{version}] - {date}\n\n{body}\n" + text[end:]
    return LINK.sub(f"[Unreleased]: {REPO}/compare/v{version}...HEAD\n[{version}]: {REPO}/compare/v{prev}...v{version}", text)


def main(argv: list[str]) -> int:
    """`uv run python scripts/changelog.py 0.2.0` — 두 CHANGELOG에 버전을 찍는다 (둘 다 되거나 둘 다 안 되거나)."""
    if len(argv) != 1:
        raise SystemExit("사용법: python scripts/changelog.py <새 버전>")
    version, today = argv[0], datetime.date.today().isoformat()
    stamped = {name: stamp(Path(name).read_text(encoding="utf-8"), version, today) for name in FILES}
    for name, text in stamped.items():
        Path(name).write_text(text, encoding="utf-8")
        print(f"✔ {name}: [Unreleased] → [{version}] - {today}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
