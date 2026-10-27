---
name: l-plan
description: 아이디어를 작업으로 만들기(기획) — 무엇을 · 왜 만드는지 정하고 작업 폴더 docs/2. 작업/W-NNN 과 기획.md(한눈에 보기 · 무엇을 · 왜 · 사용자 시나리오 · 수락 기준 · 범위 밖)를 만든다. 모르는 것은 ❓ 확인 필요로 표시하고 묻는다. Use when the user decides to build an idea (IDEA-NNN) or describes a feature to plan.
invocation: model
argument-hint: "IDEA-NNN | <만들 것 설명>"
---

# /l-plan — 아이디어를 작업으로 만들기 (기획)

**목적:** **무엇을 · 왜** 만드는지 정하고 작업 폴더를 만든다. 어떻게(설계)는 다음 단계다.

입력: `$ARGUMENTS` — `IDEA-014`, 또는 바로 설명.

## 0. 읽기 (필요한 만큼만)
- `lantern status` — 진행 중 작업
- `docs/3. 현재 상태/프로젝트 정의서.md` · `기능 목록.md`의 한눈에 보기
- 아이디어 카드 (`IDEA-014`이면)
- `docs/3. 현재 상태/규칙 · 결정 기록/작업 단위 기록.md` — 지난번 사람이 추천을 바꾼 이유

## 1. 작업 단위 제안 → 사람이 고른다
열린 작업과 겹치는지 보고 셋 중 하나를 **추천 + 이유**로 제시한다:
- **새 작업** — 사용자에게 보이는 결과 하나, 혼자 끝내고 배포할 수 있는 크기
- **기존 작업에 넣기** — 같은 화면 · 같은 데이터를 바꾸는 열린 작업이 있을 때
- **둘로 나누기** — 할 일이 10개 이상이 될 것 같거나 여러 영역에 걸칠 때

사람이 추천과 다르게 고르면 이유를 묻고 남긴다:
```bash
lantern unit-log add --what "<무엇>" --recommended "<추천>" --chosen "<사람의 선택>" --reason "<이유>"
```

## 2. 작업 폴더 만들기
```bash
lantern idea status IDEA-014 "<<idea_status.reviewing>>"   # 아이디어에서 시작할 때
lantern scaffold work "<작업 이름>" --idea IDEA-014 [--ui]  # 화면이 바뀌는 작업이면 --ui
lantern idea status IDEA-014 "<<idea_status.worked>>" --work W-012
```
- **아이디어 없이 바로** 시작하면(PL-03) 아이디어 카드를 뒤에서 함께 만든다: `lantern scaffold idea "<이름>" --kind 기능 --raw "<사용자 설명>" --status "<<idea_status.worked>>"` → 그 ID로 `scaffold work --idea` → `idea status … "<<idea_status.worked>>" --work …`.
- **기존 작업에 넣기**면 폴더를 만들지 않고 그 작업의 `기획.md`에 시나리오 · 수락 기준을 보탠 뒤 `lantern idea status IDEA-014 "<<idea_status.worked>>" --work W-010`.

## 3. 기획.md 채우기
한눈에 보기 · 무엇을 · 왜 · 사용자 시나리오 · **수락 기준** · 범위 밖, frontmatter `domain`(기능 도메인 한 단어).
<!-- lantern:if plan.ac_format=gwt -->
수락 기준 형식 (Given–When–Then): `- [ ] AC-1 상황: … · 행동: … · 결과: …` — 상황은 필요할 때만, 한 줄에 하나.
<!-- lantern:endif -->
<!-- lantern:if plan.ac_format=simple -->
수락 기준 형식: `- [ ] AC-1 ~하면 ~된다` — 한 줄에 하나.
<!-- lantern:endif -->
결과는 **확인할 수 있게** 쓴다: "빠르게" ✕ → "2초 안에" ○, "잘 보인다" ✕ → "목록 맨 위에 보인다" ○.

## 4. 모르는 것은 묻는다 (추측 금지)
모르는 부분은 해당 칸에 `❓ 확인 필요: <질문>`으로 적고, **한 번에 최대 <<plan.max_questions>>개**만 묻는다.
- 영향이 큰 순서로 고른다: 범위 → 보안 → 사용자 경험 → 세부
- 모르는 게 적으면 그만큼만 묻는다. **질문을 지어내지 않는다.**
- 남은 질문은 `❓ 확인 필요`로 두고 `/l-design` 전에 다시 묻는다.
답을 들으면 칸에 반영하고 `❓` 줄을 지운다.

## 5. 수락 기준 검사
```bash
lantern check --epic W-012
```
⚠ 애매한 말 · 여러 뜻 · 형식 경고는 고친다. 뜻을 모르겠으면 사람에게 묻는다.

<!-- lantern:if plan.ui_reference=required -->
## 6. 화면 시안 (plan.ui_reference: required)
화면이 바뀌는 작업이면 `ui: true`(`--ui`)이고 **시안이 있어야** 진행한다. 시안으로 인정하는 것: `2. 작업/W-012 …/화면/` 아래 이미지(와이어프레임 · 레퍼런스) · HTML 파일(Claude Design · artifact 내보내기). 공유 링크는 받지 않는다.
- 없으면 시안을 요청한다<!-- lantern:if design.tool=claude-design -->: "Claude Design에서 화면을 만들고 **HTML로 내보내** `화면/` 폴더에 넣어 주세요"<!-- lantern:endif --><!-- lantern:if design.tool=figma -->: Figma MCP로 프레임을 이미지로 내보내 `lantern screen import W-012 <파일>`<!-- lantern:endif --><!-- lantern:if design.tool=canva -->: Canva MCP로 PNG · PDF로 내보내 `lantern screen import W-012 <파일>`<!-- lantern:endif -->.
- 수락 기준에 자동으로 추가한다: `- [ ] AC-n 결과: 화면이 화면/<파일> 시안과 같다`
<!-- lantern:endif -->

<!-- lantern:if knowledge -->
## 7. 모르는 기술 → /l-learn 후보 (LE-02)
기획에 기술 용어가 나오면 후보를 고른다: `lantern debt find "<용어>"`(아는 기술 · 카드 확인)와 `lantern knowledge search "<용어>"`로 **노트가 있는 기술은 처음부터 뺀다.** 한 번에 최대 <<learn.max_candidates>>개, 마지막 보고 때 보여 주고 **작업은 멈추지 않는다.** 사용자가 고르면 `/l-learn`으로 넘긴다. "이건 알아"는 `lantern debt known add "<용어>"`.
<!-- lantern:endif -->

## 공통 마무리
```bash
lantern close l-plan --work W-012
```
보고 3줄: 만든 작업 · 남은 `❓ 확인 필요` · 다음 `/l-design W-012`.
