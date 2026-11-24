"""Connecting Notion as the knowledge store: `lantern knowledge setup notion`, the Keychain it stores the token in, and the token lookup.

The wizard never receives the token: on a Mac the Keychain tool asks for it itself. Everything outside the wizard (the terminal, the
Keychain, the browser, Notion) is replaced here, so these tests touch no real Keychain and no network.
"""

import subprocess
from pathlib import Path
from typing import Any

import pytest

from conftest import init_project
from lanternspec.core import profile as pm
from lanternspec.core.project import Project
from lanternspec.learn.knowledge import Hit, KnowledgeError, keychain, notion, notion_setup
from lanternspec.learn.knowledge.notion import NotionError

TOKEN = "secret-token-value"
PAGE = "124791d2c4e380b086defba8b13fd766"
PAGE_URL = f"https://www.notion.so/me/Notes-{PAGE}?pvs=4"


# --------------------------------------------------------------------------- the Keychain tool


class FakeSecurity:
    """Stands in for `subprocess.run` of the `security` command."""

    def __init__(self, stored: str | None = TOKEN, code: int = 0) -> None:
        self.stored = stored
        self.code = code
        self.calls: list[list[str]] = []
        self.kwargs: list[dict[str, Any]] = []

    def __call__(self, cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        self.calls.append(cmd)
        self.kwargs.append(kwargs)
        out = (self.stored + "\n") if (self.stored and "-w" in cmd and cmd[1] == "find-generic-password") else ""
        return subprocess.CompletedProcess(cmd, self.code, stdout=out, stderr="")


@pytest.fixture
def mac(monkeypatch):
    monkeypatch.setattr(keychain, "TOOL", "security")
    monkeypatch.setattr(keychain, "available", lambda: True)
    monkeypatch.setattr(keychain, "account", lambda: "jihyeok")
    fake = FakeSecurity()
    monkeypatch.setattr(keychain.subprocess, "run", fake)
    return fake


def test_the_keychain_is_asked_for_a_service_under_the_users_account(mac):
    assert keychain.read("NOTION_TOKEN") == TOKEN
    assert mac.calls == [["security", "find-generic-password", "-a", "jihyeok", "-s", "NOTION_TOKEN", "-w"]]


def test_a_missing_item_or_a_failed_tool_reads_as_no_token(mac):
    mac.code = 44
    assert keychain.read("NOTION_TOKEN") is None
    mac.code, mac.stored = 0, "  \n"
    assert keychain.read("NOTION_TOKEN") is None


def test_storing_lets_the_tool_ask_for_the_token_itself(mac):
    assert keychain.store("NOTION_TOKEN") is True

    (cmd,) = mac.calls
    assert cmd == ["security", "add-generic-password", "-U", "-a", "jihyeok", "-s", "NOTION_TOKEN", "-w"]  # -w last, no value: it asks
    assert TOKEN not in " ".join(cmd)
    assert "capture_output" not in mac.kwargs[0] and "stdout" not in mac.kwargs[0]  # it talks to the person's terminal directly
    mac.code = 1
    assert keychain.store("NOTION_TOKEN") is False


def test_deleting_an_item(mac):
    assert keychain.delete("NOTION_TOKEN") is True
    assert mac.calls[-1][:2] == ["security", "delete-generic-password"]


def test_off_a_mac_the_keychain_is_never_touched(monkeypatch):
    monkeypatch.setattr(keychain.sys, "platform", "linux")
    ran: list[Any] = []
    monkeypatch.setattr(keychain.subprocess, "run", lambda *a, **k: ran.append(a))
    assert keychain.available() is False
    assert keychain.read("X") is None and keychain.store("X") is False and keychain.delete("X") is False
    assert ran == []


def test_a_tool_that_cannot_run_reads_as_no_token(monkeypatch):
    monkeypatch.setattr(keychain, "available", lambda: True)

    def broken(*a: Any, **k: Any) -> Any:
        raise OSError("no such tool")

    monkeypatch.setattr(keychain.subprocess, "run", broken)
    assert keychain.read("NOTION_TOKEN") is None


# --------------------------------------------------------------------------- where the token comes from


class FakeKeychain:
    """The same four calls as the keychain module, with a token kept in memory."""

    def __init__(self, token: str | None = None, on_mac: bool = True, typed: list[str] | None = None, store_ok: bool = True) -> None:
        self.token, self.on_mac, self.store_ok = token, on_mac, store_ok
        self.typed = list(typed) if typed is not None else [TOKEN]  # what the person will type at the Keychain's prompt, in order
        self.stored: list[str] = []
        self.deleted: list[str] = []

    def available(self) -> bool:
        return self.on_mac

    def read(self, service: str) -> str | None:
        return self.token

    def store(self, service: str) -> bool:
        self.stored.append(service)
        if self.store_ok:
            self.token = self.typed.pop(0) if self.typed else TOKEN
        return self.store_ok

    def delete(self, service: str) -> bool:
        self.deleted.append(service)
        self.token = None
        return True


def test_the_keychain_comes_before_the_environment_variable():
    kc = FakeKeychain(token="from-keychain")
    assert notion.notion_token("NOTION_TOKEN", kc, {"NOTION_TOKEN": "from-env"}) == "from-keychain"  # an old variable can't hide it
    assert notion.notion_token("NOTION_TOKEN", FakeKeychain(), {"NOTION_TOKEN": "from-env"}) == "from-env"  # off a Mac, or nothing stored
    assert notion.notion_token("NOTION_TOKEN", FakeKeychain(), {}) is None
    assert notion.notion_token("NOTION_TOKEN", FakeKeychain(), {"NOTION_TOKEN": "  "}) is None  # a blank variable counts as none


def test_the_adapter_made_from_the_settings_finds_the_token_in_the_keychain(monkeypatch):
    monkeypatch.delenv("NOTION_TOKEN", raising=False)
    monkeypatch.setattr(notion.keychain, "read", lambda service: "kc-token" if service == "NOTION_TOKEN" else None)
    monkeypatch.setattr(notion.keychain, "available", lambda: True)

    assert notion.from_config({"path": "abc"}).token == "kc-token"
    monkeypatch.setenv("NOTION_TOKEN", "old-variable")
    assert notion.from_config({"path": "abc"}).token == "kc-token"  # a variable left in a shell file does not hide the new token
    with pytest.raises(KnowledgeError):
        notion.from_config({"path": "abc", "token_env": "ANOTHER_NAME"})  # the keychain item is named by token_env


# --------------------------------------------------------------------------- the wizard


class ScriptedIo:
    """The terminal: answers come from a list, and everything said is kept."""

    def __init__(self, answers: list[str]) -> None:
        self.answers = list(answers)
        self.prompts: list[str] = []
        self.said: list[str] = []
        self.opened: list[str] = []

    def ask(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if not self.answers:
            raise EOFError
        answer = self.answers.pop(0)
        if answer == "<ctrl-c>":
            raise KeyboardInterrupt
        return answer

    def say(self, text: str) -> None:
        self.said.append(text)

    def open_url(self, url: str) -> bool:
        self.opened.append(url)
        return True

    @property
    def out(self) -> str:
        return "\n".join([*self.said, *self.prompts])


class FakeNotion:
    """What the wizard needs of a Notion connection."""

    def __init__(
        self, token: str, counts: list[int] | None = None, rejects: frozenset[str] = frozenset(), visible: set[str] | None = None
    ) -> None:
        self.token = token
        self.counts = counts if counts is not None else [3]
        self.rejects = rejects
        self.visible = {PAGE} if visible is None else visible

    def overview(self, newest: int = 5) -> tuple[int, list[str]]:
        if self.token in self.rejects:
            raise NotionError("Notion API error 401: unauthorized", 401)
        n = self.counts.pop(0) if len(self.counts) > 1 else self.counts[0]
        return n, ["모니터링", "FastAPI", "회고"][:n]

    def can_see(self, ref: str) -> bool:
        return notion.page_id(ref) in self.visible

    def search(self, query: str, aliases: list[str] | None = None, limit: int = 5) -> list[Hit]:
        return [Hit(title=query, path="https://www.notion.so/x", summary="", updated="2026-11-24", score=100)]


def _run(project: Project, io: ScriptedIo, kc: FakeKeychain, env: dict[str, str] | None = None, notion_fake: Any = None, **kw: Any) -> int:
    return notion_setup.run(
        project, io, store=kc, make_adapter=notion_fake or (lambda token, state: FakeNotion(token)), env=env or {}, **kw
    )  # fmt: skip


def _project(repo) -> Project:
    init_project(repo)
    return Project.load(repo.root)


def test_the_whole_way_on_a_mac_stores_the_token_in_the_keychain_and_writes_the_settings(repo):
    project = _project(repo)
    io, kc = ScriptedIo(["1", "", PAGE_URL]), FakeKeychain()

    assert _run(project, io, kc) == 0

    knowledge = Project.load(repo.root).profile.knowledge
    assert knowledge["type"] == "notion" and knowledge["path"] == PAGE and knowledge["write"] == "propose_only"
    assert kc.stored == ["NOTION_TOKEN"] and io.opened == [notion_setup.INTEGRATIONS_URL]
    assert TOKEN not in io.out  # nothing here ever held the token
    assert "3" in io.out and "모니터링" in io.out  # how many pages the integration sees, and the newest ones


def test_the_permissions_to_turn_on_depend_on_whether_notes_are_written(repo):
    project = _project(repo)
    read_only, writing = ScriptedIo(["1", "", PAGE_URL]), ScriptedIo(["2", "", PAGE_URL])
    _run(project, read_only, FakeKeychain())
    _run(project, writing, FakeKeychain())

    assert "켤 것: 콘텐츠 읽기\n" in "\n".join(read_only.said) + "\n" and "켤 것: 콘텐츠 읽기 · 콘텐츠 삽입" not in read_only.out
    assert "켤 것: 콘텐츠 읽기 · 콘텐츠 삽입" in writing.out
    assert "끌 것: 콘텐츠 업데이트 · 콘텐츠 삽입" in read_only.out  # insert is turned off when notes are not written
    assert "끌 것: 콘텐츠 업데이트 · 댓글" in writing.out and "끌 것: 콘텐츠 업데이트 · 콘텐츠 삽입" not in writing.out
    assert Project.load(repo.root).profile.knowledge["write"] == "direct"


def test_a_token_that_is_already_stored_is_kept_when_the_person_says_so(repo):
    project = _project(repo)
    io, kc = ScriptedIo(["1", "y", PAGE_URL]), FakeKeychain(token=TOKEN)

    assert _run(project, io, kc, notion_fake=lambda token, state: FakeNotion(token)) == 0
    assert kc.stored == []  # not asked for again


def test_a_token_that_notion_does_not_accept_can_be_entered_again(repo):
    project = _project(repo)
    io, kc = ScriptedIo(["1", "", "y", "", PAGE_URL]), FakeKeychain(typed=["wrong", TOKEN])  # Enter, "enter another?" y, Enter, page

    code = _run(project, io, kc, notion_fake=lambda token, state: FakeNotion(token, rejects=frozenset({"wrong"})))

    assert code == 0 and kc.stored == ["NOTION_TOKEN", "NOTION_TOKEN"]  # asked twice: the second one is accepted
    assert "401" in io.out and "wrong" not in io.out  # the error is shown, the token is not


def test_a_token_that_stays_rejected_stops_without_touching_the_settings(repo):
    project = _project(repo)
    reject_all = lambda token, state: FakeNotion(token, rejects=frozenset({"wrong", TOKEN}))  # noqa: E731

    declined = _run(project, ScriptedIo(["1", "", "n"]), FakeKeychain(), notion_fake=reject_all)
    twice = _run(project, ScriptedIo(["1", "", "y"]), FakeKeychain(typed=["wrong", "wrong"]), notion_fake=reject_all)

    assert declined == 1 and twice == 1  # the second wrong token is not asked about again
    assert Project.load(repo.root).profile.knowledge is None


def test_an_integration_that_sees_no_page_is_told_how_to_connect_one_and_asked_again(repo):
    project = _project(repo)
    io = ScriptedIo(["1", "", "", PAGE_URL])  # the third answer is "Enter" after connecting a page

    assert _run(project, io, FakeKeychain(), notion_fake=lambda token, state: FakeNotion(token, counts=[0, 3])) == 0
    assert "Add connections" in io.out or "연결 추가" in io.out


def test_a_parent_page_the_integration_cannot_see_is_explained_and_can_be_corrected(repo):
    project = _project(repo)
    other = "0123456789abcdef0123456789abcdef"
    io = ScriptedIo(["1", "", f"https://www.notion.so/Other-{other}", "y", PAGE_URL])

    assert _run(project, io, FakeKeychain()) == 0
    assert Project.load(repo.root).profile.knowledge["path"] == PAGE
    assert "Add connections" in io.out or "연결 추가" in io.out


def test_something_that_is_not_a_page_address_is_asked_for_again(repo):
    project = _project(repo)
    io = ScriptedIo(["1", "", "아무 말", PAGE_URL])
    assert _run(project, io, FakeKeychain()) == 0


def test_without_a_lantern_yaml_it_prints_the_values_for_init_instead_of_creating_one(repo):
    project = Project.load(repo.root)  # no `lantern.yaml` yet: /l-init has not run
    assert not project.profile.exists
    io = ScriptedIo(["1", "", PAGE_URL])

    assert _run(project, io, FakeKeychain()) == 0

    assert not (repo.root / "lantern.yaml").exists()
    assert f"--knowledge {PAGE} --knowledge-type notion --knowledge-write propose_only" in io.out


def test_off_a_mac_it_checks_the_environment_variable_instead_of_the_keychain(repo):
    project = _project(repo)
    kc = FakeKeychain(on_mac=False)

    ok = _run(project, ScriptedIo(["1", "y", PAGE_URL]), kc, env={"NOTION_TOKEN": TOKEN})  # "y": use the token from the variable
    missing = ScriptedIo(["1"])
    stopped = _run(project, missing, kc, env={})

    assert ok == 0 and kc.stored == []
    assert stopped == 1 and "export NOTION_TOKEN=" in missing.out  # the person adds the variable, then runs it again


def test_stopping_with_ctrl_c_or_a_closed_input_leaves_the_settings_alone(repo):
    project = _project(repo)
    assert _run(project, ScriptedIo(["1", "", "<ctrl-c>"]), FakeKeychain()) == 1
    assert _run(project, ScriptedIo(["1", ""]), FakeKeychain()) == 1  # the input ends at the page question
    assert Project.load(repo.root).profile.knowledge is None


def test_the_keychain_tool_failing_stops_the_wizard(repo):
    project = _project(repo)
    io = ScriptedIo(["1", ""])
    assert _run(project, io, FakeKeychain(store_ok=False)) == 1
    assert Project.load(repo.root).profile.knowledge is None


def test_other_settings_of_the_knowledge_block_are_kept(repo):
    project = _project(repo)
    data = pm.load(repo.root).data
    data["knowledge"] = {"type": "notion", "path": "old", "write": "direct", "token_env": "MY_TOKEN"}
    pm.save(repo.root, data)
    project = Project.load(repo.root)

    assert _run(project, ScriptedIo(["1", "", PAGE_URL]), FakeKeychain(), env={}) == 0

    knowledge = Project.load(repo.root).profile.knowledge
    assert knowledge["token_env"] == "MY_TOKEN" and knowledge["path"] == PAGE


# --------------------------------------------------------------------------- the command


def test_the_command_refuses_to_run_without_a_terminal_and_says_where_to_run_it(repo):
    init_project(repo)
    code, out = repo("knowledge", "setup", "notion", ok=False)  # the test's input is not a terminal, like an AI tool's shell

    assert code != 0 and "터미널" in out
    assert "lantern knowledge setup notion" in out


def test_only_notion_has_a_setup(repo):
    init_project(repo)
    code, out = repo("knowledge", "setup", "obsidian", ok=False)
    assert code != 0 and "notion" in out.lower()


def test_doctor_counts_a_token_in_the_keychain(repo, monkeypatch):
    init_project(repo)
    data = pm.load(repo.root).data
    data["knowledge"] = {"type": "notion", "path": PAGE, "write": "propose_only"}
    pm.save(repo.root, data)
    monkeypatch.delenv("NOTION_TOKEN", raising=False)

    _, without = repo("doctor", ok=False)
    monkeypatch.setattr(notion.keychain, "read", lambda service: TOKEN)
    monkeypatch.setattr(notion.keychain, "available", lambda: True)
    _, with_it = repo("doctor", ok=False)

    assert "NOTION_TOKEN" in without and "없습니다" in without
    assert "있음" in with_it and TOKEN not in with_it


def test_the_overview_and_the_page_check_of_the_real_adapter(monkeypatch):
    from lanternspec.learn.knowledge.notion import NotionAdapter

    def _page(pid: str, edited: str, title: str) -> dict[str, Any]:
        return {
            "id": pid,
            "url": f"u/{pid}",
            "last_edited_time": edited,
            "properties": {"t": {"type": "title", "title": [{"plain_text": title}]}},
        }

    pages = [_page("a", "2026-11-01T00:00:00Z", "오래된"), _page("b", "2026-11-20T00:00:00Z", "최근")]

    class Opener:
        def __call__(self, req: Any) -> Any:
            import json as _json

            data = {"results": pages, "has_more": False} if req.full_url.endswith("/search") else {}
            if "/pages/" in req.full_url and PAGE not in req.full_url:
                import io
                import urllib.error

                raise urllib.error.HTTPError(req.full_url, 404, "nf", {}, io.BytesIO(b"{}"))  # type: ignore[arg-type]

            class Resp:
                def read(self_inner) -> bytes:
                    return _json.dumps(data).encode()

                def __enter__(self_inner) -> "Resp":
                    return self_inner

                def __exit__(self_inner, *a: Any) -> bool:
                    return False

            return Resp()

    adapter = NotionAdapter("p", "t", opener=Opener())

    assert adapter.overview(newest=1) == (2, ["최근"])  # the newest edited first
    assert adapter.can_see(PAGE) is True and adapter.can_see("0" * 32) is False


def test_the_state_folder_is_used_when_the_project_has_settings(repo, tmp_path):
    project = _project(repo)
    seen: list[Path | None] = []

    def notion_for(token: str, state: Path | None) -> FakeNotion:
        seen.append(state)
        return FakeNotion(token)

    _run(project, ScriptedIo(["1", "", PAGE_URL]), FakeKeychain(), notion_fake=notion_for)
    assert seen and seen[0] == project.state  # so the first search afterwards is already warm


def test_init_sends_notion_to_the_setup_command_and_never_asks_the_ai_to_handle_the_token():
    from lanternspec.tools.skills import load_sources

    for language in ("ko", "en"):
        init = next(s for s in load_sources(language) if s.name == "l-init")
        assert "lantern knowledge setup notion" in init.body, language
        assert "--knowledge-type obsidian|folder|notion" in init.body, language
        assert "Notion" in init.body.split("5.", 1)[1].splitlines()[0], language  # it is a choice of question 5


# --------------------------------------------------------------------------- how it reads on a terminal


def _whole_run(repo, answers: list[str]) -> ScriptedIo:
    io = ScriptedIo(answers)
    _run(_project(repo), io, FakeKeychain(token=None))
    return io


def test_the_steps_are_numbered_in_order_and_every_prompt_is_marked(repo):
    io = _whole_run(repo, ["1", "", PAGE_URL])
    said = [line for line in io.said if line.startswith("[")]

    assert [line.split("]")[0] for line in said] == ["[1/4", "[2/4", "[3/4", "[4/4"]
    assert all(prompt.startswith("▶ ") for prompt in io.prompts)  # what to type is always on a line that begins with ▶


def test_the_page_count_is_said_to_be_only_a_check_and_the_page_question_says_what_to_do(repo):
    io = _whole_run(repo, ["1", "", PAGE_URL])
    text = "\n".join(io.said)

    assert "확인일 뿐" in text and "더 연결하지 않아도" in text  # nothing more has to be connected to go on
    before, after = text.split("[4/4]")
    assert "확인일 뿐" in before and "링크 복사" in after  # how to get the link is told under its own step heading
    assert "지금 정해 둡니다" in after or "정해 둡니다" in after  # and why it is asked while writing drafts only


def test_the_stored_token_question_says_what_yes_and_no_mean(repo):
    io = ScriptedIo(["1", "y", PAGE_URL])
    _run(_project(repo), io, FakeKeychain(token=TOKEN))
    prompt = next(p for p in io.prompts if "[Y/n]" in p)

    assert "Y =" in prompt and "n =" in prompt


def test_no_line_is_wider_than_a_terminal_can_show_without_breaking(repo):
    from lanternspec.core.textwidth import cells

    io = _whole_run(repo, ["2", "", PAGE_URL])
    for line in io.said:
        if "http" in line or "export " in line or "--knowledge" in line:
            continue  # an address and a command are not broken up
        assert cells(line) <= 78, (cells(line), line)


def test_long_page_titles_are_cut_and_each_is_on_its_own_line(repo):
    long_title = "아주 긴 제목의 페이지입니다 " * 5

    class LongTitles(FakeNotion):
        def overview(self, newest: int = 5) -> tuple[int, list[str]]:
            return 445, [long_title, "짧은 제목", "FastAPI"][:newest]

    io = ScriptedIo(["1", "", PAGE_URL])
    _run(_project(repo), io, FakeKeychain(), notion_fake=lambda token, state: LongTitles(token))

    bullets = [line for line in io.said if line.startswith("     · ")]
    assert len(bullets) == 3 and bullets[0].endswith("…") and bullets[2].endswith("FastAPI")


def test_the_token_warning_is_marked_so_it_stands_out(repo):
    from lanternspec.cli.color import paint

    mac = _whole_run(repo, ["1", "", PAGE_URL])
    other = ScriptedIo(["1", "y", PAGE_URL])
    _run(_project(repo), other, FakeKeychain(on_mac=False), env={"NOTION_TOKEN": TOKEN})

    for io in (mac, other):
        warning = io.said[1:3]  # right under the title, before anything is asked
        assert all(line.startswith("⚠ ") for line in warning), warning
        assert "대화에는" in warning[1]
        assert all(paint(line) != line for line in warning)  # on a terminal the whole line is colored


# --------------------------------------------------------------------------- an old environment variable next to a new keychain token


def test_both_places_are_told_apart():
    kc = FakeKeychain(token="in-keychain")
    assert notion.token_sources("NOTION_TOKEN", kc, {"NOTION_TOKEN": "in-env"}) == ("in-env", "in-keychain")
    assert notion.token_sources("NOTION_TOKEN", kc, {}) == (None, "in-keychain")
    assert notion.token_sources("NOTION_TOKEN", FakeKeychain(), {"NOTION_TOKEN": " "}) == (None, None)


def test_an_old_variable_does_not_get_in_the_way_of_a_new_keychain_token(repo):
    project = _project(repo)
    checked: list[str] = []

    def notion_for(token: str, state: Any) -> FakeNotion:
        checked.append(token)
        return FakeNotion(token, rejects=frozenset({"old"}))

    io, kc = ScriptedIo(["1", "n", "", PAGE_URL]), FakeKeychain(token="old", typed=["new"])

    code = _run(project, io, kc, env={"NOTION_TOKEN": "old"}, notion_fake=notion_for)

    assert code == 0 and checked == ["new"]  # what was just typed is checked, and the variable "old" would have been rejected
    assert "무시" in io.out and "export" in io.out  # the person is told the variable is ignored and its line can go
    assert "unset" not in io.out and not [line for line in io.said if line.startswith("⚠") and "NOTION_TOKEN" in line]


def test_keeping_the_stored_token_also_ignores_an_old_variable(repo):
    project = _project(repo)
    checked: list[str] = []

    def notion_for(token: str, state: Any) -> FakeNotion:
        checked.append(token)
        return FakeNotion(token, rejects=frozenset({"old"}))

    io = ScriptedIo(["1", "y", PAGE_URL])
    assert _run(project, io, FakeKeychain(token="new"), env={"NOTION_TOKEN": "old"}, notion_fake=notion_for) == 0
    assert checked == ["new"]


def test_no_note_about_the_variable_when_it_agrees_with_the_keychain_or_is_not_set(repo):
    project = _project(repo)
    same = ScriptedIo(["1", "y", PAGE_URL])
    _run(project, same, FakeKeychain(token=TOKEN), env={"NOTION_TOKEN": TOKEN})
    only_keychain = ScriptedIo(["1", "y", PAGE_URL])
    _run(project, only_keychain, FakeKeychain(token=TOKEN), env={})

    assert "무시" not in same.out and "무시" not in only_keychain.out


def test_a_rejection_is_explained_in_plain_words(repo):
    project = _project(repo)
    io = ScriptedIo(["1", "y", "n"])  # "use the token that is there?" yes, then "enter a different one?" no

    code = _run(
        project,
        io,
        FakeKeychain(token="bad"),
        env={"NOTION_TOKEN": "other"},
        notion_fake=lambda token, state: FakeNotion(token, rejects=frozenset({"bad"})),
    )

    out = "\n".join(io.said)
    assert code == 1
    assert "401" in out and "unauthorized" not in out and "{" not in out  # the status, not Notion's raw JSON
    assert "통째로" in out  # a hint about pasting the whole token
    assert "먼저 쓰입니다" not in out  # the variable is not what was checked, so it is not blamed


def test_an_error_that_is_not_a_rejected_token_is_shown_without_the_token_advice(repo):
    project = _project(repo)

    class Down(FakeNotion):
        def overview(self, newest: int = 5) -> tuple[int, list[str]]:
            raise NotionError("Notion API error 500: server error", 500)

    io = ScriptedIo(["1", "", "n"])
    assert _run(project, io, FakeKeychain(), notion_fake=lambda token, state: Down(token)) == 1
    assert "500" in "\n".join(io.said) and "통째로" not in "\n".join(io.said)


def test_doctor_warns_when_the_variable_and_the_keychain_hold_different_tokens(repo, monkeypatch):
    init_project(repo)
    data = pm.load(repo.root).data
    data["knowledge"] = {"type": "notion", "path": PAGE, "write": "propose_only"}
    pm.save(repo.root, data)
    monkeypatch.setenv("NOTION_TOKEN", "old")
    monkeypatch.setattr(notion.keychain, "read", lambda service: "new")
    monkeypatch.setattr(notion.keychain, "available", lambda: True)

    _, out = repo("doctor", ok=False)

    assert "다릅니다" in out and "NOTION_TOKEN" in out and "키체인이 먼저" in out
    monkeypatch.setattr(notion.keychain, "read", lambda service: "old")
    _, same = repo("doctor", ok=False)
    assert "다릅니다" not in same


def test_the_adapter_error_carries_the_http_status():
    import io as _io
    import urllib.error

    from lanternspec.learn.knowledge.notion import NotionAdapter

    def reject(req: Any) -> Any:
        raise urllib.error.HTTPError(req.full_url, 401, "no", {}, _io.BytesIO(b'{"code":"unauthorized"}'))  # type: ignore[arg-type]

    with pytest.raises(NotionError) as caught:
        NotionAdapter("p", "t", opener=reject).overview()
    assert caught.value.status == 401 and isinstance(caught.value, KnowledgeError)
