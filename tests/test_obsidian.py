"""Settings for opening docs/ as an Obsidian vault — field choices come from enums.yaml; the user's own settings stay."""

import json

import yaml

from conftest import init_project

CLASS_DIR = "docs/0. 템플릿/_meta/fileClass"


def _fields(repo, doc_type):
    text = (repo.root / CLASS_DIR / f"{doc_type}.md").read_text(encoding="utf-8")
    meta = yaml.safe_load(text.split("---")[1])
    return {f["name"]: list(f["options"]["valuesList"].values()) for f in meta["fields"]}


def test_vault_settings_follow_enums_and_keep_user_settings(repo):
    init_project(repo)
    obs = repo.root / "docs/.obsidian"
    obs.mkdir(parents=True, exist_ok=True)  # init_project may have made it already
    # settings the user already had: other plugins · other app settings · an old Preset Field that overlaps a LanternSpec field
    (obs / "community-plugins.json").write_text('["calendar"]', encoding="utf-8")
    (obs / "appearance.json").write_text('{"cssTheme": "Blue Topaz", "enabledCssSnippets": ["tags"]}', encoding="utf-8")
    (obs / "app.json").write_text('{"spellcheck": false, "alwaysUpdateLinks": false}', encoding="utf-8")
    (obs / "plugins/metadata-menu").mkdir(parents=True, exist_ok=True)
    (obs / "plugins/metadata-menu/data.json").write_text(
        json.dumps({"presetFields": [{"name": "status", "id": "old"}, {"name": "mood", "id": "m"}], "isAutosuggestEnabled": False}),
        encoding="utf-8",
    )
    repo("scaffold", "init")
    # each document type gets only its own choices
    debt = _fields(repo, "debt")
    assert debt["status"] == ["처음", "되물음", "연습 중", "해결"] and "기타" in debt["area"] and debt["kind"][0] == "이해"
    assert set(_fields(repo, "idea")) == {"kind", "status"} and "type" not in _fields(repo, "plan")
    mm = json.loads((obs / "plugins/metadata-menu/data.json").read_text(encoding="utf-8"))
    assert mm["fileClassAlias"] == "type" and mm["classFilesPath"] == "0. 템플릿/_meta/fileClass/"
    assert [f["name"] for f in mm["presetFields"]] == ["mood"] and mm["isAutosuggestEnabled"] is False
    assert json.loads((obs / "community-plugins.json").read_text(encoding="utf-8")) == ["calendar", "dataview", "metadata-menu"]
    app = json.loads((obs / "app.json").read_text(encoding="utf-8"))
    assert app == {"alwaysUpdateLinks": False, "showInlineTitle": True, "spellcheck": False}  # values the user set stay
    # folder colours by stage: our CSS snippet is turned on; the user's theme and snippets stay
    look = json.loads((obs / "appearance.json").read_text(encoding="utf-8"))
    assert look == {"cssTheme": "Blue Topaz", "enabledCssSnippets": ["tags", "lanternspec"]}
    css = (obs / "snippets/lanternspec.css").read_text(encoding="utf-8")
    assert '.nav-folder-title[data-path="2. 작업"]' in css and '[data-path="📒 부채"]' in css and '[data-path="📚 도메인 지식"]' in css
    assert "--callout-radius" in css and ".markdown-rendered blockquote" in css  # callout and quote styles too
    # renaming a value renames the Obsidian choice too
    repo("enums", "rename", "debt_status", "되물음", "다시 물음")
    assert _fields(repo, "debt")["status"] == ["처음", "다시 물음", "연습 중", "해결"]
    # fileClass files and .obsidian are not format-checked
    code, out = repo("check", ok=False)
    assert "fileClass" not in out and ".obsidian" not in out


def test_obsidian_plugins_download_latest_release_files(repo, monkeypatch):
    init_project(repo)
    repo("scaffold", "init")
    asked = []

    def fake_fetch(url):
        asked.append(url)
        if url.endswith("styles.css") and "dataview" in url:
            return None  # missing files are skipped
        if url.endswith("manifest.json"):
            return json.dumps({"id": url.split("/")[4], "version": "9.9.9"}).encode()
        return b"// plugin code"

    monkeypatch.setattr("lanternspec.report.obsidian._download", fake_fetch)
    _, out = repo("obsidian", "plugins")
    assert "✔ dataview 9.9.9" in out and "✔ metadata-menu 9.9.9" in out
    assert "https://github.com/blacksmithgu/obsidian-dataview/releases/latest/download/main.js" in asked
    plugins = repo.root / "docs/.obsidian/plugins"
    assert (plugins / "metadata-menu/main.js").exists() and (plugins / "metadata-menu/data.json").exists()  # settings stay
    assert not (plugins / "dataview/styles.css").exists()
    # downloaded plugin code stays out of git — only settings (data.json) are committed
    repo.git("add", "-A")
    staged = repo.git("diff", "--cached", "--name-only").stdout
    assert "plugins/metadata-menu/data.json" in staged and "main.js" not in staged and "workspace" not in staged
    # when a download fails, say what to do
    monkeypatch.setattr("lanternspec.report.obsidian._download", lambda url: None)
    code, out = repo("obsidian", "plugins", ok=False)
    assert code == 1 and "커뮤니티 플러그인에서 직접 설치" in out


