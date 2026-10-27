"""docs/를 Obsidian 볼트로 열 때 쓰는 설정(.obsidian)과 Metadata Menu의 문서 종류별 칸 정의를 enums.yaml에서 만든다.

책임:
    - 문서 종류(type)마다 Metadata Menu fileClass 파일 만들기 — 상태 · 종류 · 주제 칸의 선택지는 enums.yaml에서
    - docs/.obsidian의 LanternSpec 몫 설정 합치기 (사용자가 바꾼 다른 설정은 그대로)
    - CSS 조각: 문서 단계별 폴더 색 · callout · 인용문 모양 (테마와 상관없이)
    - 권장 플러그인(Dataview · Metadata Menu)의 공식 배포 파일 받기 (install_plugins)

하지 않는 일:
    - 선택지 이름 바꾸기 → core/meta.py (rename_enum_value) — 바꾼 뒤 write_vault를 다시 부른다
    - 언제 플러그인을 받을지 정하기 → /l-init이 묻고 lantern obsidian plugins를 부른다
"""

from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from ..core.enums import Enums
from ..core.profile import FOLDERS
from ..core.project import Project, read, write

PLUGINS = {  # 권장 플러그인 id → GitHub 저장소. [key:: value] 표시(할 일) · 칸 선택지(상태 · 종류 · 주제)
    "dataview": "blacksmithgu/obsidian-dataview",
    "metadata-menu": "mdelobelle/metadatamenu",
}
PLUGIN_FILES = ("main.js", "manifest.json", "styles.css")  # 커뮤니티 플러그인의 공식 배포 파일 (styles.css는 없을 수도)
RELEASE_URL = "https://github.com/{repo}/releases/latest/download/{file}"
VAULT_GITIGNORE = """# LanternSpec가 생성 — 창 배치 · 플러그인 코드는 git에 올리지 않는다 (플러그인은 lantern obsidian plugins로 받는다)
workspace*.json
plugins/*/main.js
plugins/*/manifest.json
plugins/*/styles.css
"""
CLASS_DIR = f"{FOLDERS['templates']}/_meta/fileClass/"  # 볼트(docs/) 안의 경로 — Metadata Menu가 앞에 그대로 붙여 쓴다
TYPE_FIELD = "type"  # 문서 종류 칸 = Metadata Menu가 fileClass를 고르는 열쇠
PROPERTY_TYPES = {  # Obsidian Properties 칸 종류 (types.json)
    "created": "date",
    "updated": "date",
    "resolved": "date",
    "last_asked": "date",
    "links": "multitext",
    "code": "multitext",
    "attendees": "multitext",
    "aliases": "aliases",
    "ask_count": "number",
    "generated": "checkbox",
    "ui": "checkbox",
}
APP_DEFAULTS = {"alwaysUpdateLinks": True, "showInlineTitle": True}  # 이름을 바꾸면 [[링크]]도 따라 바뀌게
SNIPPET = "lanternspec"  # .obsidian/snippets/lanternspec.css — 폴더 색 · callout · 인용문 모양
FOLDER_COLORS = {  # 맨 위 폴더 → (밝은 화면 색, 어두운 화면 색). 단계 순서대로 무지개
    "debt": ("#d64545", "#f07171"),
    "templates": ("#d9730d", "#f59a4b"),
    "ideas": ("#c79100", "#e8c14a"),
    "works": ("#2f9e44", "#5fcf75"),
    "current": ("#0b8a83", "#3fc4bc"),
    "ops": ("#1c6fd1", "#5b9ef0"),
    "legacy": ("#7c4dcc", "#a685e8"),
}


def field_id(doc_type: str, name: str) -> str:
    """Metadata Menu fileClass 칸의 id를 만든다 — 다시 만들어도 같게 (칸 순서 · 화면 설정을 id로 기억하므로).

    Args:
        doc_type: 문서 종류. 예: "debt".
        name: 칸 이름. 예: "status".

    Returns:
        6글자 id.

    Example:
        >>> field_id("debt", "status") == field_id("debt", "status"), len(field_id("debt", "status"))
        (True, 6)
    """
    return hashlib.sha1(f"{doc_type}.{name}".encode()).hexdigest()[:6]


