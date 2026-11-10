"""Compaction must not write another parallel session's documents."""

import pytest

from conftest import init_project
from lanternspec.core.project import Project
from lanternspec.work.progress import save_before_compact


@pytest.mark.parametrize("mode", ["shared", "local"])
@pytest.mark.parametrize("has_record", [True, False])
def test_compaction_owns_only_its_work(repo, mode, has_record):
    init_project(repo)
    for name in ("first", "second", "base"):
        repo("scaffold", "work", name)
    if has_record:
        for wid in ("W-001", "W-002", "W-003"):
            repo("scaffold", "doc", wid, "기록")
    repo.git("add", "-A")
    repo.git("commit", "-qm", "docs: setup")
    if mode == "local":
        repo("docs-mode", "local")
    repo("work", "start", "W-001", "W-002", "--no-install", "--skip-check")
    base = Project.load(repo.root)
    first = Project.load(repo.root.parent / f"{repo.root.name}-W-001")
    second = Project.load(repo.root.parent / f"{repo.root.name}-W-002")
    snapshots = {p: p.read_bytes() for project in (base, first, second) for p in project.folder("works").rglob("*.md")}
    saved_first = save_before_compact(first)
    saved_second = save_before_compact(second)
    saved_base = save_before_compact(base)
    if has_record:
        for project, saved, wid in ((first, saved_first, "W-001"), (second, saved_second, "W-002"), (base, saved_base, "W-003")):
            assert list(saved) == [project.doc_path(project.find_work(wid), "record")]
    else:
        assert "W-001" in next(iter(saved_first)).stem
        assert "W-002" in next(iter(saved_second)).stem
        text = next(iter(saved_base)).read_text()
        assert "W-003" in text and "W-001" not in text and "W-002" not in text
    changed = {p.resolve() for saved in (saved_first, saved_second, saved_base) for p in saved}
    for path, before in snapshots.items():
        if path.resolve() not in changed:
            assert path.read_bytes() == before
