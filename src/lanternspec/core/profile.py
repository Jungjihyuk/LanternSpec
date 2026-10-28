"""`lantern.yaml` — the project's answers to /l-init, plus what can be computed from them.

Only human answers live in the file. Everything derived (enabled docs, folder paths)
is computed here on demand (one fact, one place).

Responsibilities:
    - defaults, allowed values and validation of lantern.yaml
    - read, write (with explanatory comments) and update lantern.yaml
    - the document folders and which documents the answers turn on

Not here:
    - creating the folders and documents → work/scaffold.py
    - the principle and convention tables behind kind · languages · code_size → core/principles.py
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from . import names as names_mod
from . import principles
from .messages import msg

PROFILE_FILE = "lantern.yaml"
PROFILE_VERSION = 1

DEFAULTS: dict[str, Any] = {
    "lantern": PROFILE_VERSION,
    "project": {
        "name": "",
        "origin": "greenfield",
        "team": "solo",
        "members": [],
        "clients": [],
        "server": "none",
        "language": "ko",
        "comment_language": None,
        "kind": None,
        "external": False,
        "languages": [],
        "code_size": None,
    },
    "docs": {"root": "docs/", "remote": "shared", "extra": [], "sections": {}, "unused_sections": []},
    "knowledge": None,
    "design": {"tool": "none", "approval": "required"},
    "git": {"hooks": "warn", "base": "main"},
    "idea": {"capture": "manual"},
    "plan": {"max_questions": 3, "ac_format": "gwt", "ui_reference": "off"},
    "learn": {"detect": "manual", "max_candidates": 3, "verify": "self"},
    "build": {"report_cycle": "work", "merge_approval": "required", "loop": "off", "loop_limit": 3},
    "check": {"max_lines": 300},
    "report": {"views": ["kanban", "timeline", "debt"]},
}

KNOWLEDGE_DEFAULTS: dict[str, Any] = {"type": "obsidian", "path": "", "areas_from": None, "write": "direct"}

CHOICES: dict[str, tuple[str, ...]] = {
    "project.origin": ("greenfield", "brownfield"),
    "project.team": ("solo", "team"),
    "project.server": ("none", "external", "custom"),
    "project.kind": principles.kind_names(),
    "project.comment_language": tuple(principles.comment_languages()),
    "project.code_size": principles.SIZES,
    "docs.remote": ("shared", "local"),
    "knowledge.type": ("obsidian", "folder", "notion"),
    "knowledge.write": ("direct", "propose_only"),
    "design.tool": ("claude-design", "figma", "canva", "none"),
    "design.approval": ("required", "auto", "off"),
    "git.hooks": ("warn", "block"),
    "idea.capture": ("manual", "ask", "auto"),
    "plan.ac_format": ("gwt", "simple"),
    "plan.ui_reference": ("off", "required"),
    "learn.detect": ("manual", "ask", "auto"),
    "learn.verify": ("self", "explain"),
    "build.report_cycle": ("work", "criterion", "task"),
    "build.merge_approval": ("required", "auto"),
    "build.loop": ("off", "on"),
}
LIST_CHOICES: dict[str, tuple[str, ...]] = {
    "project.clients": ("web", "desktop", "mobile"),
    "project.languages": principles.language_names(),
    "report.views": ("kanban", "timeline", "domain", "trace", "debt", "sync", "eval"),
    "docs.extra": ("api",),
}
MIN_INTS: dict[str, int] = {"plan.max_questions": 1, "learn.max_candidates": 1, "check.max_lines": 20, "build.loop_limit": 1}

# Code paths whose change means "the schema changed" (the schema-record check). Overridable via git.schema_paths.
DEFAULT_SCHEMA_PATHS = [
    "**/migrations/**",
    "**/migration/**",
    "**/*.sql",
    "**/schema.prisma",
    "**/alembic/versions/**",
    "**/drizzle/**",
    "**/*.dbml",
]


def _deep_merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def get_path(data: dict[str, Any], dotted: str, default: Any = None) -> Any:
    """Read a value from nested mappings by a dotted key.

    Args:
        data: Nested mappings, e.g. the parsed lantern.yaml.
        dotted: Key such as "project.team".
        default: Returned when any part of the key is missing.

    Returns:
        The value, or default.

    Example:
        >>> get_path({"project": {"team": "solo"}}, "project.team")
        'solo'
        >>> get_path({}, "project.team", "none")
        'none'
    """
    cur: Any = data
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def set_path(data: dict[str, Any], dotted: str, value: Any) -> None:
    """Set a value in nested mappings by a dotted key, creating the mappings on the way.

    Args:
        data: Nested mappings, changed in place.
        dotted: Key such as "build.test".
        value: The new value.

    Example:
        >>> data = {}
        >>> set_path(data, "build.test", "uv run pytest")
        >>> data
        {'build': {'test': 'uv run pytest'}}
    """
    parts = dotted.split(".")
    cur = data
    for part in parts[:-1]:
        if not isinstance(cur.get(part), dict):
            cur[part] = {}
        cur = cur[part]
    cur[parts[-1]] = value


@dataclass
class Profile:
    """The settings of one project: lantern.yaml merged over the defaults.

    Attributes:
        data: All settings, defaults filled in.
        path: Where lantern.yaml lives (or would live).
        exists: Whether lantern.yaml exists.

    Example:
        >>> profile = Profile(data={"project": {"team": "team", "clients": ["web"]}})
        >>> profile.team, profile.clients, profile.docs_root
        (True, ['web'], 'docs')
    """

    data: dict[str, Any]
    path: Path | None = None
    exists: bool = False

    def get(self, dotted: str, default: Any = None) -> Any:
        """Read a setting by a dotted key.

        Args:
            dotted: Key such as "plan.ac_format".
            default: Returned when the key is missing.

        Returns:
            The value, or default.

        Example:
            >>> Profile(data={"plan": {"ac_format": "simple"}}).get("plan.ac_format")
            'simple'
        """
        return get_path(self.data, dotted, default)

    # convenient accessors
    @property
    def docs_root(self) -> str:
        """The documents root without a trailing slash (`docs` by default)."""
        return str(self.get("docs.root", "docs/")).rstrip("/") or "docs"

    @property
    def remote(self) -> str:
        """How documents are stored: "shared" (pushed with the code) or "local"."""
        return self.get("docs.remote", "shared")

    @property
    def team(self) -> bool:
        """Whether two or more people work on the project."""
        return self.get("project.team") == "team"

    @property
    def clients(self) -> list[str]:
        """Screen types the project has (web · desktop · mobile)."""
        return list(self.get("project.clients") or [])

    @property
    def server(self) -> str:
        """Server kind: "none", "external" (a backend service) or "custom" (own server code)."""
        return self.get("project.server", "none")

    @property
    def knowledge(self) -> dict[str, Any] | None:
        """The knowledge store settings with defaults filled in; None when there is no store."""
        k = self.data.get("knowledge")
        if not k:
            return None
        return _deep_merge(KNOWLEDGE_DEFAULTS, k)

    @property
    def comment_language(self) -> str:
        """Language of code comments and docstrings — project.comment_language, else project.language."""
        return str(self.get("project.comment_language") or self.get("project.language") or "ko")

    @property
    def language(self) -> str:
        """Language of documents, skills and messages (project.language), fixed when the project is set up."""
        return str(self.get("project.language") or "ko")

    @property
    def names(self) -> names_mod.Names:
        """Every name the program uses for this project: the language's names plus renamed or unused protected sections."""
        return names_mod.load(self.language, self.get("docs.sections") or {}, self.get("docs.unused_sections") or [])

    @property
    def brownfield(self) -> bool:
        """Whether the project started from existing code."""
        return self.get("project.origin") == "brownfield"

    @property
    def schema_paths(self) -> list[str]:
        """Glob patterns of schema files (git.schema_paths, else the defaults)."""
        return list(self.get("git.schema_paths") or DEFAULT_SCHEMA_PATHS)


