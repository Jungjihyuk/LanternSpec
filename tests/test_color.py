import io

from lanternspec.cli import color


class Tty(io.StringIO):
    def isatty(self):
        return True


def test_lines_are_colored_by_their_mark_even_when_written_in_pieces():
    out = Tty()
    p = color._Painted(out)
    p.write("✔ 좋음\n  ⚠ 경")
    p.write("고\n그냥 줄\n✖ 문제")
    p.flush()
    assert out.getvalue() == ("\033[32m✔\033[0m 좋음\n  \033[33m⚠ 경고\033[0m\n그냥 줄\n\033[31m✖ 문제\033[0m")


def test_no_color_without_a_terminal_or_with_no_color(monkeypatch):
    assert not color.wanted(io.StringIO())
    monkeypatch.setenv("NO_COLOR", "1")
    assert not color.wanted(Tty())
    monkeypatch.delenv("NO_COLOR")
    monkeypatch.setenv("TERM", "xterm-256color")
    assert color.wanted(Tty())
