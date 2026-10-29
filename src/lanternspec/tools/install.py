"""`lantern install` · `lantern upgrade` — put the skills, rules and agent hooks into each tool's folder.

Like `openspec init/update`: written straight into the project (not a plugin), so `/l-init`
is called without a prefix and the team gets it through git. Upgrades only replace files
the installer wrote and nobody edited since.

Responsibilities:
    - write the skill files and the optional CI workflow, skipping files someone edited
    - merge the AGENTS.md block and each tool's settings; refresh generated documents
    - refresh unedited template copies on upgrade; report drift for doctor

Not here:
    - what the skill files contain → tools/skills.py · each tool's file
"""

from __future__ import annotations

from dataclasses import dataclass, field

import yaml

from .. import __version__
from ..check.check_docs import version_gap
from ..core import messages, principles, state
from ..core.messages import msg
from ..core.project import Project, read, write
from ..report import obsidian, principles_doc, sections_doc
from ..work.scaffold import base_template_names, base_template_text, project_template_path, template_version
from . import resolve as resolve_tools
from . import rules, skills
from .base import Tool

CI_PATH = ".github/workflows/lanternspec.yml"
CI_HEAD = """# {note}
name: lanternspec
on: [push, pull_request]
jobs:
  docs-and-acceptance:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
        with:
          fetch-depth: 0
      - uses: actions/setup-python@v7
        with:
          python-version: "3.12"
      - run: pip install lanternspec
"""
CI_CHECKS = """      - name: {check}
        run: lantern check --quiet
        if: hashFiles('lantern.yaml') != ''
      - name: {lint}
        run: lantern lint
        if: hashFiles('lantern.yaml') != ''
      - name: {scan}
        run: lantern scan --tests
"""


@dataclass
class InstallReport:
    """What an install or upgrade did.

    Attributes:
        written: Files created, updated or removed.
        unchanged: Files already up to date.
        skipped: Files left alone because someone edited them.
        merged: Settings merged into existing files.
        templates: Messages about template copies (upgrade only).
        layout: Messages about moving documents to the current layout (upgrade only).
        stopped: The upgrade only showed the moves and changed nothing (it waits for --apply).

    Example:
        >>> InstallReport(written=["AGENTS.md"]).lines()
        ['✔ 생성 · 갱신 1개', '   AGENTS.md']
    """

    written: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)  # user-modified
    merged: list[str] = field(default_factory=list)
    templates: list[str] = field(default_factory=list)
    layout: list[str] = field(default_factory=list)  # documents moved to the current layout, or waiting for --apply
    stopped: bool = False  # the upgrade waits for --apply and changed nothing

    def lines(self) -> list[str]:
        """Describe the report for the user.

        Returns:
            Lines grouped by what happened (at most 40 written files are listed).

        Example:
            >>> InstallReport(skipped=[".claude/skills/l-build/SKILL.md"]).lines()[0]
            '⚠ 사용자가 고친 파일이라 건드리지 않음 1개 (덮어쓰려면 --force):'
        """
        out = list(self.layout)
        if self.written:
            out.append(msg("✔ Created · updated {count}", count=len(self.written)))
            out += [f"   {p}" for p in self.written[:40]]
            if len(self.written) > 40:
                out.append(msg("   … and {value} more", value=len(self.written) - 40))
        if self.merged:
            out.append(msg("✔ Merged settings: ") + ", ".join(self.merged))
        if self.unchanged:
            out.append(msg("· Unchanged {count}", count=len(self.unchanged)))
        if self.skipped:
            out.append(msg("⚠ Left {count} files alone because the user edited them (to overwrite, --force):", count=len(self.skipped)))
            out += [f"   {p}" for p in self.skipped]
        out += self.templates
        return out