def load(root: Path) -> Profile:
    """Read lantern.yaml from a project root.

    Args:
        root: Project root.

    Returns:
        The profile; the defaults (exists=False) when the file is missing.

    Raises:
        ValueError: The file is not a mapping.

    Example:
        >>> load(Path("my-app")).get("project.team")  # doctest: +SKIP
        'solo'
    """
    path = root / PROFILE_FILE
    if not path.exists():
        return Profile(data=copy.deepcopy(DEFAULTS), path=path, exists=False)
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(msg("{profile_file} is malformed (must be key: value)", profile_file=PROFILE_FILE))
    data = _deep_merge(DEFAULTS, raw)
    if "knowledge" in raw and not raw.get("knowledge"):
        data["knowledge"] = None
    _unbool(data)
    return Profile(data=data, path=path, exists=True)


def _unbool(data: dict[str, Any]) -> None:
    """YAML 1.1 reads a bare `off`/`on` as a boolean; the profile means the word (`ui_reference: off`)."""
    for key, allowed in CHOICES.items():
        val = get_path(data, key)
        if isinstance(val, bool):
            word = "on" if val else "off"
            if word in allowed:
                set_path(data, key, word)


def validate(data: dict[str, Any]) -> list[str]:
    """Check settings against the allowed values and limits.

    Args:
        data: All settings (usually merged over DEFAULTS).

    Returns:
        Human-readable problems; empty when the settings are valid.

    Example:
        >>> validate(DEFAULTS)
        []
        >>> validate({**DEFAULTS, "git": {"hooks": "loud"}})[0]
        "git.hooks: 'loud' 는 허용되지 않는 값입니다 (가능: warn | block)"
    """
    problems: list[str] = []
    for key, allowed in CHOICES.items():
        if key.startswith("knowledge.") and not data.get("knowledge"):
            continue
        val = get_path(data, key)
        if val is not None and val not in allowed:
            problems.append(msg("{key}: '{val}' is not allowed (available: {items})", key=key, val=val, items=" | ".join(allowed)))
    for key, allowed in LIST_CHOICES.items():
        val = get_path(data, key) or []
        if not isinstance(val, list):
            problems.append(msg("{key}: must be a list (e.g. [{allowed}])", key=key, allowed=allowed[0]))
            continue
        for item in val:
            if item not in allowed:
                problems.append(msg("{key}: '{item}' is not allowed (available: {items})", key=key, item=item, items=", ".join(allowed)))
    if not isinstance(get_path(data, "project.external", False), bool):
        problems.append(msg("project.external must be true or false"))
    for key, minimum in MIN_INTS.items():
        val = get_path(data, key)
        if val is None:
            continue
        if not isinstance(val, int) or isinstance(val, bool):
            problems.append(msg("{key}: must be an integer", key=key))
        elif val < minimum:
            problems.append(msg("{key}: must be at least {minimum} (now {val})", key=key, minimum=minimum, val=val))
    if data.get("knowledge"):
        k = data["knowledge"]
        if not isinstance(k, dict) or not k.get("path"):
            problems.append(msg("knowledge.path: the knowledge store path is empty (delete the knowledge block if there is none)"))
    problems += _section_problems(data)
    if get_path(data, "project.team") == "team" and not get_path(data, "project.members"):
        problems.append(msg("project.members: for a team (2 or more), list the owner candidates"))
    if get_path(data, "lantern") != PROFILE_VERSION:
        problems.append(msg("lantern: the file format version must be {profile_version}", profile_version=PROFILE_VERSION))
    return problems