def file_class(enums: Enums, doc_type: str) -> str:
    r"""문서 종류 하나의 Metadata Menu fileClass 파일 내용을 만든다.

    enums.yaml에서 그 종류에 쓰이는 목록(applies)마다 선택 칸 하나를 만든다. type 칸은 fileClass를 고르는 열쇠라 뺀다.

    Args:
        enums: 프로젝트의 선택지 목록.
        doc_type: 문서 종류. 예: "debt".

    Returns:
        frontmatter에 fields가 든 Markdown.

    Example:
        >>> from lanternspec.core.enums import load
        >>> text = file_class(load(), "debt")
        >>> meta = yaml.safe_load(text.split("---")[1])
        >>> [f["name"] for f in meta["fields"]], meta["fields"][0]["options"]["valuesList"]["1"]
        (['kind', 'status', 'area'], '이해')
    """
    fields = []
    for name, enum in enums.rules_for(doc_type).items():
        if name == TYPE_FIELD:
            continue
        fields.append(
            {
                "name": name,
                "type": "Select",
                "options": {"sourceType": "ValuesList", "valuesList": {str(i): v for i, v in enumerate(enum.values, 1)}},
                "path": "",
                "id": field_id(doc_type, name),
            }
        )
    meta = {
        "fields": fields,
        "limit": 20,
        "mapWithTag": False,
        "tagNames": None,
        "filesPaths": None,
        "bookmarksGroups": None,
        "excludes": None,
        "extends": None,
        "savedViews": [],
        "favoriteView": None,
        "fieldsOrder": [f["id"] for f in fields],
    }
    head = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False).rstrip()
    return f"---\n{head}\n---\n> ⚙️ 자동 생성 — enums.yaml에서 (`lantern upgrade` · `lantern enums rename`). 손으로 고치지 마세요.\n"


CALLOUT_AND_QUOTE = """
/* callout(> [!abstract] 등 모든 종류) — 옅은 색 바탕 · 색 제목 · 테두리 없음. Obsidian이 열어 둔 변수만 쓴다 */
body {
  --callout-radius: 6px;
  --callout-border-width: 0px;
  --callout-padding: 10px 14px;
  --callout-title-weight: 600;
  --blockquote-border-thickness: 4px;
  --blockquote-border-color: var(--interactive-accent);
  --blockquote-background-color: var(--background-secondary);
}

/* 인용문(>) — 읽기 모드에서도 왼쪽에 딱 붙고 callout과 같은 폭 (들여쓰기 없음) */
.markdown-rendered blockquote {
  margin-inline: 0;
  margin-left: 0;
  margin-right: 0;
  padding: 6px 14px;
  border-radius: 0 6px 6px 0;
}
"""


def snippet_css() -> str:
    """LanternSpec CSS 조각을 만든다 — 문서 단계별 폴더 색 · callout · 인용문 (어떤 테마 위에서도).

    Returns:
        CSS 글. 폴더 이름은 core/profile.py의 FOLDERS에서 가져온다.

    Example:
        >>> css = snippet_css()
        >>> '.nav-folder-title[data-path="1. 아이디어"]' in css, "--callout-radius" in css
        (True, True)
    """
    lines = [
        "/* LanternSpec — 폴더 색 · callout · 인용문 모양. 자동 생성 (lantern upgrade) — 손으로 고치지 마세요. */",
        "",
        "/* 문서 단계별 폴더 색 */",
    ]
    for key, (light, dark) in FOLDER_COLORS.items():
        sel = f'.nav-folder-title[data-path="{FOLDERS[key]}"]'
        lines += [f"body {sel} {{ --ls-folder: {light}; }}", f".theme-dark {sel} {{ --ls-folder: {dark}; }}"]
    titles = ",\n".join(f'.nav-folder-title[data-path="{FOLDERS[k]}"]' for k in FOLDER_COLORS)
    lines += [
        "",
        titles + " {",
        "  margin: 3px 0;",
        "  border: 1px solid var(--background-modifier-border);",
        "  border-left: 3px solid var(--ls-folder);",
        "  border-radius: 4px;",
        "  color: var(--ls-folder);",
        "  font-weight: 600;",
        "}",
        CALLOUT_AND_QUOTE,
    ]
    return "\n".join(lines)


