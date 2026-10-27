---
name: l-report
description: 원하는 보기로 현황 확인 — 작업 폴더 · 현재 상태 · 부채 장부를 읽어 칸반 · 타임라인(Mermaid gantt) · 도메인별 · 추적(아이디어→작업→커밋) · 부채 현황 · 문서-코드 일치를 4. 운영 기록/보고/현황.md에 만들고, 맨 위에 팀장 보고 3줄을 쓴다. Use when the user asks for status, progress, a kanban, a timeline or a report.
invocation: model
argument-hint: "[kanban,timeline,domain,trace,debt,sync]"
---

# /l-report — 원하는 보기로 현황 확인

**목적:** 문서를 **읽어서** 한 화면에 보여 준다. 표와 Mermaid는 스크립트가 글자로 만들고, 너는 **팀장 보고 3줄만** 쓴다.

입력: `$ARGUMENTS` — 보고 싶은 보기. 없으면 프로필 기본값(<<report.views>>).

| 보기 | 이름 |
|---|---|
| 🗂 칸반 | `kanban` |
| 📅 타임라인 (WBS) | `timeline` |
| 🧩 도메인 · 요구사항별 | `domain` |
| 🔗 추적 (아이디어 → 작업 → 커밋) | `trace` |
| 📒 부채 현황 | `debt` |
| 🔄 문서-코드 일치 | `sync` |
| 📊 AI 작업 평가 (어떤 구성이 결과에 도움이 됐나) | `eval` |

## 처리 순서
1. 보기를 만든다:
   ```bash
   lantern report [--views kanban,timeline,sync]
   ```
2. 만들어진 `docs/4. 운영 기록/보고/현황.md`를 읽는다 — 특히 "한눈에 보기"와 "지난 보고와 비교".
3. **팀장 보고 3줄**을 쓴다 (사실만, 숫자로):
   1. 진척 — 끝낸 것 · 진행 중 (예: "W-012 카카오 로그인 할 일 5/7, 지난 보고 대비 +3")
   2. 위험 · 막힌 것 — 설계 승인 대기 · ❓ 확인 필요 · 문서-코드 어긋남
   3. 배움 · 다음 — 새 부채 · 해결한 부채 · 다음에 할 일
   ```bash
   lantern report --views <같은 보기> --summary "<1줄>" "<2줄>" "<3줄>"
   ```
   (같은 날 다시 만들면 그날의 지난 보고를 덮어쓴다.)
4. 사용자에게 3줄과 파일 위치를 보여 준다. 표 전체를 대화에 붙이지 않는다.
5. `eval` 보기를 만들었다면 한 줄 더: 실행 기록에서 보이는 것 (예: "설계 승인 required일 때 오류 없이 끝낸 비율이 높다") + `lantern harness suggest`가 추천하는 작업 방식이 지금 설정과 다르면 알려 준다.

## 공통 마무리
```bash
lantern close l-report --no-check
```