def _section_problems(data: dict[str, Any]) -> list[str]:
    """Check project.language and the protected-section decisions (docs.sections · docs.unused_sections)."""
    language = str(get_path(data, "project.language") or "ko")
    if language not in names_mod.languages():
        return [
            msg(
                "project.language: no language pack '{language}' (available: {items})",
                language=language,
                items=", ".join(names_mod.languages()),
            )
        ]
    roles = [s.role for s in names_mod.load(language).sections()]
    problems: list[str] = []
    renamed = get_path(data, "docs.sections") or {}
    if not isinstance(renamed, dict):
        return [msg("docs.sections: must map section → new name (e.g. {{now: Today}})")]
    for role, titles in renamed.items():
        if role not in roles:
            problems.append(
                msg("docs.sections: '{role}' is not a protected section (available: {items})", role=role, items=", ".join(roles))
            )
        elif not (isinstance(titles, str) and titles.strip()) and not (
            isinstance(titles, list) and titles and all(isinstance(x, str) and x.strip() for x in titles)
        ):
            problems.append(msg("docs.sections.{role}: must be a new name (text) or a list of names", role=role))
    unused = get_path(data, "docs.unused_sections") or []
    if not isinstance(unused, list):
        return problems + [msg("docs.unused_sections: must be a list (e.g. [schema])")]
    problems += [
        msg("docs.unused_sections: '{r}' is not a protected section (available: {items})", r=r, items=", ".join(roles))
        for r in unused
        if r not in roles
    ]
    return problems


