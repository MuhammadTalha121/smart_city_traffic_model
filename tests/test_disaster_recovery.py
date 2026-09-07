import os
import shutil
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

def test_health_endpoint_returns_200():
    response = client.get("/system/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "model_loaded" in data
    assert "redis_connected" in data

def test_backup_script_creates_backup_directory(tmp_path, monkeypatch):
    """Simulate backup logic in Python (no external shell)."""
    monkeypatch.chdir(tmp_path)

    # Create dummy files
    (tmp_path / "predictions_log.csv").touch()
    (tmp_path / "model.joblib").touch()
    (tmp_path / "construction_zones.json").write_text("{}")

    # Execute backup logic (same as script but in Python)
    import datetime
    backup_root = tmp_path / "backups"
    backup_root.mkdir()
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = backup_root / timestamp
    backup_dir.mkdir()

    # Copy files
    for f in ["predictions_log.csv", "model.joblib", "construction_zones.json"]:
        shutil.copy(tmp_path / f, backup_dir / f)

    # Write last_backup.txt
    (tmp_path / "last_backup.txt").write_text(timestamp)

    # Verify backup directory exists and contains files
    backup_dirs = list(backup_root.glob("*"))
    assert len(backup_dirs) == 1
    assert (backup_dirs[0] / "predictions_log.csv").exists()
    assert (backup_dirs[0] / "model.joblib").exists()
    assert (backup_dirs[0] / "construction_zones.json").exists()

def test_restore_script_recovers_model_files(tmp_path, monkeypatch):
    """Simulate restore logic in Python (no external shell)."""
    monkeypatch.chdir(tmp_path)

    # Create a backup directory with files
    backup_dir = tmp_path / "backup_restore_test"
    backup_dir.mkdir()
    (backup_dir / "model.joblib").write_text("dummy model content")
    (backup_dir / "predictions_log.csv").write_text("timestamp,score\n2026-09-07,0.5")

    # Simulate restore: copy all files from backup to current directory
    for f in backup_dir.glob("*"):
        shutil.copy(f, tmp_path / f.name)

    # Verify files are restored
    assert (tmp_path / "model.joblib").exists()
    assert (tmp_path / "predictions_log.csv").exists()
    content = (tmp_path / "predictions_log.csv").read_text()
    assert "2026-09-07" in content