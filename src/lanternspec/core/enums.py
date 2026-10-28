"""Read enums.yaml and provide the choice lists such as statuses and kinds.

Responsibilities:
    - read enums.yaml (the project's, else the default bundled with the package)
    - find names and icons by role — code never spells a name such as "해결" itself
    - build the values for skills and templates (`<<debt_status.resolved>>` · `${work_status.plan}`)
    - check that required roles are present
    - rename a value in the text of enums.yaml

Not here:
    - changing values written in documents → core/meta.py (rename_enum_value)
    - actually filling skills and templates → tools/skills.py · work/scaffold.py
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .. import resources
from .messages import msg

# Roles the code relies on. A project's enums.yaml must give each of them to some value of its list.
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
    """One list of enums.yaml (e.g. debt_status).

    Attributes:
        name: List name, e.g. "debt_status".
        label: Human-readable description of the list, e.g. "부채 상태".
        values: Name → icon, in the order written in enums.yaml.
        applies: Document type → the frontmatter field that uses this list, e.g. {"debt": "status"}.
        roles: Role → name. The key code uses to find a value.

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
        """Return the icon of a value.

        Args:
            value: Value name, e.g. "해결".

        Returns:
            The icon; an empty string if the name is not in the list.

        Example:
            >>> load()["debt_status"].icon("해결")
            '✅'
        """
        return self.values.get(value, "")

    def labelled(self, value: str) -> str:
        """Join icon and name into the text shown on screen.

        Args:
            value: Value name.

        Returns:
            "icon name"; just the name when there is no icon.

        Example:
            >>> load()["debt_status"].labelled("되물음")
            '🤔 되물음'
        """
        icon = self.icon(value)
        return f"{icon} {value}".strip()

    def value(self, role: str) -> str:
        """Return the name of the value that carries a role.

        Args:
            role: Role, e.g. "resolved".

        Returns:
            The name of the value with that role.

        Raises:
            LookupError: No value in this list carries that role.

        Example:
            >>> load()["debt_status"].value("asked_again")
            '되물음'
        """
        if role not in self.roles:
            raise LookupError(msg("enums.yaml {name} has no value with role '{role}'", name=self.name, role=role))
        return self.roles[role]

    def role_of(self, value: str) -> str:
        """Return the role of a value (the reverse of value).

        Args:
            value: Value name.

        Returns:
            The role; an empty string for a value without one.

        Example:
            >>> load()["debt_kind"].role_of("역량")
            'competency'
        """
        return next((r for r, v in self.roles.items() if v == value), "")


