r"""Turn the originals people put among the references (PDF · DOCX · PPTX · HWP · HWPX · XLSX · CSV) into Markdown.

The AI reads references a section at a time through `lantern ref read`; it never opens a PDF or a
200MB spreadsheet. So a text original becomes a Markdown copy next to it, cut into sections the
index can address (headings when the original has them, else pages or parts), and a data original
becomes a short card (sheets · columns · row counts · first rows) — its values stay in the original,
for code to read. Everything runs here with the standard library, except PDF, which needs `pdftotext`
(poppler) on the PATH. Nothing is promised: each copy says how well it came out.

Each copy starts with one comment line holding the original's name, size, time and hash, the tool and
the quality, and the hash of the copy's own text — so a changed original is noticed, and a copy someone
fixed by hand is not overwritten.

Responsibilities:
    - list the originals of a folder and say which are new, changed, done, duplicates or unreadable
    - convert one original (text → sections, data → a card) and rate the result
    - preview a document as its sections' first lines, so describing it doesn't take reading it all

Not here:
    - which folders are references → refs/sources.py
    - indexing and describing sections → refs/index.py
"""

from __future__ import annotations

import csv
import hashlib
import re
import shutil
import struct
import subprocess
import zipfile
import zlib
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

from ..core import outline
from ..core.messages import msg

TEXT = {".pdf": "PDF", ".docx": "DOCX", ".pptx": "PPTX", ".hwp": "HWP", ".hwpx": "HWPX"}
DATA = {".xlsx": "XLSX", ".csv": "CSV"}
PART_LINES = 80  # a text with no headings or pages is cut into parts of about this many lines
SPARSE = 200  # a page with fewer letters than this is mostly pictures or tables
HEADER = re.compile(r"^<!-- lantern:converted (.*?) -->\n")
FIELD = re.compile(r'(\w+)="([^"]*)"')


class ConvertError(Exception):
    """An original that can't be converted here; the message says what to do instead."""


@dataclass(frozen=True)
class Copy:
    """The Markdown made from one original.

    Attributes:
        body: The Markdown without the header line.
        tool: What read it ("pdftotext", "docx", …).
        quality: "ok", "check" (read it before trusting it) or "empty" (no text — a scan?).
        note: Why the quality is not "ok"; "" when it is.
    """

    body: str
    tool: str
    quality: str
    note: str = ""


@dataclass(frozen=True)
class Original:
    """One file people put among the references that is not Markdown.

    Attributes:
        path: The original.
        kind: "text", "data" or "unknown".
        target: Where its Markdown copy goes.
        state: "new", "changed" (the original changed after it was converted), "done", "edited"
            (changed, but someone edited the copy — left alone), "same" (a duplicate) or "unknown".
        same_as: For a duplicate, the original it repeats.
        quality: The quality written in the copy ("" when there is none yet).
    """

    path: Path
    kind: str
    target: Path
    state: str
    same_as: Path | None = None
    quality: str = ""

    @property
    def label(self) -> str:
        """The format as people say it ("PDF", "HWP" …).

        Example:
            >>> Original(Path("a.hwp"), "text", Path("a.md"), "new").label
            'HWP'
        """
        return {**TEXT, **DATA}.get(self.path.suffix.lower(), self.path.suffix.lstrip(".").upper() or "?")


def kind_of(path: Path) -> str:
    """Tell what an original is: "text", "data" or "unknown".

    Args:
        path: The file.

    Returns:
        The kind, from its extension.

    Example:
        >>> [kind_of(Path(n)) for n in ("법.PDF", "목록.xlsx", "그림.png")]
        ['text', 'data', 'unknown']
    """
    s = path.suffix.lower()
    return "text" if s in TEXT else "data" if s in DATA else "unknown"


def read_header(text: str) -> dict[str, str]:
    r"""Read the header a converted copy starts with.

    Args:
        text: The copy's text.

    Returns:
        Its fields; {} when the text is not a converted copy.

    Example:
        >>> read_header('<!-- lantern:converted from="a.pdf" quality="ok" -->\n# a\n')["quality"]
        'ok'
    """
    m = HEADER.match(text)
    return dict(FIELD.findall(m.group(1))) if m else {}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def _file_sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()[:16]