# --------------------------------------------------------------------------- render


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(_yaml_scalar(v) for v in value) + "]"
    s = str(value)
    dumped = yaml.safe_dump(s, allow_unicode=True, width=10_000).strip()
    if dumped.endswith("\n..."):
        dumped = dumped[:-4].strip()
    if dumped.endswith("..."):
        dumped = dumped[:-3].strip()
    return dumped


def render(data: dict[str, Any]) -> str:
    """Write settings as lantern.yaml text, with a comment explaining each key.

    Args:
        data: Settings (missing keys take the defaults).

    Returns:
        The whole file.

    Example:
        >>> render({"project": {"name": "my-app"}}).splitlines()[4]
        '  name: my-app'
    """
    d = _deep_merge(DEFAULTS, data)
    p, docs, k = d["project"], d["docs"], d.get("knowledge")
    s = _yaml_scalar
    lines = [
        msg("# lantern.yaml — what kind of project this is (the answers to /l-init). People may edit it by hand."),
        msg("lantern: {profile_version}                  # version of this file's format", profile_version=PROFILE_VERSION),
        "",
        "project:",
        f"  name: {s(p.get('name', ''))}",
        msg("  origin: {s}        # greenfield (new) | brownfield (existing code)", s=s(p["origin"])),
        msg("  team: {s}              # solo (one person) | team (2 or more)", s=s(p["team"])),
        msg("  members: {s}            # owner candidates for a team", s=s(p.get("members") or [])),
        msg("  clients: {s}          # web | desktop | mobile — several allowed", s=s(p.get("clients") or [])),
        msg(
            "  server: {s}            # none (no server) | external (a backend service like Supabase · "
            "Firebase) | custom (you write the server code — wherever it runs)",
            s=s(p["server"]),
        ),
        msg("  language: {s}              # language of documents · guidance", s=s(p.get("language", "ko"))),
        msg(
            "  comment_language: {s}    # language of code comments (docstrings · comments) — ko | en, empty follows language",
            s=s(p.get("comment_language")),
        ),
        msg(
            "  kind: {s}              # {items} — what the design principles are chosen by",
            s=s(p.get("kind")),
            items=" | ".join(principles.kind_names()),
        ),
        msg(
            "  external: {s}         # connects to outside tools · services (AI tools · payments · external APIs …)",
            s=s(bool(p.get("external"))),
        ),
        msg(
            "  languages: {s}        # languages to choose code conventions for ({items})",
            s=s(p.get("languages") or []),
            items=", ".join(principles.language_names()),
        ),
        msg(
            "  code_size: {s}         # small | medium | large — measured (lantern principles detect). "
            "When it crosses a boundary, lantern doctor asks whether to raise it",
            s=s(p.get("code_size")),
        ),
        "",
        "docs:",
        f"  root: {s(docs['root'])}",
        msg(
            "  remote: {s}          # shared (pushed together) | local (documents not pushed) — change it with lantern docs-mode",
            s=s(docs["remote"]),
        ),
    ]
    if docs.get("extra"):
        lines.append(msg("  extra: {s}           # optional documents turned on (api)", s=s(docs["extra"])))
    if docs.get("sections"):
        lines.append(
            msg(
                "  sections:                  # renamed protected sections (lantern sections rename) — in "
                "a list, the first is the current name"
            )
        )
        lines += [f"    {role}: {s(title)}" for role, title in docs["sections"].items()]
    if docs.get("unused_sections"):
        lines.append(msg("  unused_sections: {s}   # protected sections not used (lantern sections off)", s=s(docs["unused_sections"])))
    lines.append("")
    if k:
        k = _deep_merge(KNOWLEDGE_DEFAULTS, k)
        lines += [
            msg("knowledge:                  # the learning track. Delete this block if there is none"),
            msg("  type: {s}            # obsidian | folder (any Markdown folder)", s=s(k["type"])),
            f"  path: {s(k['path'])}",
        ]
        if k.get("token_env"):
            lines.append(msg("  token_env: {s}   # environment variable holding the Notion token", s=s(k["token_env"])))
        if k.get("areas_from"):
            lines.append(
                msg("  areas_from: {s}    # (optional) read this folder's categories to suggest debt-card topics", s=s(k["areas_from"]))
            )
        lines += [
            msg("  write: {s}            # direct (write right after approval) | propose_only (draft files only)", s=s(k["write"])),
            "",
        ]
    else:
        lines += [msg("# knowledge: add this block once there is a knowledge store (type · path · write)"), ""]
    lines += [
        "design:",
        msg("  tool: {s}       # claude-design | figma | canva (each tool's MCP) | none", s=s(d["design"]["tool"])),
        msg("  approval: {s}  # required (always approve) | auto (skip small designs) | off", s=s(d["design"]["approval"])),
        "",
        "git:",
        msg(
            "  hooks: {s}              # warn (warning only) | block — applies only to commit message "
            "· schema log · document format checks",
            s=s(d["git"]["hooks"]),
        ),
        msg("  base: {s}                 # the base branch work branches merge into (main | dev …)", s=s(d["git"]["base"])),
    ]
    if d["git"].get("schema_paths"):
        lines.append(msg("  schema_paths: {s}  # where schema files are (schema log check)", s=s(d["git"]["schema_paths"])))
    lines += [
        "",
        "idea:",
        msg(
            "  capture: {s}           # manual (only when called) | ask (notice and ask) | auto (record on its own)",
            s=s(d["idea"]["capture"]),
        ),
        "plan:",
        msg("  max_questions: {s}         # questions asked at once (at least 1)", s=s(d["plan"]["max_questions"])),
        msg("  ac_format: {s}           # gwt (situation·action·result) | simple (when … then …)", s=s(d["plan"]["ac_format"])),
        msg("  ui_reference: {s}         # off | required (screen work needs a mockup to proceed)", s=s(d["plan"]["ui_reference"])),
        "learn:",
        msg(
            "  detect: {s}            # manual (only when called) | ask (ask on each question in "
            "conversation) | auto (suggest new tech, count right away if a card exists)",
            s=s(d["learn"]["detect"]),
        ),
        msg("  max_candidates: {s}        # debt candidates shown at once (at least 1)", s=s(d["learn"]["max_candidates"])),
        msg("  verify: {s}             # self (mark it yourself) | explain (try explaining it in one line)", s=s(d["learn"]["verify"])),
        "build:",
        msg(
            "  report_cycle: {s}        # work (each work) | criterion (each acceptance criterion) | "
            "task (each task) — problems are reported right away anytime",
            s=s(d["build"]["report_cycle"]),
        ),
        msg(
            "  merge_approval: {s}  # required (approve before merging) | auto (summary report after merging)",
            s=s(d["build"]["merge_approval"]),
        ),
        msg(
            "  loop: {s}                # off (only the small loop within a task) | on (rerun the "
            "whole work until the acceptance tests pass) — lantern harness suggest",
            s=s(d["build"]["loop"]),
        ),
        msg("  loop_limit: {s}           # max rounds of the big loop", s=s(d["build"]["loop_limit"])),
    ]
    if d["build"].get("test"):
        lines.append(msg("  test: {s}   # test command (work finish · scan --tests)", s=s(d["build"]["test"])))
    for role in principles.COMMAND_ROLES:
        if d["build"].get(role):
            where = msg("run after editing") if role == "format" else "lantern lint · /l-build · CI"
            lines.append(
                msg(
                    "  {role}: {s}   # {role_label} command ({where})",
                    role=role,
                    s=s(d["build"][role]),
                    role_label=principles.role_label(role),
                    where=where,
                )
            )
    lines += [
        "check:",
        msg("  max_lines: {s}            # warn to split when longer (doesn't block)", s=s(d["check"]["max_lines"])),
        "report:",
        f"  views: {s(d['report']['views'])}",
        "",
    ]
    return "\n".join(lines)


