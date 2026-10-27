"""설계 원칙 기준표와 언어별 컨벤션에서 이 프로젝트에 맞는 것을 고른다.

책임:
    - principles.yaml · conventions/<언어>.yaml 읽기 (패키지에 든 기준표)
    - 종류 · 바깥 연결 · 규모로 원칙마다 단계(must · should · skip) 정하기
    - 언어 · 규모로 코드 컨벤션 고르기
    - 줄 수 · 사람 수를 규모(small · medium · large)로 바꾸기
    - 프로젝트 맨 위 폴더의 파일로 언어 · 실행기 · 이미 쓰는 도구 알아보기

하지 않는 일:
    - 코드 줄 수 세기 → report/harness.py (code_lines)
    - AGENTS.md에 넣을 글 만들기 → tools/rules.py (principles_section)
    - 개발 원칙 문서 쓰기 → report/principles_doc.py
    - 규모 경계를 넘었는지 알리기 → check/doctor.py
"""

from __future__ import annotations

import functools
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from .. import resources

if TYPE_CHECKING:
    from .profile import Profile

SIZES = ("small", "medium", "large")
COMMAND_ROLES = ("format", "lint", "typecheck")  # lantern.yaml build.<역할>에 기록하는 명령
ROLE_LABEL = {"format": "포맷", "lint": "린트", "typecheck": "타입 검사", "test": "테스트"}
DOC_LANGUAGE = {"ko": "한국어", "en": "영어"}  # lantern.yaml project.language → 문서 주석에 쓸 말
RULE_LABEL = {"lint": "린트", "typecheck": "타입 검사", "type_hints": "타입 힌트", "docs": "문서 주석", "tests": "테스트"}


@functools.cache
def table() -> dict[str, Any]:
    """설계 원칙 기준표(principles.yaml)를 읽는다.

    Returns:
        principles.yaml 전체 (levels · kinds · external · sizes · principles · always).

    Example:
        >>> table()["levels"]["must"]
        '지킴'
    """
    return yaml.safe_load(resources.read_text("principles/principles.yaml"))


@functools.cache
def conventions(language: str) -> dict[str, Any]:
    """언어 하나의 코드 컨벤션(conventions/<언어>.yaml)을 읽는다.

    Args:
        language: 언어 이름. 예: "python".

    Returns:
        그 언어의 컨벤션 (tools · runners · existing · docs · levels).

    Raises:
        LookupError: 그 언어의 컨벤션 파일이 없을 때.

    Example:
        >>> conventions("python")["tools"]["lint"]["name"]
        'ruff'
    """
    if language not in language_names():
        raise LookupError(f"'{language}' 컨벤션이 없습니다 (가능: {', '.join(language_names())})")
    return yaml.safe_load(resources.read_text(f"principles/conventions/{language}.yaml"))


def kind_names() -> tuple[str, ...]:
    """프로젝트 종류 이름들을 기준표 순서대로 돌려준다.

    Returns:
        종류 이름 튜플.

    Example:
        >>> kind_names()
        ('script', 'cli', 'library', 'service', 'data')
    """
    return tuple(table()["kinds"])


def language_names() -> tuple[str, ...]:
    """컨벤션이 있는 언어 이름들을 돌려준다.

    Returns:
        언어 이름 튜플 (이름 순).

    Example:
        >>> language_names()
        ('go', 'python', 'rust', 'swift', 'typescript')
    """
    return tuple(sorted(Path(rel).stem for rel, _ in resources.iter_files("principles/conventions")))


def code_size(lines: int) -> str:
    """코드 줄 수를 규모로 바꾼다 (경계는 기준표의 sizes.code).

    Args:
        lines: 테스트 · 문서를 뺀 코드 줄 수.

    Returns:
        "small" · "medium" · "large" 중 하나.

    Example:
        >>> code_size(9_999), code_size(10_000), code_size(50_000)
        ('small', 'medium', 'large')
    """
    for size, spec in table()["sizes"]["code"].items():
        if "below" not in spec or lines < spec["below"]:
            return size
    return SIZES[-1]


