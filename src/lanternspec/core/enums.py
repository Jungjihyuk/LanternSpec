"""enums.yaml을 읽어 상태 · 종류 같은 선택지 목록을 제공한다.

책임:
    - enums.yaml 읽기 (프로젝트 것, 없으면 패키지에 든 기본값)
    - 역할(role)로 이름 · 아이콘 찾기 — 코드는 "해결" 같은 이름을 직접 쓰지 않는다
    - 스킬 · 템플릿에 넣을 값 묶음 만들기 (`<<debt_status.resolved>>` · `${work_status.plan}`)
    - 필요한 역할이 빠졌는지 검사하기
    - enums.yaml 글에서 값 이름 바꾸기

하지 않는 일:
    - 문서에 적힌 값 바꾸기 → core/meta.py (rename_enum_value)
    - 스킬 · 템플릿에 실제로 값 채우기 → tools/skills.py · work/scaffold.py
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .. import resources

# 코드가 기대는 역할들. 프로젝트의 enums.yaml도 목록마다 이 역할을 어느 값엔가 붙여 두어야 한다.
REQUIRED_ROLES: dict[str, list[str]] = {
    "idea_status": ["new", "reviewing", "worked", "on_hold", "dropped"],
    "work_status": ["plan", "design", "tasks", "build", "done", "on_hold"],
    "adr_status": ["proposed", "accepted", "superseded"],
    "debt_kind": ["understanding", "competency", "tech"],
    "debt_status": ["new", "asked_again", "practicing", "resolved"],
    "current_status": ["active", "inactive"],
    "note_draft_status": ["pending", "applied"],
    "meeting_status": ["draft", "final"],
}


@dataclass
class Enum:
    """enums.yaml의 목록 하나 (예: debt_status).

    Attributes:
        name: 목록 이름. 예: "debt_status".
        label: 사람이 읽는 목록 설명. 예: "부채 상태".
        values: 이름 → 아이콘. 순서는 enums.yaml에 적힌 순서.
        applies: 문서 type → 이 목록을 쓰는 frontmatter 칸. 예: {"debt": "status"}.
        roles: 역할 → 이름. 코드가 값을 찾는 열쇠.

    Example:
        >>> e = load()["debt_status"]
        >>> e.roles["resolved"], e.values["해결"]
        ('해결', '✅')
    """

    name: str
    label: str
    values: dict[str, str]
    applies: dict[str, str]
    roles: dict[str, str] = field(default_factory=dict)

    def icon(self, value: str) -> str:
        """이름에 붙은 아이콘을 돌려준다.

        Args:
            value: 값 이름. 예: "해결".

        Returns:
            아이콘. 목록에 없는 이름이면 빈 문자열.

        Example:
            >>> load()["debt_status"].icon("해결")
            '✅'
        """
        return self.values.get(value, "")

    def labelled(self, value: str) -> str:
        """아이콘과 이름을 붙여 화면에 보일 글로 만든다.

        Args:
            value: 값 이름.

        Returns:
            "아이콘 이름". 아이콘이 없으면 이름만.

        Example:
            >>> load()["debt_status"].labelled("되물음")
            '🤔 되물음'
        """
        icon = self.icon(value)
        return f"{icon} {value}".strip()

    def value(self, role: str) -> str:
        """역할이 붙은 값의 이름을 돌려준다.

        Args:
            role: 역할. 예: "resolved".

        Returns:
            그 역할이 붙은 값의 이름.

        Raises:
            LookupError: 이 목록에 그 역할이 붙은 값이 없을 때.

        Example:
            >>> load()["debt_status"].value("asked_again")
            '되물음'
        """
        if role not in self.roles:
            raise LookupError(f"enums.yaml {self.name}에 role '{role}'인 값이 없습니다")
        return self.roles[role]

    def role_of(self, value: str) -> str:
        """이름에 붙은 역할을 돌려준다 (value의 반대 방향).

        Args:
            value: 값 이름.

        Returns:
            역할. 역할이 없는 값이면 빈 문자열.

        Example:
            >>> load()["debt_kind"].role_of("역량")
            'competency'
        """
        return next((r for r, v in self.roles.items() if v == value), "")


class Enums:
    """enums.yaml 전체 — 목록 이름으로 Enum을 찾고, 역할로 값을 찾는다.

    보통 직접 만들지 않고 load() 또는 project.enums로 얻는다.

    Attributes:
        version: enums.yaml의 version 값.
        enums: 목록 이름 → Enum.

    Example:
        >>> enums = load()
        >>> enums.value("work_status", "build")
        '구현'
    """

    def __init__(self, data: dict, fallback: Enums | None = None) -> None:
        """읽어 온 YAML 내용으로 목록들을 만든다.

        Args:
            data: yaml.safe_load로 읽은 enums.yaml 내용.
            fallback: 역할이 없는 옛 enums.yaml을 위해 역할을 빌려 올 기본 목록.
                옛 파일의 이름이 기본값과 같으면 그 값에 기본 역할을 붙인다.

        Example:
            >>> e = Enums({"debt_status": {"values": {"해결": {"icon": "✅", "role": "resolved"}}}})
            >>> e.value("debt_status", "resolved")
            '해결'
        """
        self.version = data.get("version", 1)
        self.enums: dict[str, Enum] = {}
        self._duplicate_roles: list[str] = []
        for name, spec in data.items():
            if not isinstance(spec, dict) or "values" not in spec:
                continue
            values = spec.get("values") or {}
            if isinstance(values, list):
                values = {str(v): "" for v in values}
            icons: dict[str, str] = {}
            roles: dict[str, str] = {}
            for k, v in values.items():
                if isinstance(v, dict):
                    icons[str(k)] = str(v.get("icon") or "")
                    if v.get("role"):
                        role = str(v["role"])
                        if role in roles:
                            self._duplicate_roles.append(f"{name}.{role}")
                        roles[role] = str(k)
                else:
                    icons[str(k)] = str(v or "")
            self.enums[name] = Enum(
                name=name,
                label=spec.get("label", name),
                values=icons,
                applies={str(k): str(v) for k, v in (spec.get("applies") or {}).items()},
                roles=roles,
            )
        if fallback is not None:
            for name, base in fallback.enums.items():
                mine = self.enums.get(name)
                if mine is None:
                    continue
                for role, value in base.roles.items():
                    if role not in mine.roles and value in mine.values:
                        mine.roles[role] = value

    def __getitem__(self, name: str) -> Enum:
        """목록 이름으로 Enum을 찾는다.

        Args:
            name: 목록 이름. 예: "debt_status".

        Returns:
            그 목록.

        Raises:
            KeyError: 그런 목록이 없을 때.

        Example:
            >>> load()["debt_status"].label
            '부채 상태'
        """
        return self.enums[name]

    def get(self, name: str) -> Enum | None:
        """목록 이름으로 Enum을 찾되, 없으면 None을 돌려준다.

        Args:
            name: 목록 이름.

        Returns:
            그 목록, 없으면 None.

        Example:
            >>> load().get("없는 목록") is None
            True
        """
        return self.enums.get(name)

    def values(self, name: str) -> list[str]:
        """목록의 값 이름들을 enums.yaml에 적힌 순서대로 돌려준다.

        Args:
            name: 목록 이름.

        Returns:
            값 이름 목록. 그런 목록이 없으면 빈 목록.

        Example:
            >>> load().values("debt_status")
            ['처음', '되물음', '연습 중', '해결']
        """
        e = self.enums.get(name)
        return list(e.values) if e else []

    def value(self, name: str, role: str) -> str:
        """목록에서 역할이 붙은 값의 이름을 돌려준다.

        Args:
            name: 목록 이름. 예: "debt_status".
            role: 역할. 예: "resolved".

        Returns:
            값 이름.

        Raises:
            KeyError: 그런 목록이 없을 때.
            LookupError: 그 역할이 붙은 값이 없을 때.

        Example:
            >>> load().value("debt_status", "resolved")
            '해결'
        """
        return self[name].value(role)

    def label(self, name: str, role: str) -> str:
        """역할이 붙은 값을 "아이콘 이름"으로 돌려준다.

        Args:
            name: 목록 이름.
            role: 역할.

        Returns:
            "아이콘 이름".

        Raises:
            KeyError: 그런 목록이 없을 때.
            LookupError: 그 역할이 붙은 값이 없을 때.

        Example:
            >>> load().label("debt_status", "resolved")
            '✅ 해결'
        """
        e = self[name]
        return e.labelled(e.value(role))

    def icon(self, name: str, role: str) -> str:
        """역할이 붙은 값의 아이콘만 돌려준다.

        Args:
            name: 목록 이름.
            role: 역할.

        Returns:
            아이콘.

        Raises:
            KeyError: 그런 목록이 없을 때.
            LookupError: 그 역할이 붙은 값이 없을 때.

        Example:
            >>> load().icon("debt_status", "practicing")
            '✍️'
        """
        e = self[name]
        return e.icon(e.value(role))

    def rules_for(self, doc_type: str) -> dict[str, Enum]:
        """문서 종류 하나에서 어느 칸이 어느 목록의 값을 써야 하는지 돌려준다 (lantern check용).

        Args:
            doc_type: 문서의 type 값. 예: "debt".

        Returns:
            frontmatter 칸 이름 → 그 칸이 따라야 할 목록.

        Example:
            >>> sorted(load().rules_for("debt"))
            ['area', 'kind', 'status', 'type']
        """
        out: dict[str, Enum] = {}
        for e in self.enums.values():
            for t, fieldname in e.applies.items():
                if t == "*" or t == doc_type:
                    out[fieldname] = e
        return out

    def context(self) -> dict[str, str]:
        """스킬 · 템플릿의 자리 표시를 채울 값 묶음을 만든다.

        역할마다 세 가지 열쇠를 만든다: `목록.역할`(이름) · `목록.역할.label`(아이콘 이름) ·
        `목록.역할.icon`(아이콘). 스킬은 `<<열쇠>>`, 템플릿은 `${열쇠}`로 쓴다.

        Returns:
            열쇠 → 채울 글.

        Example:
            >>> ctx = load().context()
            >>> ctx["debt_status.asked_again"], ctx["debt_status.asked_again.label"]
            ('되물음', '🤔 되물음')
        """
        out: dict[str, str] = {}
        for e in self.enums.values():
            for role, value in e.roles.items():
                out[f"{e.name}.{role}"] = value
                out[f"{e.name}.{role}.label"] = e.labelled(value)
                out[f"{e.name}.{role}.icon"] = e.icon(value)
        return out

    def problems(self) -> list[str]:
        """코드가 값을 찾지 못하게 되는 문제를 찾는다 (lantern doctor · lantern enums list용).

        Returns:
            문제 설명 목록. 문제가 없으면 빈 목록. 다음을 알린다:
            REQUIRED_ROLES의 목록이나 역할이 빠진 것, 한 역할이 두 값에 붙은 것.

        Example:
            >>> load().problems()
            []
        """
        out = [f"enums.yaml: role '{d}'가 두 값에 붙어 있습니다" for d in self._duplicate_roles]
        for name, roles in REQUIRED_ROLES.items():
            e = self.enums.get(name)
            if e is None:
                out.append(f"enums.yaml: '{name}'이 없습니다")
                continue
            out += [f"enums.yaml {name}: role '{r}'인 값이 없습니다 (코드가 이 값을 찾지 못함)" for r in roles if r not in e.roles]
        return out


def _base() -> Enums:
    """패키지에 든 기본 enums.yaml을 읽는다."""
    return Enums(yaml.safe_load(resources.read_text("templates/_meta/enums.yaml")) or {})


def load(enums_file: Path | None = None) -> Enums:
    """enums.yaml을 읽는다.

    프로젝트 파일이 있으면 그것을, 없으면 패키지에 든 기본값을 쓴다.
    프로젝트 코드에서는 보통 이 함수 대신 project.enums를 쓴다 (한 번만 읽는다).

    Args:
        enums_file: 프로젝트의 enums.yaml 경로 (docs/0. 템플릿/_meta/enums.yaml).
            None이거나 파일이 없으면 기본값을 읽는다.

    Returns:
        읽어 온 목록 전체.

    Example:
        >>> load().label("idea_status", "dropped")
        '❌ 버림'
    """
    if enums_file is not None and enums_file.exists():
        return Enums(yaml.safe_load(enums_file.read_text(encoding="utf-8")) or {}, fallback=_base())
    return _base()


def rename_in_text(text: str, enum: str, old: str, new: str) -> str:
    r"""enums.yaml 글에서 값 하나의 이름을 바꾼다.

    그 목록 블록 안의 값 줄만 고치고 주석 · 순서 · 아이콘 · 역할은 그대로 둔다.

    Args:
        text: enums.yaml 전체 글.
        enum: 목록 이름.
        old: 지금 이름.
        new: 새 이름.

    Returns:
        이름을 바꾼 enums.yaml 글.

    Raises:
        LookupError: 목록이나 값이 없을 때.

    Example:
        >>> text = "debt_status:\n  values:\n    되물음: {icon: 🤔, role: asked_again}\n"
        >>> print(rename_in_text(text, "debt_status", "되물음", "다시 물음"), end="")
        debt_status:
          values:
            다시 물음: {icon: 🤔, role: asked_again}
    """
    block = re.search(r"^" + re.escape(enum) + r":[ \t]*$(.*?)(?=^\S|\Z)", text, re.M | re.S)
    if block is None:
        raise LookupError(f"enums.yaml에 '{enum}'이 없습니다")
    body = block.group(1)
    pat = re.compile(rf"^(\s+)(['\"]?){re.escape(old)}\2:", re.M)
    if not pat.search(body):
        raise LookupError(f"{enum}에 '{old}' 값이 없습니다")
    body = pat.sub(lambda m: f"{m.group(1)}{_yaml_key(new)}:", body, count=1)
    return text[: block.start(1)] + body + text[block.end(1) :]


def _yaml_key(s: str) -> str:
    """YAML 키로 그대로 쓸 수 없는 이름이면 따옴표로 감싼다."""
    return s if re.fullmatch(r"[^\s:#'\"{}\[\],&*!|>%@`-][^:#{}\[\],]*", s) and s == s.strip() else '"' + s.replace('"', '\\"') + '"'


def doc_value_updates(enums: Enums, enum: str, meta: dict[str, Any], old: str, new: str) -> dict[str, str]:
    """값 이름이 바뀔 때 문서 하나에서 고쳐야 할 frontmatter 칸을 찾는다.

    문서의 type으로 그 목록을 쓰는 칸(applies)을 정하고, 그 칸의 값이 옛 이름인 것만 고른다.

    Args:
        enums: 지금 목록 전체.
        enum: 이름이 바뀐 목록.
        meta: 문서의 frontmatter.
        old: 옛 이름.
        new: 새 이름.

    Returns:
        칸 이름 → 새 이름. 고칠 칸이 없으면 빈 dict.

    Example:
        >>> doc_value_updates(load(), "debt_status", {"type": "debt", "status": "되물음"}, "되물음", "다시 물음")
        {'status': '다시 물음'}
    """
    e = enums[enum]
    doc_type = str(meta.get("type") or "")
    fields = [f for t, f in e.applies.items() if t in ("*", doc_type)]
    return {f: new for f in fields if str(meta.get(f, "")) == old}