def save(root: Path, data: dict[str, Any]) -> Path:
    """Validate settings and write lantern.yaml.

    Args:
        root: Project root.
        data: Settings (missing keys take the defaults).

    Returns:
        The written file.

    Raises:
        ValueError: The settings are not valid; the message lists every problem.

    Example:
        >>> save(Path("my-app"), {"project": {"name": "my-app"}})  # doctest: +SKIP
        PosixPath('my-app/lantern.yaml')
    """
    problems = validate(_deep_merge(DEFAULTS, data))
    if problems:
        raise ValueError(msg("Invalid lantern.yaml values:\n- ") + "\n- ".join(problems))
    path = root / PROFILE_FILE
    path.write_text(render(data), encoding="utf-8")
    return path


def update(root: Path, updates: dict[str, Any]) -> None:
    """Change some values in lantern.yaml.

    When every key is already written in the file (and no value is a mapping), only those values change
    and the comments stay; otherwise the whole file is written again.

    Args:
        root: Project root.
        updates: Dotted key → new value.

    Raises:
        ValueError: The result would not be valid.

    Example:
        >>> update(Path("my-app"), {"project.code_size": "medium"})  # doctest: +SKIP
    """
    path = root / PROFILE_FILE
    data = load(root).data
    for k, v in updates.items():
        set_path(data, k, v)
    problems = validate(data)
    if problems:
        raise ValueError("\n".join(problems))
    text: str | None = path.read_text(encoding="utf-8")
    for k, v in updates.items():
        # a mapping spans several lines: render the whole file again instead of editing one line
        text = set_in_text(text, k, v) if text is not None and not isinstance(v, dict) else None
    if text is None:  # a key not written in the file yet: render the whole file again
        save(root, data)
    else:
        path.write_text(text, encoding="utf-8")


