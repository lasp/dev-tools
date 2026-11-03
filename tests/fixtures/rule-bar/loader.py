from pathlib import Path


def load(path: Path) -> str:
    return path.read_text()


def read(source: str | Path) -> str:
    return Path(str(source)).read_text()