def people_size(team: bool, members: int) -> str:
    """사람 수를 규모로 바꾼다 (경계는 기준표의 sizes.people).

    Args:
        team: 2인 이상인가 (lantern.yaml project.team).
        members: 담당자 후보 수 (project.members). team인데 1명 이하로 적혀 있으면 2명으로 본다.

    Returns:
        "small" · "medium" · "large" 중 하나.

    Example:
        >>> people_size(False, 0), people_size(True, 3), people_size(True, 6)
        ('small', 'medium', 'large')
    """
    count = max(members, 2) if team else 1
    for size, spec in table()["sizes"]["people"].items():
        if "max" not in spec or count <= spec["max"]:
            return size
    return SIZES[-1]


def level_for(pid: str, kind: str, external: bool, code: str, people: str) -> tuple[str, str]:
    """원칙 하나의 단계와 그렇게 정한 이유를 기준표로 정한다.

    종류(와 바깥 연결)로 기본 단계를 고른 뒤 규모 보정을 한다:
    grows_with의 신호가 중간 이상이면 should → must, min_when_large가 있으면 코드가 큼일 때 그 단계 이상.

    Args:
        pid: 원칙 이름 (principles의 키). 예: "single_responsibility".
        kind: 프로젝트 종류. 예: "cli".
        external: 바깥 도구 · 서비스에 붙나.
        code: 코드 규모.
        people: 사람 규모.

    Returns:
        (단계, 이유). 단계는 "must" · "should" · "skip".

    Raises:
        KeyError: 원칙이나 종류가 기준표에 없을 때.

    Example:
        >>> level_for("extension_points", "cli", True, "small", "small")
        ('must', 'CLI 도구 · 바깥 연결 → 지킴')
        >>> level_for("dependency_direction", "cli", False, "medium", "small")
        ('must', 'CLI 도구 → 권장, 코드 중간 → 지킴')
    """
    t = table()
    p = t["principles"][pid]
    rule = p["levels"][kind]
    kind_label = t["kinds"][kind]["label"]
    if isinstance(rule, dict):
        level = rule["external" if external else "else"]
        why = f"{kind_label} · {'바깥 연결' if external else '바깥 연결 없음'} → {t['levels'][level]}"
    else:
        level = rule
        why = f"{kind_label} → {t['levels'][level]}"
    signal = {"code": ("코드", code), "people": ("사람", people)}.get(p["grows_with"])
    if level == "should" and signal and signal[1] != SIZES[0]:
        level = "must"
        why += f", {signal[0]} {t['sizes'][p['grows_with']][signal[1]]['label']} → {t['levels'][level]}"
    floor = p.get("min_when_large")
    if floor and code == SIZES[-1] and _rank(level) < _rank(floor):
        level = floor
        why += f", 코드 {t['sizes']['code'][code]['label']} → {t['levels'][level]}"
    return level, why


@dataclass(frozen=True)
class Principle:
    """고른 설계 원칙 하나.

    Attributes:
        id: 원칙 이름 (principles의 키).
        name: 보여 줄 이름. 예: "단일 책임 (SRP)".
        level: "must" · "should" · "skip".
        reason: 이 단계로 정한 이유 한 줄.
        explain: 원칙 설명 한 줄.
        rules: 지키는 법.
        note: 종류에 따른 덧붙임 (데이터 · ML의 data_note). 없으면 빈 문자열.
    """

    id: str
    name: str
    level: str
    reason: str
    explain: str
    rules: tuple[str, ...]
    note: str = ""


@dataclass(frozen=True)
class Convention:
    """고른 언어 하나의 코드 컨벤션.

    Attributes:
        language: 언어 이름. 예: "python".
        label: 보여 줄 이름. 예: "Python".
        size: 규칙의 강도를 고른 규모 (문서 주석은 종류에 따라 더 높을 수 있다).
        tools: 역할(package · format · lint · typecheck · test) → (도구 이름, 기본 명령 또는 안내).
        rules: 항목(lint · typecheck · type_hints · docs · tests) → 규칙 한 줄.
        docs_style: 문서 주석 형식. 예: "Google 스타일 docstring".
        example: 문서 주석 예시 코드.
    """

    language: str
    label: str
    size: str
    tools: dict[str, tuple[str, str]]
    rules: dict[str, str]
    docs_style: str
    example: str


