"""Build the settings for opening docs/ as an Obsidian vault (.obsidian) and per-type Metadata Menu fields, from enums.yaml.

Responsibilities:
    - a Metadata Menu fileClass file per document type — status · kind · topic choices come from enums.yaml
    - merge LanternSpec's share of docs/.obsidian settings (other user settings stay)
    - CSS snippet: folder colors per document stage · folder and file icons · callout · quote styles (any theme)
    - download the recommended plugins' official releases (Dataview · Metadata Menu) (install_plugins)

Not here:
    - renaming choices → core/meta.py (rename_enum_value) — write_vault runs again afterwards
    - deciding when to download plugins → /l-init asks and calls lantern obsidian plugins
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
from ..core.messages import msg
from ..core.names import Names
from ..core.project import Project, read, write

PLUGINS = {  # recommended plugin id → GitHub repo. [key:: value] display (tasks) · field choices (status · kind · topic)
    "dataview": "blacksmithgu/obsidian-dataview",
    "metadata-menu": "mdelobelle/metadatamenu",
}
PLUGIN_FILES = ("main.js", "manifest.json", "styles.css")  # official release files of a community plugin (styles.css may be missing)
RELEASE_URL = "https://github.com/{repo}/releases/latest/download/{file}"
VAULT_GITIGNORE = """# {note}
workspace*.json
plugins/*/main.js
plugins/*/manifest.json
plugins/*/styles.css
"""
TYPE_FIELD = "type"  # the document-type field = the key Metadata Menu picks the fileClass by
PROPERTY_TYPES = {  # Obsidian Properties field types (types.json)
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
APP_DEFAULTS = {"alwaysUpdateLinks": True, "showInlineTitle": True}  # renaming a file updates its [[links]]
SNIPPET = "lanternspec"  # .obsidian/snippets/lanternspec.css — folder colors · file icons · callout · quote styles
FOLDER_COLORS = {  # top-level folder → (light color, dark color). A rainbow in stage order
    "debt": ("#d64545", "#f07171"),
    "templates": ("#d9730d", "#f59a4b"),
    "ideas": ("#c79100", "#e8c14a"),
    "works": ("#2f9e44", "#5fcf75"),
    "current": ("#0b8a83", "#3fc4bc"),
    "ops": ("#1c6fd1", "#5b9ef0"),
    "legacy": ("#7c4dcc", "#a685e8"),
}


def field_id(doc_type: str, name: str) -> str:
    """Make the id of a Metadata Menu fileClass field — stable across rebuilds (field order and views are keyed by id).

    Args:
        doc_type: Document type, e.g. "debt".
        name: Field name, e.g. "status".

    Returns:
        A 6-character id.

    Example:
        >>> field_id("debt", "status") == field_id("debt", "status"), len(field_id("debt", "status"))
        (True, 6)
    """
    return hashlib.sha1(f"{doc_type}.{name}".encode()).hexdigest()[:6]


def file_class(enums: Enums, doc_type: str) -> str:
    r"""Build the Metadata Menu fileClass file for one document type.

    One select field per enums.yaml list that applies to the type. The type field is left out — it selects the fileClass.

    Args:
        enums: The project's choice lists.
        doc_type: Document type, e.g. "debt".

    Returns:
        Markdown with `fields` in its frontmatter.

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
    return msg(
        "---\n{head}\n---\n> ⚙️ Generated — from enums.yaml (`lantern upgrade` · `lantern enums rename`). Don't edit by hand.\n", head=head
    )


def _icon(paths: str) -> str:
    """Make a CSS url() of a 24px stroke icon (Lucide shapes, as Obsidian's own icons) for use as a mask."""
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' "
        f"stroke-linecap='round' stroke-linejoin='round'>{paths}</svg>"
    )
    return f'url("data:image/svg+xml,{svg}")'


ICONS = {
    "folder": _icon(
        "<path d='M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z'/>"
    ),
    "folder-open": _icon(
        "<path d='m6 14 1.5-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.54 6a2 2 0 0 1-1.95 1.5H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9"
        "a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H18a2 2 0 0 1 2 2v2'/>"
    ),
    "file": _icon(
        "<path d='M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z'/><path d='M14 2v4a2 2 0 0 0 2 2h4'/>"
        "<path d='M16 13H8'/><path d='M16 17H8'/><path d='M10 9H8'/>"
    ),
}

FILE_ICONS = """
/* ICON_NOTE */
.nav-files-container .nav-folder-title .collapse-icon { display: none; }
.nav-folder:not(.mod-root) .nav-folder > .nav-folder-title {
  color: var(--ls-folder, var(--nav-item-color));
  font-weight: 600;
}
.nav-file-title-content::before,
.nav-folder:not(.mod-root) .nav-folder > .nav-folder-title .nav-folder-title-content::before {
  content: "";
  display: inline-block;
  width: 14px;
  height: 14px;
  margin-inline-end: 6px;
  vertical-align: -2px;
  background-color: var(--ls-folder, var(--text-muted));
  opacity: 0.75;
  -webkit-mask: var(--ls-icon) no-repeat center / contain;
  mask: var(--ls-icon) no-repeat center / contain;
}
.nav-file-title-content::before { --ls-icon: ICON_FILE; }
.nav-folder-title-content::before { --ls-icon: ICON_FOLDER; }
.nav-folder:not(.is-collapsed) > .nav-folder-title .nav-folder-title-content::before { --ls-icon: ICON_FOLDER_OPEN; }
"""

CALLOUT_AND_QUOTE = """
/* CALLOUT_NOTE */
body {
  --callout-radius: 6px;
  --callout-border-width: 0px;
  --callout-padding: 10px 14px;
  --callout-title-weight: 600;
  --blockquote-border-thickness: 4px;
  --blockquote-border-color: var(--interactive-accent);
  --blockquote-background-color: var(--background-secondary);
}

