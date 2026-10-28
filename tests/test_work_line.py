"""The work line end to end: /l-init → idea → plan → design → task → build → current state → archive → report."""

import json

from conftest import docs, fill, fill_plan, init_project, work_dir
from lanternspec.core import frontmatter


def meta(path):
    return frontmatter.parse(path.read_text(encoding="utf-8")).meta


def test_init_creates_the_profile_structure(repo):
    init_project(repo)
    d = docs(repo)
    for rel in [
        "개발문서 MOC.md",
        "0. 템플릿/_meta/enums.yaml",
        "0. 템플릿/기획.md",
        "1. 아이디어",
        "2. 작업/보관",
        "3. 현재 상태/프로젝트 정의서.md",
        "3. 현재 상태/데이터/schema.dbml",
        "3. 현재 상태/화면/화면.md",
        "3. 현재 상태/배포.md",
        "3. 현재 상태/규칙 · 결정 기록/작업 단위 기록.md",
        "4. 운영 기록/보고/지난 보고",
    ]:
        assert (d / rel).exists(), rel
    assert not (d / "3. 현재 상태/API.md").exists()  # external server: API only when asked
    assert not (d / "📒 부채").exists()  # no knowledge store → learning line off
    deploy = (d / "3. 현재 상태/배포.md").read_text(encoding="utf-8")
    assert "## 모바일" in deploy and "## 웹" not in deploy and "lantern:if" not in deploy
    definition = (d / "3. 현재 상태/프로젝트 정의서.md").read_text(encoding="utf-8")
    assert "| 화면 유형 | 모바일 |" in definition
    assert "based_on" not in definition
    code, out = repo("check")
    assert "✖" not in out  # freshly scaffolded docs have blanks, never errors
    moc = (d / "개발문서 MOC.md").read_text(encoding="utf-8")
    assert "<!-- l-map:start -->" in moc and "| 2. 작업 |" in moc


def test_rerun_init_adds_new_docs_and_marks_unneeded(repo):
    init_project(repo)
    repo("profile", "set", "project.clients=[web]", "project.server=custom")
    _, plan = repo("scaffold", "init", "--plan")
    assert "API.md" in plan and "서버 배포 · 운영.md" in plan
    assert "물을 것" in plan
    repo("scaffold", "init")
    d = docs(repo)
    assert (d / "3. 현재 상태/API.md").exists()
    repo("profile", "set", "project.clients=[]", "project.server=none")
    _, plan = repo("scaffold", "init", "--plan")
    assert "사용 안 함" in plan
    repo("scaffold", "init")
    assert meta(d / "3. 현재 상태/API.md")["status"] == "사용 안 함"
    assert meta(d / "3. 현재 상태/배포.md")["status"] == "사용 안 함"
    # never deleted, and switching back re-enables
    repo("profile", "set", "project.server=custom")
    repo("scaffold", "init")
    assert meta(d / "3. 현재 상태/API.md")["status"] == "사용"


def test_profile_set_refuses_docs_remote(repo):
    init_project(repo)
    code, out = repo("profile", "set", "docs.remote=local", ok=False)
    assert code == 1 and "docs-mode" in out


def test_idea_capture_dedupe_and_status_flow(repo):
    init_project(repo)
    repo("scaffold", "idea", "카카오 로그인", "--kind", "기능", "--raw", "로그인할 때 카톡으로도 되면 좋겠다")
    _, out = repo("idea", "find", "카톡 로그인")
    assert "IDEA-001 카카오 로그인" in out
    _, out = repo("idea", "find", "다크 모드")
    assert "겹치는 아이디어 없음" in out
    code, out = repo("idea", "status", "IDEA-001", "버림", ok=False)
    assert code == 1 and "이유" in out
    repo("idea", "status", "IDEA-001", "버림", "--reason", "카카오 심사가 오래 걸림")
    _, out = repo("idea", "find", "카카오")
    assert "버린 이유: 카카오 심사가 오래 걸림" in out
    code, _ = repo("idea", "status", "IDEA-001", "아무거나", ok=False)
    assert code == 1
    idea = next((docs(repo) / "1. 아이디어").glob("IDEA-001*"))
    text = idea.read_text(encoding="utf-8")
    assert "> 로그인할 때 카톡으로도 되면 좋겠다" in text
    assert "❌ 버림 — 카카오 심사가 오래 걸림" in text


def test_auto_capture_is_marked(repo):
    init_project(repo)
    repo("scaffold", "idea", "다크 모드", "--auto")
    idea = next((docs(repo) / "1. 아이디어").glob("IDEA-001*"))
    assert "🤖 자동 기록" in idea.read_text(encoding="utf-8")
    assert meta(idea)["auto"] is True


