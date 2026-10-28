"""Translate what the program says: messages, generated document text, help and file comments.

The code writes every message in English; `resources/messages.yaml` maps each English message to
its translations (`ko: …`). The language is the project's (lantern.yaml project.language), set when
a project is loaded, so callers just write `msg("Document not found: {target}", target=...)`.

Responsibilities:
    - keep the current message language
    - look up and fill a message in that language

Not here:
    - names the program reads and writes (folders · sections · markers) → core/names.py
"""

from __future__ import annotations

from functools import cache
from typing import Any

import yaml

from .. import resources

_current = {"locale": "ko"}


def use(locale: str) -> None:
    """Switch the language messages are given in.

    Args:
        locale: Language code, e.g. "en" (lantern.yaml project.language).

    Example:
        >>> use("en"); msg("Document not found: {target}", target="Plan.md")
        'Document not found: Plan.md'
        >>> use("ko")
    """
    _current["locale"] = locale


def locale() -> str:
    """Return the current message language.

    Returns:
        The language code.

    Example:
        >>> locale()
        'ko'
    """
    return _current["locale"]


@cache
def catalog() -> dict[str, dict[str, str]]:
    """Read messages.yaml once: English message → {language: translation}.

    Returns:
        The catalog.

    Example:
        >>> catalog()["Document not found: {target}"]["ko"]
        '문서를 찾지 못했습니다: {target}'
    """
    return yaml.safe_load(resources.read_text("messages.yaml")) or {}


def msg(message: str, /, **values: Any) -> str:
    """Give a message in the current language, with its `{name}` slots filled.

    Args:
        message: The message in English, exactly as listed in messages.yaml (`{{` · `}}` for literal braces).
        **values: Values for the slots.

    Returns:
        The translated message; the English one when the language has no translation.

    Example:
        >>> msg("Document not found: {target}", target="기획.md")
        '문서를 찾지 못했습니다: 기획.md'
    """
    text = message if locale() == "en" else (catalog().get(message) or {}).get(locale(), message)
    return text.format(**values)
