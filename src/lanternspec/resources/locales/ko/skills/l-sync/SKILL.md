---
name: l-sync
description: 문서와 코드 맞추기 — lantern scan으로 주인 없는 커밋(작업 ID 없음) · 마지막 확인 커밋 이후 코드가 바뀐 오래된 문서 · 기록 없는 스키마 변경 · DBML과 마이그레이션의 어긋남 · 실패한 수락 기준 테스트를 찾고, 항목마다 기준표(무엇·왜는 문서, 어떻게는 코드, 데이터는 마이그레이션)로 고칠 방향을 추천해 사람 확인 후 맞춘다. Use after code was edited by hand or plans changed mid-work.
invocation: model
argument-hint: "[--tests]"
---

# /l-sync — 문서와 코드 맞추기

**목적:** 어긋남은 반드시 생긴다. 빨리 알아채고(스크립트), 쉽게 맞춘다(너 + 사람).

## 1. 찾기 (스크립트)
```bash
lantern scan [--tests]
```
`--tests`는 `lantern.yaml`의 `build.test`로 수락 기준 테스트까지 돌린다.

## 2. 맞추기 — 항목마다 방향을 추천하고 사람이 확인
| 내용 | 기준(원본) | 어긋나면 |
|---|---|---|
| 무엇을 · 왜 (기획 · 수락 기준) | **문서** | 코드를 고친다 → 할 일 추가 `lantern task add W-012 "<맞추기>" --size S --ac AC-n`. 의도가 바뀐 거면 문서를 먼저 고치고 `/l-adr` |
| 어떻게 (구조 · 함수 · 화면 세부) | **코드** | 문서를 코드에 맞춰 갱신 |
| 데이터 (스키마) | **마이그레이션** | DBML을 다시 맞춘다: `lantern dbml diff --sql <마이그레이션 폴더>` → `schema.dbml` 고침 → `lantern dbml render` |

- **주인 없는 변경:** 어느 작업인지 묻는다 →
  ```bash
  lantern sync adopt <커밋> --work W-012          # 그 작업의 <<file.record>>에 연결
  lantern sync adopt <커밋> --none "<이유>"        # 작업 없이 고친 것으로 기록
  ```
- **오래된 문서:** 내용을 코드에 맞춘 뒤 확인 시점을 올린다: `lantern meta set "<문서>" checked_commit=$(git rev-parse --short HEAD)`
- **기록 없는 스키마 변경:** 해당 작업 `<<file.record>>`의 `## <<section.schema>>`에 한 줄 (날짜 · 변경 · 이유 · 마이그레이션 파일). 데이터 구조 변경은 `/l-adr`도.
- **실패한 수락 기준 테스트:** 기획이 맞으면 코드를 고칠 할 일을, 기획이 낡았으면 기획 수정 + `/l-adr`.
- **할 일 여러 개가 섞인 커밋:** 참고로만 알린다 (다음부터 할 일 하나 = 커밋 하나).

기획 · 설계를 바꿀 때는 원본을 조용히 덮어쓰지 않는다: 작업 `<<file.record>>` 결정 칸에 **무엇이 바뀌었나**를 먼저 적고 합친다.

## 3. 공통 마무리
```bash
lantern scan            # 다시 확인 — 남은 것만 보고
lantern close l-sync
```
보고: 맞춘 것 · 남은 것 · 사람이 정해야 할 것.
