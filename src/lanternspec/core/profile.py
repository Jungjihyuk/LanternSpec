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
        raise ValueError(f"{PROFILE_FILE} 형식이 올바르지 않습니다 (키: 값 형태여야 함)")
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
            problems.append(f"{key}: '{val}' 는 허용되지 않는 값입니다 (가능: {' | '.join(allowed)})")
    for key, allowed in LIST_CHOICES.items():
        val = get_path(data, key) or []
        if not isinstance(val, list):
            problems.append(f"{key}: 목록이어야 합니다 (예: [{allowed[0]}])")
            continue
        for item in val:
            if item not in allowed:
                problems.append(f"{key}: '{item}' 는 허용되지 않는 값입니다 (가능: {', '.join(allowed)})")
    if not isinstance(get_path(data, "project.external", False), bool):
        problems.append("project.external: true 또는 false여야 합니다")
    for key, minimum in MIN_INTS.items():
        val = get_path(data, key)
        if val is None:
            continue
        if not isinstance(val, int) or isinstance(val, bool):
            problems.append(f"{key}: 정수여야 합니다")
        elif val < minimum:
            problems.append(f"{key}: 최소 {minimum} 이상이어야 합니다 (지금 {val})")
    if data.get("knowledge"):
        k = data["knowledge"]
        if not isinstance(k, dict) or not k.get("path"):
            problems.append("knowledge.path: 지식 저장소 경로가 비어 있습니다 (없으면 knowledge 블록을 지우세요)")
    problems += _section_problems(data)
    if get_path(data, "project.team") == "team" and not get_path(data, "project.members"):
        problems.append("project.members: 2인 이상(team)이면 담당자 후보를 적어 주세요")
    if get_path(data, "lantern") != PROFILE_VERSION:
        problems.append(f"lantern: 파일 형식 버전은 {PROFILE_VERSION} 이어야 합니다")
    return problems