@dataclass(frozen=True)
class Selection:
    """프로젝트 하나에 고른 원칙 · 작업 방식 · 컨벤션 전부.

    Attributes:
        kind: 프로젝트 종류.
        external: 바깥 도구 · 서비스에 붙나.
        code: 코드 규모 (lantern.yaml에 기록한 값).
        people: 사람 규모.
        principles: 기준표 순서대로 모든 원칙 (skip 포함).
        always: 늘 넣는 작업 방식 (이름, 규칙들).
        conventions: 언어마다 하나.
    """

    kind: str
    external: bool
    code: str
    people: str
    principles: tuple[Principle, ...]
    always: tuple[tuple[str, tuple[str, ...]], ...]
    conventions: tuple[Convention, ...] = field(default=())

    def at(self, level: str) -> list[Principle]:
        """한 단계의 원칙들을 기준표 순서대로 돌려준다.

        Args:
            level: "must" · "should" · "skip".

        Returns:
            그 단계의 원칙 목록.

        Example:
            >>> [p.id for p in selection.at("must")]  # doctest: +SKIP
            ['simplicity', 'single_responsibility', 'single_source']
        """
        return [p for p in self.principles if p.level == level]

    def summary(self) -> str:
        """종류 · 바깥 연결 · 규모를 한 줄로 돌려준다.

        Returns:
            예: "CLI 도구 · 바깥 연결 · 코드 작음 · 1인".

        Example:
            >>> selection.summary()  # doctest: +SKIP
            'CLI 도구 · 바깥 연결 · 코드 작음 · 1인'
        """
        t = table()
        parts = [t["kinds"][self.kind]["label"]] + (["바깥 연결"] if self.external else [])
        parts += [f"코드 {t['sizes']['code'][self.code]['label']}", t["sizes"]["people"][self.people]["label"]]
        return " · ".join(parts)


def select(profile: Profile) -> Selection | None:
    """lantern.yaml의 답으로 원칙 · 작업 방식 · 컨벤션을 고른다.

    Args:
        profile: 프로젝트 프로필. project.kind가 있어야 고른다.
            코드 규모는 기록된 project.code_size를 쓰고, 없으면 작음으로 본다.

    Returns:
        고른 결과. project.kind가 없으면 None.

    Example:
        >>> from lanternspec.core.profile import DEFAULTS, Profile
        >>> data = {**DEFAULTS, "project": {**DEFAULTS["project"], "kind": "script", "languages": ["python"]}}
        >>> sel = select(Profile(data))
        >>> [p.id for p in sel.at("must")], sel.conventions[0].rules["typecheck"]
        (['simplicity'], 'pyright basic')
    """
    kind = profile.get("project.kind")
    if not kind:
        return None
    t = table()
    external = bool(profile.get("project.external"))
    code = str(profile.get("project.code_size") or SIZES[0])
    people = people_size(profile.team, len(profile.get("project.members") or []))
    principles = []
    for pid, p in t["principles"].items():
        level, why = level_for(pid, kind, external, code, people)
        note = str(p.get("data_note") or "") if kind == "data" else ""
        principles.append(Principle(pid, p["name"], level, why, p["explain"], tuple(p["rules"]), note))
    always = tuple((a["name"], tuple(a["rules"])) for a in t["always"].values())
    docs_size = t["kinds"][kind].get("docs") or code
    convs = []
    for lang in profile.get("project.languages") or []:
        c = conventions(lang)
        rules = dict(c["levels"][code])
        rules["docs"] = c["levels"][docs_size]["docs"]
        tools = {role: (spec["name"], _default_command(c, role)) for role, spec in c["tools"].items()}
        convs.append(Convention(lang, c["label"], code, tools, rules, c["docs"]["style"], c["docs"]["example"]))
    return Selection(kind, external, code, people, tuple(principles), always, tuple(convs))