def test_full_work_line(repo):
    init_project(repo)
    d = docs(repo)
    # idea → plan
    repo("scaffold", "idea", "카카오 로그인", "--raw", "카톡 로그인")
    repo("idea", "status", "IDEA-001", "검토 중")
    repo("scaffold", "work", "카카오 로그인", "--idea", "IDEA-001", "--ui")
    repo("idea", "status", "IDEA-001", "작업됨", "--work", "W-001")
    w = work_dir(repo, "W-001")
    assert (w / "화면").is_dir()
    plan = fill_plan(repo, "W-001")
    assert meta(plan)["links"] == ["[[1. 아이디어/IDEA-001 카카오 로그인]]"]
    _, out = repo("check", "--epic", "W-001")
    assert "⚠" not in out
    # design + gate
    repo("scaffold", "doc", "W-001", "설계")
    design = w / "설계.md"
    fill(
        design,
        [("// {{변경되는 테이블}}", "Table users {\n  id int [pk]\n  kakao_id varchar [unique, note: '카카오 회원 번호. 예: 123']\n}")],
    )
    _, out = repo("check-dbml", str(design))
    assert "✔ DBML" in out
    repo("design", "approve", "W-001", "--by", "지혁")
    assert meta(design)["approved"].endswith("지혁")
    # tasks
    repo("scaffold", "doc", "W-001", "할 일")
    repo("task", "add", "W-001", "users.kakao_id 추가", "--size", "S", "--ac", "AC-1")
    repo("task", "add", "W-001", "카카오 버튼", "--size", "M", "--ac", "AC-1", "--after", "T01", "--screen", "로그인")
    _, out = repo("check", str(w / "할 일.md"))
    assert "AC-2에 연결된 할 일이 없습니다" in out
    repo("task", "add", "W-001", "로그아웃", "--size", "S", "--ac", "AC-2")
    tasks_text = (w / "할 일.md").read_text(encoding="utf-8")
    assert "{{할 일" not in tasks_text and "W-001-T03 로그아웃 [크기:: S] [기준:: AC-2]" in tasks_text
    repo("work", "stage", "W-001", "할 일")
    assert meta(plan)["status"] == "할 일"
    # build loop
    _, out = repo("task", "next", "W-001", "--json")
    assert json.loads(out)["task"] == "W-001-T01"
    repo("task", "start", "W-001-T01")
    assert meta(plan)["status"] == "구현"
    _, out = repo("task", "next", "W-001")
    assert "W-001-T01" in out  # started but not done: still the next one
    repo("task", "done", "W-001-T01")
    _, out = repo("task", "next", "W-001")
    assert "W-001-T02" in out
    _, out = repo("task", "done", "W-001-T02")
    assert "AC 체크포인트: AC-1" in out
    repo("task", "ac", "W-001", "AC-1")
    _, out = repo("task", "done", "W-001-T03")
    assert "AC 체크포인트: AC-2" in out and "모두 끝냈습니다" in out
    _, out = repo("task", "next", "W-001")
    assert "모든 할 일 완료" in out
    line = (w / "할 일.md").read_text(encoding="utf-8")
    assert "- [x] W-001-T01" in line and "[시작:: " in line and "[완료:: " in line
    # pack
    repo("scaffold", "doc", "W-001", "기록")
    _, out = repo("pack", "W-001")
    pack = (repo.root / ".lantern/pack/W-001.md").read_text(encoding="utf-8")
    assert "모든 할 일 완료" in pack and "카카오 계정으로 로그인한다" in pack and "[!guide]" not in pack
    assert "schema.dbml" in pack
    # report
    _, out = repo("report", "--views", "kanban,timeline,domain,trace,sync")
    report = (d / "4. 운영 기록/보고/현황.md").read_text(encoding="utf-8")
    assert "✅ 완료 (3)" in report and "gantt" in report and "| 인증 |" in report and "IDEA-001" in report
    repo("report", "--summary", "W-001 끝", "위험 없음", "다음 W-002")
    report = (d / "4. 운영 기록/보고/현황.md").read_text(encoding="utf-8")
    assert "1. W-001 끝" in report and "3. 다음 W-002" in report
    repo("report")  # without --summary the last summary stays
    assert "1. W-001 끝" in (d / "4. 운영 기록/보고/현황.md").read_text(encoding="utf-8")
    # archive rewrites links (the idea links to the work)
    repo("work", "archive", "W-001")
    archived = d / "2. 작업/보관/W-001 카카오 로그인"
    assert archived.exists() and meta(archived / "기획.md")["status"] == "완료"
    idea = next((d / "1. 아이디어").glob("IDEA-001*")).read_text(encoding="utf-8")
    assert "[[2. 작업/보관/W-001 카카오 로그인/기획|W-001]]" in idea
    _, out = repo("check")
    assert "깨진 링크" not in out
    # status / map
    _, out = repo("status")
    assert "진행 중: 없음" in out
    repo("map")
    moc = (d / "개발문서 MOC.md").read_text(encoding="utf-8")
    assert "보관된 작업" in moc and "W-001 카카오 로그인" in moc


