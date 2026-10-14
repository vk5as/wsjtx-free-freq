import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
_RELEASE_INFO = _SCRIPTS / "release_info.py"
_SMOKE = _SCRIPTS / "ci_smoke_test.py"

# release_info.py reads pyproject.toml with tomllib, which arrived in Python 3.11; the Release workflow runs it on 3.14.
requires_tomllib = pytest.mark.skipif(sys.version_info < (3, 11), reason="tomllib needs Python 3.11+")


def _release_info(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - fixed interpreter and script, test arguments only
        [sys.executable, str(_RELEASE_INFO), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def _pyproject(directory: Path, version: str) -> None:
    (directory / "pyproject.toml").write_text(f'[project]\nname = "wsjtx_free_freq"\nversion = "{version}"\n')


def _dist(directory: Path, *names: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name in names:
        (directory / name).write_bytes(b"")


@requires_tomllib
def test_version_and_tag_come_from_pyproject(tmp_path: Path) -> None:
    _pyproject(tmp_path, "1.2.3rc1")
    version = _release_info("version", cwd=tmp_path)
    tag = _release_info("tag", cwd=tmp_path)
    assert (version.returncode, version.stdout) == (0, "1.2.3rc1\n")
    assert (tag.returncode, tag.stdout) == (0, "v1.2.3rc1\n")


@requires_tomllib
def test_pyproject_option_is_accepted_before_or_after_the_subcommand(tmp_path: Path) -> None:
    other = tmp_path / "elsewhere.toml"
    other.write_text('[project]\nname = "wsjtx_free_freq"\nversion = "2.0.0"\n')
    before = _release_info("--pyproject", str(other), "tag", cwd=tmp_path)
    after = _release_info("tag", "--pyproject", str(other), cwd=tmp_path)
    assert before.stdout == after.stdout == "v2.0.0\n"


@requires_tomllib
@pytest.mark.parametrize("version", ["not-a-version", "1", "1.0.0-beta"])
def test_unusable_version_is_refused(tmp_path: Path, version: str) -> None:
    _pyproject(tmp_path, version)
    result = _release_info("tag", cwd=tmp_path)
    assert result.returncode == 1
    assert "no usable [project] version" in result.stderr


@requires_tomllib
def test_missing_pyproject_is_refused(tmp_path: Path) -> None:
    result = _release_info("version", cwd=tmp_path)
    assert result.returncode == 1
    assert "Cannot read" in result.stderr


@requires_tomllib
def test_check_dist_accepts_exactly_the_wheel_and_sdist_of_the_version(tmp_path: Path) -> None:
    _pyproject(tmp_path, "0.1.0")
    dist = tmp_path / "dist"
    _dist(dist, "wsjtx_free_freq-0.1.0-py3-none-any.whl", "wsjtx_free_freq-0.1.0.tar.gz")
    result = _release_info("check-dist", str(dist), cwd=tmp_path)
    assert result.returncode == 0
    assert "Distributions match version 0.1.0" in result.stdout


@requires_tomllib
@pytest.mark.parametrize(
    "files",
    [
        ("wsjtx_free_freq-0.1.0.tar.gz",),  # no wheel
        ("wsjtx_free_freq-0.1.0-py3-none-any.whl",),  # no sdist
        ("wsjtx_free_freq-0.0.9-py3-none-any.whl", "wsjtx_free_freq-0.0.9.tar.gz"),  # stale version
        ("wsjtx_free_freq-0.1.0-py3-none-any.whl", "wsjtx_free_freq-0.1.0.tar.gz", "wsjtx_free_freq-0.0.9.tar.gz"),
    ],
)
def test_check_dist_refuses_anything_but_the_exact_pair(tmp_path: Path, files: tuple[str, ...]) -> None:
    _pyproject(tmp_path, "0.1.0")
    dist = tmp_path / "dist"
    _dist(dist, *files)
    result = _release_info("check-dist", str(dist), cwd=tmp_path)
    assert result.returncode == 1
    assert "release_info: error:" in result.stderr


@requires_tomllib
def test_check_dist_refuses_an_empty_directory(tmp_path: Path) -> None:
    _pyproject(tmp_path, "0.1.0")
    empty = tmp_path / "empty"
    empty.mkdir()
    result = _release_info("check-dist", str(empty), cwd=tmp_path)
    assert result.returncode == 1


def test_smoke_test_installed_mode_refuses_a_source_tree() -> None:
    # Under pytest the package is the editable install from src/, not an installed wheel, so --installed must refuse.
    result = subprocess.run(  # noqa: S603 - fixed interpreter and script, fixed argument
        [sys.executable, str(_SMOKE), "--installed"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "not from an installed wheel" in result.stderr
