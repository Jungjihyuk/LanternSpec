"""지식 연결기 — the same four questions for any knowledge store (LE-05).

| 계약     | 질문                               | 돌려주는 것                      |
| search   | 이 용어에 관한 노트가 있나?        | 제목 · 위치 · 요약 · 수정일 목록 |
| read     | 이 노트 내용은?                    | 본문                             |
| propose  | 이 주제로 노트를 만들어도 되나?    | 초안 (승인 대기)                 |
| write    | (승인 후) 노트를 만들어 줘         | 만들어진 위치 (쓰기 막힌 저장소는 거절) |

The contract (names · inputs · outputs) is fixed now; v1 ships it as `lantern knowledge …`
CLI commands, an MCP server can wrap the same functions later.
We never change the other store's structure (P6): counts and status live in our ledger.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from ...core.project import Project


@dataclass
class Hit:
    title: str
    path: str  # relative to the store root
    summary: str
    updated: str
    score: int

    def to_dict(self) -> dict:
        return asdict(self)


class Adapter:
    name = "base"

    def search(self, query: str, aliases: list[str] | None = None, limit: int = 5) -> list[Hit]:
        raise NotImplementedError

    def read(self, path: str) -> str:
        raise NotImplementedError

    def write(self, rel_path: str, content: str) -> str:
        raise NotImplementedError

    def areas(self, folder: str) -> list[str]:
        return []


class KnowledgeError(RuntimeError):
    pass


def adapter_for(project: Project) -> Adapter:
    k = project.profile.knowledge
    if not k:
        raise KnowledgeError("지식 저장소가 설정되지 않았습니다 (lantern.yaml의 knowledge 블록)")
    kind = k["type"]
    if kind in ("obsidian", "folder"):  # folder = 아무 Markdown 폴더 (기타 저장소)
        from .obsidian import ObsidianAdapter

        return ObsidianAdapter(Path(str(k["path"])).expanduser())
    if kind == "notion":
        from .notion import from_config

        return from_config(k)
    raise KnowledgeError(f"'{kind}' 어댑터가 없습니다 (가능: obsidian · folder · notion)")
