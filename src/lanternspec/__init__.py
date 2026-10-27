"""LanternSpec — 모르는 것은 밝히고, 걸어온 길은 보여 준다."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("lanternspec")  # 버전의 유일한 출처는 pyproject.toml — 설치할 때 옮겨 적힌 값을 읽는다
except PackageNotFoundError:  # 설치하지 않고 소스 폴더를 바로 불러 쓸 때
    __version__ = "0+unknown"
