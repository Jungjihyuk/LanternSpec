"""Rules files stay within what the installed AI tools read in full — measured in bytes and lines, never tokens.

One token is at least one byte for every tokenizer, so a byte budget holds for any model without a
tokenizer or an API. Korean (3 bytes a letter) and English (1 byte) weigh differently on their own.
"""

import json

from conftest import init_project
from lanternspec.check.budget import Budget, folder_budget, root_budget, size
from lanternspec.tools import get, resolve


def test_the_budget_follows_the_tightest_installed_tool():
    assert root_budget(resolve(["claude"])) == Budget(200, None)  # Claude only gives a line guideline
    assert root_budget(resolve(["codex"])) == Budget(None, int(32 * 1024 * 0.9))  # the rules chain
    assert root_budget(resolve(["claude", "codex", "antigravity"])) == Budget(200, int(24_000 * 0.9))  # agy cuts at 24,000 bytes
    assert folder_budget(resolve(["codex"])).max_bytes == int(8000 * 0.9)  # a hook hands it over in one go


def test_bytes_weigh_korean_and_english_by_themselves():
    assert size("가")[0] == 3 and size("a")[0] == 1 and size("가a\nb")[1] == 2


def test_codex_hooks_raise_the_context_limit_only_where_context_can_be_added():
    hooks = get("codex").hooks()
    limit = {event: entries[0]["hooks"][0].get("additionalContextLimit") for event, entries in hooks.items()}
    assert limit["SessionStart"] == limit["UserPromptSubmit"] == limit["PostToolUse"] == get("codex").hook_context_max_tokens
    assert limit["PreCompact"] is None and limit["Stop"] is None  # Codex warns about the setting on these


def test_doctor_shows_each_rules_file_against_its_budget(repo):
    init_project(repo)
    repo("install", "--tools", "claude,antigravity")
    (repo.root / "backend").mkdir()
    (repo.root / "backend/AGENTS.md").write_text("# backend\n", encoding="utf-8")
    _, out = repo("doctor", ok=False)
    assert "AGENTS.md" in out and "(예산 21.1KB · 200줄)" in out
    assert "backend/AGENTS.md" in out
    agents = repo.root / "AGENTS.md"
    agents.write_text(agents.read_text(encoding="utf-8") + "- 우리 규칙\n" * 250, encoding="utf-8")
    _, out = repo("doctor", ok=False)
    assert "예산을 넘었습니다: LanternSpec 블록" in out and "직접 쓴 글" in out


def test_upgrade_warns_when_agents_md_grows_past_the_budget(repo):
    init_project(repo)
    repo("install")
    agents = repo.root / "AGENTS.md"
    agents.write_text(agents.read_text(encoding="utf-8") + "- 우리 규칙\n" * 250, encoding="utf-8")
    _, out = repo("upgrade")
    assert "⚠ AGENTS.md" in out and "예산을 넘었습니다" in out
    settings = json.loads((repo.root / ".claude/settings.json").read_text(encoding="utf-8"))
    assert settings["hooks"]  # the warning never stops the upgrade
