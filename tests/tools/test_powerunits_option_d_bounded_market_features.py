"""Tests for bounded Option D market_features wrapper (no live DB / no uv)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from tools import powerunits_option_d_bounded_market_features as mod


def _fake_proc(*, rc: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=[],
        returncode=rc,
        stdout=stdout,
        stderr=stderr,
    )


def test_valid_invocation_emits_ok_json(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "product"
    job = root / "backend" / "services" / "data_ingestion" / "jobs" / "market_feature_job.py"
    job.parent.mkdir(parents=True)
    job.write_text("# stub\n", encoding="utf-8")

    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h1:5432/db1")
    monkeypatch.setenv("DATABASE_URL_TIMESCALE", "postgresql://u:p@h2:5432/db2")
    monkeypatch.setenv("MARKET_FEATURES_WRITE_TARGET", "timescale")
    monkeypatch.setenv("POWERUNITS_OPTION_D_PRODUCT_ROOT", str(root))

    out = (
        "[market_features_write] ok\n"
        "Run: 48112f3f-f6a7-49eb-a86e-aecb061b07d9 status=success rows_written=24\n"
    )
    with patch.object(mod, "_delegate_uv", return_value=_fake_proc(rc=0, stdout=out, stderr="")):
        code = mod.main(
            [
                "--country",
                "PL",
                "--start",
                "2024-01-01T00:00:00Z",
                "--end",
                "2024-01-02T00:00:00Z",
                "--version",
                "v1",
            ]
        )
    assert code == 0
    captured = capsys.readouterr().out.strip()
    data = json.loads(captured)
    assert data["ok"] is True
    assert data["wrapper"] == mod.WRAPPER_ID
    assert data["slice"]["country"] == "PL"
    assert data["job"]["rows_written"] == 24


def test_invalid_country(capsys: pytest.CaptureFixture[str]) -> None:
    code = mod.main(
        [
            "--country",
            "DE",
            "--start",
            "2024-01-01T00:00:00Z",
            "--end",
            "2024-01-02T00:00:00Z",
            "--version",
            "v1",
        ]
    )
    assert code == 2
    data = json.loads(capsys.readouterr().out.strip())
    assert data["ok"] is False
    assert data["error_class"] == "validation"


def test_invalid_duration_over_24h(capsys: pytest.CaptureFixture[str]) -> None:
    code = mod.main(
        [
            "--country",
            "PL",
            "--start",
            "2024-01-01T00:00:00Z",
            "--end",
            "2024-01-03T00:00:00Z",
            "--version",
            "v1",
        ]
    )
    assert code == 2
    data = json.loads(capsys.readouterr().out.strip())
    assert data["code"] == 2


def test_invalid_version(capsys: pytest.CaptureFixture[str]) -> None:
    code = mod.main(
        [
            "--country",
            "PL",
            "--start",
            "2024-01-01T00:00:00Z",
            "--end",
            "2024-01-02T00:00:00Z",
            "--version",
            "v2",
        ]
    )
    assert code == 2


def test_missing_env_database_url(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL_TIMESCALE", "postgresql://u:p@h:5432/db")
    monkeypatch.setenv("MARKET_FEATURES_WRITE_TARGET", "timescale")
    code = mod.main(
        [
            "--country",
            "PL",
            "--start",
            "2024-01-01T00:00:00Z",
            "--end",
            "2024-01-02T00:00:00Z",
            "--version",
            "v1",
        ]
    )
    assert code == 3
    data = json.loads(capsys.readouterr().out.strip())
    assert data["error_class"] == "environment"


def test_delegated_subprocess_nonzero_exit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "product"
    job = root / "backend" / "services" / "data_ingestion" / "jobs" / "market_feature_job.py"
    job.parent.mkdir(parents=True)
    job.write_text("# stub\n", encoding="utf-8")

    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h1:5432/db1")
    monkeypatch.setenv("DATABASE_URL_TIMESCALE", "postgresql://u:p@h2:5432/db2")
    monkeypatch.setenv("MARKET_FEATURES_WRITE_TARGET", "timescale")
    monkeypatch.setenv("POWERUNITS_OPTION_D_PRODUCT_ROOT", str(root))

    with patch.object(mod, "_delegate_uv", return_value=_fake_proc(rc=1, stdout="", stderr="psql died")):
        code = mod.main(
            [
                "--country",
                "PL",
                "--start",
                "2024-01-01T00:00:00Z",
                "--end",
                "2024-01-02T00:00:00Z",
                "--version",
                "v1",
            ]
        )
    assert code == 4
    data = json.loads(capsys.readouterr().out.strip())
    assert data["error_class"] == "job_failed"


def test_delegated_job_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "product"
    job = root / "backend" / "services" / "data_ingestion" / "jobs" / "market_feature_job.py"
    job.parent.mkdir(parents=True)
    job.write_text("# stub\n", encoding="utf-8")

    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h1:5432/db1")
    monkeypatch.setenv("DATABASE_URL_TIMESCALE", "postgresql://u:p@h2:5432/db2")
    monkeypatch.setenv("MARKET_FEATURES_WRITE_TARGET", "timescale")
    monkeypatch.setenv("POWERUNITS_OPTION_D_PRODUCT_ROOT", str(root))

    out = "Run: 00000000-0000-4000-8000-000000000001 status=failed rows_written=0\nError: boom\n"
    with patch.object(mod, "_delegate_uv", return_value=_fake_proc(rc=0, stdout=out, stderr="")):
        code = mod.main(
            [
                "--country",
                "PL",
                "--start",
                "2024-01-01T00:00:00Z",
                "--end",
                "2024-01-02T00:00:00Z",
                "--version",
                "v1",
            ]
        )
    assert code == 4
    data = json.loads(capsys.readouterr().out.strip())
    assert data["ok"] is False
    assert data["error_class"] == "job_failed"
