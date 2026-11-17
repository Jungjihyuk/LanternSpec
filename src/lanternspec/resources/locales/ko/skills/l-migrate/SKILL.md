---
name: l-migrate
description: 다른 도구의 문서를 우리 방식으로 옮기기 — OpenSpec의 변경(openspec/changes)을 끝난 것은 <<folder.archive>>의 작업으로, 진행 중인 것은 <<folder.works>>의 작업으로, 아직 정해지지 않은 것은 <<folder.ideas>>의 아이디어로 옮긴다. proposal · design · tasks의 칸을 <<file.plan>> · <<file.design>> · <<file.tasks>>의 칸에 맞춰 넣고, 맞는 칸이 없는 내용은 지우지 않고 모아 둔다. 원본은 <<folder.legacy>>에 보관한다. Use when an existing project has an openspec/ folder and the user wants its changes as LanternSpec works and ideas.
invocation: model
argument-hint: "openspec"
---

# /l-migrate — 다른 도구의 문서를 우리 방식으로

**목적:** 형식이 일정한 다른 도구의 문서를 LanternSpec의 폴더와 양식으로 옮겨서, 지난 일과 하던 일을 한 곳에서 이어 간다.
지금은 OpenSpec을 옮긴다. 형식이 일정하지 않은 문서는 옮기지 않고 `<<folder.legacy>>/`에 그대로 둔다.

## 규칙
- 변환은 `lantern migrate openspec`이 한다. 문서를 네가 다시 쓰지 않는다 — 내용이 바뀌면 안 된다.
- 원본은 `<<folder.legacy>>/openspec/`에 보관하고 고치지 않는다.
- 어디로 옮길지는 명령이 추천하고, 진행 중인 변경은 사람이 확인한다.

## 처리 순서
1. 미리보기를 보여 준다 (아무것도 바뀌지 않는다):
   ```bash
   lantern migrate openspec
   ```
   - 보관된 변경(`changes/archive/`)은 날짜 순서로 `<<folder.archive>>/W-NNN …`이 된다.
   - 진행 중인 변경은 할 일이 전부 끝났으면 보관, 설계나 할 일이 있으면 `<<folder.works>>/W-NNN …`, 메모만 있으면 `<<folder.ideas>>/`로 추천된다.
   - `specs/`의 기능은 `<<folder.current>>/<<file.features>>`에 한 줄씩 더해진다.
2. **진행 중인 변경의 분류를 사람에게 확인받는다.** 목록으로 보여 주고, 바꿀 것만 묻는다. 바꾼 것은 옵션으로 넘긴다 (여러 번 쓸 수 있다):
   ```bash
   lantern migrate openspec --idea "<변경 이름>" --work "<변경 이름>" --archive "<변경 이름>"
   ```
3. 승인되면 옮긴다. 문서에 커밋하지 않은 변경이 있어서 멈추면 먼저 커밋하자고 한다:
   ```bash
   lantern migrate openspec --apply
   ```
   git이 추적하는 저장소면 커밋 하나로 남고, `git revert` 한 번으로 되돌린다.
4. 결과를 확인한다:
   ```bash
   lantern check
   ```
   - 보관된 작업에는 경고가 없어야 한다.
   - 진행 중인 작업에는 "크기가 없습니다" · "연결된 할 일이 없습니다" 경고가 남는다. OpenSpec의 할 일에는 크기와 수락 기준 연결이 없기 때문이다. 그 작업을 이어서 할 때 `/l-task`로 채우면 된다고 알린다. 지금 한꺼번에 채우지 않는다.
5. 옮긴 문서에서 사람이 볼 곳을 알려 준다:
   - 문서 맨 아래 `## <<marker.migrate_bin>>` — 맞는 칸이 없어 모아 둔 내용 (OpenSpec의 Capabilities · Impact · Risks 등). 필요한 것만 맞는 칸으로 옮기고 나머지는 지워도 된다.
   - `<<file.design>>`의 "되돌리기 어려운 선택" — 비어 있다. 읽어 보고 되돌리기 어려운 결정이 있었으면 `/l-adr`로 남기자고 제안한다.
6. `<<folder.legacy>>/`에 남은 다른 문서는 그대로 둔다. 사람이 읽어 보고 옮기고 싶은 문서를 말하면 그때 `/l-template migrate "<<folder.legacy>>/<문서>.md"`로 하나씩 옮긴다.
7. 미리보기에 "OpenSpec 안내 · 명령이 남아 있는 곳"이 나왔으면 그 목록을 보여 준다. 지우지 않는다 — 계속 쓸지는 사람이 정한다.

## 공통 마무리
```bash
lantern close l-migrate [--commit]
```
