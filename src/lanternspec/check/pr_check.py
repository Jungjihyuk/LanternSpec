"""`lantern check-pr` — check a pull request's title and commits for work IDs (for CI).

Responsibilities:
    - a PR title needs a work ID, so the work stays findable after a squash merge
    - commits follow the same message rules as the commit-msg hook

Not here:
    - the message rules themselves → check/githooks.py (message_problems)
    - the workflow that runs this → tools/install.py (CI_CHECKS)
"""

from __future__ import annotations

from ..core.messages import msg
from ..core.project import Project
from .githooks import ID_RE, SKIP_MSG, message_problems


def title_problems(title: str) -> list[str]:
    """Check a PR title.

    Args:
        title: The PR title.

    Returns:
        What is wrong; empty when the title has a work ID or is a revert.

    Example:
        >>> title_problems("[FEAT] 로그인 [W-012]")
        []
        >>> len(title_problems("로그인"))
        1
    """
    if SKIP_MSG.search(title) or ID_RE.search(title):
        return []
    return [msg("PR title: no work ID — add one at the end, like [W-012]")]


def pr_problems(project: Project, title: str, rev: str) -> list[str]:
    """Check a PR's title and each of its commits, leaving out merges.

    Args:
        project: The project.
        title: The PR title.
        rev: The PR's commits, e.g. "abc123..def456".

    Returns:
        What is wrong, one line per problem.

    Example:
        >>> pr_problems(project, "로그인 [W-012]", "main..HEAD")  # doctest: +SKIP
        []
    """
    from ..report.scan import commits, is_doc_path

    out = title_problems(title)
    for c in commits(project, rev):
        message = f"{c.subject}\n{c.body}".strip()
        if SKIP_MSG.search(message):
            continue
        has_code = any(not is_doc_path(project, f) for f in c.files)
        out += [f"{c.short} {c.subject}: {p}" for p in message_problems(message, has_code)]
    return out
