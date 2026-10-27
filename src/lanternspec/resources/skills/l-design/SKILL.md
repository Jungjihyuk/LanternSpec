---
name: l-design
description: 어떻게 만들지 설계 — 작업(W-NNN)에서 바뀌는 부분만 구조(Mermaid) · 화면(Claude Design 시안 파일) · 데이터(DBML 변경분 + 마이그레이션 계획)로 설계.md에 쓰고, 되돌리기 어려운 선택은 결정 기록(ADR)으로 넘기고, 사람 승인(설계 게이트)을 받는다. Use after /l-plan when a work needs a design.
invocation: model
argument-hint: "W-NNN"
---

# /l-design — 어떻게 만들지 (구조 · 화면 · 데이터)

**목적:** 이번 작업에서 **바뀌는 부분만** 설계한다. 지금 시스템 전체를 다시 쓰지 않는다.

입력: `$ARGUMENTS` — `W-012`.

## 0. 시작 전
- `기획.md`를 읽는다. **`❓ 확인 필요`가 남아 있으면 먼저 묻는다** (최대 <<plan.max_questions>>개, 영향 큰 순).
- 현재 상태에서 관련된 부분만 읽는다: `3. 현재 상태/시스템 구조.md` · `화면/` · `데이터/schema.dbml`.

## 1. 설계.md 만들기 · 칸 고르기
```bash
lantern scaffold doc W-012 설계
```
세 칸 중 **이번 작업에 필요한 칸만** 남긴다 (예: 화면만, 데이터만). 고른 칸을 frontmatter `parts`에 적는다 (예: `[구조, 데이터]`). 쓰지 않는 칸은 섹션째 지운다. "한눈에 보기"와 "되돌리기 어려운 선택"은 지우지 않는다.

## 2. 🏗 구조
바뀌는 부품과 흐름을 Mermaid로 그린다. 글은 그림을 설명한다. 코드 위치는 `` `src/…` `` 처럼 백틱으로 적는다 (동시 작업 충돌 경고에 쓰인다).

## 3. 🎨 화면
<!-- lantern:if design.tool=claude-design -->
Claude Design으로 시안을 만든다 → **파일로** `2. 작업/W-012 …/화면/`에 저장한다: HTML 내보내기(권장 — AI가 직접 읽고 git에 남음) 또는 이미지. Claude Code로 넘기기(handoff) 묶음(zip · 폴더)을 받으면 `lantern screen import W-012 <묶음>`으로 `화면/` 아래에 푼다.
<!-- lantern:endif -->
<!-- lantern:if design.tool=figma -->
Figma MCP 서버(Dev Mode MCP)로 해당 프레임을 읽는다 → 프레임을 **이미지로 내보내** `2. 작업/W-012 …/화면/`에 저장한다 (`lantern screen import W-012 <파일 · 폴더>`). 구현에 필요한 값(색 · 간격 · 컴포넌트 이름)은 MCP가 준 것을 설계서 표에 옮긴다. Figma 링크만 적고 끝내지 않는다 — 팀원과 AI가 열 수 있는 **파일**이 원본이다.
<!-- lantern:endif -->
<!-- lantern:if design.tool=canva -->
Canva MCP 서버로 디자인을 찾아 **PNG 또는 PDF로 내보내** `2. 작업/W-012 …/화면/`에 저장한다 (`lantern screen import W-012 <파일 · 폴더>`). 공유 링크만 적고 끝내지 않는다.
<!-- lantern:endif -->
<!-- lantern:if design.tool=none -->
시안은 와이어프레임 · 레퍼런스 이미지 · HTML 파일로 `2. 작업/W-012 …/화면/`에 둔다.
<!-- lantern:endif -->
**공유 링크는 받지 않는다** (조직 밖에서 안 열릴 수 있음). **그림이 원본**이고 설계서 글은 그림을 설명한다. 표에 화면 · 시안 파일 · 설명을 적는다.

## 4. 🗄 데이터
- 현재 ERD(`3. 현재 상태/데이터/schema.dbml`) 대비 **변경분**만 ```` ```dbml ```` 블록에 쓴다 (바뀌는 테이블은 완성된 정의로).
- 변경 표(추가 · 변경 · 삭제)와 **마이그레이션 계획**을 쓴다.
- 검사: `lantern check-dbml "docs/2. 작업/W-012 …/설계.md"` (현재 schema.dbml과 합쳐서 참조를 확인한다)
- 서버 없는 앱의 기기 저장소도 같은 DBML로 쓴다.

## 5. 되돌리기 어려운 선택 → /l-adr (AD-01)
**남김:** 바꾸기 어려운 도구 선택(DB · 프레임워크 · 인증 방식 · 외부 서비스) · 데이터 구조 변경 · 공개 API 변경 · 방향을 바꾼 결정. **안 남김:** 작은 라이브러리(`기록.md`에 한 줄) · 코드 정리.
판단 질문: "6개월 뒤 '왜 이렇게 했지?'가 나올까?" — AI는 **제안만**, 남길지는 사람이 정한다. 단 **데이터 구조 변경은 항상** 남긴다. 남기면 `/l-adr`을 부르고 설계.md frontmatter `adr`에 ID를 적는다.

## 6. 설계 승인 게이트 (DE-02) — 지금 설정: design.approval = <<design.approval>>
승인 화면은 **요약 3줄** + 선택지:
```
🏗 구조: …   🎨 화면: …   🗄 데이터: …   (⚠ 되돌리기 어려운 것: …)
→ [진행] / [고칠 곳]
```
- `required`: 항상 묻는다.
- `auto`: 데이터 변경과 ADR이 **없는** 작은 설계는 묻지 않고 한 줄로 알린다.
- `off`: 묻지 않는다.
- **데이터 구조 변경이나 ADR이 있으면 값과 상관없이 묻는다.**

승인(또는 auto 통과)을 받으면 기록한다:
```bash
lantern design approve W-012 --by "<승인한 사람>"     # auto로 통과했으면 --by auto
```
고칠 곳을 들으면 고치고 다시 요약을 보여 준다.

<!-- lantern:if knowledge -->
## 7. 모르는 기술 → /l-learn 후보
설계에 새 기술 · 라이브러리가 나오면 /l-plan과 같은 규칙으로 후보를 모은다 (노트 있는 기술은 빼고, 최대 <<learn.max_candidates>>개, 작업은 멈추지 않음).
<!-- lantern:endif -->

## 공통 마무리
```bash
lantern close l-design --work W-012
```
**다음:** `/l-task W-012`.
