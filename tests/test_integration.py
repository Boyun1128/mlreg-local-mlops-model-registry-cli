"""
test_integration.py — Integration 測試 #28, #29, #30, #31
"""
import json
import pytest
from unittest.mock import patch

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from v1.storage import JsonBackend
from v1.exceptions import RegistryCorruptedError, StorageWriteError
from v1.models import ModelRecord


def make_backend(tmp_path):
    """建立指向 tmp_path/registry.json 的 JsonBackend。"""
    env = os.environ.copy()
    env["MLREG_REGISTRY_PATH"] = str(tmp_path / "registry.json")
    with patch.dict(os.environ, {"MLREG_REGISTRY_PATH": str(tmp_path / "registry.json")}):
        return JsonBackend(), tmp_path / "registry.json"


# ── #28 原子寫入失敗 cleanup ──────────────────────────────────────────────────
def test_28_atomic_write_failure_cleanup(tmp_path):
    with patch.dict(os.environ, {"MLREG_REGISTRY_PATH": str(tmp_path / "registry.json")}):
        backend = JsonBackend()

    # 先寫入一筆正常記錄
    record = ModelRecord(
        id="m_0000000001_aaaa",
        project_name="test",
        version="v1",
        file_path="./dummy.pt",
        created_at="2026-01-01T00:00:00Z",
    )
    backend.save([record])

    original_content = (tmp_path / "registry.json").read_text()

    # 模擬 os.replace 失敗
    with patch("v1.storage.os.replace", side_effect=OSError("mock error")):
        with pytest.raises(StorageWriteError):
            backend.save([record])

    # registry.json 內容不變
    assert (tmp_path / "registry.json").read_text() == original_content
    # .tmp 被清除
    assert not (tmp_path / "registry.json.tmp").exists()


# ── #29 load() 缺欄位 record ─────────────────────────────────────────────────
def test_29_load_missing_field(tmp_path):
    reg_path = tmp_path / "registry.json"
    reg_path.write_text(json.dumps({
        "schema_version": "1.0",
        "models": [{"id": "m_1_aaaa", "project_name": "test", "file_path": "./x.pt",
                    "created_at": "2026-01-01T00:00:00Z"}]  # 缺 version
    }))

    with patch.dict(os.environ, {"MLREG_REGISTRY_PATH": str(reg_path)}):
        backend = JsonBackend()
        with pytest.raises(RegistryCorruptedError) as exc_info:
            backend.load()
        assert "record[0]" in str(exc_info.value)


# ── #30 load() 重複 ID ────────────────────────────────────────────────────────
def test_30_load_duplicate_id(tmp_path):
    reg_path = tmp_path / "registry.json"
    record = {"id": "m_1_aaaa", "project_name": "test", "version": "v1",
              "file_path": "./x.pt", "created_at": "2026-01-01T00:00:00Z"}
    reg_path.write_text(json.dumps({
        "schema_version": "1.0",
        "models": [record, record]  # 重複 ID
    }))

    with patch.dict(os.environ, {"MLREG_REGISTRY_PATH": str(reg_path)}):
        backend = JsonBackend()
        with pytest.raises(RegistryCorruptedError):
            backend.load()


# ── #31 load() 重複 (project_name, version) ──────────────────────────────────
def test_31_load_duplicate_project_version(tmp_path):
    reg_path = tmp_path / "registry.json"
    reg_path.write_text(json.dumps({
        "schema_version": "1.0",
        "models": [
            {"id": "m_1_aaaa", "project_name": "test", "version": "v1",
             "file_path": "./x.pt", "created_at": "2026-01-01T00:00:00Z"},
            {"id": "m_2_bbbb", "project_name": "test", "version": "v1",  # 重複 (name, version)
             "file_path": "./y.pt", "created_at": "2026-01-01T00:00:01Z"},
        ]
    }))

    with patch.dict(os.environ, {"MLREG_REGISTRY_PATH": str(reg_path)}):
        backend = JsonBackend()
        with pytest.raises(RegistryCorruptedError):
            backend.load()
