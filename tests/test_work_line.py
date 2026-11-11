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
        "3. 현재 상태/배포 · 운영/배포.md",
        "3. 현재 상태/규칙/작업 나누기 기준.md",
        "4. 운영 기록/보고/지난 보고",
    ]:
        assert (d / rel).exists(), rel
    assert not (d / "3. 현재 상태/API.md").exists()  # external server: API only when asked
    assert (d / "3. 현재 상태/배포 · 운영/서버 배포 · 운영.md").exists()  # but its keys, permissions and limits have a place
    assert not (d / "📒 부채").exists()  # no knowledge store → learning line off
    deploy = (d / "3. 현재 상태/배포 · 운영/배포.md").read_text(encoding="utf-8")
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
    assert "API.md" in plan
    assert "물을 것" in plan
    repo("scaffold", "init")
    d = docs(repo)
    assert (d / "3. 현재 상태/API.md").exists()
    repo("profile", "set", "project.clients=[]", "project.server=none")
    _, plan = repo("scaffold", "init", "--plan")
    assert "사용 안 함" in plan
    repo("scaffold", "init")
    assert meta(d / "3. 현재 상태/API.md")["status"] == "사용 안 함"
    assert meta(d / "3. 현재 상태/배포 · 운영/서버 배포 · 운영.md")["status"] == "사용 안 함"
    assert meta(d / "3. 현재 상태/배포 · 운영/배포.md")["status"] == "사용 안 함"
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
    assert "{{할 일" not in tasks_text and "W-001-T03 로그아웃 [크기:: 1h] [기준:: AC-2]" in tasks_text
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


def test_report_leaves_out_views_with_nothing_to_show(repo):
    init_project(repo)  # no knowledge store: the learning track is off
    report = docs(repo) / "4. 운영 기록/보고/현황.md"
    repo("report")
    text = report.read_text(encoding="utf-8")
    assert "## 🗂 칸반" not in text and "## 📅 타임라인" not in text and "## 📒 부채 현황" not in text
    assert "보기: —" in text and frontmatter.parse(text).meta["views"] == []

    repo("scaffold", "work", "로그인")
    repo("scaffold", "doc", "W-001", "할 일")
    tasks = work_dir(repo, "W-001") / "할 일.md"
    tasks.write_text("- [ ] W-001-T01 로그인 API — [[설계#구조]] · [[설계#화면]] [크기:: S]\n", encoding="utf-8")
    repo("report")
    text = report.read_text(encoding="utf-8")
    assert "## 🗂 칸반" in text and "## 📅 타임라인" in text and "## 📒 부채 현황" not in text
    assert "보기: 🗂 칸반, 📅 타임라인" in text
    assert "| W-001-T01 로그인 API [S] |" in text  # the card says what the task is, not where it is described


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
    current = work_dir(repo, "W-001") / "화면" / "지금"
    current.mkdir(parents=True)
    (current / "홈.png").write_bytes(b"")  # the screen before the change isn't a mockup
    _, out = repo("task", "next", "W-001")
    assert "화면 시안 없음" in out
    (work_dir(repo, "W-001") / "화면" / "홈.html").write_text("<html></html>", encoding="utf-8")
    _, out = repo("task", "next", "W-001")
    assert "▶ W-001-T02" in out
    # the mockup and its criterion come from /l-design, so they are flagged only once the design is approved
    (work_dir(repo, "W-001") / "화면" / "홈.html").unlink()
    _, out = repo("check", "--epic", "W-001")
    assert "시안과 같다" not in out and "시안이 없습니다" not in out
    repo("scaffold", "doc", "W-001", "설계")
    repo("design", "approve", "W-001", "--by", "지혁")
    _, out = repo("check", "--epic", "W-001")
    assert "시안과 같다" in out and "/l-design으로 만들어" in out


def test_close_logs_a_run(repo):
    init_project(repo)
    _, out = repo("close", "l-plan", "--work", "W-001")
    assert "MOC 갱신" in out
    line = json.loads((repo.root / ".lantern/runs.jsonl").read_text(encoding="utf-8").strip().splitlines()[-1])
    assert line["skill"] == "l-plan" and line["kind"] == "skill" and "check" in line