/* QUOTE_NOTE */
.markdown-rendered blockquote {
  margin-inline: 0;
  margin-left: 0;
  margin-right: 0;
  padding: 6px 14px;
  border-radius: 0 6px 6px 0;
}
"""


def class_dir(names: Names) -> str:
    """Return the fileClass folder inside the vault (docs/), with a trailing slash — Metadata Menu uses it as a prefix as is.

    Args:
        names: The project's names (the template folder's name).

    Returns:
        e.g. "0. 템플릿/_meta/fileClass/".

    Example:
        >>> from lanternspec.core.names import load
        >>> class_dir(load("ko"))
        '0. 템플릿/_meta/fileClass/'
    """
    return f"{names.folder('templates')}/_meta/fileClass/"


def snippet_css(names: Names) -> str:
    """Build the LanternSpec CSS snippet — folder colors per document stage · folder and file icons · callouts · quotes (on any theme).

    Args:
        names: The project's names (folder names).

    Returns:
        CSS text.

    Example:
        >>> from lanternspec.core.names import load
        >>> css = snippet_css(load("ko"))
        >>> '.nav-folder-title[data-path="1. 아이디어"]' in css, ".nav-file-title-content::before" in css, "--callout-radius" in css
        (True, True, True)
    """
    lines = [
        msg("/* LanternSpec — folder colors · file icons · callouts · quote style. Generated (lantern upgrade) — don't edit by hand. */"),
        "",
        msg("/* folder colors by document stage — the box holds the folder and everything in it */"),
    ]
    for key, (light, dark) in FOLDER_COLORS.items():
        sel = f'.nav-folder:has(> .nav-folder-title[data-path="{names.folder(key)}"])'
        lines += [f"body {sel} {{ --ls-folder: {light}; }}", f".theme-dark {sel} {{ --ls-folder: {dark}; }}"]
    boxes = ",\n".join(f'.nav-folder:has(> .nav-folder-title[data-path="{names.folder(k)}"])' for k in FOLDER_COLORS)
    titles = ",\n".join(f'.nav-folder-title[data-path="{names.folder(k)}"]' for k in FOLDER_COLORS)
    lines += [
        "",
        boxes + " {",
        "  margin: 3px 0;",
        "  border: 1px solid var(--background-modifier-border);",
        "  border-left: 3px solid var(--ls-folder);",
        "  border-radius: 4px;",
        "  --nav-indentation-guide-color: transparent;",
        "}",
        titles + " {",
        "  color: var(--ls-folder);",
        "  font-weight: 600;",
        "}",
        FILE_ICONS.replace(
            "ICON_NOTE",
            msg("folder and file icons — the stage color, no collapse arrow (an open folder shows an open icon). Only CSS, no plugin"),
        )
        .replace("ICON_FOLDER_OPEN", ICONS["folder-open"])
        .replace("ICON_FOLDER", ICONS["folder"])
        .replace("ICON_FILE", ICONS["file"]),
        CALLOUT_AND_QUOTE.replace(
            "CALLOUT_NOTE",
            msg(
                "callouts (> [!abstract] and every other kind) — pale background · colored title · "
                "no border. Only variables Obsidian exposes"
            ),
        ).replace("QUOTE_NOTE", msg("quotes (>) — flush left in reading mode too, the same width as callouts (no indent)")),
    ]
    return "\n".join(lines)


def write_vault(project: Project) -> list[Path]:
    """(Re)write docs/ Obsidian settings and fileClass files. Unchanged files are left alone.

    Args:
        project: The project. Nothing is written without docs/.

    Returns:
        Files created or changed.

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
    save(obs / "snippets" / f"{SNIPPET}.css", snippet_css(project.names))
    look = _load(obs / "appearance.json")
    snippets = look.get("enabledCssSnippets") or []
    save(obs / "appearance.json", _dump({**look, "enabledCssSnippets": snippets + [SNIPPET] * (SNIPPET not in snippets)}))
    plugins = _load(obs / "community-plugins.json", [])
    save(obs / "community-plugins.json", _dump(plugins + [p for p in PLUGINS if p not in plugins]))
    save(
        obs / ".gitignore",
        VAULT_GITIGNORE.format(
            note=msg(
                "Generated by LanternSpec — window layout · plugin code are not committed (get the plugins with lantern obsidian plugins)"
            )
        ),
    )
    types = _load(obs / "types.json")
    save(obs / "types.json", _dump({**types, "types": {**PROPERTY_TYPES, **(types.get("types") or {})}}))
    mm = _load(obs / "plugins" / "metadata-menu" / "data.json")
    mm.update({"fileClassAlias": TYPE_FIELD, "classFilesPath": class_dir(project.names)})
    mm["presetFields"] = [f for f in mm.get("presetFields") or [] if f.get("name") not in _managed_fields(enums)]
    save(obs / "plugins" / "metadata-menu" / "data.json", _dump(mm))
    classes = project.docs / class_dir(project.names)
    wanted = {f"{t}.md": file_class(enums, t) for t in enums.values("doc_type")}
    for name, text in wanted.items():
        save(classes / name, text)
    for stale in classes.glob("*.md"):  # document types that no longer exist after a rename
        if stale.name not in wanted:
            stale.unlink()
            out.append(stale)
    return out


