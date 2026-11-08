---
name: l-design
description: 어떻게 만들지 설계 — 작업(W-NNN)에서 바뀌는 부분만 구조(Mermaid) · 화면(와이어프레임 · 시안 파일) · 데이터(DBML 변경분 + 마이그레이션 계획)로 <<file.design>>에 쓰고, 되돌리기 어려운 선택은 결정 기록(ADR)으로 넘기고, 사람 승인(설계 게이트)을 받는다. Use after /l-plan when a work needs a design.
invocation: model
argument-hint: "W-NNN"
---

# /l-design — 어떻게 만들지 (구조 · 화면 · 데이터)

**목적:** 이번 작업에서 **바뀌는 부분만** 설계한다. 지금 시스템 전체를 다시 쓰지 않는다.

입력: `$ARGUMENTS` — `W-012`.

## 0. 시작 전
- `<<file.plan>>`를 읽는다. **`<<marker.unknown>>`가 남아 있으면 먼저 묻는다** (최대 <<plan.max_questions>>개, 영향 큰 순).
- 현재 상태에서 관련된 부분만 읽는다: `<<folder.current>>/<<file.architecture>>` · `<<folder.screens>>/` · `<<folder.data>>/schema.dbml`.
- 이미 정한 결정을 읽는다: `<<folder.decisions>>/`에서 상태가 `<<adr_status.accepted>>`인 결정 기록 중 이 작업과 관련된 것 (인증 · 데이터 · API · 기술 선택 등). 이미 정한 것은 다시 묻지 않고 따른다. 바꿔야 하면 사람에게 묻고, 바꾸기로 하면 새 결정 기록으로 이전 것을 대신한다 (`/l-adr`).
- 설계 판단이 도메인 규칙에 달렸으면 `lantern ref domain --work W-012`에 연결된 절만 `lantern ref read`로 읽는다 (색인 전체를 다시 훑지 않는다).

## 1. <<file.design>> 만들기 · 칸 고르기
```bash
lantern scaffold doc W-012 "<<doc.design>>"
```
세 칸 중 **이번 작업에 필요한 칸만** 남긴다 (예: 화면만, 데이터만). 고른 칸을 frontmatter `parts`에 적는다 (예: `[구조, 데이터]`). 쓰지 않는 칸은 섹션째 지운다. "<<marker.glance>>"와 "되돌리기 어려운 선택"은 지우지 않는다.

## 2. 🏗 구조
바뀌는 부품과 흐름을 Mermaid로 그린다. 글은 그림을 설명한다. 코드 위치는 `` `src/…` `` 처럼 백틱으로 적는다 (동시 작업 충돌 경고에 쓰인다).

## 3. 🎨 화면
<!-- lantern:if design.tool=claude-design -->
**Claude의 Design 도구를 쓸 수 있으면** (artifact 도구에 Design 타입이 있으면) 와이어프레임을 직접 만든다.
1. `<<file.plan>>`의 사용자 시나리오와 수락 기준에서 화면 목록을 뽑는다.
2. 작업 이름으로 Design 캔버스를 하나 만들고, 화면마다 보드를 하나씩 그린다. 디자인 시스템이 있으면 그것을 따른다.
   보드는 움직이는 값 없이 정적인 마크업으로 그린다 — 저장한 파일이 캔버스 밖에서도 그대로 열린다.
   - 기존 화면을 바꾸는 작업이면, 바꾸기 전 화면을 먼저 남긴다. 실행 중인 화면을 캡처하거나, 그 화면의 코드를 보고 캔버스에 그대로 옮겨 그려 `<<folder.screens>>/<<folder.screens_current>>/`에 저장한다 (이 폴더는 시안으로 세지 않는다). 바뀔 화면은 같은 캔버스의 옆 보드에 그린다.
   - 디자인 시스템이 없고 코드에 공통 UI 부품이 있으면 한 번 안내한다: "기존 버튼 · 색 · 글꼴을 Claude의 디자인 시스템으로 옮겨 두면 시안이 지금 앱과 같은 모양으로 나와요. 원하시면 `/design-sync`를 실행해 주세요."
3. 각 보드 파일(`.dc.html`)을 `<<folder.works>>/W-012 …/<<folder.screens>>/`에도 저장한다. 캔버스 링크는 설계서에 참고로 적는다.
4. 사람에게 캔버스 링크를 보여 주고 확인을 받는다. 빠진 요구사항이 나오면 `<<file.plan>>`의 수락 기준을 먼저 고치고 화면을 다시 만든다.
   사람이 캔버스에서 직접 고쳤으면 그 파일을 다시 읽어 `<<folder.screens>>/`의 파일을 바꾼다.