def _section_problems(data: dict[str, Any]) -> list[str]:
    """Check project.language and the protected-section decisions (docs.sections · docs.unused_sections)."""
    language = str(get_path(data, "project.language") or "ko")
    if language not in names_mod.languages():
        return [f"project.language: '{language}' 언어 묶음이 없습니다 (가능: {', '.join(names_mod.languages())})"]
    roles = [s.role for s in names_mod.load(language).sections()]
    problems: list[str] = []
    renamed = get_path(data, "docs.sections") or {}
    if not isinstance(renamed, dict):
        return ["docs.sections: 칸 → 새 이름 형태여야 합니다 (예: {now: 오늘 한 일})"]
    for role, titles in renamed.items():
        if role not in roles:
            problems.append(f"docs.sections: '{role}'는 보호 칸이 아닙니다 (가능: {', '.join(roles)})")
        elif not (isinstance(titles, str) and titles.strip()) and not (
            isinstance(titles, list) and titles and all(isinstance(x, str) and x.strip() for x in titles)
        ):
            problems.append(f"docs.sections.{role}: 새 이름(글자)이나 이름 목록이어야 합니다")
    unused = get_path(data, "docs.unused_sections") or []
    if not isinstance(unused, list):
        return problems + ["docs.unused_sections: 목록이어야 합니다 (예: [schema])"]
    problems += [f"docs.unused_sections: '{r}'는 보호 칸이 아닙니다 (가능: {', '.join(roles)})" for r in unused if r not in roles]
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
        "# lantern.yaml — 이 프로젝트가 어떤 프로젝트인지 (/l-init의 답). 사람이 직접 고쳐도 된다.",
        f"lantern: {PROFILE_VERSION}                  # 이 파일 형식의 버전",
        "",
        "project:",
        f"  name: {s(p.get('name', ''))}",
        f"  origin: {s(p['origin'])}        # greenfield(새로) | brownfield(기존 코드 있음)",
        f"  team: {s(p['team'])}              # solo(1인) | team(2인 이상)",
        f"  members: {s(p.get('members') or [])}            # team일 때 담당자 후보",
        f"  clients: {s(p.get('clients') or [])}          # web | desktop | mobile — 여러 개 가능",
        f"  server: {s(p['server'])}            # none(서버 없음) | external(Supabase · Firebase 같은 백엔드 서비스)"
        " | custom(서버 코드를 직접 작성 — 어디에 띄우든)",
        f"  language: {s(p.get('language', 'ko'))}              # 문서 · 안내의 언어",
        f"  comment_language: {s(p.get('comment_language'))}    # 코드 주석(docstring · 주석)의 언어 — ko | en, 비우면 language를 따름",
        f"  kind: {s(p.get('kind'))}              # {' | '.join(principles.kind_names())} — 설계 원칙을 고르는 기준",
        f"  external: {s(bool(p.get('external')))}         # 바깥 도구 · 서비스(AI 도구 · 결제 · 외부 API 등)에 붙나",
        f"  languages: {s(p.get('languages') or [])}        # 코드 컨벤션을 고를 언어 ({', '.join(principles.language_names())})",
        f"  code_size: {s(p.get('code_size'))}         # small | medium | large — 잰 값 (lantern principles detect)."
        " 경계를 넘으면 lantern doctor가 올릴지 묻는다",
        "",
        "docs:",
        f"  root: {s(docs['root'])}",
        f"  remote: {s(docs['remote'])}          # shared(같이 올림) | local(문서는 원격에 안 올림) — 바꿀 때는 lantern docs-mode",
    ]
    if docs.get("extra"):
        lines.append(f"  extra: {s(docs['extra'])}           # '필요하면 켜짐' 문서 중 켠 것 (api)")
    if docs.get("sections"):
        lines.append("  sections:                  # 이름을 바꾼 보호 칸 (lantern sections rename) — 목록이면 앞이 지금 이름")
        lines += [f"    {role}: {s(title)}" for role, title in docs["sections"].items()]
    if docs.get("unused_sections"):
        lines.append(f"  unused_sections: {s(docs['unused_sections'])}   # 쓰지 않는 보호 칸 (lantern sections off)")
    lines.append("")
    if k:
        k = _deep_merge(KNOWLEDGE_DEFAULTS, k)
        lines += [
            "knowledge:                  # 배우는 선로. 없으면 이 블록을 지운다",
            f"  type: {s(k['type'])}            # obsidian | folder(아무 Markdown 폴더)",
            f"  path: {s(k['path'])}",
        ]
        if k.get("token_env"):
            lines.append(f"  token_env: {s(k['token_env'])}   # Notion 토큰을 담은 환경 변수")
        if k.get("areas_from"):
            lines.append(f"  areas_from: {s(k['areas_from'])}    # (선택) 이 폴더 분류를 읽어 부채 카드 주제 추가를 제안한다")
        lines += [f"  write: {s(k['write'])}            # direct(승인 후 바로 씀) | propose_only(초안 파일만)", ""]
    else:
        lines += ["# knowledge: 지식 저장소가 생기면 블록을 추가한다 (type · path · write)", ""]
    lines += [
        "design:",
        f"  tool: {s(d['design']['tool'])}       # claude-design | figma | canva (각 도구의 MCP) | none",
        f"  approval: {s(d['design']['approval'])}  # required(항상 승인) | auto(작은 설계는 건너뜀) | off",
        "",
        "git:",
        f"  hooks: {s(d['git']['hooks'])}              # warn(경고만) | block(막기) — 커밋 메시지 · 스키마 기록 · 문서 양식 검사에만 적용",
        f"  base: {s(d['git']['base'])}                 # 작업 브랜치를 머지할 기준 브랜치 (main | dev …)",
    ]
    if d["git"].get("schema_paths"):
        lines.append(f"  schema_paths: {s(d['git']['schema_paths'])}  # 스키마 파일 위치 (스키마 기록 검사)")
    lines += [
        "",
        "idea:",
        f"  capture: {s(d['idea']['capture'])}           # manual(직접 부를 때만) | ask(알아채고 묻기) | auto(알아서 기록)",
        "plan:",
        f"  max_questions: {s(d['plan']['max_questions'])}         # 한 번에 묻는 질문 수 (최소 1)",
        f"  ac_format: {s(d['plan']['ac_format'])}           # gwt(상황·행동·결과) | simple(~하면 ~된다)",
        f"  ui_reference: {s(d['plan']['ui_reference'])}         # off | required(화면 작업은 시안이 있어야 진행)",
        "learn:",
        f"  detect: {s(d['learn']['detect'])}            # manual(불릴 때만) | ask(대화 중 질문마다 묻기)"
        " | auto(새 기술은 제안, 카드 있으면 바로 셈)",
        f"  max_candidates: {s(d['learn']['max_candidates'])}        # 한 번에 보여 줄 부채 후보 수 (최소 1)",
        f"  verify: {s(d['learn']['verify'])}             # self(스스로 표시) | explain(한 줄 설명해 보기)",
        "build:",
        f"  report_cycle: {s(d['build']['report_cycle'])}        # work(작업마다) | criterion(수락 기준마다) | task(할 일마다)"
        " — 문제가 생기면 언제든 바로 보고",
        f"  merge_approval: {s(d['build']['merge_approval'])}  # required(반영 전 승인) | auto(반영 후 요약 보고)",
        f"  loop: {s(d['build']['loop'])}                # off(할 일 안의 작은 반복만)"
        " | on(수락 기준 테스트가 통과할 때까지 작업 전체를 다시) — lantern harness suggest",
        f"  loop_limit: {s(d['build']['loop_limit'])}           # 큰 반복 최대 횟수",
    ]
    if d["build"].get("test"):
        lines.append(f"  test: {s(d['build']['test'])}   # 테스트 명령 (work finish · scan --tests)")
    for role in principles.COMMAND_ROLES:
        if d["build"].get(role):
            where = "고친 뒤 돌린다" if role == "format" else "lantern lint · /l-build · CI"
            lines.append(f"  {role}: {s(d['build'][role])}   # {principles.role_label(role)} 명령 ({where})")
    lines += [
        "check:",
        f"  max_lines: {s(d['check']['max_lines'])}            # 이보다 길면 나누자고 경고 (막지는 않음)",
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
        raise ValueError("lantern.yaml 값이 올바르지 않습니다:\n- " + "\n- ".join(problems))
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


DATA_VARIANT = {"none": "기기 안 저장소", "external": "외부 DB", "custom": "서버 DB"}
CLIENT_LABEL = {"web": "웹", "desktop": "데스크톱", "mobile": "모바일"}


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
        DocSpec("moc", n.file("moc"), n.doc("moc"), "항상"),
        folder("templates", "항상"),
        folder("ideas", "항상"),
        folder("works", "항상"),
        folder("archive", "항상"),
        doc("project-definition", "current", "project_definition", "항상"),
        doc("features", "current", "features", "항상"),
        doc("architecture", "current", "architecture", "항상"),
        DocSpec(
            "data",
            f"{data_dir}/{n.file('data')}",
            n.doc("data"),
            f"항상 ({DATA_VARIANT.get(server, server)})",
            variant=DATA_VARIANT.get(server),
        ),
        DocSpec("schema", f"{data_dir}/schema.dbml", None, "데이터 원본 (DBML)"),
        folder("rules", "항상"),
        doc("unit-log", "rules", "unit_log", "항상"),
        folder("reports", "항상", "past_reports"),
    ]
    if clients:
        labels = ", ".join(CLIENT_LABEL[c] for c in clients if c in CLIENT_LABEL)
        out += [
            DocSpec("screens", f"{f('current')}/{f('screens')}/{n.file('screens')}", n.doc("screens"), f"화면 유형: {labels}"),
            doc("platform", "current", "platform", f"화면 유형: {labels}", sections=list(clients)),
            doc("deploy", "current", "deploy", f"화면 유형: {labels}", sections=list(clients)),
        ]
    if server == "custom" or (server == "external" and "api" in extra):
        out.append(doc("api", "current", "api", "서버 직접 구축" if server == "custom" else "외부 서비스 + API 켬"))
    if server == "custom":
        out.append(doc("server-ops", "current", "server_ops", "서버 직접 구축"))
    if profile.team:
        out += [doc("collab", "rules", "collab", "2인 이상"), folder("meetings", "2인 이상")]
    if profile.knowledge:
        out += [
            folder("debt-cards", "지식 저장소 있음 (배우는 선로)", "debt_cards"),
            DocSpec("debt-status", f"{f('debt')}/{n.file('debt_status')}", None, "지식 저장소 있음 (자동 생성)"),
            doc("known-tech", "debt", "known_tech", "지식 저장소 있음"),
        ]
    if profile.get("project.kind"):
        out.append(DocSpec("principles", f"{f('rules')}/{n.file('principles')}", None, "프로젝트 종류를 정함 (자동 생성)"))
    if profile.brownfield:
        out += [folder("legacy", "브라운필드"), doc("legacy-map", "legacy", "legacy_map", "브라운필드")]
    return out


# Doc keys that may become "사용 안 함" (inactive) when answers change. Folders are never removed.
OPTIONAL_DOC_KEYS = {"screens", "platform", "deploy", "api", "server-ops", "collab", "known-tech", "legacy-map"}

# Which /l-init follow-up questions a newly enabled doc needs.
FOLLOW_UP_QUESTIONS = {
    "deploy": "배포 방식 (호스팅 · 스토어 · 서명 등)",
    "platform": "플랫폼 연동 (푸시 · 딥링크 · URL 스킴 등)",
    "api": "API 형태 (REST · GraphQL 등)와 인증 방식",
    "server-ops": "서버 배포 위치와 운영 방법",
    "collab": "팀원 이름 (project.members)과 리뷰 · 브랜치 규칙",
    "known-tech": "이미 잘 아는 기술 (부채 후보에서 뺄 것)",
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