def install_plugins(project: Project, fetch: Callable[[str], bytes | None] | None = None) -> list[tuple[str, str]]:
    """Download the latest official releases of the recommended Obsidian plugins (Dataview · Metadata Menu) into docs/.obsidian/plugins/.

    Plugin settings (data.json) are not touched. Downloaded files stay out of git via .obsidian/.gitignore.

    Args:
        project: The project. docs/ must exist.
        fetch: URL → content (None if missing). Downloads from the internet by default (replaced in tests).

    Returns:
        List of (plugin id, downloaded version).

    Raises:
        RuntimeError: docs/ is missing, or main.js · manifest.json could not be downloaded.

    Example:
        >>> install_plugins(project)  # doctest: +SKIP
        [('dataview', '0.5.68'), ('metadata-menu', '0.8.12')]
    """
    if not project.docs.exists():
        raise RuntimeError(msg("No docs/ — run lantern scaffold init first"))
    get = fetch or _download
    done: list[tuple[str, str]] = []
    for plugin_id, repo in PLUGINS.items():
        files = {f: get(RELEASE_URL.format(repo=repo, file=f)) for f in PLUGIN_FILES}
        if files["main.js"] is None or files["manifest.json"] is None:
            raise RuntimeError(
                msg("Couldn't download {plugin_id} — install it yourself from Obsidian's community plugins", plugin_id=plugin_id)
            )
        folder = project.docs / ".obsidian" / "plugins" / plugin_id
        folder.mkdir(parents=True, exist_ok=True)
        for name, data in files.items():
            if data is not None:
                (folder / name).write_bytes(data)
        done.append((plugin_id, str(json.loads(files["manifest.json"]).get("version", "?"))))
    return done


def _download(url: str) -> bytes | None:
    """Download a URL; None on 404."""
    try:
        with urllib.request.urlopen(url, timeout=30) as r:  # GitHub redirects to the latest release file
            return r.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise RuntimeError(msg("Download failed ({code}): {url}", code=e.code, url=url)) from e
    except urllib.error.URLError as e:
        raise RuntimeError(msg("Can't connect to the internet: {reason}", reason=e.reason)) from e


def _managed_fields(enums: Enums) -> set[str]:
    """Field names enums.yaml defines — removed from Preset Fields since they would clash with the fileClasses."""
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
