"""Screen mockups: bring mockups in as files, and compare a capture with its mockup.

* `import`  — images · HTML · PDF, or a handoff bundle (zip / folder) → `2. 작업/W-012 …/화면/`
* `compare` — PNG capture vs PNG mockup → similarity %. Automatic comparison is a *hint*;
  the person still answers "does it match the mockup?" before the criterion is ticked.

PNG files are decoded with the standard library only, so no image package is needed.
"""

from __future__ import annotations

import shutil
import struct
import zipfile
import zlib
from pathlib import Path

from ..core.messages import msg
from ..core.project import Project, nfc
from .epic_rules import MOCKUP_EXT

BUNDLE_EXT = MOCKUP_EXT | {".css", ".js", ".json", ".md", ".woff", ".woff2", ".ttf"}


def import_files(project: Project, work_id: str, sources: list[Path]) -> list[str]:
    """Copy mockups into a work's `화면/` folder.

    Zip bundles are unpacked into a folder of their own (unsafe paths and other file types skipped);
    folders are copied with only web and image files.

    Args:
        project: The project.
        work_id: A work in progress, e.g. "W-012".
        sources: Image, HTML or PDF files, zip bundles or folders.

    Returns:
        Where each source landed, relative to the project root (folders end with "/").

    Raises:
        ValueError: The work is not in progress, or a file is not a mockup type.
        FileNotFoundError: A source does not exist.

    Example:
        >>> import_files(project, "W-012", [Path("~/Downloads/login.png")])  # doctest: +SKIP
        ['docs/2. 작업/W-012 로그인/화면/login.png']
    """
    folder = project.find_work(work_id, include_archive=False)
    if folder is None:
        raise ValueError(msg("Work in progress {work_id} not found", work_id=work_id))
    dest = folder / project.names.folder("screens")
    dest.mkdir(exist_ok=True)
    out: list[str] = []
    for src in sources:
        if not src.exists():
            raise FileNotFoundError(msg("Not found: {src}", src=src))
        if src.suffix.lower() == ".zip":
            target = dest / src.stem
            with zipfile.ZipFile(src) as z:
                for info in z.infolist():
                    name = Path(info.filename)
                    if info.is_dir() or name.is_absolute() or ".." in name.parts or name.parts[0] == "__MACOSX":
                        continue
                    if name.suffix.lower() not in BUNDLE_EXT:
                        continue
                    p = target / name
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_bytes(z.read(info))
            out.append(project.rel(target) + "/")
        elif src.is_dir():
            target = dest / src.name
            shutil.copytree(
                src,
                target,
                dirs_exist_ok=True,
                ignore=lambda d, names: [n for n in names if (Path(d) / n).is_file() and Path(n).suffix.lower() not in BUNDLE_EXT],
            )
            out.append(project.rel(target) + "/")
        else:
            if src.suffix.lower() not in MOCKUP_EXT:
                raise ValueError(msg("Not a mockup format: {name} (image · HTML · PDF · zip)", name=src.name))
            target = dest / nfc(src.name)
            shutil.copy2(src, target)
            out.append(project.rel(target))
    return out


