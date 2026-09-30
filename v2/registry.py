"""
registry.py — Registry_Core：業務邏輯（v2.0）
v2.0 新增：archive_model(), compare_models()
         list_models() 新增 show_archived 參數
         delete_model() 新增 soft 參數
依賴：storage.py, models.py, utils.py, exceptions.py
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

try:
    from exceptions import (
        AlreadyArchivedError,
        CompareRequiresMultipleIdsError,
        ModelNotFoundError,
        VersionConflictError,
    )
    from models import ModelRecord
    from storage import StorageBackend, get_backend
    from utils import generate_id, validate_metrics, validate_path
except ImportError:
    from .exceptions import (
        AlreadyArchivedError,
        CompareRequiresMultipleIdsError,
        ModelNotFoundError,
        VersionConflictError,
    )
    from .models import ModelRecord
    from .storage import StorageBackend, get_backend
    from .utils import generate_id, validate_metrics, validate_path


class Registry:
    """業務邏輯層，協調 Storage_Layer 與 Utils。"""

    def __init__(self, backend: StorageBackend | None = None) -> None:
        self._backend: StorageBackend = backend or get_backend()

    # ── register ──────────────────────────────────────────────────────────────

    def register(
        self,
        name: str,
        path: str,
        version: str | None = None,
        metrics: dict[str, Any] | None = None,
        hyperparameters: dict[str, Any] | None = None,
    ) -> ModelRecord:
        validate_path(path)
        if metrics:
            validate_metrics(metrics)

        records = self._backend.load()

        if version is not None:
            for r in records:
                if r.project_name == name and r.version == version:
                    raise VersionConflictError(
                        f"Error: Version '{version}' already exists for project '{name}'."
                    )
        else:
            version = self._next_version(name, records)

        existing_ids = {r.id for r in records}
        new_id = generate_id(existing_ids)

        record = ModelRecord(
            id=new_id,
            project_name=name,
            version=version,
            file_path=path,
            created_at=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            metrics=metrics or {},
            hyperparameters=hyperparameters or {},
            archived=False,
        )

        records.append(record)
        self._backend.save(records)
        return record

    def _next_version(self, name: str, records: list[ModelRecord]) -> str:
        """計算同 project_name 下現存 vN 記錄（含 archived）的最大 N，+1 回傳下一版本號。"""
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
        show_archived: bool = False,
    ) -> tuple[list[ModelRecord], bool]:
        """回傳 (records, sort_key_found)。
        show_archived=False 時過濾掉已封存記錄（v2.0 新增參數）。
        """
        records = self._backend.load()

        # 封存篩選
        if not show_archived:
            records = [r for r in records if not r.archived]

        # 名稱篩選
        if name:
            records = [r for r in records if r.project_name == name]

        if sort_by is None:
            return records, True

        key_found = any(sort_by in r.metrics for r in records)
        if not key_found:
            return records, False

        def sort_key(r: ModelRecord):
            val = r.metrics.get(sort_by)
            if val is None:
                return (1, 0)
            return (0, val)

        records = sorted(records, key=sort_key, reverse=desc)
        return records, True

    # ── get_model ─────────────────────────────────────────────────────────────

    def get_model(self, model_id: str) -> ModelRecord:
        """依 ID 查詢（含 archived）；不存在時拋出 ModelNotFoundError。"""
        records = self._backend.load()
        for r in records:
            if r.id == model_id:
                return r
        raise ModelNotFoundError(
            f"Error: Model ID '{model_id}' not found in registry."
        )

    # ── delete_model ──────────────────────────────────────────────────────────

    def delete_model(self, model_id: str, soft: bool = False) -> None:
        """刪除或封存指定 ID 的記錄。
        soft=True：軟刪除（設定 archived=True）
        soft=False：硬刪除（從 records 移除，v1.0 行為）
        """
        records = self._backend.load()

        if soft:
            for r in records:
                if r.id == model_id:
                    if r.archived:
                        raise AlreadyArchivedError(
                            f"Error: Model ID '{model_id}' is already archived."
                        )
                    r.archived = True
                    self._backend.save(records)
                    return
            raise ModelNotFoundError(
                f"Error: Model ID '{model_id}' not found in registry."
            )
        else:
            new_records = [r for r in records if r.id != model_id]
            if len(new_records) == len(records):
                raise ModelNotFoundError(
                    f"Error: Model ID '{model_id}' not found in registry."
                )
            self._backend.save(new_records)

    # ── compare_models ────────────────────────────────────────────────────────

    def compare_models(self, model_ids: list[str]) -> list[ModelRecord]:
        """依序查詢多個 ID，回傳對應的 ModelRecord 列表。
        ID 數量 < 2 時拋出 CompareRequiresMultipleIdsError。
        任何 ID 不存在時拋出 ModelNotFoundError。
        """
        if len(model_ids) < 2:
            raise CompareRequiresMultipleIdsError(
                "Error: compare requires at least 2 model IDs."
            )
        return [self.get_model(mid) for mid in model_ids]
