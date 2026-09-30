"""
registry.py — Registry_Core：業務邏輯
依賴：storage.py, models.py, utils.py, exceptions.py
"""

from __future__ import annotations

import re
import sys
from datetime import datetime
from typing import Any

try:
    from exceptions import ModelNotFoundError, VersionConflictError
    from models import ModelRecord
    from storage import JsonBackend, StorageBackend
    from utils import generate_id, validate_metrics, validate_path
except ImportError:
    from .exceptions import ModelNotFoundError, VersionConflictError
    from .models import ModelRecord
    from .storage import JsonBackend, StorageBackend
    from .utils import generate_id, validate_metrics, validate_path


class Registry:
    """業務邏輯層，協調 Storage_Layer 與 Utils。"""

    def __init__(self, backend: StorageBackend | None = None) -> None:
        self._backend: StorageBackend = backend or JsonBackend()

    # ── register ──────────────────────────────────────────────────────────────

    def register(
        self,
        name: str,
        path: str,
        version: str | None = None,
        metrics: dict[str, Any] | None = None,
        hyperparameters: dict[str, Any] | None = None,
    ) -> ModelRecord:
        """驗證輸入、計算版本號、產生 ID、寫入 registry。"""
        # 1. 驗證模型檔案存在
        validate_path(path)

        # 2. 驗證 metrics 有限數值
        if metrics:
            validate_metrics(metrics)

        # 3. 載入現有記錄
        records = self._backend.load()

        # 4. 版本號處理
        if version is not None:
            # 檢查版本號是否已存在
            for r in records:
                if r.project_name == name and r.version == version:
                    raise VersionConflictError(
                        f"Error: Version '{version}' already exists for project '{name}'."
                    )
        else:
            version = self._next_version(name, records)

        # 5. 產生唯一 ID
        existing_ids = {r.id for r in records}
        new_id = generate_id(existing_ids)

        # 6. 建立 ModelRecord
        record = ModelRecord(
            id=new_id,
            project_name=name,
            version=version,
            file_path=path,
            created_at=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            metrics=metrics or {},
            hyperparameters=hyperparameters or {},
        )

        # 7. 寫入
        records.append(record)
        self._backend.save(records)

        return record

    def _next_version(self, name: str, records: list[ModelRecord]) -> str:
        """計算同 project_name 下現存 vN 記錄的最大 N，+1 回傳下一版本號。"""
        pattern = re.compile(r"^v(\d+)$")
        max_n = 0
        for r in records:
            if r.project_name == name:
                m = pattern.match(r.version)
                if m:
                    max_n = max(max_n, int(m.group(1)))
        return f"v{max_n + 1}"

    # ── list_models ───────────────────────────────────────────────────────────

    def list_models(
        self,
        name: str | None = None,
        sort_by: str | None = None,
        desc: bool = False,
    ) -> tuple[list[ModelRecord], bool]:
        """回傳 (records, sort_key_found)。
        sort_key_found=False 表示 sort_by key 完全不存在於任何 record。
        """
        records = self._backend.load()

        # 篩選
        if name:
            records = [r for r in records if r.project_name == name]

        if sort_by is None:
            return records, True

        # 檢查 sort_by key 是否存在於任何 record
        key_found = any(sort_by in r.metrics for r in records)

        if not key_found:
            return records, False

        # stable sort：缺值排末尾
        def sort_key(r: ModelRecord):
            val = r.metrics.get(sort_by)
            if val is None:
                # 缺值排末尾：升冪用 +inf，降冪用 -inf
                return (1, 0)
            return (0, val)

        records = sorted(records, key=sort_key, reverse=desc)
        return records, True

    # ── get_model ─────────────────────────────────────────────────────────────

    def get_model(self, model_id: str) -> ModelRecord:
        """依 ID 查詢；不存在時拋出 ModelNotFoundError。"""
        records = self._backend.load()
        for r in records:
            if r.id == model_id:
                return r
        raise ModelNotFoundError(
            f"Error: Model ID '{model_id}' not found in registry."
        )

    # ── delete_model ──────────────────────────────────────────────────────────

    def delete_model(self, model_id: str) -> None:
        """刪除指定 ID 的記錄；不存在時拋出 ModelNotFoundError。"""
        records = self._backend.load()
        new_records = [r for r in records if r.id != model_id]
        if len(new_records) == len(records):
            raise ModelNotFoundError(
                f"Error: Model ID '{model_id}' not found in registry."
            )
        self._backend.save(new_records)