def test_unit_log_and_adr_and_meta(repo):
    init_project(repo)
    repo("unit-log", "add", "--what", "로그인", "--recommended", "새 작업", "--chosen", "W-001에 넣기", "--reason", "같은 화면")
    log = (docs(repo) / "3. 현재 상태/규칙/작업 나누기 기준.md").read_text(encoding="utf-8")
    assert "| 새 작업 | W-001에 넣기 | 같은 화면 |" in log
    repo("scaffold", "adr", "인증 방식")
    adr = docs(repo) / "3. 현재 상태/결정 기록/ADR-001 인증 방식.md"
    assert adr.exists()
    repo("meta", "set", str(adr), "status=채택")
    assert meta(adr)["status"] == "채택"
    code, out = repo("meta", "set", str(adr), "status=좋음", ok=False)
    assert code == 1 and "결정 상태" in out
    _, out = repo("meta", "get", "ADR-001", "status")
    assert out.strip() == '"채택"'


def test_a_blocked_idea_says_why_and_when_to_look_again_and_can_wait_for_a_competency_card(repo):
    init_project(repo)
    repo("scaffold", "idea", "HWP 표 살리기", "--raw", "표까지 살리면 좋겠다")
    code, out = repo("idea", "status", "IDEA-001", "막힘", "--reason", "표 구조를 못 읽음", ok=False)
    assert code != 0 and "--revisit" in out
    code, out = repo("debt", "promote", "IDEA-001", ok=False)
    assert code != 0 and "막힌 아이디어가 아닙니다" in out

    repo("idea", "status", "IDEA-001", "막힘", "--reason", "표 구조를 못 읽음", "--revisit", "표를 읽는 도구가 생기면")
    card = next((repo.root / "docs/1. 아이디어").glob("IDEA-001 *"))
    text = card.read_text(encoding="utf-8")
    meta = frontmatter.parse(text).meta
    assert meta["blocked_reason"] == "표 구조를 못 읽음" and meta["revisit_when"] == "표를 읽는 도구가 생기면"
    assert "🚧 막힘 — 표 구조를 못 읽음 (다시 볼 조건: 표를 읽는 도구가 생기면)" in text
    _, out = repo("idea", "find", "HWP 표")
    assert "다시 볼 조건: 표를 읽는 도구가 생기면" in out

    repo("map")
    moc = (repo.root / "docs/개발문서 MOC.md").read_text(encoding="utf-8")
    assert "### 🚧 막힘" in moc and "| 표 구조를 못 읽음 | 표를 읽는 도구가 생기면 |" in moc

    repo("debt", "promote", "IDEA-001", "표 구조 해석 직접 만들기")
    made = next((repo.root / "docs/📒 부채/카드").glob("D-001 *"))
    made_text = made.read_text(encoding="utf-8")
    assert frontmatter.parse(made_text).meta["from"] == "IDEA-001" and "이해 부채 [[" not in made_text
    assert "D-001" in card.read_text(encoding="utf-8")
    code, _ = repo("debt", "promote", "IDEA-001", ok=False)
    assert code != 0  # one card per idea

    repo("idea", "status", "IDEA-001", "검토 중")
    text = card.read_text(encoding="utf-8")
    assert frontmatter.parse(text).meta["blocked_reason"] == "" and "다시 볼 조건: 표를 읽는 도구가 생기면" in text  # the log keeps it
    repo("map")
    assert "### 🚧 막힘" not in (repo.root / "docs/개발문서 MOC.md").read_text(encoding="utf-8")


def test_check_asks_for_the_reason_of_a_blocked_idea_set_by_hand(repo):
    init_project(repo)
    repo("scaffold", "idea", "손으로 막힘", "--raw", "원문")
    card = next((repo.root / "docs/1. 아이디어").glob("IDEA-001 *"))
    card.write_text(frontmatter.set_fields(card.read_text(encoding="utf-8"), {"status": "막힘"}), encoding="utf-8")
    _, out = repo("check", str(card), ok=False)
    assert "다시 볼 조건(revisit_when)" in out


