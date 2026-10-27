"""MY_BRAIN (llm-wiki) adapter — searches the vault's card index, writes only proposals (그림 5).

MY_BRAIN keeps `.my-wiki/document_cards.jsonl` (faster and more accurate than a full-text scan)
and its own write rules: a model may read and propose; promotion into 0~5 folders goes through
the vault's dispatcher with the owner's approval. So `write` drops the note into
`.my-wiki/workspace/lanternspec/` and says how to promote it — it never touches the 0~5 folders.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...core.project import nfc
from . import Hit, KnowledgeError
from .obsidian import ObsidianAdapter, _norm

CARDS = ".my-wiki/document_cards.jsonl"
WORKSPACE = ".my-wiki/workspace/lanternspec"


class MyBrainAdapter(ObsidianAdapter):
    name = "my_brain"
    proposal_only = True

    def _cards(self) -> list[dict[str, Any]] | None:
        p = self.root / CARDS
        if not p.exists():
            return None
        out = []
        for line in p.read_text(encoding="utf-8").splitlines():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out

    def search(self, query: str, aliases: list[str] | None = None, limit: int = 5) -> list[Hit]:
        cards = self._cards()
        if cards is None:  # no index yet — fall back to reading files
            return super().search(query, aliases, limit)
        terms = [t for t in [query, *(aliases or [])] if t and t.strip()]
        nterms = [_norm(t) for t in terms]
        lterms = [nfc(t).lower() for t in terms]
        hits: list[Hit] = []
        for c in cards:
            if str(c.get("path", "")).startswith("4. Work/"):
                continue  # MY_BRAIN: 4. Work is read-only and possibly sensitive — keep it out of suggestions
            title = nfc(str(c.get("title") or Path(str(c.get("path", ""))).stem))
            ntitle = _norm(title)
            props = c.get("properties") or {}
            aliases_c = [str(a) for a in (props.get("aliases") or [])] if isinstance(props, dict) else []
            score = 0
            for nt in nterms:
                if not nt:
                    continue
                if ntitle == nt:
                    score += 100
                elif nt in ntitle:
                    score += 40
                if any(_norm(a) == nt for a in aliases_c):
                    score += 80
            hay = " ".join(
                [str(c.get("summary") or ""), " ".join(map(str, c.get("headings") or [])), " ".join(map(str, c.get("tags") or []))]
            ).lower()
            score += sum(10 for lt in lterms if lt and lt in hay)
            if score:
                hits.append(
                    Hit(
                        title=title,
                        path=nfc(str(c.get("path"))),
                        summary=str(c.get("summary") or "")[:200],
                        updated=str(c.get("updated_at") or ""),
                        score=score,
                    )
                )
        hits.sort(key=lambda h: (-h.score, h.path))
        return hits[:limit]

    def write(self, rel_path: str, content: str) -> str:
        name = Path(rel_path).name
        target = self.root / WORKSPACE / name
        if target.exists():
            raise KnowledgeError(f"이미 같은 제안이 있습니다: {WORKSPACE}/{name}")
        target.parent.mkdir(parents=True, exist_ok=True)
        meta = f"<!-- lanternspec 제안 · 원하는 위치: {rel_path} · 승격은 MY_BRAIN 규칙대로 (brain-add) -->\n"
        target.write_text(meta + content, encoding="utf-8")
        return nfc(f"{WORKSPACE}/{name}")