def _write_managed(project: Project, files: dict[str, str], record: dict, report: InstallReport, force: bool) -> None:
    for rel, content in sorted(files.items()):
        path = project.root / rel
        new_hash = state.sha256_text(content)
        if path.exists():
            cur_hash = state.sha256_file(path)
            if cur_hash == new_hash:
                record[rel] = new_hash
                report.unchanged.append(rel)
                continue
            known = record.get(rel)
            if not force and known != cur_hash:
                report.skipped.append(rel)
                continue
        write(path, content)
        record[rel] = new_hash
        report.written.append(rel)


def tools_cover(rel: str, tools: list[Tool]) -> bool:
    """Tell whether a generated file belongs to one of the chosen tools' skill folders.

    Args:
        rel: Path relative to the project root.
        tools: The chosen tools.

    Returns:
        True when one of the tools owns it.

    Example:
        >>> from lanternspec.tools import get
        >>> tools_cover(".agents/skills/l-build/SKILL.md", [get("claude")])
        False
    """
    return any(t.owns_skill_file(rel) for t in tools)


def ci_workflow(project: Project) -> str:
    """Build the GitHub Actions workflow: lanternspec + the project's own tools (each language's runner, found by its lock file).

    Args:
        project: The project.

    Returns:
        The workflow YAML.

    Example:
        >>> ci_workflow(project).splitlines()[1]  # doctest: +SKIP
        'name: lanternspec'
    """
    steps: list[dict] = []
    for lang in project.profile.get("project.languages") or []:
        if lang not in principles.language_names():
            continue
        runner = principles.find_runner(project.root, lang)
        label = principles.conventions(lang, project.profile.language)["label"]
        steps += [{"name": msg("{label} tool setup ({name})", label=label, name=runner["name"]), **step} for step in runner["ci"]]
    if steps:
        prepare = msg(
            "      # Project tools · dependencies — from lantern.yaml project.languages and the lock "
            "files (kept in step by lantern upgrade)\n"
        )
        dumped = yaml.safe_dump(steps, allow_unicode=True, sort_keys=False, width=1000)
        prepare += "".join(f"      {line}\n" for line in dumped.splitlines())
    else:
        prepare = msg(
            "      # Once the languages (lantern.yaml project.languages) are set, lantern upgrade puts the project tool setup steps here\n"
        )
    head = CI_HEAD.format(
        note=msg("Generated by lanternspec — CI also checks formats · lint · types · acceptance tests · doc-code mismatches")
    )
    checks = CI_CHECKS.format(
        check=msg("Check formats (lantern check)"),
        lint=msg("Lint · type check (lantern lint — build.lint · build.typecheck)"),
        scan=msg("Doc-code mismatches + acceptance tests (lantern scan --tests)"),
    )
    return head + prepare + checks


def generated_files(project: Project, tools: list[Tool], ci: bool) -> dict[str, str]:
    """Build every file the installer manages: skill files, and the CI workflow when asked.

    Args:
        project: The project.
        tools: The chosen tools.
        ci: Include the CI workflow.

    Returns:
        Path relative to the project root → text.

    Example:
        >>> CI_PATH in generated_files(project, [get("claude")], ci=True)  # doctest: +SKIP
        True
    """
    files = skills.generate(project.profile, tools, project.enums)
    if ci:
        files[CI_PATH] = ci_workflow(project)
    return files


def _ours(rel: str, tools: list[Tool]) -> bool:
    """A generated file this install still manages: the chosen tools' skill files, or the CI workflow."""
    return rel == CI_PATH or tools_cover(rel, tools)


