---
name: l-learn
description: 모르는 기술을 내 지식 저장소와 비교 — 기술 용어를 지식 저장소(Obsidian)에서 찾아 🟢 노트 있음 · 🟡 노트 있는데 다시 물음 · 🔴 노트 없음으로 나누고, 이해 부채 카드(📒 부채/카드/D-NNN)를 만들거나 물은 횟수를 늘리고, 복습할 것과 새로 공부할 것(학습 노트 초안)을 제안한다. Use when the user asks what a technology is, or when /l-plan · /l-design · /l-build hand over unfamiliar terms.
invocation: model
argument-hint: "<기술 용어> [용어 …]"
---

# /l-learn — 모르는 기술을 지식 저장소와 비교

**목적:** 이해 부채를 찾아 장부에 남기고, 복습 · 공부를 제안한다. "몇 번 물었나 · 이해했나"는 **전부 우리 장부에** 둔다. 지식 저장소는 읽기만 하고, 사용자가 승인한 새 노트만 쓴다.

입력: `$ARGUMENTS` — 용어 하나 또는 목록. `/l-plan` · `/l-design` · `/l-build`가 넘긴 후보일 수도 있다 (그때는 작업 ID도 함께).

<!-- lantern:if !knowledge -->
> ⚠ 이 프로젝트는 지식 저장소가 없어 배우는 선로가 꺼져 있다. 사용자에게 알리고 `/l-init`을 다시 실행해 `knowledge`를 설정할지 묻는다. 그 전까지는 용어를 설명만 하고 카드는 만들지 않는다.
<!-- lantern:endif -->
<!-- lantern:if knowledge -->
## 처리 순서 (용어마다)
1. **아는 기술 · 기존 카드 확인:**
   ```bash
   lantern debt find "<용어>"            # 아는 기술이면 끝 — 다시 묻지 않는다
   ```
2. **지식 연결기로 검색:**
   ```bash
   lantern knowledge search "<용어>" --alias "<별칭>" --json
   ```
   (JWT · JSON Web Token · 제이슨 웹 토큰처럼 **별칭은 같은 기술**로 본다.)
3. **분류:**
   - 🟢 노트 있음, 처음 물음 → 노트 링크만 붙인다
   - 🟡 노트 있는데 다시 물음 (카드가 이미 있음) → 복습 제안
   - 🔴 노트 없음 → 학습 노트 초안 제안
   - 다른 스킬이 넘긴 후보 중 **노트가 있는 기술은 처음부터 뺀다**
4. **부채 카드 만들기 · 갱신** (번호 · 횟수는 스크립트가 센다 — 같은 대화에서는 한 번만 센다):
   ```bash
   # 카드가 없으면
   lantern debt new "<용어>" --area <주제> --alias "<별칭>" [--work W-012] [--note "<노트 위치>"] --session "<<SESSION_ID>>" --context "<어디서 나왔나 한 줄>"
   # 카드가 있으면
   lantern debt ask <D-NNN> [--work W-012] --session "<<SESSION_ID>>" --context "<맥락>"
   ```
   - **주제**는 `enums.yaml`의 `area` 중 하나 (backend · frontend · data · ai · infra · 기타). 카드 하나에 주제 하나. 맞는 게 없으면 `기타`로 두고 새 주제를 제안한다 (사용자가 승인하면 `enums.yaml`에 추가).
   - <<debt_status.resolved.label>>된 카드를 또 물으면 스크립트가 다시 연다 (<<debt_status.resolved.label>> → <<debt_status.asked_again.label>>).
   - 카드의 "한눈에 보기"에 이 기술이 무엇이고 왜 쓰는지 한 줄을 채운다.
5. **제안:**
   - 🟡 → 노트를 읽고(`lantern knowledge read "<경로>"`) 노트 링크 + 복습 포인트 2~3개
   - 🔴 → 학습 노트 초안을 만든다:
     ```bash
     lantern knowledge propose "<용어>" --area <주제>
     ```
     만들어진 초안(`📒 부채/노트 초안/…`)의 빈칸을 채워 보여 주고 승인을 묻는다.
     - 지금 저장소 쓰기 방식: `<<knowledge.write>>` — `direct`면 승인 후 `lantern knowledge write "<초안 경로>"`, `propose_only`면 초안 경로만 알려 주고 넣는 것은 사용자가 한다.
     - 노트가 생기면 카드에 연결: `lantern meta set "<카드>" note="<노트 위치>"`

## "이해했어" — 지금 설정: learn.verify = <<learn.verify>>
- `self`: 사용자가 이해했다고 하면 바로 `lantern debt resolve <D-NNN>`
- `explain`: "한 줄로 설명해 볼래요?" → 노트와 비교해 빠진 부분을 짚는다 → 괜찮으면 `lantern debt resolve <D-NNN>`. 설명은 카드 "지금 이해한 것"에 적는다.
- 해결 뒤 "직접 만들어 볼까요?"라고 **역량 부채**로 넘길지 한 번 묻는다 (이해 → 역량 순서). 예면:
  ```bash
  lantern debt promote <D-NNN>              # <<debt_kind.competency.label>> 카드 (출처: <<debt_kind.understanding>> 카드)
  ```
  역량 카드의 "연습 과제"에 작고 확인할 수 있는 과제 1~3개를 함께 정한다. 사용자가 만들어 볼 때마다
  `lantern debt practice <역량 D-NNN> "<만든 것 · 링크 · 한 줄 소감>"` (<<debt_status.practicing.label>>), 과제를 다 하면 `lantern debt resolve <역량 D-NNN>`.

## 기술 부채 (코드에 남은 빚)
일반적인 기술 부채는 기존 도구의 영역이지만, 사용자가 남기자고 하면 같은 장부에 둔다: `lantern debt new "<무엇>" --kind "<<debt_kind.tech>>" --area <주제> [--work W-012]`.

## "이건 알아"
사용자가 아는 기술이라고 하면 `lantern debt known add "<용어>" --alias "<별칭>"` — 다시 묻지 않는다.

## 대화 중 질문 감지 — 지금 설정: learn.detect = <<learn.detect>>
- `manual`: `/l-learn`을 부르거나 다른 스킬이 넘길 때만 센다.
- (에이전트 hook이 설치된 도구 — Claude Code · Codex · Antigravity — 에서는 `ask` · `auto`일 때 hook이 질문을 알아채 `LanternSpec 기술 질문` 메시지로 알려 준다. 그 메시지를 따른다.)
<!-- lantern:if learn.detect=ask -->
- `ask`: 대화 중 "JWT가 뭐야?" 같은 기술 질문을 알아챌 때마다, 답한 뒤 한 줄로 "📒 부채로 남길까요?"를 묻는다.
<!-- lantern:endif -->
<!-- lantern:if learn.detect=auto -->
- `auto`: 대화 중 기술 질문을 알아채면 — 카드가 **없으면** 만들지 한 줄로 제안하고, 카드가 **있으면** 묻지 않고 `lantern debt ask`로 센다.
<!-- lantern:endif -->

## 한 번에 보여 줄 후보 수
최대 <<learn.max_candidates>>개. 나머지는 작업 끝에 한꺼번에.

## 공통 마무리
```bash
lantern close l-learn [--work W-012]
```
결과를 한 줄씩: `<<debt_status.asked_again.icon>> D-002 JWT 갱신 — <<debt_status.asked_again>> (3번째) · 복습: [[노트]]`
<!-- lantern:endif -->