def parse_value(raw: str) -> Any:
    """Parse a CLI value (`key=value`) with YAML rules.

    Args:
        raw: The text after "=".

    Returns:
        The parsed value; the text itself when it is not valid YAML.

    Example:
        >>> parse_value("[web, mobile]"), parse_value("3"), parse_value("true"), parse_value("a: [")
        (['web', 'mobile'], 3, True, 'a: [')
    """
    try:
        return yaml.safe_load(raw)
    except yaml.YAMLError:
        return raw


# --------------------------------------------------------------------------- enabled docs


@dataclass
class DocSpec:
    """One document or folder the answers turn on.

    Attributes:
        key: Stable key, e.g. "screens".
        path: Path from the documents root; folders end with "/".
        template: The template to fill; None for folders and generated files.
        reason: Why it is on, shown to the user.
        sections: Client sections to keep in the document (web · desktop · mobile).
        variant: Which variant of the template to use, e.g. the data document for a server DB.

    Example:
        >>> spec = enabled_docs(Profile(data={"project": {"clients": ["web"]}}))[-2]
        >>> spec.key, spec.sections
        ('platform', ['web'])
    """

    key: str
    path: str  # relative to docs root; folders end with "/"
    template: str | None
    reason: str
    sections: list[str] = field(default_factory=list)  # client sections to keep
    variant: str | None = None


