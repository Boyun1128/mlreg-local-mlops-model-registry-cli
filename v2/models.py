"""
models.py — ModelRecord dataclass（v2.0）
v2.0 新增 archived 欄位（選填，預設 False）。
無任何外部依賴，為底層模組。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ModelRecord:
    """單筆模型版本記錄，對應 registry 中的一個元素。"""

    id: str
    project_name: str
    version: str
    file_path: str
    created_at: str
    metrics: dict[str, float | int] = field(default_factory=dict)
    hyperparameters: dict[str, Any] = field(default_factory=dict)
    archived: bool = False  # v2.0 新增：軟刪除封存狀態

    def to_dict(self) -> dict[str, Any]:
        """序列化為可直接寫入 JSON 的 dict。"""
        return {
            "id": self.id,
            "project_name": self.project_name,
            "version": self.version,
            "file_path": self.file_path,
            "metrics": self.metrics,
            "hyperparameters": self.hyperparameters,
            "created_at": self.created_at,
            "archived": self.archived,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModelRecord":
        """從 dict 反序列化；呼叫端（storage.py）負責事先驗證欄位完整性。
        archived 欄位選填，缺失時預設為 False（向下相容 v1.0 資料）。
        """
        return cls(
            id=data["id"],
            project_name=data["project_name"],
            version=data["version"],
            file_path=data["file_path"],
            created_at=data["created_at"],
            metrics=data.get("metrics", {}),
            hyperparameters=data.get("hyperparameters", {}),
            archived=bool(data.get("archived", False)),
        )
