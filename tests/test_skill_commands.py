"""Every `lantern …` command a skill tells the AI to run must exist with those flags."""

import re
import shlex

import pytest

from lanternspec import resources
from lanternspec.cli import build_parser
from lanternspec.core.names import languages
from lanternspec.tools.skills import SKILL_NAMES


def _commands(text: str):
    found = []
    for m in re.finditer(r"`(lantern [^`]+)`", text):
        found.append(m.group(1))
    in_fence = False
    for line in text.split("\n"):
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence and line.strip().startswith("lantern "):
            found.append(line.strip())
    return found


def _normalise(cmd: str) -> str:
    cmd = re.sub(r"<!--.*?-->", "", cmd)  # lantern:if markers inside a command line
    cmd = cmd.split("  #")[0].split(" # ")[0].strip()
    cmd = re.sub(r"\$\([^)]*\)", "X", cmd)
    cmd = re.sub(r"\[([^\[\]]*)\]", r" \1 ", cmd)  # optional parts are kept (they must parse too)
    cmd = re.sub(r'"<[^>"]*>"', "X", cmd)
    cmd = re.sub(r"<[^>]*>", "X", cmd)
    cmd = cmd.replace("…", "").replace("\\", " ")
    cmd = re.sub(r"(\S+)\|(\S+)", lambda m: m.group(1).split("|")[0], cmd)  # first of alternatives
    return re.sub(r"\s+", " ", cmd).strip()


SOURCES = [f"locales/{lang}/{rel}" for lang in languages() for rel in [*(f"skills/{n}/SKILL.md" for n in SKILL_NAMES), "agents/AGENTS.md"]]


@pytest.mark.parametrize("source", SOURCES)
def test_skill_commands_parse(source):
    text = resources.read_text(source)
    cmds = _commands(text)
    parser = build_parser()
    for raw in cmds:
        norm = _normalise(raw)
        argv = shlex.split(norm)[1:]
        if argv[:2] == ["task", "add"]:
            argv = ["task-add", *argv[2:]]
        if len(argv) <= 1 or argv == ["--version"]:
            continue  # prose mentions like `lantern close` / `lantern scaffold …`
        try:
            parser.parse_args(argv)
        except SystemExit:
            pytest.fail(f"{source}: `{raw}` → `{' '.join(argv)}` does not parse")


@pytest.mark.parametrize("language", languages())
def test_every_skill_mentions_its_wrapup(language):
    for name in SKILL_NAMES:
        text = resources.read_text(f"locales/{language}/skills/{name}/SKILL.md")
        if name in ("l-map",):
            assert "lantern map" in text
            continue
        if name == "l-check":
            assert "lantern check" in text
            continue
        assert f"lantern close {name}" in text, f"{name} lacks the common close"