def install(
    project: Project,
    tools: list[str] | None = None,
    force: bool = False,
    mcp: bool | None = None,
    ci: bool | None = None,
    language: str | None = None,
) -> InstallReport:
    """Install or refresh everything for the chosen tools.

    Files someone edited are skipped unless force; files no longer generated are removed when unedited.
    Choices not given (tools, MCP, CI) are kept from the last install.

    Args:
        project: The project.
        tools: Tool names; the last install's (or Claude Code) when None.
        force: Overwrite files someone edited.
        mcp: Register the knowledge MCP server; the last choice when None.
        ci: Write the CI workflow; the last choice when None.
        language: Language of the skills and rules before lantern.yaml exists (`lantern install --language en`);
            remembered until /l-init writes it into lantern.yaml. Once lantern.yaml exists, its language is used.

    Returns:
        What was done.

    Raises:
        ValueError: A tool is not supported, or language differs from the language lantern.yaml already fixed.

    Example:
        >>> install(project, ["claude"]).merged[0]  # doctest: +SKIP
        'AGENTS.md'
    """
    st = state.load(project)
    language = _language(project, st, language)
    names = tools or st.get("tools") or ["claude"]
    chosen = resolve_tools(names)
    mcp = bool(st.get("mcp")) if mcp is None else mcp
    ci = bool(st.get("ci")) if ci is None else ci
    report = InstallReport()
    files = generated_files(project, chosen, ci)
    records: dict[str, str] = st["files"]
    _write_managed(project, files, records, report, force)
    # files we generated before but not any more (e.g. Codex openai.yaml once l-idea is not manual-only):
    # remove them if nobody edited them, otherwise leave them and forget them
    for rel in list(records):
        if rel in files:
            continue
        path = project.root / rel
        if path.exists() and state.sha256_file(path) == records[rel] and _ours(rel, chosen):
            path.unlink()
            report.written.append(msg("{rel} (removed)", rel=rel))
            try:
                path.parent.rmdir()
            except OSError:
                pass
        elif path.exists() and _ours(rel, chosen):
            report.skipped.append(msg("{rel} (no longer used, but kept because the user edited it)", rel=rel))
        if not path.exists() or not _ours(rel, chosen):
            records.pop(rel)
    agents = project.root / "AGENTS.md"
    write(agents, rules.merge_block(read(agents) if agents.exists() else "", rules.agents_block(project.profile, chosen, project.enums)))
    report.merged.append("AGENTS.md")
    doc = principles_doc.write_doc(project)  # the details behind the AGENTS.md summary — always from the same tables
    if doc:
        report.written.append(project.rel(doc))
    report.written += [project.rel(p) for p in obsidian.write_vault(project)]
    page = sections_doc.write_page(project)  # protected sections follow renames and the project's choices
    if page:
        report.written.append(project.rel(page))  # Obsidian choices follow enums.yaml changes too
    for tool in chosen:  # each tool merges its own settings (rules hookup · hooks · MCP)
        report.merged += tool.install_config(project, mcp)
    st["language"] = language
    st["mcp"] = mcp
    st["ci"] = ci
    st["tools"] = names
    st["version"] = __version__
    state.save(project, st)
    return report


def _language(project: Project, st: dict, language: str | None) -> str:
    """The language to install in: lantern.yaml's once it exists, else the one asked for or remembered."""
    from ..core.names import languages

    if language is not None and language not in languages():
        raise ValueError(msg("No language pack '{language}' (available: {items})", language=language, items=", ".join(languages())))
    if project.profile.exists:
        fixed = project.profile.language
        if language is not None and language != fixed:
            raise ValueError(msg("This project's language is set to '{fixed}' in lantern.yaml — it doesn't change once set", fixed=fixed))
        return fixed
    chosen = language or st.get("language") or project.profile.language
    project.profile.data.setdefault("project", {})["language"] = chosen  # no lantern.yaml yet: render in this language
    messages.use(chosen)
    return chosen


