"""
storage.py — StorageBackend ABC + JsonBackend
依賴：models.py, exceptions.py
"""

from __future__ import annotations

import json
import math
import os
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

try:
    from exceptions import (
        InvalidRegistryPathError,
        RegistryCorruptedError,
        StorageWriteError,
        UnsupportedSchemaVersionError,
    )
    from models import ModelRecord
except ImportError:
    from .exceptions import (
        InvalidRegistryPathError,
        RegistryCorruptedError,
        StorageWriteError,
        UnsupportedSchemaVersionError,
    )
    from .models import ModelRecord

SCHEMA_VERSION = "1.0"


class StorageBackend(ABC):
    """Storage 抽象介面，供 v2.0 替換為 SQLiteBackend。"""

    @abstractmethod
    def load(self) -> list[ModelRecord]: ...

    @abstractmethod
    def save(self, records: list[ModelRecord]) -> None: ...


class JsonBackend(StorageBackend):
    """以 registry.json 為後端的 Storage 實作。"""

    def __init__(self) -> None:
        env_path = os.environ.get("MLREG_REGISTRY_PATH")
        if env_path:
            # 相對路徑以初始化時的 cwd 為基準
            self._path = os.path.join(os.getcwd(), env_path) if not os.path.isabs(env_path) else env_path
            self._validate_registry_path(self._path)
        else:
            self._path = os.path.join(os.getcwd(), "registry.json")

    # ── 路徑驗證 ──────────────────────────────────────────────────────────────

    def _validate_registry_path(self, path: str) -> None:
        if os.path.isdir(path):
            raise InvalidRegistryPathError(
                f"Error: MLREG_REGISTRY_PATH '{path}' is a directory, not a file."
            )
        parent = os.path.dirname(os.path.abspath(path))
        if not os.path.isdir(parent):
            raise InvalidRegistryPathError(
                f"Error: Parent directory of MLREG_REGISTRY_PATH '{path}' does not exist."
            )

    # ── 讀取 ──────────────────────────────────────────────────────────────────

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

        # schema_version 驗證
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

        # models 必須為 array
        models_raw = raw.get("models") if isinstance(raw, dict) else None
        if not isinstance(models_raw, list):
            raise RegistryCorruptedError(
                "Error: registry.json is corrupted. "
                "Please restore from backup or delete the file to start fresh."
            )

        return self._parse_records(models_raw)

    def _parse_records(self, models_raw: list[Any]) -> list[ModelRecord]:
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

            # 必填欄位存在且型別為 str
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

            # created_at 格式驗證
            try:
                datetime.strptime(item["created_at"], "%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                raise RegistryCorruptedError(
                    f"Error: registry.json is corrupted at record[{idx}]: "
                    f"created_at has invalid format '{item['created_at']}'. "
                    "Please restore from backup or delete the file to start fresh."
                )

            # metrics 型別與有限數值驗證
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

            # hyperparameters 型別驗證
            hyperparameters = item.get("hyperparameters", {})
            if not isinstance(hyperparameters, dict):
                raise RegistryCorruptedError(
                    f"Error: registry.json is corrupted at record[{idx}]: "
                    "hyperparameters must be a JSON object. "
                    "Please restore from backup or delete the file to start fresh."
                )

            # ID 全域唯一
            record_id = item["id"]
            if record_id in seen_ids:
                raise RegistryCorruptedError(
                    f"Error: registry.json is corrupted at record[{idx}]: "
                    f"id '{record_id}' is duplicated. "
                    "Please restore from backup or delete the file to start fresh."
                )
            seen_ids.add(record_id)

            # (project_name, version) 唯一
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

    # ── 寫入（原子） ──────────────────────────────────────────────────────────

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
            # 步驟 1 失敗：清除暫存檔，保持原檔不變
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise StorageWriteError(f"Error: Failed to write registry: {e}") from e

        try:
            os.replace(tmp_path, self._path)
        except OSError as e:
            # 步驟 2 失敗：清除暫存檔
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise StorageWriteError(f"Error: Failed to write registry: {e}") from e
