"""
storage.py — StorageBackend ABC + JsonBackend + SQLiteBackend + get_backend()（v2.0）
依賴：models.py, exceptions.py
"""

from __future__ import annotations

import json
import math
import os
import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

try:
    from exceptions import (
        InvalidRegistryPathError,
        RegistryCorruptedError,
        StorageWriteError,
        UnsupportedBackendError,
        UnsupportedSchemaVersionError,
    )
    from models import ModelRecord
except ImportError:
    from .exceptions import (
        InvalidRegistryPathError,
        RegistryCorruptedError,
        StorageWriteError,
        UnsupportedBackendError,
        UnsupportedSchemaVersionError,
    )
    from .models import ModelRecord

SCHEMA_VERSION = "1.0"


class StorageBackend(ABC):
    """Storage 抽象介面，供後端替換。"""

    @abstractmethod
    def load(self) -> list[ModelRecord]: ...

    @abstractmethod
    def save(self, records: list[ModelRecord]) -> None: ...


# ── 路徑驗證（共用） ──────────────────────────────────────────────────────────

def _validate_registry_path(path: str) -> None:
    if os.path.isdir(path):
        raise InvalidRegistryPathError(
            f"Error: MLREG_REGISTRY_PATH '{path}' is a directory, not a file."
        )
    parent = os.path.dirname(os.path.abspath(path))
    if not os.path.isdir(parent):
        raise InvalidRegistryPathError(
            f"Error: Parent directory of MLREG_REGISTRY_PATH '{path}' does not exist."
        )


def _resolve_registry_path(default_filename: str) -> str:
    """依 MLREG_REGISTRY_PATH 環境變數解析 registry 路徑。"""
    env_path = os.environ.get("MLREG_REGISTRY_PATH")
    if env_path:
        path = os.path.join(os.getcwd(), env_path) if not os.path.isabs(env_path) else env_path
        _validate_registry_path(path)
        return path
    return os.path.join(os.getcwd(), default_filename)


# ── JsonBackend ───────────────────────────────────────────────────────────────

class JsonBackend(StorageBackend):
    """以 registry.json 為後端的 Storage 實作（v2.0，含 archived 欄位支援）。"""

    def __init__(self) -> None:
        self._path = _resolve_registry_path("registry.json")

    def load(self) -> list[ModelRecord]:
        """讀取並驗證 registry.json；不存在時回傳空列表。"""
        if not os.path.exists(self._path):
            return []

        try:
            with open(self._path, "r", encoding="utf-8") as f:
                raw: Any = json.load(f)
        except json.JSONDecodeError:
            raise RegistryCorruptedError(
                "Error: registry.json is corrupted. "
                "Please restore from backup or delete the file to start fresh."
            )

        schema_ver = raw.get("schema_version") if isinstance(raw, dict) else None
        if schema_ver != SCHEMA_VERSION:
            if isinstance(schema_ver, str):
                raise UnsupportedSchemaVersionError(
                    f"Error: Unsupported schema version '{schema_ver}'. Please upgrade mlreg."
                )
            raise RegistryCorruptedError(
                "Error: registry.json is corrupted. "
                "Please restore from backup or delete the file to start fresh."
            )

        models_raw = raw.get("models") if isinstance(raw, dict) else None
        if not isinstance(models_raw, list):
            raise RegistryCorruptedError(
                "Error: registry.json is corrupted. "
                "Please restore from backup or delete the file to start fresh."
            )

        return _parse_records(models_raw)

    def save(self, records: list[ModelRecord]) -> None:
        """原子寫入：先寫 .tmp，再 os.replace() 替換正式檔案。"""
        payload = {
            "schema_version": SCHEMA_VERSION,
            "models": [r.to_dict() for r in records],
        }
        tmp_path = self._path + ".tmp"

        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except OSError as e:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise StorageWriteError(f"Error: Failed to write registry: {e}") from e

        try:
            os.replace(tmp_path, self._path)
        except OSError as e:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise StorageWriteError(f"Error: Failed to write registry: {e}") from e


# ── record 驗證（JsonBackend 共用） ───────────────────────────────────────────