def test_plan_without_idea_creates_the_card(repo):
    init_project(repo)
    repo("scaffold", "idea", "바로 기획", "--status", "작업됨", "--raw", "설명")
    repo("scaffold", "work", "바로 기획", "--idea", "IDEA-001")
    repo("idea", "status", "IDEA-001", "작업됨", "--work", "W-001")
    assert "W-001" in str(meta(next((docs(repo) / "1. 아이디어").glob("IDEA-001*")))["links"])


def test_report_compares_with_the_previous_day(repo):
    init_project(repo)
    past = docs(repo) / "4. 운영 기록/보고/지난 보고"
    past.mkdir(parents=True, exist_ok=True)
    (past / "2000-01-01.md").write_text(
        frontmatter.render({"type": "report", "generated": True, "stats": {"tasks_done": 0, "debt_total": 0, "debt_resolved": 0}}, "old"),
        encoding="utf-8",
    )
    repo("scaffold", "work", "작업")
    repo("scaffold", "doc", "W-001", "할 일")
    repo("task", "add", "W-001", "하나", "--size", "S")
    repo("task", "done", "W-001-T01")
    repo("report", "--views", "kanban")
    text = (docs(repo) / "4. 운영 기록/보고/현황.md").read_text(encoding="utf-8")
    assert "지난 보고(2000-01-01) 대비: ✅ 완료한 할 일 **+1**" in text


def test_task_dependencies_unknowns_and_mockup_gate(repo):
    init_project(repo)
    repo("profile", "set", "plan.ui_reference=required")
    repo("scaffold", "work", "화면 작업", "--ui")
    repo("scaffold", "doc", "W-001", "할 일")
    repo("task", "add", "W-001", "모르는 일", "--size", "S", "--unknown")
    repo("task", "add", "W-001", "화면", "--size", "M", "--screen", "홈")
    repo("task", "add", "W-001", "뒤 일", "--size", "S", "--after", "T02")
    _, out = repo("task", "next", "W-001")
    assert "지금 시작할 수 있는 할 일이 없습니다" in out
    assert "W-001-T01: ❓ 확인 필요" in out and "화면 시안 없음" in out and "W-001-T02 먼저" in out
    (work_dir(repo, "W-001") / "화면" / "홈.html").write_text("<html></html>", encoding="utf-8")
    _, out = repo("task", "next", "W-001")
    assert "▶ W-001-T02" in out
    # ui work without a "시안과 같다" criterion is flagged
    _, out = repo("check", "--epic", "W-001")
    assert "시안과 같다" in out


def test_close_logs_a_run(repo):
    init_project(repo)
    _, out = repo("close", "l-plan", "--work", "W-001")
    assert "MOC 갱신" in out
    line = json.loads((repo.root / ".lantern/runs.jsonl").read_text(encoding="utf-8").strip().splitlines()[-1])
    assert line["skill"] == "l-plan" and line["kind"] == "skill" and "check" in line


def test_unit_log_and_adr_and_meta(repo):
    init_project(repo)
    repo("unit-log", "add", "--what", "로그인", "--recommended", "새 작업", "--chosen", "W-001에 넣기", "--reason", "같은 화면")
    log = (docs(repo) / "3. 현재 상태/규칙 · 결정 기록/작업 단위 기록.md").read_text(encoding="utf-8")
    assert "| 새 작업 | W-001에 넣기 | 같은 화면 |" in log
    repo("scaffold", "adr", "인증 방식")
    adr = docs(repo) / "3. 현재 상태/규칙 · 결정 기록/ADR-001 인증 방식.md"
    assert adr.exists()
    repo("meta", "set", str(adr), "status=채택")
    assert meta(adr)["status"] == "채택"
    code, out = repo("meta", "set", str(adr), "status=좋음", ok=False)
    assert code == 1 and "결정 상태" in out
    _, out = repo("meta", "get", "ADR-001", "status")
    assert out.strip() == '"채택"'
