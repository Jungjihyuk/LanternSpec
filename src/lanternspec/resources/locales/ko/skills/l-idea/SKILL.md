---
name: l-idea
description: 생각으로만 있는 것을 적어 두기 — 대화에서 나온 아이디어 · 하고 싶은 것 · 불편함 · 버그 같은 것 · 궁금한 기술 · 해 보고 싶은 실험처럼, 지금 하지 않으면 잊힐 생각을 원문 그대로 + 정리본으로 docs/<<folder.ideas>>/IDEA-NNN 에 남긴다. 종류(기능 · 개선 · 버그 · 실험 · 기술 검토)에 꼭 맞지 않아도 남길 만하면 제안한다. 겹치는 카드에는 덧붙인다. Use when the conversation shows a thought worth keeping for later — a wish, an annoyance, a possible bug, a technology to look into, an experiment to try — even if it doesn't fit a kind exactly ("이런 거 있으면 좋겠다", "이거 좀 불편한데", "버그 같은데 나중에 보자").
invocation: profile:idea.capture
argument-hint: "<생각 한 줄> | 방금 대화에서 나온 아이디어들"
---

# /l-idea — 대화 속 생각을 아이디어 노트로

**목적:** 떠오른 생각을 **원문 그대로 + 정리본**으로 바로 남긴다. 속도가 중요하므로 **승인 없이 바로 쓴다** ("쓰기 전에 보여 준다" 규칙의 예외).

입력: `$ARGUMENTS` — 생각 한 줄, 또는 "방금 대화에서 나온 아이디어들"(이 대화에서 나온 아이디어를 모두 모은다).

## 언제 제안하나
대화를 하다가 **나중에 다시 꺼낼 만한 생각**이 보이면, 말이 끝난 뒤 한 줄로 남길지 묻는다. 예: "이거 아이디어로 남겨 둘까요? (`/l-idea`)"
- 이런 말이 낌새다:
  - 바람 ("~면 좋겠다", "언젠가 ~하고 싶다")
  - 불편함 ("~가 번거롭다", "매번 ~한다")
  - 이상한 동작 ("~가 이상하게 나온다", "가끔 ~된다")
  - 궁금한 기술 ("~는 어떨까", "~ 써 보고 싶다")
  - 해 볼 실험 ("~하면 빨라질까")
- **종류에 딱 맞지 않아도 제안한다.** 종류는 남길 때 가장 가까운 것을 고르면 되고, 애매하면 사람에게 묻는다.
- 지금 바로 하기로 한 일은 제안하지 않는다 — 그건 `/l-plan`이나 지금 작업에서 다룬다.
- 같은 대화에서 같은 생각을 두 번 제안하지 않는다. 사람이 남기지 않겠다고 하면 그 대화에서는 다시 묻지 않는다.

## 처리 순서
1. **뽑기:** 말에서 아이디어를 뽑는다. 서로 다른 생각이면 여러 장으로 나눈다. 원문은 고치지 않고 그대로 보관한다.
2. **겹치는지 보기:** 아이디어마다
   ```bash
   lantern idea find "<핵심 단어 두세 개>"
   ```
   - 같은 아이디어가 있으면 **새로 만들지 않는다.** 그 카드의 `## <<section.raw>>`에 날짜와 함께 덧붙이고(`> …` 인용), 정리본에 새 내용만 보탠다.
   - 같은 아이디어가 <<idea_status.dropped.label>> 상태면, 지난 이유(`dropped_reason`)를 알려 주고 "다시 살릴까요?"를 묻는다. 살리면 `lantern idea status IDEA-NNN "<<idea_status.new>>" --note "다시 나옴"`.
   - 같은 아이디어가 <<idea_status.blocked.label>> 상태면, 막힌 이유와 다시 볼 조건을 알려 주고 그 조건이 이루어졌는지 묻는다.
3. **유형 정하기** (`docs/<<folder.templates>>/_meta/enums.yaml`의 `idea_kind`): ✨ 기능 · 🔧 개선 · 🐞 버그 · 🧪 실험 · 🔍 기술 검토. 버그도 여기 모은다 (할 일 후보는 한 곳에).
4. **만들기 · 채우기:**
   ```bash
   lantern scaffold idea "<짧은 제목>" --kind 기능 --raw "<사용자 원문>"
   ```
   종류마다 양식이 있으면(`docs/<<folder.templates>>/<<doc.idea>> - <종류>.md`, 예: 기능 → 기능 요약 표) 그 양식으로, 없으면 기본 `<<doc.idea>>` 양식으로 만들어진다.
   만들어진 파일의 빈칸만 채운다: 한 줄 요약<<marker.required>> · 그 양식의 칸 · 관련 문서(링크만 — 내용 복사 금지). 쓸 것이 없는 선택 칸은 지운다.
   표의 칸은 대화에서 나온 만큼만 채우고, 모르는 칸은 짐작하지 말고 비워 둔다. 끝난 뒤에 채우는 표(결과 · 원인과 해결 · 결론)는 손대지 않는다 — `/l-build`가 마무리할 때 채운다. 글로 쓰는 칸에서 모르면 `<<marker.unknown>>`.
5. **한 줄로 알린다:** `💡 IDEA-014 카카오 로그인 (기능) 기록함` (여러 장이면 한 줄씩)

## 상태는 스킬이 바꾼다
<<idea_status.new.label>>(`/l-idea`) → <<idea_status.reviewing.label>> · <<idea_status.worked.label>>(`/l-plan`) / <<idea_status.on_hold.label>> · <<idea_status.dropped.label>>(사람). 사람이 <<idea_status.on_hold>> · <<idea_status.dropped>>을 말하면:
```bash
lantern idea status IDEA-014 "<<idea_status.on_hold>>"
lantern idea status IDEA-014 "<<idea_status.dropped>>" --reason "<이유 한 줄 <<marker.required>>>"
```
버린 아이디어는 지우지 않는다.

## 막힌 아이디어
원하지만 지금은 못 하는 것(기술 한계 · 실력 · 경험 · 데이터 부족)은 <<idea_status.on_hold>>가 아니라 <<idea_status.blocked>>으로 둔다. <<idea_status.on_hold>>은 그냥 미룬 것이고, <<idea_status.blocked>>은 무엇이 되면 다시 볼지가 있다.
```bash
lantern idea status IDEA-014 "<<idea_status.blocked>>" --reason "<무엇 때문에 막혔나 · 시도해 본 것>" --revisit "<무엇이 되면 다시 보나>"
lantern debt promote IDEA-014 "<익힐 것>"   # 사람의 실력 때문에 막혔을 때만: <<debt_kind.competency.label>> 카드를 만들어 서로 잇는다
```
- `--revisit`은 확인할 수 있게 쓴다. 나쁜 예: "나중에 기술이 좋아지면". 좋은 예: "표 구조까지 읽는 HWP 도구가 생기면".
- 두 값은 사람이 말한 것을 쓴다. 모르면 묻는다. 막힌 목록은 `<<file.moc>>`에서 모아 본다.

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
