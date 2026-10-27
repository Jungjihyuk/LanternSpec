"""scripts/changelog.py — make release가 CHANGELOG에 버전을 찍는 규칙."""

import doctest
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("changelog", ROOT / "scripts/changelog.py")
assert spec and spec.loader
changelog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(changelog)


def test_docstring_examples():
    assert doctest.testmod(changelog).failed == 0


def test_both_real_changelogs_can_be_stamped():
    for name in changelog.FILES:
        text = (ROOT / name).read_text(encoding="utf-8")
        if "## [Unreleased]\n\n## [" in text:
            continue  # 비어 있으면 찍을 수 없는 게 맞다
        out = changelog.stamp(text, "9.9.9", "2099-01-01")
        assert "## [9.9.9] - 2099-01-01" in out and "/compare/v9.9.9...HEAD" in out


def test_refuses_empty_unreleased_and_older_version():
    text = "## [Unreleased]\n\n## [0.1.0] - 2026-10-27\n\n[Unreleased]: x/compare/v0.1.0...HEAD\n"
    with pytest.raises(SystemExit, match="비어 있습니다"):
        changelog.stamp(text, "0.2.0", "2026-10-28")
    text = text.replace("## [Unreleased]\n", "## [Unreleased]\n\n- 무엇\n")
    with pytest.raises(SystemExit, match="커야 합니다"):
        changelog.stamp(text, "0.1.0", "2026-10-28")
