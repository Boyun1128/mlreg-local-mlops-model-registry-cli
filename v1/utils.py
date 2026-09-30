"""
utils.py — validate_path, parse_json_object, generate_id
依賴：exceptions.py
"""

from __future__ import annotations

import json
import math
import os
import random
import time
from typing import Any

try:
    from exceptions import JsonSyntaxError, JsonTypeError, MetricsValidationError, StorageWriteError
except ImportError:
    from .exceptions import JsonSyntaxError, JsonTypeError, MetricsValidationError, StorageWriteError


def validate_path(path: str) -> None:
    """驗證路徑在本地檔案系統中存在（os.path.exists）。
    不存在時拋出 ModelFileNotFoundError。
    """
    try:
        from exceptions import ModelFileNotFoundError
    except ImportError:
        from .exceptions import ModelFileNotFoundError

    if not os.path.exists(path):
        raise ModelFileNotFoundError(f"Error: Model file not found at {path}")


def parse_json_object(s: str) -> dict[str, Any]:
    """解析 JSON 字串，確保頂層為 object。
    - 語法錯誤 → JsonSyntaxError
    - 合法 JSON 但非 object → JsonTypeError
    """
    try:
        data = json.loads(s)
    except json.JSONDecodeError:
        raise JsonSyntaxError(
            "Error: Invalid JSON syntax. Please ensure it is a valid JSON string."
        )

    if not isinstance(data, dict):
        raise JsonTypeError(
            f"Error: Invalid JSON format. Expected a JSON object, got {type(data).__name__}."
        )

    return data


def validate_metrics(metrics: dict[str, Any]) -> None:
    """驗證 metrics 的每個 value 必須為有限數值（int 或 float，不含 NaN / Infinity）。"""
    for key, value in metrics.items():
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise MetricsValidationError(
                f"Error: Invalid metrics value for key '{key}'. Expected finite numeric value."
            )
        if not math.isfinite(value):
            raise MetricsValidationError(
                f"Error: Invalid metrics value for key '{key}'. Expected finite numeric value."
            )


def generate_id(existing_ids: set[str]) -> str:
    """產生 m_<unix_timestamp>_<4位隨機十六進位> 格式的唯一 ID。
    若碰撞則重試，最多 5 次；超過則拋出 StorageWriteError。
    """
    for _ in range(5):
        timestamp = int(time.time())
        rand_bytes = random.randbytes(2)
        candidate = f"m_{timestamp}_{rand_bytes.hex()}"
        if candidate not in existing_ids:
            return candidate

    raise StorageWriteError(
        "Error: Failed to write registry: ID generation collision exceeded retry limit."
    )
