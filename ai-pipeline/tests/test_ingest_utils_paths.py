import os
import pathlib
import sys

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from training.tools.ingest_utils import resolve_repo_path  # noqa: E402


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("data/raw/cambridge", PROJECT_ROOT / "data" / "raw" / "cambridge"),
        (str(PROJECT_ROOT / "ai-pipeline"), PROJECT_ROOT / "ai-pipeline"),
    ],
)
def test_resolve_repo_path_relative_and_absolute(raw: str, expected: pathlib.Path) -> None:
    resolved = resolve_repo_path(raw)
    assert resolved == expected


def test_resolve_repo_path_wsl_drive_roundtrip() -> None:
    if os.name == "nt":
        pytest.skip("Windows host does not use /mnt drive layout")

    posix_root = PROJECT_ROOT.as_posix()
    if not posix_root.startswith("/mnt/"):
        pytest.skip("Repository is not mounted under /mnt; skipping WSL translation check")

    sample_dir = PROJECT_ROOT / "tmp_resolve_repo_path"
    sample_dir.mkdir(exist_ok=True)
    sample = sample_dir / "example.txt"
    sample.write_text("demo", encoding="utf-8")

    try:
        parts = sample.as_posix().split("/", 3)
        if len(parts) < 4:
            pytest.skip("Unexpected path layout; skipping")
        drive_letter = parts[2]
        remainder = parts[3]
        if len(drive_letter) != 1:
            pytest.skip("Unexpected drive letter segment; skipping")
        converted = remainder.replace('/', '\\')
        windows_path = f"{drive_letter.upper()}:\\{converted}"
        resolved = resolve_repo_path(windows_path)
        assert resolved == sample
    finally:
        sample.unlink(missing_ok=True)
        try:
            sample_dir.rmdir()
        except OSError:
            pass
