"""`lantern install` · `lantern upgrade` — put the skills, rules and agent hooks into each tool's folder.

Like `openspec init/update`: written straight into the project (not a plugin), so `/l-init`
is called without a prefix and the team gets it through git. Upgrades only replace files
the installer wrote and nobody edited since.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import yaml

from .. import __version__
from ..check.check_docs import version_gap
from ..core import principles, state
from ..core.project import Project, read, write
from ..report import obsidian, principles_doc
from ..work.scaffold import base_template_names, base_template_text, project_template_path, template_version
from . import resolve as resolve_tools
from . import rules, skills
from .base import Tool

CI_PATH = ".github/workflows/lanternspec.yml"
CI_HEAD = """# lanternspec가 생성 — 그림 8 ③: 양식 · 린트 · 타입 검사 · 수락 기준 테스트 · 문서-코드 어긋남을 CI에서도 본다
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
CI_CHECKS = """      - name: 양식 검사 (lantern check)
        run: lantern check --quiet
        if: hashFiles('lantern.yaml') != ''
      - name: 린트 · 타입 검사 (lantern lint — build.lint · build.typecheck)
        run: lantern lint
        if: hashFiles('lantern.yaml') != ''
      - name: 문서-코드 어긋남 + 수락 기준 테스트 (lantern scan --tests)
        run: lantern scan --tests
"""


@dataclass
class InstallReport:
    written: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)  # user-modified
    merged: list[str] = field(default_factory=list)
    templates: list[str] = field(default_factory=list)

    def lines(self) -> list[str]:
        out = []
        if self.written:
            out.append(f"✔ 생성 · 갱신 {len(self.written)}개")
            out += [f"   {p}" for p in self.written[:40]]
            if len(self.written) > 40:
                out.append(f"   … 외 {len(self.written) - 40}개")
        if self.merged:
            out.append("✔ 설정 합침: " + ", ".join(self.merged))
        if self.unchanged:
            out.append(f"· 그대로 {len(self.unchanged)}개")
        if self.skipped:
            out.append(f"⚠ 사용자가 고친 파일이라 건드리지 않음 {len(self.skipped)}개 (덮어쓰려면 --force):")
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
    return any(t.owns_skill_file(rel) for t in tools)


def ci_workflow(project: Project) -> str:
    """GitHub Actions workflow: lanternspec + the project's own tools (each language's runner, found by its lock file)."""
    steps: list[dict] = []
    for lang in project.profile.get("project.languages") or []:
        if lang not in principles.language_names():
            continue
        runner = principles.find_runner(project.root, lang)
        label = principles.conventions(lang)["label"]
        steps += [{"name": f"{label} 도구 준비 ({runner['name']})", **step} for step in runner["ci"]]
    if steps:
        prepare = "      # 프로젝트 도구 · 의존성 준비 — lantern.yaml project.languages와 lock 파일에서 (lantern upgrade가 맞춘다)\n"
        dumped = yaml.safe_dump(steps, allow_unicode=True, sort_keys=False, width=1000)
        prepare += "".join(f"      {line}\n" for line in dumped.splitlines())
    else:
        prepare = "      # 언어(lantern.yaml project.languages)가 정해지면 lantern upgrade가 프로젝트 도구 준비 단계를 여기에 넣는다\n"
    return CI_HEAD + prepare + CI_CHECKS


def generated_files(project: Project, tools: list[Tool], ci: bool) -> dict[str, str]:
    files = skills.generate(project.profile, tools, project.enums)
    if ci:
        files[CI_PATH] = ci_workflow(project)
    return files


def _ours(rel: str, tools: list[Tool]) -> bool:
    """A generated file this install still manages: the chosen tools' skill files, or the CI workflow."""
    return rel == CI_PATH or tools_cover(rel, tools)


def install(
    project: Project, tools: list[str] | None = None, force: bool = False, mcp: bool | None = None, ci: bool | None = None
) -> InstallReport:
    st = state.load(project)
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
            report.written.append(f"{rel} (지움)")
            try:
                path.parent.rmdir()
            except OSError:
                pass
        elif path.exists() and _ours(rel, chosen):
            report.skipped.append(f"{rel} (더 쓰지 않지만 사용자가 고친 파일이라 지우지 않음)")
        if not path.exists() or not _ours(rel, chosen):
            records.pop(rel)
    agents = project.root / "AGENTS.md"
    write(agents, rules.merge_block(read(agents) if agents.exists() else "", rules.agents_block(project.profile, chosen, project.enums)))
    report.merged.append("AGENTS.md")
    doc = principles_doc.write_doc(project)  # AGENTS.md 요약의 자세한 설명 — 늘 같은 기준으로
    if doc:
        report.written.append(project.rel(doc))
    report.written += [project.rel(p) for p in obsidian.write_vault(project)]  # enums.yaml이 바뀌었으면 Obsidian 선택지도
    for tool in chosen:  # each tool merges its own settings (rules hookup · hooks · MCP)
        report.merged += tool.install_config(project, mcp)
    st["mcp"] = mcp
    st["ci"] = ci
    st["tools"] = names
    st["version"] = __version__
    state.save(project, st)
    return report


def upgrade_templates(project: Project, force: bool = False) -> list[str]:
    """C-04 안 C: refresh docs/0. 템플릿 copies that nobody edited; report the edited ones."""
    if not project.templates_dir.exists():
        return []
    st = state.load(project)
    rec = st["templates"]
    out: list[str] = []
    for name in base_template_names():
        base_text = base_template_text(name)
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
            out.append(f"✔ 양식 '{name}' {info.get('based_on')} → {base_ver}")
        else:
            out.append(
                f"ℹ 양식 '{name}': 기본 양식이 {info.get('based_on')} → {base_ver}로 바뀌었지만 다듬은 양식이라 그대로 둠 "
                f'(비교: lantern template diff "{name}")'
            )
    state.save(project, st)
    return out


def upgrade(project: Project, force: bool = False) -> InstallReport:
    report = install(project, None, force=force)
    report.templates = upgrade_templates(project, force=force)
    return report


def expected_files(project: Project) -> dict[str, str]:
    st = state.load(project)
    return generated_files(project, resolve_tools(st.get("tools") or ["claude"]), bool(st.get("ci")))


def drift(project: Project) -> dict[str, list[str]]:
    """For doctor: installed skills that differ from what the current profile would generate."""
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