def _timeline_project(repo):
    init_project(repo)
    repo("scaffold", "work", "로그인")
    tasks = repo.root / "docs/2. 작업/W-001 로그인/할 일.md"
    lines = (
        "- [x] W-001-T01 설계 — [[2. 작업/W-001 로그인/설계|설계]] [크기:: S] [시작:: 2026-10-29 10:00] [완료:: 2026-10-29 10:00]\n"
        "- [ ] W-001-T02 버튼 `확인` [크기:: M] [시작 예정:: 2026-11-02] [마감 예정:: 2026-11-04]\n"
        "- [ ] W-001-T03 연결 [크기:: L]\n"
    )
    tasks.write_text(lines, encoding="utf-8")
    return repo.root / "docs/.obsidian/plugins/lantern-timeline", repo.root / "docs/4. 운영 기록/보고/현황.md"


def test_the_timeline_plugin_comes_with_obsidian_plugins_and_reports_then_use_it(repo):
    plugin, report = _timeline_project(repo)
    repo("report", "--views", "timeline")
    text = report.read_text(encoding="utf-8")  # no plugins in this vault: Mermaid, as anywhere else
    assert not plugin.exists() and "```mermaid" in text and "lantern-timeline" not in text
    assert "`lantern report`를 실행한 때의 상태다" in text
    assert "T01 설계 :done, w001t01, 2026-10-29 10:00, 2026-10-29 10:30" in text and "[[" not in text.split("```mermaid")[1]

    dataview = repo.root / "docs/.obsidian/plugins/dataview"  # upgrade brings it to a vault that already uses plugins
    dataview.mkdir(parents=True)
    (dataview / "main.js").write_text("", encoding="utf-8")
    repo("upgrade")
    assert {"main.js", "manifest.json", "styles.css"} == {p.name for p in plugin.iterdir()}
    assert json.loads((plugin / "manifest.json").read_text(encoding="utf-8"))["id"] == "lantern-timeline"
    assert "lantern-timeline" in json.loads((repo.root / "docs/.obsidian/community-plugins.json").read_text(encoding="utf-8"))

    repo("report", "--views", "timeline")
    text = report.read_text(encoding="utf-8")
    assert "```mermaid" not in text
    data = json.loads(text.split("```lantern-timeline\n")[1].split("\n```")[0])
    assert "`" not in text.split("```lantern-timeline\n")[1].split("\n```")[0]  # can't close the code block early
    assert data["labels"]["doing"] == "진행 중"
    work = data["works"][0]
    assert work["id"] == "W-001" and work["file"] == "2. 작업/W-001 로그인/할 일.md"
    t1, t2, t3 = work["tasks"]
    assert t1 == {
        "id": "T01",
        "title": "설계",
        "start": "2026-10-29 10:00",
        "end": "2026-10-29 10:30",
        "state": "done",
        "basis": "actual",
    }
    assert (t2["basis"], t2["state"], t2["start"], t2["end"]) == ("planned", "todo", "2026-11-02 00:00", "2026-11-04 00:00")
    assert (t3["basis"], t3["start"], t3["end"]) == (
        "estimated",
        "2026-11-04 00:00",
        "2026-11-07 00:00",
    )  # after the task before it, L = 3 days


def test_the_timeline_shows_each_task_by_its_checkbox_and_its_actual_days(repo):
    plugin, report = _timeline_project(repo)
    tasks = repo.root / "docs/2. 작업/W-001 로그인/할 일.md"
    tasks.write_text(
        "- [x] W-001-T01 여러 날 [시작:: 2026-10-29 10:00] [완료:: 2026-11-02 18:00]\n"
        "- [ ] W-001-T02 체크를 푼 일 [시작:: 2026-10-29 10:00] [완료:: 2026-10-29 11:00]\n"
        "- [ ] W-001-T03 하는 중 [시작:: 2026-10-30 10:00]\n",
        encoding="utf-8",
    )
    (plugin / "main.js").parent.mkdir(parents=True)
    (plugin / "main.js").write_text("", encoding="utf-8")
    repo("report", "--views", "timeline")
    text = report.read_text(encoding="utf-8")
    t1, t2, t3 = json.loads(text.split("```lantern-timeline\n")[1].split("\n```")[0])["works"][0]["tasks"]
    assert (t1["state"], t1["start"], t1["end"]) == ("done", "2026-10-29 10:00", "2026-11-02 18:00")
    assert (t2["state"], t2["end"]) == ("doing", "2026-10-29 11:00")
    assert t3["state"] == "doing"
    assert "체크 상태는 바로 반영되고" in text
    assert json.loads(text.split("```lantern-timeline\n")[1].split("\n```")[0])["startField"] == "시작"


def test_the_vault_turns_off_metadata_menus_dataview_notice(repo):
    init_project(repo)
    data = json.loads((repo.root / "docs/.obsidian/plugins/metadata-menu/data.json").read_text(encoding="utf-8"))
    assert data["disableDataviewPrompt"] is True


def test_the_timeline_plugin_ships_and_only_draws():
    from lanternspec import resources

    files = dict(resources.iter_files("obsidian/lantern-timeline"))
    assert set(files) == {"main.js", "manifest.json", "styles.css"}
    code = files["main.js"].read_text(encoding="utf-8")
    assert 'registerMarkdownCodeBlockProcessor("lantern-timeline"' in code
    assert not any(call in code for call in (".modify(", ".process(", ".create(", ".append(", ".delete("))  # reading only, for now