def test_upgrade_adds_the_blocked_status_to_an_older_project(repo):
    init_project(repo)
    path = repo.root / "docs/0. 템플릿/_meta/enums.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace("    막힘: {icon: 🚧, role: blocked}\n", ""), encoding="utf-8")
    repo("scaffold", "idea", "옛 아이디어", "--raw", "원문")
    repo("idea", "status", "IDEA-001", "보류")  # still works before the upgrade
    repo("map")
    _, out = repo("doctor", ok=False)
    assert "blocked" in out
    _, out = repo("upgrade")
    assert "막힘" in out
    text = path.read_text(encoding="utf-8")
    assert "    보류: {icon: 🗄, role: on_hold}\n    버림: {icon: ❌, role: dropped}\n    막힘: {icon: 🚧, role: blocked}\n" in text
    assert "■ 상세 설명" in text  # comments stay
    repo("idea", "status", "IDEA-001", "막힘", "--reason", "이유", "--revisit", "조건")


def test_task_sizes_spikes_and_the_task_rules_document(repo):
    init_project(repo)
    assert (docs(repo) / "3. 현재 상태/규칙/할 일 나누기 기준.md").exists()  # every project gets the rules /l-task follows
    rules = (docs(repo) / "3. 현재 상태/규칙/할 일 나누기 기준.md").read_text(encoding="utf-8")
    assert "`15m`" in rules and "`8h`" in rules and "${size" not in rules
    repo("scaffold", "work", "작업")
    repo("scaffold", "doc", "W-001", "할 일")
    repo("task", "add", "W-001", "결제 환불 지원 확인", "--size", "1h", "--spike")
    repo("task", "add", "W-001", "환불 API", "--after", "T01")  # no size: the middle one
    code, out = repo("task", "add", "W-001", "너무 큰 일", "--size", "2d", ok=False)
    assert code != 0 and "15m · 1h · 4h · 8h" in out
    text = (work_dir(repo, "W-001") / "할 일.md").read_text(encoding="utf-8")
    assert "- [ ] W-001-T01 [조사] 결제 환불 지원 확인 [크기:: 1h]" in text
    assert "- [ ] W-001-T02 환불 API [크기:: 4h] [먼저:: T01]" in text


def test_upgrade_apply_writes_older_sizes_with_their_new_names(repo):
    init_project(repo)
    repo("scaffold", "work", "작업")
    repo("scaffold", "doc", "W-001", "할 일")
    tasks = work_dir(repo, "W-001") / "할 일.md"
    tasks.write_text("- [ ] W-001-T01 하나 [크기:: S]\n- [ ] W-001-T02 둘 [크기:: M]\n- [x] W-001-T03 셋 [크기:: L]\n", encoding="utf-8")
    enums = docs(repo) / "0. 템플릿/_meta/enums.yaml"
    enums.write_text(
        enums.read_text(encoding="utf-8").replace("    15m: {icon: ⚪, role: xs}\n", "    15m: {icon: ⚪, role: xs}\n    S: 🟢\n"),
        encoding="utf-8",
    )
    _, out = repo("upgrade")
    assert "할 일 3개가 예전 크기 이름(S · M · L)을 씁니다" in out
    assert "[크기:: S]" in tasks.read_text(encoding="utf-8")  # nothing changes without --apply
    repo("check", str(tasks))  # the older names are still read
    repo("upgrade", "--apply")
    text = tasks.read_text(encoding="utf-8")
    assert "[크기:: 1h]" in text and "[크기:: 4h]" in text and "[크기:: 8h]" in text
    assert "    S: 🟢" not in enums.read_text(encoding="utf-8")


def test_renaming_a_size_renames_it_on_task_lines(repo):
    init_project(repo)
    repo("scaffold", "work", "작업")
    repo("scaffold", "doc", "W-001", "할 일")
    repo("task", "add", "W-001", "하나")
    repo("enums", "rename", "size", "4h", "4시간")
    assert "[크기:: 4시간]" in (work_dir(repo, "W-001") / "할 일.md").read_text(encoding="utf-8")