def render(original: Path, copy: Copy) -> str:
    r"""Put a copy's header line above its body.

    Args:
        original: The original file.
        copy: The converted copy.

    Returns:
        The text to write next to the original.

    Example:
        >>> render(Path("없는.pdf"), Copy("# 없는\n", "pdftotext", "ok"))  # doctest: +SKIP
        '<!-- lantern:converted from="없는.pdf" … -->\n# 없는\n'
    """
    st = original.stat()
    fields = {
        "from": original.name,
        "size": str(st.st_size),
        "mtime": str(st.st_mtime_ns),
        "sha": _file_sha(original),
        "tool": copy.tool,
        "quality": copy.quality,
        "note": copy.note.replace('"', "'"),
        "body": _sha(copy.body.encode("utf-8")),
    }
    return "<!-- lantern:converted " + " ".join(f'{k}="{v}"' for k, v in fields.items() if v) + " -->\n" + copy.body


def _target(path: Path, taken: set[Path]) -> Path:
    """Where an original's copy goes: `이름.md` next to it, or `이름.pdf.md` when that name is taken."""
    plain = path.with_suffix(".md")
    if plain in taken or (plain.exists() and not read_header(plain.read_text(encoding="utf-8", errors="replace"))):
        return path.with_name(path.name + ".md")
    return plain


def originals(root: Path) -> list[Original]:
    """List the originals under a folder (or one file) and what state their copies are in.

    Hidden files and folders, `_` folders and Markdown files are left out. Duplicates (same size and
    hash) are found among the originals not converted yet; the first by path is the one converted.

    Args:
        root: A references folder, or one original.

    Returns:
        One entry per original, sorted by path.

    Example:
        >>> originals(Path("없는 폴더"))
        []
    """
    if root.is_file():
        files = [root]
    elif root.is_dir():
        files = [
            f
            for f in sorted(root.rglob("*"))
            if f.is_file() and not any(x.startswith((".", "_")) for x in f.relative_to(root).parts[:-1]) and not f.name.startswith(".")
        ]
    else:
        files = []
    files = [f for f in files if f.suffix.lower() != ".md"]
    out: list[Original] = []
    taken: set[Path] = set()
    for f in files:
        kind = kind_of(f)
        target = _target(f, taken)
        taken.add(target)
        if kind == "unknown":
            out.append(Original(f, kind, target, "unknown"))
            continue
        head = read_header(target.read_text(encoding="utf-8", errors="replace")) if target.exists() else {}
        st = f.stat()
        if head and head.get("size") == str(st.st_size) and (head.get("mtime") == str(st.st_mtime_ns) or head.get("sha") == _file_sha(f)):
            out.append(Original(f, kind, target, "done", quality=head.get("quality", "")))
        elif head:
            body = HEADER.sub("", target.read_text(encoding="utf-8", errors="replace"), count=1)
            edited = head.get("body") not in ("", None, _sha(body.encode("utf-8")))
            out.append(Original(f, kind, target, "edited" if edited else "changed", quality=head.get("quality", "")))
        else:
            out.append(Original(f, kind, target, "new"))
    # a new original with the same bytes as another (converted or earlier) one is a duplicate, converted once
    sizes: dict[int, int] = {}
    for o in out:
        if o.kind != "unknown":
            sizes[o.path.stat().st_size] = sizes.get(o.path.stat().st_size, 0) + 1
    first: dict[str, Path] = {}
    for o in sorted((o for o in out if sizes.get(o.path.stat().st_size, 0) > 1), key=lambda o: (o.state != "done", str(o.path))):
        first.setdefault(_file_sha(o.path), o.path)
    return [
        Original(o.path, o.kind, o.target, "same", same_as=first[sha])
        if o.state == "new" and sizes.get(o.path.stat().st_size, 0) > 1 and first.get(sha := _file_sha(o.path), o.path) != o.path
        else o
        for o in out
    ]


# ---- text originals


