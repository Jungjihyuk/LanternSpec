---
name: l-build
description: 할 일을 구현하고 증거로 보고 — 작업(W-NNN 전체 또는 W-NNN-T03 하나)의 할 일을 순서대로 구현 → 테스트 → 할 일마다 커밋([W-NNN-T03]) → 체크하고, 기록.md에 바뀐 파일 · 테스트 결과 · 수락 기준 · 캡처 · 스키마 변경을 증거로 남긴 뒤, 끝나면 현재 상태에 반영할 요약을 보여 주고 승인받아 합친다. Use to implement a planned work.
invocation: model
argument-hint: "W-NNN | W-NNN-T03 [--report-cycle work|criterion|task]"
---

# /l-build — 구현하고 증거로 보고

**목적:** 할 일을 구현하고, **"끝났어요"가 아니라 증거로** 보고한다.

입력: `$ARGUMENTS` — `W-012`(전체) 또는 `W-012-T03`(하나). `--report-cycle task`처럼 이번 작업만 보고 주기를 바꿀 수 있다.
지금 설정: 보고 주기 `<<build.report_cycle>>` · 현재 상태 반영 `<<build.merge_approval>>`<!-- lantern:if build.test --> · 테스트 `<<build.test>>`<!-- lantern:endif -->

## 0. 준비
1. `할 일.md`가 없으면 멈추고 `/l-task`를 먼저 하자고 한다. 설계 승인(`설계.md`의 `approved`)이 비어 있으면<!-- lantern:if design.approval=off --> 게이트가 꺼져 있으니 진행한다.<!-- lantern:endif --><!-- lantern:if !design.approval=off --> 멈추고 `/l-design` 게이트를 먼저 거친다.<!-- lantern:endif -->
2. 작업 하나 = 브랜치 하나: `lantern work branch W-012` (동시 작업용 worktree 안이면 이미 그 브랜치다 — 건너뛴다)
3. 작업 꾸러미를 만들고 **그것만** 읽는다 (작업 폴더 + 관련 현재 상태 부분만 모은 한 번 쓰고 버리는 요약):
   ```bash
   lantern pack W-012     # → .lantern/pack/W-012.md
   ```
4. `기록.md`가 없으면 `lantern scaffold doc W-012 기록`

## 1. 할 일 하나씩 (작은 반복)
```bash
lantern task next W-012          # 순서대로 지금 시작할 수 있는 할 일 (막힌 것은 이유와 함께 건너뜀)
lantern task next W-012 --all    # 지금 시작할 수 있는 할 일 전부 — [P] 표시는 서로 동시에 해도 되는 할 일
lantern task start W-012-T03     # [시작:: 시각]을 정확히 찍는다
```
**병렬 (그래프):** `--all`에 `[P]` 할 일이 둘 이상이고 이 도구가 서브 에이전트를 지원하면, `[P]` 할 일을 **하나씩** 서브 에이전트에 맡길 수 있다. 각자 같은 규칙(시작 · 증거 · 할 일 하나 = 커밋 하나)을 지키게 하고, 같은 파일을 고치는 할 일은 함께 맡기지 않는다. 지원하지 않으면 차례로 한다.

1. 구현한다. 설계에 없는 **큰 변경**이 필요하면 멈추고 보고한다 (→ `/l-design`).
2. 테스트한다<!-- lantern:if build.lint --> · 린트 · 타입 검사도 돌린다 (`lantern lint`)<!-- lantern:endif -->. 실패하면 고치고 다시 — **최대 3번**. 3번째도 실패하면 멈추고 보고한다.
3. `기록.md`에 증거를 남긴다:
   - `## 증거` 표에 한 줄: 할 일 · 커밋(커밋 후 채움) · 바뀐 파일 · 테스트 결과(명령과 통과 수) · 수락 기준
   - 화면이면 캡처를 `화면/구현/`에 저장하고 경로를 적는다
   - 스키마를 바꿨으면 `## 스키마 변경`에 한 줄 (날짜 · 변경 · 이유/ADR · 마이그레이션 파일) — **실제 DB에 마이그레이션을 실행해야 하면 멈추고 묻는다**
   - `## 지금 상황`은 덮어쓴다 (진행 · 다음 · 막힌 것, 3~5줄)
4. 체크하고 커밋한다:
   ```bash
   lantern task done W-012-T03      # [완료:: 시각] + 수락 기준 체크포인트 알림
   ```
<!-- lantern:if docs.remote=shared -->
   코드 + `할 일.md` + `기록.md`를 **한 커밋에**: `git add … && git commit -m "feat: <무엇> [W-012-T03]"` (사용자의 커밋 규칙을 따르고 ID는 끝에). 커밋 후 증거 표의 커밋 칸을 채워 다음 커밋에 함께 넣는다.
<!-- lantern:endif -->
<!-- lantern:if docs.remote=local -->
   코드 커밋 `git commit -m "feat: <무엇> [W-012-T03]"` → 그 번호로 문서 커밋 `git -C docs add -A && git -C docs commit -m "docs: W-012-T03 기록 (code $(git rev-parse --short HEAD))"`. 코드 커밋에 `docs/`를 넣지 않는다.
