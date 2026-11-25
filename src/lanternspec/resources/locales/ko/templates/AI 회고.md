---
id: ${id}
type: report
status: ${current_status.active}
created: ${today}
updated: ${today}
links: []
template: AI 회고
template_version: 1.1.0
based_on: 1.1.0
month: ${month}
---
# 🔁 AI 회고 — ${month}

> [!abstract] 한눈에 보기
> 자율 반복이 끝날 때마다, 첫 시도에 통과하지 못한 수락 기준(또는 검증)을 한 줄씩 쌓는다.
> 사실 칸(시각 · 작업 · 시도 · 결과 · 실행)은 lantern이 쓰고, 판단 칸(약점 · 보완 · 가설 · 제안)은 AI가 `lantern retro judge`로 채우고, 확인은 사람이 주 1회 `lantern retro review`로 한다.
> 구현하다 AI가 막힌 것(`[막힘:: …]`)은 반복이 없어도 AI가 `lantern retro note`로 적는다.

## 요약
> [!guide]- 🔁 업데이트 구역 — 매번 새로 씀: 요약
> **덮어쓰는 칸.** 줄이 더해지거나 확인될 때마다 lantern이 줄 수 · 약점 · 보완의 합계로 새로 쓴다. 손으로 고치지 않는다.

<!-- lantern:template-only -->
## 변경 기록
| 버전 | 날짜 | 무엇이 바뀌었나 |
|---|---|---|
| 1.0.0 | 2026-11-19 | 기본 양식 |
| 1.1.0 | 2026-11-25 | AI가 막힌 줄(`lantern retro note`)의 설명을 더함 |
