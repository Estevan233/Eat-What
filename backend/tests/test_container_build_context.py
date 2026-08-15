import re
import shlex
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_every_docker_copy_source_exists() -> None:
    missing: list[str] = []

    for raw_line in (BACKEND_ROOT / "Dockerfile").read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line.startswith("COPY "):
            continue

        tokens = shlex.split(line)
        first_source = 1
        while first_source < len(tokens) and tokens[first_source].startswith("--"):
            first_source += 1

        for source in tokens[first_source:-1]:
            if not (BACKEND_ROOT / source).exists():
                missing.append(source)

    assert missing == [], f"Dockerfile COPY sources are missing: {missing}"


def test_pyproject_readme_exists() -> None:
    pyproject = (BACKEND_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^readme\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)

    assert match is not None, "project.readme metadata is missing"
    readme = match.group(1)

    assert (BACKEND_ROOT / readme).is_file(), f"project.readme is missing: {readme}"
