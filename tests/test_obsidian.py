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
    assert '.nav-folder-title[data-path="2. 작업"]' in css and '[data-path="📒 부채"]' in css
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
