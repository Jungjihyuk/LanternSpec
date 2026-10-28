---
name: l-adr
description: 결정 기록(ADR) — 되돌리기 어려운 결정(DB · 프레임워크 · 인증 방식 · 외부 서비스 · 데이터 구조 변경 · 공개 API 변경 · 방향을 바꾼 결정)을 배경 · 검토한 선택지(장단점) · 결정 · 결과/영향 · 상태로 3. 현재 상태/규칙 · 결정 기록/ADR-NNN 에 남긴다. Use when an important, hard-to-reverse decision is made, or /l-design · /l-build · /l-sync hit one.
invocation: model
argument-hint: "<결정할 일> [--work W-NNN]"
---

# /l-adr — 결정 기록

**목적:** "6개월 뒤 '왜 이렇게 했지?'"에 답할 기록을 남긴다.

## 남길까?
- **남김:** 바꾸기 어려운 도구 선택(DB · 프레임워크 · 인증 방식 · 외부 서비스) · 데이터 구조 변경 · 공개 API 변경 · 방향을 바꾼 결정(`/l-sync`에서 의도 변경)
- **안 남김:** 작은 라이브러리(작업 `기록.md`에 한 줄) · 코드 정리
- AI는 **제안만** 하고 남길지는 사람이 정한다. 단 **데이터 구조 변경은 항상** 남긴다.

## 처리 순서
1. 만들기:
   ```bash
   lantern scaffold adr "<결정할 일>" [--work W-012]
   ```
2. 채우기: 한눈에 보기(결정 한 줄) · 배경(무엇을 정해야 했고 왜 지금인가) · 검토한 선택지(선택지마다 장단점 — 고르지 않은 것도 지우지 않음) · 결정(무엇을, 결정적 이유, 누가 · 언제) · 결과 · 영향(쉬워지는 것 · 어려워지는 것 · 바뀌는 문서).
3. 상태: 처음은 `<<adr_status.proposed>>`. 사람이 정하면 `lantern meta set "<ADR 파일>" status="<<adr_status.accepted>>"`.
   이전 결정을 뒤집으면 옛 ADR을 `lantern meta set "<옛 ADR>" status="<<adr_status.superseded>>" superseded_by=ADR-NNN`.
4. 잇기: 작업 `기록.md`의 `## 결정 · 실패한 시도`에 `[[ADR-NNN …]]` 링크, 설계에서 나왔으면 `설계.md` frontmatter `adr`에 ID 추가.

## 공통 마무리
```bash
lantern close l-adr [--work W-012]
```
