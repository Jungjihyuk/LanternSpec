---
name: l-idea
description: 대화 속 생각을 아이디어 노트로 — 사용자가 형식 없이 말한 생각을 원문 그대로 + 정리본(한 줄 요약 · 왜 좋은가 · 관련 문서)으로 docs/1. 아이디어/IDEA-NNN 에 바로 남긴다. 겹치는 아이디어는 기존 카드에 덧붙인다. Use to capture an idea, feature wish, bug, experiment or tech review the user mentions ("이런 거 있으면 좋겠다").
invocation: profile:idea.capture
argument-hint: "<생각 한 줄> | 방금 대화에서 나온 아이디어들"
---

# /l-idea — 대화 속 생각을 아이디어 노트로

**목적:** 떠오른 생각을 **원문 그대로 + 정리본**으로 바로 남긴다. 속도가 중요하므로 **승인 없이 바로 쓴다** ("쓰기 전에 보여 준다" 규칙의 예외).

입력: `$ARGUMENTS` — 생각 한 줄, 또는 "방금 대화에서 나온 아이디어들"(이 대화에서 나온 아이디어를 모두 모은다).

## 처리 순서
1. **뽑기:** 말에서 아이디어를 뽑는다. 서로 다른 생각이면 여러 장으로 나눈다. 원문은 고치지 않고 그대로 보관한다.
2. **겹치는지 보기:** 아이디어마다
   ```bash
   lantern idea find "<핵심 단어 두세 개>"
   ```
   - 같은 아이디어가 있으면 **새로 만들지 않는다.** 그 카드의 `## 원문`에 날짜와 함께 덧붙이고(`> …` 인용), 정리본에 새 내용만 보탠다.
   - 같은 아이디어가 <<idea_status.dropped.label>> 상태면, 지난 이유(`dropped_reason`)를 알려 주고 "다시 살릴까요?"를 묻는다. 살리면 `lantern idea status IDEA-NNN "<<idea_status.new>>" --note "다시 나옴"`.
3. **유형 정하기** (`docs/0. 템플릿/_meta/enums.yaml`의 `idea_kind`): ✨ 기능 · 🔧 개선 · 🐞 버그 · 🧪 실험 · 🔍 기술 검토. 버그도 여기 모은다 (할 일 후보는 한 곳에).
4. **만들기 · 채우기:**
   ```bash
   lantern scaffold idea "<짧은 제목>" --kind 기능 --raw "<사용자 원문>"
   ```
   만들어진 파일의 빈칸만 채운다: 한 줄 요약(필수) · 왜 좋은가 · 관련 문서(링크만 — 내용 복사 금지). 모르면 `❓ 확인 필요`. 쓸 것이 없는 선택 칸은 지운다.
5. **한 줄로 알린다:** `💡 IDEA-014 카카오 로그인 (기능) 기록함` (여러 장이면 한 줄씩)

## 상태는 스킬이 바꾼다
<<idea_status.new.label>>(`/l-idea`) → <<idea_status.reviewing.label>> · <<idea_status.worked.label>>(`/l-plan`) / <<idea_status.on_hold.label>> · <<idea_status.dropped.label>>(사람). 사람이 <<idea_status.on_hold>> · <<idea_status.dropped>>을 말하면:
```bash
lantern idea status IDEA-014 "<<idea_status.on_hold>>"
lantern idea status IDEA-014 "<<idea_status.dropped>>" --reason "<이유 한 줄 (필수)>"
```
버린 아이디어는 지우지 않는다.

<!-- lantern:if idea.capture=ask -->
## 대화 중 알아채기 (idea.capture: ask)
사용자가 대화 중 아이디어 같은 말("~하면 좋겠다", "나중에 ~도")을 하면 (에이전트 hook이 `LanternSpec 아이디어` 메시지로 알려 준다), 하던 일을 마친 뒤 **한 줄로만** 묻는다: "💡 이거 아이디어로 남길까요?" — **대화당 한 번만** 묻고, 거절하면 다시 묻지 않는다.
<!-- lantern:endif -->
<!-- lantern:if idea.capture=auto -->
## 대화 중 알아서 기록 (idea.capture: auto)
사용자가 대화 중 아이디어 같은 말을 하면 묻지 않고 바로 기록한다: `lantern scaffold idea "<제목>" --kind <유형> --raw "<원문>" --auto` (`🤖 자동 기록` 표시가 붙는다). 하던 일은 멈추지 않고 한 줄로만 알린다: `💡🤖 IDEA-015 … 자동 기록함 (틀렸으면 말해 주세요)`.
<!-- lantern:endif -->

## 공통 마무리
```bash
lantern close l-idea
```

**다음:** 만들기로 했다면 `/l-plan IDEA-014`.
