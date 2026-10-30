---
name: l-resume
description: 지난 대화 이어 가기 — 이 프로젝트에서 어느 AI 도구(Claude Code · Codex · Antigravity)로 하던 대화든, 중간에 끊겼든 정상으로 끝났든, 멈춘 곳(마지막 요청 · AI의 마지막 말 · 고친 파일 · 커밋 안 된 변경 · 진행 중인 작업)을 읽고 확인받은 뒤 이어서 한다. Use when the user asks to continue earlier work, or a previous session was cut off (usage limit, crash) or happened in another AI tool.
invocation: model
argument-hint: "[대화 번호]"
---

# /l-resume — 지난 대화 이어 가기

**목적:** 지난 대화가 멈춘 곳을 찾아, 같은 흐름으로 이어 간다. 대화 기록 파일이 어디 있는지는 사람이 몰라도 된다 — hook이 대화마다 적어 둔 것을 `lantern resume`이 읽는다.

입력: `$ARGUMENTS` — 비우면 가장 최근 대화, 번호를 주면 그 대화.

## 1. 멈춘 곳 읽기
```bash
lantern resume                 # 최근 대화 목록 + 가장 최근 대화의 끝부분
lantern resume --session 2     # 다른 대화
lantern resume --more 1        # 더 앞의 메시지 (필요할 때만 — 컨텍스트를 아낀다)
```
- **⚠ 끊김**이면 마지막 턴이 끝나지 못했다. 그 턴이 하던 일이 반쯤 된 채 남았을 수 있다.
- 기록 파일을 읽지 못하면 끝 몇 줄을 그대로 보여 준다 — 그것과 아래 2번으로 판단한다.

## 2. 지금 상태와 맞춰 보기
- **커밋 안 된 변경**(요약에 나온 것)이 마지막 요청과 맞는지 본다. 끊긴 대화라면 고치다 만 파일은 `git diff`로 열어 어디까지 됐는지 확인한다.
- **진행 중인 작업**이 있으면 그 작업의 `<<file.record>>` "<<section.now>>" 칸과 `<<file.tasks>>`에서 어디까지 했는지 확인한다.
- 요약과 문서가 다르면 **문서와 코드가 기준**이다 (대화는 잘렸을 수 있다).

## 3. 확인받고 이어 가기
한 줄로 묻는다: **"여기서부터 이어 가겠습니다: <무엇을 · 어디서부터>. 맞나요?"**
- 맞다고 하면 이어 간다. 작업 중이었다면 그 단계의 스킬로 넘어간다 (예: 구현 중이었으면 `/l-build W-012`).
- 다르다고 하면 사람이 말한 곳부터 한다.
- 끊긴 턴이 하던 일을 **다시 실행하기 전에** 그 결과가 이미 남아 있는지(파일 · 커밋 · 문서) 먼저 본다 — 같은 일을 두 번 하지 않는다.

## 4. 마무리
다른 스킬로 넘어가지 않고 여기서 끝나면, 실행 기록만 남긴다 (문서를 바꾸지 않았으니 검사 · 지도 갱신은 하지 않는다):
```bash
lantern close l-resume --no-check --no-map
```