def upgrade_templates(project: Project, force: bool = False) -> list[str]:
    """Refresh the copies in `docs/0. 템플릿` that nobody edited when the bundled base is newer; report the edited ones.

    Args:
        project: The project.
        force: Replace edited copies too.

    Returns:
        One message per template with a newer base.

    Example:
        >>> upgrade_templates(project)  # doctest: +SKIP
        ["✔ 양식 '기획' 1.0.0 → 1.1.0"]
    """
    if not project.templates_dir.exists():
        return []
    st = state.load(project)
    rec = st["templates"]
    out: list[str] = []
    language = project.profile.language
    for name in base_template_names(language):
        base_text = base_template_text(name, language)
        base_ver = template_version(base_text)
        dest = project_template_path(project, name)
        if not dest.exists():
            continue
        info = rec.get(name) or {}
        if not version_gap(info.get("based_on"), base_ver):
            continue
        cur_hash = state.sha256_file(dest)
        if cur_hash == info.get("sha256") or force:
            write(dest, base_text)
            rec[name] = {"based_on": base_ver, "sha256": state.sha256_text(base_text)}
            out.append(msg("✔ Template '{name}' {get} → {base_ver}", name=name, get=info.get("based_on"), base_ver=base_ver))
        else:
            out.append(
                msg(
                    "ℹ Template '{name}': the base template went {get} → {base_ver}, but this one was refined, "
                    'so it stays (compare: lantern template diff "{name}")',
                    name=name,
                    get=info.get("based_on"),
                    base_ver=base_ver,
                )
            )
    state.save(project, st)
    return out


def upgrade(project: Project, force: bool = False, apply: bool = False) -> InstallReport:
    """Re-install with the last choices and refresh template copies (`lantern upgrade`).

    When documents are not where the current layout puts them (check/layout.py), nothing is
    written unless `apply` is given: the report shows the plan and stops, so generated documents
    are never written to the new place while the old ones still exist. With `apply`, the documents
    move first (one commit) and the upgrade goes on.

    Args:
        project: The project.
        force: Overwrite files and templates someone edited.
        apply: Move documents to the current layout (`--apply`).

    Returns:
        What was done, including template and layout messages; `stopped` when the move awaits --apply.

    Raises:
        LayoutError: apply was asked but the documents have uncommitted changes.

    Example:
        >>> upgrade(project).templates  # doctest: +SKIP
        []
    """
    from ..check import layout

    found = layout.plan(project)
    notes = layout.describe(project, found)
    if not found.empty and not apply:
        return InstallReport(layout=[*notes, msg("→ To move them, run lantern upgrade --apply (nothing was changed)")], stopped=True)
    moved = layout.apply(project, found) if apply else []
    report = install(project, None, force=force)
    report.templates = upgrade_templates(project, force=force)
    if moved:
        from ..report import doc_map

        doc_map.run(project)
        report.layout = [*notes, *moved]
    else:
        report.layout = notes  # nothing to move: at most the conflicts a person must settle
    return report


def expected_files(project: Project) -> dict[str, str]:
    """Build the files the last install's choices would generate now.

    Args:
        project: The project.

    Returns:
        Path relative to the project root → text.

    Example:
        >>> len(expected_files(project))  # doctest: +SKIP
        13
    """
    st = state.load(project)
    return generated_files(project, resolve_tools(st.get("tools") or ["claude"]), bool(st.get("ci")))


def drift(project: Project) -> dict[str, list[str]]:
    """Compare installed files with what the current profile would generate (for doctor).

    Args:
        project: The project.

    Returns:
        missing (not there), stale (unedited but outdated — upgrade fixes them) and modified (edited by someone).

    Example:
        >>> drift(project)  # doctest: +SKIP
        {'missing': [], 'stale': [], 'modified': []}
    """
    st = state.load(project)
    out: dict[str, list[str]] = {"missing": [], "stale": [], "modified": []}
    for rel, content in expected_files(project).items():
        p = project.root / rel
        if not p.exists():
            out["missing"].append(rel)
            continue
        cur = state.sha256_file(p)
        if cur == state.sha256_text(content):
            continue
        if st["files"].get(rel) == cur:
            out["stale"].append(rel)
        else:
            out["modified"].append(rel)
    return out