def write_vault(project: Project) -> list[Path]:
    """docs/의 Obsidian 설정과 fileClass 파일을 (다시) 쓴다. 내용이 그대로인 파일은 건드리지 않는다.

    Args:
        project: 프로젝트. docs/가 있어야 쓴다.

    Returns:
        새로 쓰거나 바꾼 파일들.

    Example:
        >>> [project.rel(p) for p in write_vault(project)][:2]  # doctest: +SKIP
        ['docs/.obsidian/app.json', 'docs/.obsidian/community-plugins.json']
    """
    if not project.docs.exists():
        return []
    enums = project.enums
    obs = project.docs / ".obsidian"
    out: list[Path] = []

    def save(path: Path, text: str) -> None:
        if not path.exists() or read(path) != text:
            write(path, text)
            out.append(path)

    save(obs / "app.json", _dump({**APP_DEFAULTS, **_load(obs / "app.json")}))
    save(obs / "snippets" / f"{SNIPPET}.css", snippet_css())
    look = _load(obs / "appearance.json")
    snippets = look.get("enabledCssSnippets") or []
    save(obs / "appearance.json", _dump({**look, "enabledCssSnippets": snippets + [SNIPPET] * (SNIPPET not in snippets)}))
    plugins = _load(obs / "community-plugins.json", [])
    save(obs / "community-plugins.json", _dump(plugins + [p for p in PLUGINS if p not in plugins]))
    save(obs / ".gitignore", VAULT_GITIGNORE)
    types = _load(obs / "types.json")
    save(obs / "types.json", _dump({**types, "types": {**PROPERTY_TYPES, **(types.get("types") or {})}}))
    mm = _load(obs / "plugins" / "metadata-menu" / "data.json")
    mm.update({"fileClassAlias": TYPE_FIELD, "classFilesPath": CLASS_DIR})
    mm["presetFields"] = [f for f in mm.get("presetFields") or [] if f.get("name") not in _managed_fields(enums)]
    save(obs / "plugins" / "metadata-menu" / "data.json", _dump(mm))
    class_dir = project.docs / CLASS_DIR
    wanted = {f"{t}.md": file_class(enums, t) for t in enums.values("doc_type")}
    for name, text in wanted.items():
        save(class_dir / name, text)
    for stale in class_dir.glob("*.md"):  # 이름이 바뀌어 더는 없는 문서 종류
        if stale.name not in wanted:
            stale.unlink()
            out.append(stale)
    return out


def install_plugins(project: Project, fetch: Callable[[str], bytes | None] | None = None) -> list[tuple[str, str]]:
    """권장 Obsidian 플러그인(Dataview · Metadata Menu)의 최신 공식 배포 파일을 받아 docs/.obsidian/plugins/에 넣는다.

    플러그인 설정(data.json)은 건드리지 않는다. 받은 파일은 .obsidian/.gitignore로 git에서 빠진다.

    Args:
        project: 프로젝트. docs/가 있어야 한다.
        fetch: 주소 → 내용(없으면 None). 기본은 인터넷에서 받기 (테스트에서 바꿔 끼운다).

    Returns:
        (플러그인 id, 받은 버전) 목록.

    Raises:
        RuntimeError: docs/가 없거나, main.js · manifest.json을 받지 못했을 때.

    Example:
        >>> install_plugins(project)  # doctest: +SKIP
        [('dataview', '0.5.68'), ('metadata-menu', '0.8.12')]
    """
    if not project.docs.exists():
        raise RuntimeError("docs/가 없습니다 — 먼저 lantern scaffold init")
    get = fetch or _download
    done: list[tuple[str, str]] = []
    for plugin_id, repo in PLUGINS.items():
        files = {f: get(RELEASE_URL.format(repo=repo, file=f)) for f in PLUGIN_FILES}
        if files["main.js"] is None or files["manifest.json"] is None:
            raise RuntimeError(f"{plugin_id}를 받지 못했습니다 — Obsidian의 커뮤니티 플러그인에서 직접 설치하세요")
        folder = project.docs / ".obsidian" / "plugins" / plugin_id
        folder.mkdir(parents=True, exist_ok=True)
        for name, data in files.items():
            if data is not None:
                (folder / name).write_bytes(data)
        done.append((plugin_id, str(json.loads(files["manifest.json"]).get("version", "?"))))
    return done


def _download(url: str) -> bytes | None:
    """주소의 내용을 받는다. 없으면(404) None."""
    try:
        with urllib.request.urlopen(url, timeout=30) as r:  # GitHub가 최신 배포 파일로 넘겨 준다
            return r.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise RuntimeError(f"받기 실패 ({e.code}): {url}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"인터넷에 연결할 수 없습니다: {e.reason}") from e


def _managed_fields(enums: Enums) -> set[str]:
    """enums.yaml이 정하는 칸 이름 — Preset Fields에 남아 있으면 fileClass와 겹치므로 뺀다."""
    return {name for e in enums.enums.values() for name in e.applies.values()}


def _load(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return {} if default is None else default
    try:
        return json.loads(read(path))
    except json.JSONDecodeError:
        return {} if default is None else default


def _dump(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"
