---
name: l-task
description: 설계를 순서 있는 할 일 목록으로 쪼개기 — 작업(W-NNN)의 <<file.plan>> · <<file.design>>를 읽어 <<file.tasks>>에 W-NNN-T01 형식으로 할 일마다 크기(S/M/L) · 연결된 수락 기준 · 먼저 끝나야 할 일을 적는다. Use after /l-design is approved, before /l-build.
invocation: model
argument-hint: "W-NNN"
---

# /l-task — 할 일로 쪼개기

**목적:** 설계를 **순서 있는 할 일 목록**으로 만든다. 칸반 · 타임라인은 `/l-report`가 이 목록을 읽어 만든다.

입력: `$ARGUMENTS` — `W-012`.

## 0. 시작 전
- `<<file.design>>`가 승인됐는지 본다 (frontmatter `approved`). 비어 있으면<!-- lantern:if design.approval=off --> (design.approval: off라 게이트는 없다) 그대로 진행한다.<!-- lantern:endif --><!-- lantern:if !design.approval=off --> 멈추고 `/l-design W-012`의 승인 게이트를 먼저 거치자고 말한다.<!-- lantern:endif -->
- `<<file.plan>>`의 수락 기준(AC)과 `<<file.design>>`를 읽는다.

## 1. 할 일 목록 만들기
```bash
lantern scaffold doc W-012 "<<doc.tasks>>"
```
그다음 할 일을 **작업하기 좋은 순서대로** 하나씩 넣는다 (번호는 스크립트가 매긴다):
```bash
lantern task add W-012 "<무엇>" --size S|M|L --ac AC-1 [--after T01] [--screen "<화면 이름>"]<!-- lantern:if team --> --owner "<담당>"<!-- lantern:endif -->
```
- **순서:** 먼저 끝나야 할 일 → 데이터 · 바탕 → 기능 → 화면 → 마무리. 한 번에 확인할 수 있는 단위로.
- **크기**는 네가 정한다 (S 한두 시간 · M 반나절 · L 하루).
- **예정일은 넣지 않는다.** 사람이 날짜를 말했을 때만 `--start-plan 2026-11-01 --due-plan 2026-11-03`.
- 긴 설명은 쓰지 말고 `<<file.design>>`의 해당 부분을 링크한다.
- 다른 할 일과 **동시에 해도 되는** 할 일(서로 다른 파일, 먼저 끝나야 할 일 없음)은 `--parallel` (`[P]` 표시 — 병렬 에이전트가 함께 맡을 수 있다).
- 모르는 것이 있는 할 일은 `--unknown` (줄 끝에 `<<marker.unknown>>`) — `/l-build`가 건너뛴다.
- 화면 할 일은 `--screen`을 붙인다<!-- lantern:if plan.ui_reference=required --> (시안이 없으면 `/l-build`가 시작하지 않는다)<!-- lantern:endif -->.

## 2. 점검
- **모든 수락 기준에 할 일이 하나 이상** 연결됐는가 (`lantern check`가 빠진 AC를 알려 준다)
- 할 일이 **작업 이름의 목적을 벗어나는 것**이 보이면, 그 할 일을 빼고 `/l-plan`의 **나눠 담기**를 제안한다 (작업 하나 = 목적 하나)
- `lantern task list W-012`로 순서와 막힌 것을 확인한다
- 사람이 예정일을 원하면 크기별 실제 평균으로 **제안**만 한다: `lantern task estimate W-012 [--from 2026-11-01]` → 동의하면 `--apply`

## 3. 마무리
"<<marker.glance>>"에 할 일 수 · 큰 흐름을 한 줄로 쓰고, 단계를 올린다:
```bash
lantern work stage W-012 "<<work_status.tasks>>"
lantern close l-task --work W-012
```
**다음:** `/l-build W-012`.
