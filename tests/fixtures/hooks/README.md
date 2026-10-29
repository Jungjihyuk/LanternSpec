# Hook payload samples

One JSON file per tool and per our hook event (`<tool>/<event>.json`), read by `tests/test_tool_health.py`.
Each sample must parse into a call with every field `tools/health.py` expects.

Where they come from:
- claude: Claude Code hooks reference (snake_case keys), checked on 2.1.308
- codex: Codex hooks docs (same schema as Claude Code, plus `turn_id`), checked on 0.164.0
- antigravity: agy's built-in guide `agy-customizations/docs/hooks.md` (camelCase keys), checked on 1.4.9

These follow the documented shape; values are made up. When a tool changes its payload, add the
new shape as another file (e.g. `post-tool.0.170.json`) instead of editing the old one.