<!-- lantern:endif -->
   여러 할 일을 한 커밋에 섞지 않는다. 할 일이 크면 같은 ID로 여러 커밋도 된다.
5. **수락 기준 체크포인트:** `task done`이 `AC 체크포인트: AC-1`을 알리면 그 AC만 따로 확인한다(관련 테스트 · 동작 확인). 통과하면 `lantern task ac W-012 AC-1`.

<!-- lantern:if plan.ui_reference=required -->
6. **화면 시안 확인 (PL-04):** `[화면:: …]` 할 일이 끝나면 구현 화면을 캡처(`화면/구현/…png`)하고, 시안도 PNG면 먼저 자동 비교로 다른 곳을 짚는다: `lantern screen compare "화면/구현/로그인.png" "화면/로그인.png"` (참고용). 그다음 둘을 **나란히 보여 주고 사용자에게 묻는다**: "시안과 같나요?" → 같으면 해당 AC 체크, 다르면 다른 곳마다 `lantern task add W-012 "<다른 곳 맞추기>" --size S --ac AC-n --screen "<화면>"`.
<!-- lantern:endif -->

## 2. 언제 보고하나 (BU-02)
- `work`: 작업이 다 끝나면 · `criterion`: 수락 기준 하나가 완성될 때마다 · `task`: 할 일 하나마다
- **값과 상관없이 바로 보고하고 멈춘다:** 테스트를 3번 고쳐도 실패 · `❓ 확인 필요`를 만남 · 화면 시안 확인 · 실제 DB 마이그레이션 실행 · 설계에 없는 큰 변경
- 보고는 3줄: **한 일 · 멈춘 이유 · 골라야 할 것**

<!-- lantern:if knowledge -->
## 3. 새 기술 · 라이브러리 → /l-learn 후보
구현 중 새 기술이 들어오면 후보로 모은다 (노트 있는 기술 · 아는 기술은 빼고, 최대 <<learn.max_candidates>>개). **작업은 멈추지 않고** 마지막 보고 때 보여 준다. 작은 라이브러리 선택은 `기록.md` 결정 칸에 한 줄, 되돌리기 어려운 선택은 `/l-adr`.
<!-- lantern:endif -->

<!-- lantern:if build.loop=on -->
## 3½. 큰 반복 (build.loop: on · 최대 <<build.loop_limit>>번)
모든 할 일이 끝나면 수락 기준 테스트를 한꺼번에 돌린다<!-- lantern:if build.test --> (`<<build.test>>`)<!-- lantern:endif -->.
- 모두 통과 → 4단계로.
- 실패한 수락 기준이 있으면 → 실패마다 고칠 할 일을 추가하고(`lantern task add W-012 "<AC-n 맞추기>" --size S --ac AC-n`) 1단계부터 다시 돈다. `기록.md`에 "큰 반복 n번째: 실패한 AC · 원인 한 줄"을 남긴다.
- <<build.loop_limit>>번을 돌아도 통과하지 못하면 멈추고 보고한다 (한 일 · 남은 실패 · 골라야 할 것).
<!-- lantern:endif -->

## 4. 모두 끝나면 — 현재 상태에 반영 (BU-03)
`lantern task next W-012`가 "모든 할 일 완료"를 알리면:
1. 설계의 변경분을 현재 상태에 합칠 **요약 한 장**을 보여 준다:
   ```
   📘 기능 목록  ✚ 카카오 로그인 (W-012)
   🏗 시스템 구조 ✎ 인증 흐름에 카카오 OAuth 추가
   🗄 데이터     ✚ users.kakao_id   (⚠ 데이터 구조 변경)
   🔌 API        —
   → [모두 반영] / [골라서 반영] / [고칠 곳]
   ```
   - `required`: 항상 묻는다. `auto`: 먼저 반영하고 요약을 보고한다 (잘못되면 git으로 되돌림).
   - **데이터 구조 · API 변경은 값과 상관없이 묻는다.**
2. 반영한다: 한 사실은 한 곳에 — 출처 작업을 링크한다.
   - 데이터: 설계의 DBML 변경분을 `3. 현재 상태/데이터/schema.dbml`에 합친다 → `lantern check-dbml` → `lantern dbml render`
   - 반영한 문서의 확인 시점: `lantern meta set "<문서>" checked_commit=$(git rev-parse --short HEAD)` (관련 코드 경로가 늘었으면 `code`도)
3. 작업 브랜치를 기준 브랜치에 합치고 정리한다 (테스트 → 머지 → 정리):
   ```bash
   lantern work finish W-012
   lantern work archive W-012      # 작업 폴더 → 2. 작업/보관/ (링크도 고쳐 준다)
   ```
4. 공통 마무리 + 맞추기 검사 + 보고 갱신:
   ```bash
   lantern close l-build --work W-012
   lantern scan
   lantern report
   ```
5. 마지막 보고: 증거 요약(할 일 · 커밋 · 테스트 · AC) · 반영한 것 · `scan`에서 나온 어긋남 · 부채 후보 · 다음 할 일.