# --------------------------------------------------------------------------- PNG → pixels (stdlib only)


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def read_png(path: Path) -> tuple[int, int, list[tuple[int, int, int]]]:
    """Decode an 8-bit, non-interlaced PNG into RGB pixels.

    Args:
        path: The PNG file.

    Returns:
        (width, height, pixels) with pixels in row order; grey and palette images become RGB.

    Raises:
        ValueError: The file is not a PNG, or uses a bit depth or interlacing this reader does not support.

    Example:
        >>> width, height, pixels = read_png(Path("capture.png"))  # doctest: +SKIP
        >>> pixels[0]  # doctest: +SKIP
        (255, 255, 255)
    """
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(msg("Not a PNG: {name} (automatic comparison works only between PNG captures)", name=path.name))
    pos, idat, palette = 8, b"", b""
    width = height = depth = color = interlace = 0
    while pos < len(data):
        length, kind = struct.unpack(">I4s", data[pos : pos + 8])
        chunk = data[pos + 8 : pos + 8 + length]
        if kind == b"IHDR":
            width, height, depth, color, _, _, interlace = struct.unpack(">IIBBBBB", chunk)
        elif kind == b"PLTE":
            palette = chunk
        elif kind == b"IDAT":
            idat += chunk
        elif kind == b"IEND":
            break
        pos += 12 + length
    if depth != 8 or interlace or color not in (0, 2, 3, 4, 6):
        raise ValueError(msg("Unsupported PNG format: {name} (8-bit · non-interlaced only)", name=path.name))
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color]
    raw = zlib.decompress(idat)
    stride = width * channels
    rows: list[bytearray] = []
    prev = bytearray(stride)
    i = 0
    for _ in range(height):
        ftype = raw[i]
        line = bytearray(raw[i + 1 : i + 1 + stride])
        i += 1 + stride
        for x in range(stride):
            a = line[x - channels] if x >= channels else 0
            b = prev[x]
            c = prev[x - channels] if x >= channels else 0
            if ftype == 1:
                line[x] = (line[x] + a) & 0xFF
            elif ftype == 2:
                line[x] = (line[x] + b) & 0xFF
            elif ftype == 3:
                line[x] = (line[x] + ((a + b) >> 1)) & 0xFF
            elif ftype == 4:
                line[x] = (line[x] + _paeth(a, b, c)) & 0xFF
        rows.append(line)
        prev = line
    pixels: list[tuple[int, int, int]] = []
    for line in rows:
        for x in range(width):
            px = line[x * channels : (x + 1) * channels]
            if color == 0 or color == 4:
                pixels.append((px[0], px[0], px[0]))
            elif color == 3:
                j = px[0] * 3
                pixels.append((palette[j], palette[j + 1], palette[j + 2]))
            else:
                pixels.append((px[0], px[1], px[2]))
    return width, height, pixels


def _grid(path: Path, n: int = 32) -> list[tuple[float, float, float]]:
    w, h, px = read_png(path)
    cells = []
    for gy in range(n):
        for gx in range(n):
            x0, x1 = gx * w // n, max(gx * w // n + 1, (gx + 1) * w // n)
            y0, y1 = gy * h // n, max(gy * h // n + 1, (gy + 1) * h // n)
            acc = [0, 0, 0]
            count = 0
            for y in range(y0, min(y1, h), max(1, (y1 - y0) // 4)):
                for x in range(x0, min(x1, w), max(1, (x1 - x0) // 4)):
                    r, g, b = px[y * w + x]
                    acc[0] += r
                    acc[1] += g
                    acc[2] += b
                    count += 1
            cells.append(tuple(v / max(count, 1) for v in acc))  # type: ignore[arg-type]
    return cells


def compare(capture: Path, mockup: Path) -> tuple[float, list[str]]:
    """Compare a capture with its mockup on a 32×32 colour grid.

    Args:
        capture: PNG capture of the built screen.
        mockup: PNG mockup.

    Returns:
        The similarity (0–100) and the regions (of a 3×3 split) that differ by more than 12%.

    Raises:
        ValueError: Either file is not a supported PNG.

    Example:
        >>> compare(Path("capture.png"), Path("화면/로그인.png"))  # doctest: +SKIP
        (91.4, ['아래 가운데 (18% 다름)'])
    """
    a, b = _grid(capture), _grid(mockup)
    diffs = [sum(abs(x - y) for x, y in zip(ca, cb, strict=True)) / (3 * 255) for ca, cb in zip(a, b, strict=True)]
    score = round(100 * (1 - sum(diffs) / len(diffs)), 1)
    regions = {msg("top"): range(0, 11), msg("middle"): range(11, 21), msg("bottom"): range(21, 32)}
    hot = []
    for name, ys in regions.items():
        for side, xs in ((msg("left"), range(0, 11)), (msg("middle"), range(11, 21)), (msg("right"), range(21, 32))):
            cell = [diffs[y * 32 + x] for y in ys for x in xs]
            avg = sum(cell) / len(cell)
            if avg > 0.12:
                hot.append(msg("{name} {side} ({round}% different)", name=name, side=side, round=round(avg * 100)))
    return score, hot
