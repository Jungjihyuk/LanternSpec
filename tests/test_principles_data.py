"""principles.yaml · conventions/*.yaml — the shape the program reads, in every language.

Each table keeps one set of rules; text sits next to it under language keys (ko: · en:).
"""

import pytest
import yaml

from lanternspec import resources
from lanternspec.core import principles
from lanternspec.core.names import languages

LEVELS = {"must", "should", "skip"}
SIZES = ["small", "medium", "large"]
LEVEL_KEYS = {"lint", "typecheck", "type_hints", "docs", "tests"}
TOOL_KEYS = {"package", "format", "lint", "typecheck", "test"}


def _text_blocks(node, path=""):
    """Every mapping that holds text under language keys, with where it is."""
    if isinstance(node, dict):
        if set(node) & {"ko", "en"}:
            yield path, node
        for k, v in node.items():
            if k not in ("ko", "en"):
                yield from _text_blocks(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _text_blocks(v, f"{path}[{i}]")


@pytest.mark.parametrize("rel", ["principles.yaml", *(f"conventions/{p.name}" for _, p in resources.iter_files("conventions"))])
def test_every_text_has_every_language(rel):
    raw = yaml.safe_load(resources.read_text(rel))
    blocks = list(_text_blocks(raw))
    assert blocks
    for path, block in blocks:
        missing = [lang for lang in languages() if lang not in block]
        assert not missing, f"{rel}{path}: {missing}"


@pytest.mark.parametrize("locale", languages())
def test_every_principle_has_a_level_for_every_kind(locale):
    data = principles.table(locale)
    kinds = set(data["kinds"])
    assert kinds == {"script", "cli", "library", "service", "data"}
    assert list(data["sizes"]["code"]) == SIZES and list(data["sizes"]["people"]) == SIZES
    assert data["sizes"]["code"]["small"]["below"] == 10000 and data["sizes"]["code"]["medium"]["below"] == 50000
    for pid, p in data["principles"].items():
        assert p["name"] and p["explain"] and p["rules"], pid
        assert p["grows_with"] in {"code", "people", "none"}, pid
        assert set(p["levels"]) == kinds, pid
        for kind, level in p["levels"].items():
            values = set(level.values()) if isinstance(level, dict) else {level}
            if isinstance(level, dict):
                assert set(level) == {"external", "else"}, (pid, kind)
            assert values <= LEVELS, (pid, kind)
    assert set(data["always"]) == {"think_first", "surgical_changes", "verify_by_goal"}
    assert set(data["levels"]) == LEVELS and data["priority"]
    assert set(data["roles"]) == {"package", "format", "lint", "typecheck", "test"} and set(data["rules"]) == LEVEL_KEYS
    assert set(principles.comment_languages(locale)) == {"ko", "en"}
    for p in data["principles"].values():
        assert p.get("min_when_large", "should") in LEVELS


@pytest.mark.parametrize("locale", languages())
def test_every_language_file_has_the_same_shape(locale):
    names = sorted(p.name for _, p in resources.iter_files("conventions"))
    assert names == ["go.yaml", "python.yaml", "rust.yaml", "swift.yaml", "typescript.yaml"]
    for name in names:
        c = principles.conventions(name.removesuffix(".yaml"), locale)
        assert c["language"] == name.removesuffix(".yaml") and c["label"] and c["detect"], name
        assert set(c["tools"]) == TOOL_KEYS, name
        assert all(t["name"] for t in c["tools"].values()), name
        assert c["docs"]["style"] and c["docs"]["example"], name
        assert list(c["levels"]) == SIZES, name
        assert c["runners"], name
        for r in c["runners"]:
            assert r["name"] and isinstance(r["prefix"], str) and isinstance(r["ci"], list), (name, r)
            assert all(set(step) <= {"uses", "with", "run"} and ("uses" in step or "run" in step) for step in r["ci"]), (name, r)
        assert set(c["existing"]) == {"format", "lint", "typecheck"}, name
        for cands in c["existing"].values():
            assert all(e["name"] and e["find"] and e["command"] for e in cands), name
        for size in SIZES:
            assert set(c["levels"][size]) == LEVEL_KEYS, (name, size)
