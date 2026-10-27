"""docs/를 Obsidian 볼트로 열 때의 설정 — 칸 선택지는 enums.yaml에서, 사용자가 바꾼 설정은 그대로."""

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
    obs.mkdir(parents=True, exist_ok=True)  # init_project가 이미 만들었을 수 있다
    # 사용자가 이미 쓰던 설정: 다른 플러그인 · 다른 앱 설정 · LanternSpec 칸과 겹치는 옛 Preset Field
    (obs / "community-plugins.json").write_text('["calendar"]', encoding="utf-8")
    (obs / "appearance.json").write_text('{"cssTheme": "Blue Topaz", "enabledCssSnippets": ["tags"]}', encoding="utf-8")
    (obs / "app.json").write_text('{"spellcheck": false, "alwaysUpdateLinks": false}', encoding="utf-8")
    (obs / "plugins/metadata-menu").mkdir(parents=True, exist_ok=True)
    (obs / "plugins/metadata-menu/data.json").write_text(
        json.dumps({"presetFields": [{"name": "status", "id": "old"}, {"name": "mood", "id": "m"}], "isAutosuggestEnabled": False}),
        encoding="utf-8",
    )
    repo("scaffold", "init")
    # 문서 종류마다 그 종류의 선택지만
    debt = _fields(repo, "debt")
    assert debt["status"] == ["처음", "되물음", "연습 중", "해결"] and "기타" in debt["area"] and debt["kind"][0] == "이해"
    assert set(_fields(repo, "idea")) == {"kind", "status"} and "type" not in _fields(repo, "plan")
    mm = json.loads((obs / "plugins/metadata-menu/data.json").read_text(encoding="utf-8"))
    assert mm["fileClassAlias"] == "type" and mm["classFilesPath"] == "0. 템플릿/_meta/fileClass/"
    assert [f["name"] for f in mm["presetFields"]] == ["mood"] and mm["isAutosuggestEnabled"] is False
    assert json.loads((obs / "community-plugins.json").read_text(encoding="utf-8")) == ["calendar", "dataview", "metadata-menu"]
    app = json.loads((obs / "app.json").read_text(encoding="utf-8"))
    assert app == {"alwaysUpdateLinks": False, "showInlineTitle": True, "spellcheck": False}  # 사용자가 정한 값은 그대로
    # 문서 단계별 폴더 색: LanternSpec CSS 조각을 켜고, 사용자의 테마 · 조각은 그대로
    look = json.loads((obs / "appearance.json").read_text(encoding="utf-8"))
    assert look == {"cssTheme": "Blue Topaz", "enabledCssSnippets": ["tags", "lanternspec"]}
    css = (obs / "snippets/lanternspec.css").read_text(encoding="utf-8")
    assert '.nav-folder-title[data-path="2. 작업"]' in css and '[data-path="📒 부채"]' in css
    assert "--callout-radius" in css and ".markdown-rendered blockquote" in css  # callout · 인용문 모양도
    # 이름을 바꾸면 Obsidian 선택지도 같이
    repo("enums", "rename", "debt_status", "되물음", "다시 물음")
    assert _fields(repo, "debt")["status"] == ["처음", "다시 물음", "연습 중", "해결"]
    # fileClass 파일 · .obsidian은 양식 검사 대상이 아니다
    code, out = repo("check", ok=False)
    assert "fileClass" not in out and ".obsidian" not in out


def test_obsidian_plugins_download_latest_release_files(repo, monkeypatch):
    init_project(repo)
    repo("scaffold", "init")
    asked = []

    def fake_fetch(url):
        asked.append(url)
        if url.endswith("styles.css") and "dataview" in url:
            return None  # 없는 파일은 건너뛴다
        if url.endswith("manifest.json"):
            return json.dumps({"id": url.split("/")[4], "version": "9.9.9"}).encode()
        return b"// plugin code"

    monkeypatch.setattr("lanternspec.report.obsidian._download", fake_fetch)
    _, out = repo("obsidian", "plugins")
    assert "✔ dataview 9.9.9" in out and "✔ metadata-menu 9.9.9" in out
    assert "https://github.com/blacksmithgu/obsidian-dataview/releases/latest/download/main.js" in asked
    plugins = repo.root / "docs/.obsidian/plugins"
    assert (plugins / "metadata-menu/main.js").exists() and (plugins / "metadata-menu/data.json").exists()  # 설정은 그대로
    assert not (plugins / "dataview/styles.css").exists()
    # 받은 코드는 git에 올라가지 않는다 — 설정(data.json)만 올라간다
    repo.git("add", "-A")
    staged = repo.git("diff", "--cached", "--name-only").stdout
    assert "plugins/metadata-menu/data.json" in staged and "main.js" not in staged and "workspace" not in staged
    # 받지 못하면 무엇을 하면 되는지 알려 준다
    monkeypatch.setattr("lanternspec.report.obsidian._download", lambda url: None)
    code, out = repo("obsidian", "plugins", ok=False)
    assert code == 1 and "커뮤니티 플러그인에서 직접 설치" in out
