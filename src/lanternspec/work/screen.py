"""화면 시안 (DE-01 · PL-04): bring mockups in as files, and compare a capture with its mockup.

* `import`  — images · HTML · PDF, or a handoff bundle (zip / folder) → `2. 작업/W-012 …/화면/`
* `compare` — PNG capture vs PNG mockup → similarity %. Automatic comparison is a *hint*;
  the person still answers "시안과 같나요?" before the criterion is ticked.
"""

from __future__ import annotations

import shutil
import struct
import zipfile
import zlib
from pathlib import Path

from ..core.project import Project, nfc
from .epic_rules import MOCKUP_EXT

BUNDLE_EXT = MOCKUP_EXT | {".css", ".js", ".json", ".md", ".woff", ".woff2", ".ttf"}


def import_files(project: Project, work_id: str, sources: list[Path]) -> list[str]:
    folder = project.find_work(work_id, include_archive=False)
    if folder is None:
        raise ValueError(f"진행 중인 작업 {work_id}를 찾지 못했습니다")
    dest = folder / "화면"
    dest.mkdir(exist_ok=True)
    out: list[str] = []
    for src in sources:
        if not src.exists():
            raise FileNotFoundError(f"없습니다: {src}")
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
                raise ValueError(f"시안으로 받는 형식이 아닙니다: {src.name} (이미지 · HTML · PDF · zip)")
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
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"PNG가 아닙니다: {path.name} (자동 비교는 PNG 캡처끼리만)")
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
        raise ValueError(f"지원하지 않는 PNG 형식입니다: {path.name} (8비트 · 비인터레이스만)")
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
    """Similarity (0~100) on a 32×32 colour grid, plus where the biggest differences are."""
    a, b = _grid(capture), _grid(mockup)
    diffs = [sum(abs(x - y) for x, y in zip(ca, cb, strict=True)) / (3 * 255) for ca, cb in zip(a, b, strict=True)]
    score = round(100 * (1 - sum(diffs) / len(diffs)), 1)
    regions = {"위": range(0, 11), "가운데": range(11, 21), "아래": range(21, 32)}
    hot = []
    for name, ys in regions.items():
        for side, xs in (("왼쪽", range(0, 11)), ("가운데", range(11, 21)), ("오른쪽", range(21, 32))):
            cell = [diffs[y * 32 + x] for y in ys for x in xs]
            avg = sum(cell) / len(cell)
            if avg > 0.12:
                hot.append(f"{name} {side} ({round(avg * 100)}% 다름)")
    return score, hot