def test_task_add_refuses_a_prerequisite_in_another_work(repo):
    init_project(repo)
    repo("scaffold", "work", "작업")
    repo("scaffold", "doc", "W-001", "할 일")
    repo("task", "add", "W-001", "하나", "--size", "S")
    tasks = work_dir(repo, "W-001") / "할 일.md"
    before = tasks.read_text(encoding="utf-8")
    code, out = repo("task", "add", "W-001", "둘", "--size", "S", "--after", "W-002-T01", ok=False)
    assert code != 0 and "W-002-T01" in out
    assert tasks.read_text(encoding="utf-8") == before  # it must not quietly become this work's T01
    # the full ID of a task in the same work still means that task
    repo("task", "add", "W-001", "둘", "--size", "S", "--after", "W-001-T01")
    assert "W-001-T02 둘 [크기:: 1h] [먼저:: T01]" in tasks.read_text(encoding="utf-8")


def test_upgrade_apply_renames_sizes_as_an_earlier_version_named_them(repo):
    init_project(repo)
    enums = docs(repo) / "0. 템플릿/_meta/enums.yaml"  # a project made by 0.3.1, when the sizes were 반나절 · 1d
    text = enums.read_text(encoding="utf-8").replace("4h: {icon: 🟡, role: m, was: [반나절]}", "반나절: {icon: 🟡, role: m}")
    enums.write_text(text.replace("8h: {icon: 🔴, role: l, was: [1d]}", "1d: {icon: 🔴, role: l}"), encoding="utf-8")
    repo("scaffold", "work", "작업")
    repo("scaffold", "doc", "W-001", "할 일")
    tasks = work_dir(repo, "W-001") / "할 일.md"
    tasks.write_text("- [ ] W-001-T01 하나 [크기:: 반나절]\n- [ ] W-001-T02 둘 [크기:: 1d]\n", encoding="utf-8")
    _, out = repo("upgrade")
    assert "size의 '반나절'는 이제 '4h'입니다" in out and "[크기:: 반나절]" in tasks.read_text(encoding="utf-8")
    repo("upgrade", "--apply")
    text = tasks.read_text(encoding="utf-8")
    assert "[크기:: 4h]" in text and "[크기:: 8h]" in text
    assert "반나절" not in enums.read_text(encoding="utf-8")


def test_task_done_records_who_did_it_and_the_charts_tell_people_from_ai(repo):
    init_project(repo)
    repo("scaffold", "work", "작업")
    repo("scaffold", "doc", "W-001", "할 일")
    for name in ("하나", "둘", "셋"):
        repo("task", "add", "W-001", name, "--size", "1h")
    repo("task", "done", "W-001-T01", "--by", "claude-opus-5-5")
    repo("task", "done", "W-001-T02", "--by", "지혁, gpt-5.1-codex")
    repo("task", "done", "W-001-T03", "--by", "지혁")
    text = (work_dir(repo, "W-001") / "할 일.md").read_text(encoding="utf-8")
    assert "[한 사람:: claude-opus-5-5]" in text and "[한 사람:: 지혁, gpt-5.1-codex]" in text and "[한 사람:: 지혁]" in text
    plugin = docs(repo) / ".obsidian/plugins/lantern-timeline"  # the timeline plugin, there and turned on
    plugin.mkdir(parents=True)
    (plugin / "main.js").write_text("", encoding="utf-8")
    (docs(repo) / ".obsidian/community-plugins.json").write_text('["lantern-timeline"]', encoding="utf-8")
    repo("report", "--views", "timeline")
    report = (docs(repo) / "4. 운영 기록/보고/현황.md").read_text(encoding="utf-8")
    tasks = json.loads(report.split("```lantern-timeline\n")[1].split("\n```")[0])["works"][0]["tasks"]
    assert [t.get("who") for t in tasks] == ["ai", "both", "human"]
    assert tasks[1]["by"] == ["지혁", "gpt-5.1-codex"]