class Enums:
    """All of enums.yaml — find an Enum by list name and a value by role.

    Usually obtained through load() or project.enums rather than built directly.

    Attributes:
        version: The version value of enums.yaml.
        enums: List name → Enum.

    Example:
        >>> enums = load()
        >>> enums.value("work_status", "build")
        '구현'
    """

    def __init__(self, data: dict, fallback: Enums | None = None) -> None:
        """Build the lists from loaded YAML.

        Args:
            data: enums.yaml as read by yaml.safe_load.
            fallback: Default lists to borrow roles from for an old enums.yaml without roles.
                A value whose name matches the default gets the default role.

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
        """Find an Enum by list name.

        Args:
            name: List name, e.g. "debt_status".

        Returns:
            That list.

        Raises:
            KeyError: There is no such list.

        Example:
            >>> load()["debt_status"].label
            '부채 상태'
        """
        return self.enums[name]

    def get(self, name: str) -> Enum | None:
        """Find an Enum by list name, or None if there is none.

        Args:
            name: List name.

        Returns:
            That list, or None.

        Example:
            >>> load().get("없는 목록") is None
            True
        """
        return self.enums.get(name)

    def values(self, name: str) -> list[str]:
        """Return a list's value names in the order written in enums.yaml.

        Args:
            name: List name.

        Returns:
            Value names; an empty list if there is no such list.

        Example:
            >>> load().values("debt_status")
            ['처음', '되물음', '연습 중', '해결']
        """
        e = self.enums.get(name)
        return list(e.values) if e else []

    def value(self, name: str, role: str) -> str:
        """Return the name of the value in a list that carries a role.

        Args:
            name: List name, e.g. "debt_status".
            role: Role, e.g. "resolved".

        Returns:
            The value name.

        Raises:
            KeyError: There is no such list.
            LookupError: No value carries that role.

        Example:
            >>> load().value("debt_status", "resolved")
            '해결'
        """
        return self[name].value(role)

    def label(self, name: str, role: str) -> str:
        """Return the value carrying a role as "icon name".

        Args:
            name: List name.
            role: Role.

        Returns:
            "icon name".

        Raises:
            KeyError: There is no such list.
            LookupError: No value carries that role.

        Example:
            >>> load().label("debt_status", "resolved")
            '✅ 해결'
        """
        e = self[name]
        return e.labelled(e.value(role))

    def icon(self, name: str, role: str) -> str:
        """Return only the icon of the value carrying a role.

        Args:
            name: List name.
            role: Role.

        Returns:
            The icon.

        Raises:
            KeyError: There is no such list.
            LookupError: No value carries that role.

        Example:
            >>> load().icon("debt_status", "practicing")
            '✍️'
        """
        e = self[name]
        return e.icon(e.value(role))

    def rules_for(self, doc_type: str) -> dict[str, Enum]:
        """Return which field of a document type must use which list (for lantern check).

        Args:
            doc_type: The document's type value, e.g. "debt".

        Returns:
            Frontmatter field name → the list that field must follow.

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
        """Build the values that fill placeholders in skills and templates.

        Three keys per role: `list.role` (name) · `list.role.label` (icon name) ·
        `list.role.icon` (icon). Skills write `<<key>>`, templates `${key}`.

        Returns:
            Key → text to fill in.

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
        """Find problems that would stop code from finding values (for lantern doctor · lantern enums list).

        Returns:
            Problem descriptions; an empty list when there are none. Reports
            lists or roles of REQUIRED_ROLES that are missing, and one role on two values.

        Example:
            >>> load().problems()
            []
        """
        out = [msg("enums.yaml: role '{d}' is on two values", d=d) for d in self._duplicate_roles]
        for name, roles in REQUIRED_ROLES.items():
            e = self.enums.get(name)
            if e is None:
                out.append(msg("enums.yaml: '{name}' is missing", name=name))
                continue
            out += [
                msg("enums.yaml {name}: no value with role '{r}' (the code can't find this value)", name=name, r=r)
                for r in roles
                if r not in e.roles
            ]
        return out


def _base(language: str = "ko") -> Enums:
    """Read the default enums.yaml of a language bundled with the package."""
    return Enums(yaml.safe_load(resources.read_text(f"locales/{language}/templates/_meta/enums.yaml")) or {})


def load(enums_file: Path | None = None, language: str = "ko") -> Enums:
    """Read enums.yaml.

    Uses the project's file when it exists, else the default bundled with the package.
    Project code usually uses project.enums instead (read only once).

    Args:
        enums_file: Path of the project's enums.yaml (`docs/0. 템플릿/_meta/enums.yaml`).
            When None or missing, the default is read.
        language: Language of the default (lantern.yaml project.language).

    Returns:
        All lists that were read.

    Example:
        >>> load().label("idea_status", "dropped")
        '❌ 버림'
    """
    if enums_file is not None and enums_file.exists():
        return Enums(yaml.safe_load(enums_file.read_text(encoding="utf-8")) or {}, fallback=_base(language))
    return _base(language)


def rename_in_text(text: str, enum: str, old: str, new: str) -> str:
    r"""Rename one value in the text of enums.yaml.

    Only the value line inside that list's block changes; comments, order, icons and roles stay.

    Args:
        text: The whole text of enums.yaml.
        enum: List name.
        old: Current name.
        new: New name.

    Returns:
        The enums.yaml text with the value renamed.

    Raises:
        LookupError: The list or the value does not exist.

    Example:
        >>> text = "debt_status:\n  values:\n    되물음: {icon: 🤔, role: asked_again}\n"
        >>> print(rename_in_text(text, "debt_status", "되물음", "다시 물음"), end="")
        debt_status:
          values:
            다시 물음: {icon: 🤔, role: asked_again}
    """
    block = re.search(r"^" + re.escape(enum) + r":[ \t]*$(.*?)(?=^\S|\Z)", text, re.M | re.S)
    if block is None:
        raise LookupError(msg("enums.yaml has no '{enum}'", enum=enum))
    body = block.group(1)
    pat = re.compile(rf"^(\s+)(['\"]?){re.escape(old)}\2:", re.M)
    if not pat.search(body):
        raise LookupError(msg("{enum} has no value '{old}'", enum=enum, old=old))
    body = pat.sub(lambda m: f"{m.group(1)}{_yaml_key(new)}:", body, count=1)
    return text[: block.start(1)] + body + text[block.end(1) :]


def _yaml_key(s: str) -> str:
    """Quote a name that cannot be a bare YAML key."""
    return s if re.fullmatch(r"[^\s:#'\"{}\[\],&*!|>%@`-][^:#{}\[\],]*", s) and s == s.strip() else '"' + s.replace('"', '\\"') + '"'


def doc_value_updates(enums: Enums, enum: str, meta: dict[str, Any], old: str, new: str) -> dict[str, str]:
    """Find the frontmatter fields of one document to update when a value is renamed.

    The document's type decides which fields use that list (applies); only fields holding the old name are picked.

    Args:
        enums: All current lists.
        enum: The list whose value was renamed.
        meta: The document's frontmatter.
        old: Old name.
        new: New name.

    Returns:
        Field name → new name; an empty dict when nothing needs changing.

    Example:
        >>> doc_value_updates(load(), "debt_status", {"type": "debt", "status": "되물음"}, "되물음", "다시 물음")
        {'status': '다시 물음'}
    """
    e = enums[enum]
    doc_type = str(meta.get("type") or "")
    fields = [f for t, f in e.applies.items() if t in ("*", doc_type)]
    return {f: new for f in fields if str(meta.get(f, "")) == old}