def _parts(lines: list[str], title: str) -> list[tuple[str, list[str]]]:
    """Cut headingless lines into parts of about PART_LINES lines, ending a part at a blank line when one is near."""
    out: list[tuple[str, list[str]]] = []
    i = 0
    while i < len(lines):
        end = min(i + PART_LINES, len(lines))
        if end < len(lines):
            blank = next((k for k in range(end, max(i + PART_LINES // 2, i + 1), -1) if not lines[k - 1].strip()), end)
            end = blank
        out.append((msg("{title} {n}", title=title, n=len(out) + 1), lines[i:end]))
        i = end
    return out


def _markdown(name: str, sections: list[tuple[str, list[str]]]) -> str:
    """Join titled sections under the document's own title."""
    out = [f"# {name}", ""]
    for title, lines in sections:
        body = "\n".join(lines).strip("\n")
        out += [f"## {title}", "", body, ""] if body else [f"## {title}", ""]
    return "\n".join(out).rstrip() + "\n"


def _letters(text: str) -> int:
    return sum(1 for c in text if not c.isspace())


def pdf_copy(path: Path) -> Copy:
    """Convert a PDF a page per section with `pdftotext`.

    Args:
        path: The PDF.

    Returns:
        The copy; "empty" when there is (almost) no text, "check" when most pages hold little.

    Raises:
        ConvertError: `pdftotext` is missing or fails.

    Example:
        >>> pdf_copy(Path("보고서.pdf")).quality  # doctest: +SKIP
        'ok'
    """
    tool = shutil.which("pdftotext")
    if not tool:
        raise ConvertError(msg("PDF needs pdftotext — install poppler (brew install poppler · apt install poppler-utils)"))
    run = subprocess.run([tool, "-enc", "UTF-8", "-layout", str(path), "-"], capture_output=True, timeout=600)
    if run.returncode != 0:
        raise ConvertError(msg("pdftotext could not read it: {error}", error=run.stderr.decode("utf-8", "replace").strip()[:200]))
    pages = [p.rstrip() for p in run.stdout.decode("utf-8", "replace").split("\f")]
    if pages and not pages[-1].strip():
        pages.pop()
    sections = [(msg("Page {n}", n=i + 1), [ln.rstrip() for ln in p.split("\n")]) for i, p in enumerate(pages)]
    return _rate(_markdown(path.stem, sections), "pdftotext", [p for p in pages])


def _rate(body: str, tool: str, pages: list[str], note: str = "") -> Copy:
    """Rate a copy from how many letters its pages hold."""
    letters = [_letters(p) for p in pages]
    if sum(letters) < 100:
        return Copy(body, tool, "empty", msg("almost no text — maybe a scanned image; put an OCR'd .md next to it instead"))
    sparse = sum(1 for n in letters if n < SPARSE)
    if pages and sparse * 2 > len(pages):
        return Copy(
            body, tool, "check", msg("{sparse} of {pages} pages hold little text (pictures or tables)", sparse=sparse, pages=len(pages))
        )
    return Copy(body, tool, "check" if note else "ok", note)


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def docx_copy(path: Path) -> Copy:
    """Convert a Word document, keeping its headings and tables.

    Args:
        path: The .docx file.

    Returns:
        The copy; headingless text is cut into parts and rated "check".

    Raises:
        ConvertError: It is not a readable .docx.

    Example:
        >>> docx_copy(Path("안내.docx")).tool  # doctest: +SKIP
        'docx'
    """
    try:
        with zipfile.ZipFile(path) as z:
            doc = ET.fromstring(z.read("word/document.xml"))
            styles = ET.fromstring(z.read("word/styles.xml")) if "word/styles.xml" in z.namelist() else None
    except (zipfile.BadZipFile, KeyError, ET.ParseError) as e:
        raise ConvertError(msg("not a readable Word file ({error}) — save it again as .docx or PDF", error=e)) from e
    names = {}
    for s in styles.iter(W + "style") if styles is not None else []:
        n = s.find(W + "name")
        names[s.get(W + "styleId")] = (n.get(W + "val") if n is not None else "") or ""

    def level(p: ET.Element) -> int:
        ps = p.find(f"{W}pPr/{W}pStyle")
        name = names.get(ps.get(W + "val"), ps.get(W + "val") or "") if ps is not None else ""
        m = re.match(r"(?i)(heading|제목)\s*(\d)", name.replace(" ", " "))
        return int(m.group(2)) if m else (1 if name.lower() == "title" else 0)

    def text(el: ET.Element) -> str:
        out = []
        for node in el.iter():
            if node.tag == W + "t":
                out.append(node.text or "")
            elif node.tag == W + "tab":
                out.append("\t")
            elif node.tag in (W + "br", W + "cr"):
                out.append("\n")
        return "".join(out).strip()

    lines: list[str] = []
    heads = 0
    body = doc.find(W + "body")
    for el in list(body) if body is not None else []:
        if el.tag == W + "p":
            t, lv = text(el), level(el)
            if lv and t:
                heads += 1
                lines += ["", "#" * min(lv + 1, 6) + " " + t.replace("\n", " "), ""]
            else:
                lines.append(t)
        elif el.tag == W + "tbl":
            rows = [[text(c).replace("\n", " ").replace("|", "/") for c in tr.iter(W + "tc")] for tr in el.iter(W + "tr")]
            if rows:
                width = max(len(r) for r in rows)
                rows = [r + [""] * (width - len(r)) for r in rows]
                lines += ["", "| " + " | ".join(rows[0]) + " |", "|" + "---|" * width, *("| " + " | ".join(r) + " |" for r in rows[1:]), ""]
    if heads:
        body_md = f"# {path.stem}\n\n" + re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip() + "\n"
        return _rate(body_md, "docx", [body_md])
    md = _markdown(path.stem, _parts(lines, msg("Part")))
    return _rate(md, "docx", [md], msg("no headings — cut into parts"))


A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


def pptx_copy(path: Path) -> Copy:
    """Convert a PowerPoint deck a slide per section.

    Args:
        path: The .pptx file.

    Returns:
        The copy.

    Raises:
        ConvertError: It is not a readable .pptx.

    Example:
        >>> pptx_copy(Path("발표.pptx")).tool  # doctest: +SKIP
        'pptx'
    """
    try:
        with zipfile.ZipFile(path) as z:
            names = sorted(
                (n for n in z.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)), key=lambda n: int(re.findall(r"\d+", n)[-1])
            )
            slides = [ET.fromstring(z.read(n)) for n in names]
    except (zipfile.BadZipFile, ET.ParseError) as e:
        raise ConvertError(msg("not a readable PowerPoint file ({error}) — save it again as .pptx or PDF", error=e)) from e
    pages = []
    for s in slides:
        paras = ["".join(t.text or "" for t in p.iter(A + "t")).strip() for p in s.iter(A + "p")]
        pages.append([p for p in paras if p])
    md = _markdown(path.stem, [(msg("Slide {n}", n=i + 1), p) for i, p in enumerate(pages)])
    return _rate(md, "pptx", ["\n".join(p) for p in pages] if len(pages) > 1 else [md])


def _cfb_streams(data: bytes) -> dict[str, bytes]:
    """Read the streams of an OLE compound file (the container of HWP 5.0) by their paths."""
    if data[:8] != bytes.fromhex("d0cf11e0a1b11ae1"):
        raise ConvertError(msg("not an HWP 5.0 file — save it again from Hangul as .hwpx, .docx or PDF"))
    ss = 1 << struct.unpack_from("<H", data, 0x1E)[0]
    mss = 1 << struct.unpack_from("<H", data, 0x20)[0]
    nfat, dir0 = struct.unpack_from("<I", data, 0x2C)[0], struct.unpack_from("<I", data, 0x30)[0]
    cutoff, minifat0, nminifat, difat0, ndifat = struct.unpack_from("<IIIII", data, 0x38)

    def sector(i: int) -> bytes:
        return data[(i + 1) * ss : (i + 2) * ss]

    difat = list(struct.unpack_from("<109I", data, 0x4C))
    d = difat0
    for _ in range(ndifat):
        b = sector(d)
        difat += struct.unpack_from(f"<{ss // 4 - 1}I", b)
        d = struct.unpack_from("<I", b, ss - 4)[0]
    fat: list[int] = []
    for i in difat[:nfat]:
        fat += struct.unpack(f"<{ss // 4}I", sector(i))

    def chain(start: int, table: list[int]) -> Iterator[int]:
        seen = 0
        while start < 0xFFFFFFFA and start < len(table) and seen <= len(table):
            yield start
            start, seen = table[start], seen + 1

    def big(start: int) -> bytes:
        return b"".join(sector(i) for i in chain(start, fat))

    raw_dir = big(dir0)
    entries = []
    for o in range(0, len(raw_dir) - 127, 128):
        e = raw_dir[o : o + 128]
        n = struct.unpack_from("<H", e, 0x40)[0]
        left, right, child = struct.unpack_from("<III", e, 0x44)
        start, size = struct.unpack_from("<II", e, 0x74)
        entries.append((e[: max(n - 2, 0)].decode("utf-16le", "replace"), e[0x42], left, right, child, start, size))
    if not entries:
        return {}
    mini = big(entries[0][5])
    minifat: list[int] = []
    for i in chain(minifat0, fat) if nminifat else []:
        minifat += struct.unpack(f"<{ss // 4}I", sector(i))
    out: dict[str, bytes] = {}

    def walk(i: int, prefix: str, depth: int = 0) -> None:
        if i >= len(entries) or depth > 64:
            return
        name, typ, left, right, child, start, size = entries[i]
        walk(left, prefix, depth + 1)
        walk(right, prefix, depth + 1)
        if typ == 2:
            raw = b"".join(mini[k * mss : (k + 1) * mss] for k in chain(start, minifat)) if size < cutoff else big(start)
            out[prefix + name] = raw[:size]
        elif typ == 1:
            walk(child, prefix + name + "/", depth + 1)

    walk(entries[0][4], "")
    return out


INLINE = {1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23}  # controls that take 8 characters


def _hwp_paragraphs(section: bytes) -> list[str]:
    """Read the paragraph texts (HWPTAG_PARA_TEXT records) of one decompressed HWP body section."""
    out = []
    o = 0
    while o + 4 <= len(section):
        h = struct.unpack_from("<I", section, o)[0]
        o += 4
        tag, size = h & 0x3FF, h >> 20
        if size == 0xFFF:
            size = struct.unpack_from("<I", section, o)[0]
            o += 4
        if tag == 67:
            text, k, t = bytearray(), 0, section[o : o + size]
            while k + 1 < len(t):
                c = struct.unpack_from("<H", t, k)[0]
                if c < 32:
                    text += {9: "\t", 10: "\n"}.get(c, "").encode("utf-16le")
                    k += 16 if c in INLINE else 2
                    continue
                text += t[k : k + 2]  # surrogate pairs stay together, so decode the whole run at once
                k += 2
            out.append(text.decode("utf-16le", "replace").rstrip())
        o += size
    return out


def hwp_copy(path: Path) -> Copy:
    """Convert an HWP 5.0 file: its text in parts (HWP keeps no heading levels; tables come out a cell per line).

    Args:
        path: The .hwp file.

    Returns:
        The copy, rated "check" at best.

    Raises:
        ConvertError: Not HWP 5.0, or locked (password or distribution copy).

    Example:
        >>> hwp_copy(Path("보고.hwp")).quality  # doctest: +SKIP
        'check'
    """
    streams = _cfb_streams(path.read_bytes())
    head = streams.get("FileHeader", b"")
    if len(head) < 40 or not head.startswith(b"HWP Document File"):
        raise ConvertError(msg("not an HWP 5.0 file — save it again from Hangul as .hwpx, .docx or PDF"))
    props = struct.unpack_from("<I", head, 36)[0]
    if props & 0b110:
        raise ConvertError(msg("a locked HWP (password or distribution copy) — open it in Hangul and save it as .hwpx, .docx or PDF"))
    names = sorted((n for n in streams if re.fullmatch(r"BodyText/Section\d+", n)), key=lambda n: int(n[16:]))
    paras: list[str] = []
    for n in names:
        raw = streams[n]
        try:
            raw = zlib.decompress(raw, -15) if props & 1 else raw
        except zlib.error as e:
            raise ConvertError(msg("the HWP body could not be read ({error})", error=e)) from e
        paras += _hwp_paragraphs(raw)
    lines = "\n".join(paras).split("\n")
    md = _markdown(path.stem, _parts(lines, msg("Part")))
    return _rate(md, "hwp", [md], msg("no headings and no table layout (cells one per line) — cut into parts"))


def hwpx_copy(path: Path) -> Copy:
    """Convert an HWPX file (zipped XML): its text in parts.

    Args:
        path: The .hwpx file.

    Returns:
        The copy, rated "check" at best.

    Raises:
        ConvertError: It is not a readable .hwpx.

    Example:
        >>> hwpx_copy(Path("보고.hwpx")).tool  # doctest: +SKIP
        'hwpx'
    """
    try:
        with zipfile.ZipFile(path) as z:
            names = sorted(
                (n for n in z.namelist() if re.fullmatch(r"Contents/section\d+\.xml", n)), key=lambda n: int(re.findall(r"\d+", n)[-1])
            )
            roots = [ET.fromstring(z.read(n)) for n in names]
    except (zipfile.BadZipFile, ET.ParseError) as e:
        raise ConvertError(msg("not a readable HWPX file ({error}) — save it again from Hangul as .docx or PDF", error=e)) from e
    lines = []
    for r in roots:
        for p in r.iter():
            if p.tag.endswith("}p"):
                lines.append("".join(t.text or "" for t in p.iter() if t.tag.endswith("}t") and t is not p).rstrip())
    md = _markdown(path.stem, _parts(lines, msg("Part")))
    return _rate(md, "hwpx", [md], msg("no headings and no table layout (cells one per line) — cut into parts"))


# ---- data originals

S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
SAMPLE_ROWS = 3
MAX_COLUMNS = 30
CELL = 40


def _cell_text(value: str) -> str:
    v = value.replace("\n", " ").replace("|", "/").strip()
    return v if len(v) <= CELL else v[: CELL - 1] + "…"


def _table(rows: list[list[str]]) -> list[str]:
    if not rows:
        return []
    width = min(max(len(r) for r in rows), MAX_COLUMNS)
    rows = [[_cell_text(c) for c in (r + [""] * width)[:width]] for r in rows]
    return ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * width, *("| " + " | ".join(r) + " |" for r in rows[1:])]


def _col(ref: str) -> int:
    n = 0
    for ch in re.match(r"[A-Z]*", ref).group(0):  # pyright: ignore[reportOptionalMemberAccess]  # the pattern always matches
        n = n * 26 + ord(ch) - 64
    return max(n - 1, 0)


def _sheet_head(z: zipfile.ZipFile, name: str) -> tuple[list[list[tuple[str, str]]], int, int]:
    """Read a sheet's first rows (cell type, raw value) without loading it, plus its row and column counts."""
    rows: list[list[tuple[str, str]]] = []
    count, width = 0, 0
    dim = ""
    with z.open(name) as f:
        for _, el in ET.iterparse(f, events=("end",)):
            if el.tag == S + "dimension":
                dim = el.get("ref", "")
            elif el.tag == S + "row":
                count += 1
                if len(rows) <= SAMPLE_ROWS:
                    row: list[tuple[str, str]] = []
                    for c in el.iter(S + "c"):
                        i = _col(c.get("r", ""))
                        row += [("", "")] * (i - len(row))
                        v = c.find(S + "v")
                        t = c.find(f"{S}is/{S}t")
                        row.append((c.get("t", ""), (t.text if t is not None else v.text if v is not None else "") or ""))
                    rows.append(row)
                width = max(width, len(list(el.iter(S + "c"))))
                el.clear()
    m = re.match(r"[A-Z]+\d+:([A-Z]+)\d+", dim)
    return rows, count, max(width, _col(m.group(1)) + 1 if m else 0)


def xlsx_card(path: Path) -> Copy:
    """Describe a spreadsheet as a card: each sheet's row and column counts, header and first rows.

    The sheets are streamed, so a 200MB file is never loaded whole; shared strings are read only as far
    as the sample needs.

    Args:
        path: The .xlsx file.

    Returns:
        The card.

    Raises:
        ConvertError: It is not a readable .xlsx.

    Example:
        >>> xlsx_card(Path("목록.xlsx")).tool  # doctest: +SKIP
        'xlsx'
    """
    try:
        z = zipfile.ZipFile(path)
    except zipfile.BadZipFile as e:
        raise ConvertError(msg("not a readable Excel file ({error}) — save it again as .xlsx or .csv", error=e)) from e
    with z:
        try:
            book = ET.fromstring(z.read("xl/workbook.xml"))
            rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        except (KeyError, ET.ParseError) as e:
            raise ConvertError(msg("not a readable Excel file ({error}) — save it again as .xlsx or .csv", error=e)) from e
        target = {r.get("Id"): r.get("Target", "") for r in rels}
        sheets = []
        for s in book.iter(S + "sheet"):
            t = target.get(s.get(R + "id"), "")
            sheets.append((s.get("name", ""), "xl/" + t.lstrip("/").removeprefix("xl/")))
        heads = [(name, *_sheet_head(z, file)) for name, file in sheets if file in z.namelist()]
        need = {int(v) for _, rows, _, _ in heads for r in rows for t, v in r if t == "s" and v.isdigit()}
        shared: dict[int, str] = {}
        if need and "xl/sharedStrings.xml" in z.namelist():
            with z.open("xl/sharedStrings.xml") as f:
                i = 0
                for _, el in ET.iterparse(f, events=("end",)):
                    if el.tag == S + "si":
                        if i in need:
                            shared[i] = "".join(t.text or "" for t in el.iter(S + "t"))
                        i += 1
                        el.clear()
                        if i > max(need):
                            break
    lines = [
        f"# {path.stem}",
        "",
        msg("> Data file — its values stay in {name}; read them from code, not from this card.", name=path.name),
        "",
    ]
    seen: dict[tuple[str, ...], str] = {}
    for name, rows, count, width in heads:
        table = [[shared.get(int(v), "") if t == "s" and v.isdigit() else v for t, v in r] for r in rows]
        size = msg("{rows} rows · {columns} columns", rows=f"{count:,}", columns=width)
        header = tuple(table[0]) if table and any(c.strip() for c in table[0]) else ()
        if header in seen:  # sheets split by category share their columns — show them once
            lines += [f"## {name}", "", size + " — " + msg("same columns as '{sheet}'", sheet=seen[header]), ""]
            continue
        if header:
            seen[header] = name
        lines += [f"## {name}", "", size, "", *_table(table), ""]
    return Copy("\n".join(lines).rstrip() + "\n", "xlsx", "ok")


def csv_card(path: Path) -> Copy:
    """Describe a CSV file as a card: its row count, header and first rows.

    Args:
        path: The .csv file.

    Returns:
        The card.

    Example:
        >>> csv_card(Path("목록.csv")).tool  # doctest: +SKIP
        'csv'
    """
    rows: list[list[str]] = []
    count = 0
    with path.open(encoding="utf-8-sig", errors="replace", newline="") as f:
        for row in csv.reader(f):
            count += 1
            if len(rows) <= SAMPLE_ROWS:
                rows.append(row)
    width = max((len(r) for r in rows), default=0)
    lines = [
        f"# {path.stem}",
        "",
        msg("> Data file — its values stay in {name}; read them from code, not from this card.", name=path.name),
        "",
    ]
    lines += [msg("{rows} rows · {columns} columns", rows=f"{count:,}", columns=width), "", *_table(rows)]
    return Copy("\n".join(lines).rstrip() + "\n", "csv", "ok")


CONVERTERS = {
    ".pdf": pdf_copy,
    ".docx": docx_copy,
    ".pptx": pptx_copy,
    ".hwp": hwp_copy,
    ".hwpx": hwpx_copy,
    ".xlsx": xlsx_card,
    ".csv": csv_card,
}


def convert(original: Original) -> Copy:
    """Convert one original and write its copy next to it.

    Args:
        original: A "new" or "changed" original.

    Returns:
        The copy written.

    Raises:
        ConvertError: It can't be converted here; nothing is written.

    Example:
        >>> convert(originals(Path("docs/📚 도메인 지식"))[0]).quality  # doctest: +SKIP
        'ok'
    """
    fn = CONVERTERS.get(original.path.suffix.lower())
    if fn is None:
        raise ConvertError(msg("this format can't be read — save it as PDF, DOCX or XLSX"))
    copy = fn(original.path)
    original.target.write_text(render(original.path, copy), encoding="utf-8")
    return copy


MANY = 40  # past this many sections (a long report a page per section), the preview shows one line each


def preview(text: str, lines: int | None = None, width: int = 100) -> str:
    r"""Show a document as its sections' addresses, sizes and first lines — enough to say what each is about.

    Args:
        text: The document.
        lines: How many lines of each section to show; by default 3, or 1 past MANY sections.
        width: How long a shown line may be.

    Returns:
        One block per section: its address and line count, then its first non-empty lines, indented.

    Example:
        >>> print(preview("# 법\n## 보관\n지원자 정보는 1년 둔다.\n그 뒤 지운다.\n## 파기\n바로 지운다.\n", lines=1))
        보관  (3)
          지원자 정보는 1년 둔다.
        파기  (3)
          바로 지운다.
    """
    text = HEADER.sub("", text, count=1)
    all_lines = text.split("\n")
    sections = outline.sections(text)
    if lines is None:
        lines = 3 if len(sections) <= MANY else 1
    out = []
    for s in sections:
        first = [ln.strip() for ln in all_lines[s.start + 1 : s.own_end] if ln.strip() and not ln.lstrip().startswith(("|---", "<!--"))]
        if not s.titles or (not first and s.own_end < s.end):
            continue  # a heading that only holds sub-sections
        out.append(f"{s.address}  ({s.end - s.start})")
        out += ["  " + (ln if len(ln) <= width else ln[: width - 1] + "…") for ln in first[:lines]]
    return "\n".join(out)