**쓸 수 없으면** (Codex, Antigravity 등) 사람에게 시안을 받는다: "Claude에서 화면을 만들고 **HTML로 내보내** `<<folder.screens>>/` 폴더에 넣어 주세요". 화면 파일을 zip이나 폴더로 받으면 `lantern screen import W-012 <묶음>`으로 `<<folder.screens>>/` 아래에 푼다.
<!-- lantern:endif -->
<!-- lantern:if design.tool=figma -->
Figma MCP 서버(Dev Mode MCP)로 해당 프레임을 읽는다 → 프레임을 **이미지로 내보내** `<<folder.works>>/W-012 …/<<folder.screens>>/`에 저장한다 (`lantern screen import W-012 <파일 · 폴더>`). 구현에 필요한 값(색 · 간격 · 컴포넌트 이름)은 MCP가 준 것을 설계서 표에 옮긴다. Figma 링크만 적고 끝내지 않는다 — 팀원과 AI가 열 수 있는 **파일**이 원본이다.
<!-- lantern:endif -->
<!-- lantern:if design.tool=canva -->
Canva MCP 서버로 디자인을 찾아 **PNG 또는 PDF로 내보내** `<<folder.works>>/W-012 …/<<folder.screens>>/`에 저장한다 (`lantern screen import W-012 <파일 · 폴더>`). 공유 링크만 적고 끝내지 않는다.
<!-- lantern:endif -->
<!-- lantern:if design.tool=none -->
시안은 와이어프레임 · 레퍼런스 이미지 · HTML 파일로 `<<folder.works>>/W-012 …/<<folder.screens>>/`에 둔다.
<!-- lantern:endif -->
**링크만으로 끝내지 않는다** (나중에 바뀌거나 조직 밖에서 안 열릴 수 있음). 링크는 참고로 적고, `<<folder.screens>>/`의 **파일이 원본**이다. 설계서 글은 그림을 설명한다. 표에 화면 · 시안 파일 · 설명을 적는다.
<!-- lantern:if plan.ui_reference=required -->
시안을 넣었으면 `<<file.plan>>`에 수락 기준을 더한다: `- [ ] AC-n 결과: 화면이 화면/<파일> 시안과 같다`
<!-- lantern:endif -->

## 4. 🗄 데이터
- 현재 ERD(`<<folder.current>>/<<folder.data>>/schema.dbml`) 대비 **변경분**만 ```` ```dbml ```` 블록에 쓴다 (바뀌는 테이블은 완성된 정의로).
- 변경 표(추가 · 변경 · 삭제)와 **마이그레이션 계획**을 쓴다.
- 검사: `lantern check-dbml "docs/<<folder.works>>/W-012 …/<<file.design>>"` (현재 schema.dbml과 합쳐서 참조를 확인한다)
- 서버 없는 앱의 기기 저장소도 같은 DBML로 쓴다.

## 5. 되돌리기 어려운 선택 → /l-adr
**남김:** 바꾸기 어려운 도구 선택(DB · 프레임워크 · 인증 방식 · 외부 서비스) · 데이터 구조 변경 · 공개 API 변경 · 방향을 바꾼 결정. **안 남김:** 작은 라이브러리(`<<file.record>>`에 한 줄) · 코드 정리.
판단 질문: "6개월 뒤 '왜 이렇게 했지?'가 나올까?" — AI는 **제안만**, 남길지는 사람이 정한다. 단 **데이터 구조 변경은 항상** 남긴다. 남기면 `/l-adr`을 부르고 <<file.design>> frontmatter `adr`에 ID를 적는다.
`adr`에는 **이 설계가 따르는 기존 결정도** 함께 적는다 (예: 로그인 방식을 따르는 프로필 설계 → `[ADR-002, ADR-003]`). `/l-build`와 `/l-parallel`은 이 목록을 보고 결정을 읽는다.

## 6. 설계 승인 게이트 — 지금 설정: design.approval = <<design.approval>>
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

도메인 지식이 있는 프로젝트면(`lantern ref domain`이 비어 있지 않으면) 승인 화면에 한 줄 더한다: `📚 참고한 도메인 지식 N개 — 필요한데 빠진 것이 있나요?` 빠진 것을 들으면 `lantern ref attach`로 연결한다.

<!-- lantern:if knowledge -->
## 7. 모르는 기술 → /l-learn 후보
설계에 새 기술 · 라이브러리가 나오면 /l-plan과 같은 규칙으로 후보를 모은다 (노트 있는 기술은 빼고, 최대 <<learn.max_candidates>>개, 작업은 멈추지 않음).
<!-- lantern:endif -->

## 공통 마무리
```bash
lantern close l-design --work W-012 --commit
```
**다음:** `/l-task W-012`.
