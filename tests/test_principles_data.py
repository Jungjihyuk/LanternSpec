"""resources/principles — the principle table and per-language conventions have the shape the program reads."""

import yaml

from lanternspec import resources

LEVELS = {"must", "should", "skip"}
SIZES = ["small", "medium", "large"]
LEVEL_KEYS = {"lint", "typecheck", "type_hints", "docs", "tests"}
TOOL_KEYS = {"package", "format", "lint", "typecheck", "test"}


def _load(rel):
    return yaml.safe_load(resources.read_text(f"principles/{rel}"))


def test_every_principle_has_a_level_for_every_kind():
    data = _load("principles.yaml")
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
    for p in data["principles"].values():
        assert p.get("min_when_large", "should") in LEVELS


def test_every_language_file_has_the_same_shape():
    names = sorted(p.name for _, p in resources.iter_files("principles/conventions"))
    assert names == ["go.yaml", "python.yaml", "rust.yaml", "swift.yaml", "typescript.yaml"]
    for name in names:
        c = _load(f"conventions/{name}")
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