@dataclass
class Detected:
    """프로젝트 파일에서 알아본 것.

    Attributes:
        languages: 언어 이름들 (컨벤션 파일의 detect가 맞은 것).
        evidence: 언어 → 알아본 근거 파일.
        runners: 언어 → 실행기가 명령 앞에 붙이는 글 (lock 파일로 알아봄, 없으면 처음 실행기).
        existing: 언어 → 역할 → (도구 이름, 실행기를 붙인 명령, 근거). 이미 설정이 있는 도구만.
    """

    languages: list[str] = field(default_factory=list)
    evidence: dict[str, str] = field(default_factory=dict)
    runners: dict[str, str] = field(default_factory=dict)
    existing: dict[str, dict[str, tuple[str, str, str]]] = field(default_factory=dict)

    def commands(self, fill_defaults: bool) -> dict[str, str]:
        """lantern.yaml build.<역할>에 기록할 명령을 만든다.

        Args:
            fill_defaults: 이미 쓰는 도구가 없는 역할을 컨벤션의 기본 도구로 채울까 (새 프로젝트).
                기존 프로젝트는 False — 이미 있는 설정만 기록하고 새 도구를 들이지 않는다.

        Returns:
            역할(format · lint · typecheck) → 명령. 언어가 여럿이면 " && "로 잇는다.

        Example:
            >>> d = Detected(["python"], runners={"python": "uv run "})
            >>> d.commands(fill_defaults=True)["lint"]
            'uv run ruff check .'
            >>> d.commands(fill_defaults=False)
            {}
        """
        out: dict[str, str] = {}
        for role in COMMAND_ROLES:
            cmds = []
            for lang in self.languages:
                found = self.existing.get(lang, {}).get(role)
                if found:
                    cmds.append(found[1])
                elif fill_defaults:
                    c = conventions(lang)
                    cmds.append(self.runners.get(lang, c["runners"][0]["prefix"]) + c["tools"][role]["command"])
            if cmds:
                out[role] = " && ".join(cmds)
        return out


def detect(root: Path) -> Detected:
    """프로젝트 맨 위 폴더의 파일로 언어 · 실행기 · 이미 쓰는 도구를 알아본다.

    설정 파일은 읽기만 하고 바꾸지 않는다.

    Args:
        root: 프로젝트 루트.

    Returns:
        알아본 것. 아무것도 없으면 빈 Detected (새 프로젝트).

    Example:
        >>> detect(project.root).languages  # doctest: +SKIP
        ['python']
    """
    out = Detected()
    for lang in language_names():
        c = conventions(lang)
        hit = next((e for pat in c["detect"] if (e := _found(root, pat))), None)
        if not hit:
            continue
        out.languages.append(lang)
        out.evidence[lang] = hit
        out.runners[lang] = find_runner(root, lang)["prefix"]
        roles: dict[str, tuple[str, str, str]] = {}
        for role, candidates in (c.get("existing") or {}).items():
            for cand in candidates or []:
                ev = next((e for pat in cand["find"] if (e := _found(root, pat))), None)
                if ev:
                    roles[role] = (cand["name"], out.runners[lang] + cand["command"], ev)
                    break
        out.existing[lang] = roles
    return out


def find_runner(root: Path, language: str) -> dict[str, Any]:
    """그 언어의 실행기를 lock 파일로 알아본다.

    Args:
        root: 프로젝트 루트.
        language: 언어 이름.

    Returns:
        컨벤션의 runners 항목 하나 (name · prefix · ci). lock 파일이 맞는 것이 없으면 처음 것 (새 프로젝트의 기본값).

    Example:
        >>> find_runner(Path("/없는/폴더"), "python")["name"]
        'uv'
    """
    runners = conventions(language)["runners"]
    for r in runners:
        locks = r.get("lock") or []
        if any((root / f).exists() for f in ([locks] if isinstance(locks, str) else locks)):
            return r
    return runners[0]


def _default_command(c: dict[str, Any], role: str) -> str:
    """컨벤션의 기본 명령에 기본 실행기를 붙인다 (명령이 없는 역할은 안내 글)."""
    spec = c["tools"][role]
    if "command" not in spec:
        return str(spec.get("note") or "")
    return c["runners"][0]["prefix"] + spec["command"] + (f" ({spec['note']})" if spec.get("note") else "")


def _found(root: Path, pattern: str) -> str | None:
    """`파일` · `글로브` · `파일:들어 있는 글` 하나가 맞으면 근거 글을, 아니면 None을 돌려준다."""
    name, _, needle = pattern.partition(":")
    paths = sorted(root.glob(name)) if any(ch in name for ch in "*?[") else [root / name]
    for p in paths:
        if not p.exists():
            continue
        if not needle:
            return p.name
        try:
            if needle in p.read_text(encoding="utf-8", errors="ignore"):
                return f"{p.name} {needle}"
        except OSError:
            continue
    return None


def _rank(level: str) -> int:
    return ("skip", "should", "must").index(level)
