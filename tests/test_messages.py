"""The message catalog matches the code: every message is translated, slots agree, nothing is stale, no Korean is left in code."""

import ast
import re
from pathlib import Path

import pytest

from lanternspec.core.messages import catalog

SRC = Path(__file__).resolve().parent.parent / "src" / "lanternspec"
HANGUL = re.compile("[가-힣]")
SLOT = re.compile(r"(?<!\{)\{([a-z_0-9]+)(?:![rsa])?(?::[^}]*)?\}(?!\})")
LOOKS_LIKE_REGEX = re.compile(r"\(\?|\\[swdb]|\[")
KOREAN_DATA = {("learn/knowledge/obsidian.py", "요약")}  # a frontmatter key people write in Korean notes


def _modules():
    for p in sorted(SRC.rglob("*.py")):
        yield p.relative_to(SRC).as_posix(), ast.parse(p.read_text(encoding="utf-8"))


def _docstrings(tree):
    kinds = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    return {id(n.body[0].value) for n in ast.walk(tree) if isinstance(n, kinds) and ast.get_docstring(n)}


def _msg_literals():
    for rel, tree in _modules():
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "msg" and n.args:
                if isinstance(n.args[0], ast.Constant):
                    yield rel, n.args[0].value


def test_every_message_has_a_korean_translation():
    missing = sorted({f"{rel}: {m}" for rel, m in _msg_literals() if "ko" not in (catalog().get(m) or {})})
    assert not missing, "\n".join(missing[:10])


@pytest.mark.parametrize("english", list(catalog()))
def test_slots_match(english):
    for language, text in catalog()[english].items():
        assert set(SLOT.findall(text)) == set(SLOT.findall(english)), f"{language}: {text}"


def test_no_stale_entries():
    literals = {n.value for _, tree in _modules() for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    stale = [m for m in catalog() if m not in literals]
    assert not stale, "\n".join(stale[:10])


def test_no_korean_left_in_code():
    found = []
    for rel, tree in _modules():
        docs = _docstrings(tree)
        parents = {id(c): n for n in ast.walk(tree) for c in ast.iter_child_nodes(n)}
        for n in ast.walk(tree):
            if not (isinstance(n, ast.Constant) and isinstance(n.value, str)) or id(n) in docs or not HANGUL.search(n.value):
                continue
            chain, x = [], n
            while id(x) in parents:
                x = parents[id(x)]
                chain.append(x)
            if any(isinstance(c, ast.Compare) for c in chain[:2]):  # accepting Korean input, e.g. "없음"
                continue
            if LOOKS_LIKE_REGEX.search(n.value) or (rel, n.value) in KOREAN_DATA:
                continue
            found.append(f"{rel}:{n.lineno}: {n.value[:60]!r}")
    assert not found, "\n".join(found[:10])
