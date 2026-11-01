---
name: l-domain
description: 도메인 지식 찾아 읽기 — 법령 · 정책 · 업무 규칙처럼 프로젝트에 들여 둔 도메인 지식이 필요할 때, 색인(lantern ref domain)에서 그 상황에 맞는 절을 찾아 그 절만 원문으로 읽고 따른다. Use when a question, a design choice or a change depends on domain rules (law, policy, business rules) the project may hold.
invocation: model
argument-hint: "[무엇을 알아야 하나]"
---

# /l-domain — 도메인 지식 찾아 읽기

**목적:** 필요한 순간에 필요한 절만 읽고, 읽자마자 쓴다. 색인 전체나 문서 전체를 컨텍스트에 넣지 않는다.

입력: `$ARGUMENTS` — 알아야 하는 것 (비었으면 지금 대화에서 판단).

## 1. 찾기
1. 진행 중인 작업이 있으면 먼저 거기 걸린 것을 본다: `lantern ref domain --work W-012 [--task T03]`. 맞는 절이 있으면 2로.
2. 없으면 색인을 본다: `lantern ref domain`. **"언제 읽나"** 칸이 지금 상황과 맞는 절을 고른다.
   - "무엇" 칸은 주제일 뿐이다 — 그것만 보고 답하지 않는다. 규칙의 내용은 원문에만 있다.
   - 맞는 절이 없으면 지어내지 않는다: "들여 둔 도메인 지식에 없습니다"라고 말하고 사람에게 묻는다.

## 2. 읽기
```bash
lantern ref read "<주소>"
```
- 한 번에 한 절. 절이 길면 하위 절 목록이 나오니 그중 필요한 것만 읽는다.
- **📌 원문 필수:** 숫자 · 기한 · 예외를 원문 그대로 따른다. 판단을 코드나 문서로 옮기기 직전에 다시 읽는다.
- **⚠ 색인 뒤에 바뀜:** 원문을 따르고, 사람에게 `/l-ref domain`으로 색인을 고치자고 한 줄 알린다.
- 프로젝트 밖의 자료는 파일 읽기 도구로 열지 않는다. 그 경로 · 제목 · 원문을 git에 올라가는 파일(문서 · 코드 · 커밋 메시지)에 옮겨 적지 않는다.

## 3. 걸어 두기
작업 안에서 새로 읽은 절은 그 작업에 건다 — 요약 뒤에도, 다음 사람도 무엇에 기댔는지 알 수 있게:
```bash
lantern ref attach "<주소>" --work W-012 [--task T03] --note "어디에 썼는지"
```

## 공통 마무리
```bash
lantern close l-domain
```
