"""The same word in two vocabularies must be a known, written-down choice (GLOSSARY.md).

LanternSpec names things in several places — lantern.yaml keys, enums.yaml lists, names.yaml roles,
skills, CLI commands and the Tool · Adapter contracts. When one word turns up in two of them (or with
two spellings in one, like `language` · `languages`), people and AI start to mix them up. Most such
overlaps are one idea used in several places (`plan`); a few are different ideas sharing a word
(`origin`). Either way the glossary must say so, so a new overlap is noticed when it is added.
"""

import argparse
import re
from collections import defaultdict
from pathlib import Path

import yaml

from lanternspec import resources
from lanternspec.cli import build_parser
from lanternspec.core.profile import DEFAULTS
from lanternspec.learn.knowledge import Adapter
from lanternspec.tools.base import Tool
from lanternspec.tools.skills import SKILL_NAMES

GLOSSARY = Path(__file__).resolve().parents[1] / "GLOSSARY.md"


def _keys(d: dict, out: set) -> set:
    for k, v in d.items():
        out.add(k)
        if isinstance(v, dict):
            _keys(v, out)
    return out


def _vocabularies() -> dict[str, set[str]]:
    names = yaml.safe_load(resources.read_text("names.yaml"))
    sub = next(a for a in build_parser()._actions if isinstance(a, argparse._SubParsersAction))
    vocab = {
        "lantern.yaml": _keys(DEFAULTS, set()),
        "enums.yaml": set(yaml.safe_load(resources.read_text("locales/ko/templates/_meta/enums.yaml"))),
        "skills": {s.removeprefix("l-") for s in SKILL_NAMES},
        "cli": set(sub.choices),
        "Tool": {m for m in dir(Tool) if not m.startswith("_")},
        "Adapter": {m for m in dir(Adapter) if not m.startswith("_")},
    }
    vocab.update({f"names.yaml {group}": set(names[group]) for group in names})
    return vocab


def _norm(word: str) -> str:
    w = word.lower().replace("-", "_")
    if w.endswith("ies"):
        return w[:-3] + "y"
    return w[:-1] if w.endswith("s") and not w.endswith("ss") else w


def overlaps() -> dict[str, set[str]]:
    """Normalized word → "vocabulary:spelling" entries, for words in two vocabularies or with two spellings."""
    where: dict[str, set[str]] = defaultdict(set)
    for vocab, words in _vocabularies().items():
        for w in words:
            where[_norm(w)].add(f"{vocab}:{w}")
    out = {}
    for word, entries in where.items():
        vocabs = {e.split(":")[0] for e in entries}
        spellings = {e.split(":")[1] for e in entries}
        if len(vocabs) > 1 or len(spellings) > 1:
            out[word] = entries
    return out


def glossary_words() -> set[str]:
    """Every `word` in the first column of GLOSSARY.md's tables, normalized."""
    words = set()
    for line in GLOSSARY.read_text(encoding="utf-8").splitlines():
        if line.startswith("| ") and not line.startswith("|---"):
            first = line.split("|")[1]
            words |= {_norm(w) for w in re.findall(r"`([^`]+)`", first)}
    return words


def test_every_overlapping_name_is_in_the_glossary():
    missing = {w: sorted(e) for w, e in overlaps().items() if w not in glossary_words()}
    assert not missing, "Add these to GLOSSARY.md (same idea in several places, or different ideas sharing a word):\n" + "\n".join(
        f"  {w}: {', '.join(e)}" for w, e in sorted(missing.items())
    )


def test_the_check_sees_overlaps_inside_one_vocabulary_too():
    assert "language" in overlaps()  # project.language (documents) · project.languages (code)