DATA_VARIANT = {"none": "on-device storage", "external": "external DB", "custom": "server DB"}
CLIENT_LABEL = {"web": "web", "desktop": "desktop", "mobile": "mobile"}


def data_variant(server: str) -> str:
    """Name where the data lives for a server answer, in the project's language.

    Args:
        server: project.server (none · external · custom).

    Returns:
        The name, e.g. "서버 DB"; an unknown answer as it is.

    Example:
        >>> data_variant("custom"), data_variant("other")
        ('서버 DB', 'other')
    """
    return msg(DATA_VARIANT[server]) if server in DATA_VARIANT else server


def client_label(client: str) -> str:
    """Name a client kind in the project's language.

    Args:
        client: One of project.clients (web · desktop · mobile).

    Returns:
        The name, e.g. "모바일"; an unknown kind as it is.

    Example:
        >>> client_label("mobile")
        '모바일'
    """
    return msg(CLIENT_LABEL[client]) if client in CLIENT_LABEL else client


def enabled_docs(profile: Profile) -> list[DocSpec]:
    """List the documents and folders the answers turn on.

    Args:
        profile: The project's settings.

    Returns:
        The documents, always-on ones first.

    Example:
        >>> keys = [d.key for d in enabled_docs(Profile(data={"project": {"server": "custom"}}))]
        >>> "api" in keys, "screens" in keys
        (True, False)
    """
    clients = profile.clients
    server = profile.server
    extra = set(profile.get("docs.extra") or [])
    n = profile.names
    f = n.folder

    def doc(key: str, folder: str, role: str, reason: str, **kw: Any) -> DocSpec:
        """A document named by its role, created from the template of the same name."""
        return DocSpec(key, f"{f(folder)}/{n.file(role)}", n.doc(role), reason, **kw)

    def folder(key: str, reason: str, folder_key: str = "") -> DocSpec:
        """A folder; folder_key names it in names.yaml when it differs from the key."""
        return DocSpec(key, f(folder_key or key) + "/", None, reason)

    data_dir = f"{f('current')}/{f('data')}"
    out: list[DocSpec] = [
        DocSpec("moc", n.file("moc"), n.doc("moc"), msg("always")),
        folder("templates", msg("always")),
        folder("ideas", msg("always")),
        folder("works", msg("always")),
        folder("archive", msg("always")),
        doc("project-definition", "current", "project_definition", msg("always")),
        doc("features", "current", "features", msg("always")),
        doc("architecture", "current", "architecture", msg("always")),
        DocSpec(
            "data",
            f"{data_dir}/{n.file('data')}",
            n.doc("data"),
            msg("always ({get})", get=data_variant(server)),
            variant=data_variant(server) if server in DATA_VARIANT else None,
        ),
        DocSpec("schema", f"{data_dir}/schema.dbml", None, msg("data source (DBML)")),
        folder("rules", msg("always")),
        doc("unit-log", "rules", "unit_log", msg("always")),
        folder("reports", msg("always"), "past_reports"),
    ]
    if clients:
        labels = ", ".join(client_label(c) for c in clients if c in CLIENT_LABEL)
        out += [
            DocSpec(
                "screens", f"{f('current')}/{f('screens')}/{n.file('screens')}", n.doc("screens"), msg("clients: {labels}", labels=labels)
            ),
            doc("platform", "current", "platform", msg("clients: {labels}", labels=labels), sections=list(clients)),
            doc("deploy", "current", "deploy", msg("clients: {labels}", labels=labels), sections=list(clients)),
        ]
    if server == "custom" or (server == "external" and "api" in extra):
        out.append(doc("api", "current", "api", msg("custom server") if server == "custom" else msg("external service + API on")))
    if server == "custom":
        out.append(doc("server-ops", "current", "server_ops", msg("custom server")))
    if profile.team:
        out += [doc("collab", "rules", "collab", msg("2 or more people")), folder("meetings", msg("2 or more people"))]
    if profile.knowledge:
        out += [
            folder("debt-cards", msg("knowledge store (the learning track)"), "debt_cards"),
            DocSpec("debt-status", f"{f('debt')}/{n.file('debt_status')}", None, msg("knowledge store (generated)")),
            doc("known-tech", "debt", "known_tech", msg("knowledge store")),
        ]
    if profile.get("project.kind"):
        out.append(DocSpec("principles", f"{f('rules')}/{n.file('principles')}", None, msg("project kind set (generated)")))
    if profile.brownfield:
        out += [folder("legacy", msg("brownfield")), doc("legacy-map", "legacy", "legacy_map", msg("brownfield"))]
    return out