def _parse_records(models_raw: list[Any]) -> list[ModelRecord]:
    """逐筆驗證 record，任何違反均拋出 RegistryCorruptedError。"""
    seen_ids: set[str] = set()
    seen_versions: set[tuple[str, str]] = set()
    records: list[ModelRecord] = []

    required_str_fields = ("id", "project_name", "version", "file_path", "created_at")

    for idx, item in enumerate(models_raw):
        if not isinstance(item, dict):
            raise RegistryCorruptedError(
                f"Error: registry.json is corrupted at record[{idx}]: "
                "record is not a JSON object. "
                "Please restore from backup or delete the file to start fresh."
            )

        for field_name in required_str_fields:
            if field_name not in item:
                raise RegistryCorruptedError(
                    f"Error: registry.json is corrupted at record[{idx}]: "
                    f"{field_name} is missing. "
                    "Please restore from backup or delete the file to start fresh."
                )
            if not isinstance(item[field_name], str):
                raise RegistryCorruptedError(
                    f"Error: registry.json is corrupted at record[{idx}]: "
                    f"{field_name} must be a string. "
                    "Please restore from backup or delete the file to start fresh."
                )

        try:
            datetime.strptime(item["created_at"], "%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            raise RegistryCorruptedError(
                f"Error: registry.json is corrupted at record[{idx}]: "
                f"created_at has invalid format '{item['created_at']}'. "
                "Please restore from backup or delete the file to start fresh."
            )

        metrics = item.get("metrics", {})
        if not isinstance(metrics, dict):
            raise RegistryCorruptedError(
                f"Error: registry.json is corrupted at record[{idx}]: "
                "metrics must be a JSON object. "
                "Please restore from backup or delete the file to start fresh."
            )
        for k, v in metrics.items():
            if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v):
                raise RegistryCorruptedError(
                    f"Error: registry.json is corrupted at record[{idx}]: "
                    f"metrics['{k}'] is not a finite numeric value. "
                    "Please restore from backup or delete the file to start fresh."
                )

        hyperparameters = item.get("hyperparameters", {})
        if not isinstance(hyperparameters, dict):
            raise RegistryCorruptedError(
                f"Error: registry.json is corrupted at record[{idx}]: "
                "hyperparameters must be a JSON object. "
                "Please restore from backup or delete the file to start fresh."
            )

        # v2.0：archived 欄位型別驗證（選填）
        if "archived" in item and not isinstance(item["archived"], bool):
            raise RegistryCorruptedError(
                f"Error: registry.json is corrupted at record[{idx}]: "
                "archived must be a boolean. "
                "Please restore from backup or delete the file to start fresh."
            )

        record_id = item["id"]
        if record_id in seen_ids:
            raise RegistryCorruptedError(
                f"Error: registry.json is corrupted at record[{idx}]: "
                f"id '{record_id}' is duplicated. "
                "Please restore from backup or delete the file to start fresh."
            )
        seen_ids.add(record_id)

        pv_key = (item["project_name"], item["version"])
        if pv_key in seen_versions:
            raise RegistryCorruptedError(
                f"Error: registry.json is corrupted at record[{idx}]: "
                f"(project_name, version) ('{pv_key[0]}', '{pv_key[1]}') is duplicated. "
                "Please restore from backup or delete the file to start fresh."
            )
        seen_versions.add(pv_key)

        records.append(ModelRecord.from_dict(item))

    return records


# ── SQLiteBackend ─────────────────────────────────────────────────────────────

class SQLiteBackend(StorageBackend):
    """以 SQLite 資料庫為後端的 Storage 實作（v2.0 新增）。"""

    def __init__(self) -> None:
        env_path = os.environ.get("MLREG_REGISTRY_PATH")
        if env_path:
            # 若 MLREG_REGISTRY_PATH 以 .json 結尾，自動轉換為 .db
            db_path = env_path
            if db_path.endswith(".json"):
                db_path = db_path[:-5] + ".db"
            self._path = os.path.join(os.getcwd(), db_path) if not os.path.isabs(db_path) else db_path
            _validate_registry_path(self._path)
        else:
            self._path = os.path.join(os.getcwd(), "registry.db")
        self._init_db()

    def _init_db(self) -> None:
        """建立資料表（若不存在）。"""
        with sqlite3.connect(self._path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS models (
                    id              TEXT PRIMARY KEY,
                    project_name    TEXT NOT NULL,
                    version         TEXT NOT NULL,
                    file_path       TEXT NOT NULL,
                    metrics         TEXT NOT NULL DEFAULT '{}',
                    hyperparameters TEXT NOT NULL DEFAULT '{}',
                    created_at      TEXT NOT NULL,
                    archived        INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(project_name, version)
                )
            """)
            conn.commit()

    def load(self) -> list[ModelRecord]:
        """讀取所有記錄（含 archived）。"""
        with sqlite3.connect(self._path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM models ORDER BY rowid"
            ).fetchall()

        records = []
        for row in rows:
            records.append(ModelRecord(
                id=row["id"],
                project_name=row["project_name"],
                version=row["version"],
                file_path=row["file_path"],
                created_at=row["created_at"],
                metrics=json.loads(row["metrics"]),
                hyperparameters=json.loads(row["hyperparameters"]),
                archived=bool(row["archived"]),
            ))
        return records

    def save(self, records: list[ModelRecord]) -> None:
        """全量替換：在 transaction 內 DELETE + INSERT。"""
        try:
            with sqlite3.connect(self._path) as conn:
                conn.execute("BEGIN EXCLUSIVE")
                conn.execute("DELETE FROM models")
                for r in records:
                    conn.execute(
                        """INSERT INTO models
                           (id, project_name, version, file_path, metrics,
                            hyperparameters, created_at, archived)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            r.id,
                            r.project_name,
                            r.version,
                            r.file_path,
                            json.dumps(r.metrics, ensure_ascii=False),
                            json.dumps(r.hyperparameters, ensure_ascii=False),
                            r.created_at,
                            1 if r.archived else 0,
                        ),
                    )
                conn.commit()
        except sqlite3.Error as e:
            raise StorageWriteError(f"Error: Failed to write registry: {e}") from e


# ── 工廠函式 ──────────────────────────────────────────────────────────────────

def get_backend() -> StorageBackend:
    """依 MLREG_BACKEND 環境變數回傳對應後端實例。
    預設為 JsonBackend；設定為 'sqlite' 時回傳 SQLiteBackend。
    非法值拋出 UnsupportedBackendError。
    """
    backend_env = os.environ.get("MLREG_BACKEND", "json").lower()
    if backend_env == "json":
        return JsonBackend()
    elif backend_env == "sqlite":
        return SQLiteBackend()
    else:
        raise UnsupportedBackendError(
            f"Error: Unsupported backend '{backend_env}'. Supported backends: json, sqlite."
        )
