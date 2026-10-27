---
id: CUR-api
type: current
status: ${current_status.active}
created: ${today}
updated: ${today}
links: []
template: API
template_version: 1.0.0
based_on: 1.0.0
code: []
checked_commit: ""
---
# 📘 API

> [!abstract] 한눈에 보기
> {{API 형태와 인증 방식 한 문장 (필수)}}

> [!guide] 어떻게(엔드포인트 세부)는 **코드가 기준**이다. 코드에서 뽑을 수 있으면(OpenAPI 등) 생성물 링크를 걸고, 여기에는 목록과 규칙만 둔다.

## 공통 규칙
- 인증: {{인증 방식}}
- 오류 형식: {{오류 형식}}

## 엔드포인트
| 메서드 | 경로 | 하는 일 | 출처 작업 |
|---|---|---|---|
| {{GET}} | `{{/path}}` | {{하는 일}} | {{작업 링크}} |

<!-- lantern:template-only -->
## 변경 기록
| 버전 | 날짜 | 무엇이 바뀌었나 |
|---|---|---|
| 1.0.0 | 2026-10-27 | 기본 양식 |