# Doc keys that may become "사용 안 함" (inactive) when answers change. Folders are never removed.
OPTIONAL_DOC_KEYS = {"screens", "platform", "deploy", "api", "server-ops", "collab", "known-tech", "legacy-map"}

# Which /l-init follow-up questions a newly enabled doc needs (English; msg() translates them).
FOLLOW_UP_QUESTIONS = {
    "deploy": "How it's deployed (hosting · stores · signing …)",
    "platform": "Platform integration (push · deep links · URL schemes …)",
    "api": "API style (REST · GraphQL …) and authentication",
    "server-ops": "Where the server is deployed and how it's run",
    "collab": "Team member names (project.members) and review · branch rules",
    "known-tech": "Technologies you already know well (left out of debt candidates)",
}


_KEY_LINE = re.compile(r"^(\s*)([A-Za-z_]+):(\s*)([^#\n]*?)(\s*#.*)?$")


def set_in_text(text: str, dotted: str, value: Any) -> str | None:
    r"""Replace one scalar value in lantern.yaml text, keeping comments.

    Args:
        text: The lantern.yaml text.
        dotted: Key such as "git.hooks".
        value: The new value.

    Returns:
        The changed text; None when the key is not written in the text.

    Example:
        >>> set_in_text("git:\n  hooks: warn   # warn | block\n", "git.hooks", "block")
        'git:\n  hooks: block  # warn | block\n'
        >>> set_in_text("git:\n", "git.base", "dev") is None
        True
    """
    parts = dotted.split(".")
    lines = text.split("\n")
    depth = 0
    start, end = 0, len(lines)
    for depth, part in enumerate(parts):
        indent = "  " * depth
        found = None
        for i in range(start, end):
            m = _KEY_LINE.match(lines[i])
            if m and m.group(1) == indent and m.group(2) == part:
                found = i
                break
        if found is None:
            return None
        if depth == len(parts) - 1:
            m = _KEY_LINE.match(lines[found])
            assert m
            comment = (m.group(5) or "").strip()
            new_line = f"{indent}{part}: {_yaml_scalar(value)}"
            if comment:
                new_line += "  " + comment
            lines[found] = new_line
            return "\n".join(lines)
        # narrow the block to the children of this key
        start = found + 1
        new_end = len(lines)
        for j in range(start, end):
            stripped = lines[j]
            if stripped.strip() and not stripped.startswith("  " * (depth + 1)) and not stripped.lstrip().startswith("#"):
                new_end = j
                break
        end = new_end
    return None
