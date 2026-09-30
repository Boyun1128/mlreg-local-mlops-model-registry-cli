"""
exceptions.py — MlregError 及所有子類別（v2.0）
無任何外部依賴，為最底層模組。
"""


class MlregError(Exception):
    """所有業務邏輯例外的基底類別。"""

    def __init__(self, message: str, exit_code: int = 1) -> None:
        super().__init__(message)
        self.exit_code = exit_code


# ── 資料驗證類 ────────────────────────────────────────────────────────────────

class JsonSyntaxError(MlregError):
    """--metrics / --params 字串無法被 json.loads() 解析。"""


class JsonTypeError(MlregError):
    """JSON 合法，但頂層型別不是 object（例如 array、string）。"""


class MetricsValidationError(MlregError):
    """metrics value 不是有限數值（含 NaN、Infinity、-Infinity）。"""


# ── 業務邏輯類（v1.0 繼承） ───────────────────────────────────────────────────

class ModelNotFoundError(MlregError):
    """指定的 model ID 在 registry 中不存在。"""


class ModelFileNotFoundError(MlregError):
    """--path 指定的模型檔案在本地檔案系統中不存在。"""


class VersionConflictError(MlregError):
    """同一 project_name 下，指定的版本號已存在。"""


# ── 業務邏輯類（v2.0 新增） ───────────────────────────────────────────────────

class AlreadyArchivedError(MlregError):
    """對已封存記錄執行 --soft 軟刪除。"""


class CompareRequiresMultipleIdsError(MlregError):
    """compare 指令僅提供 1 個 ID。"""


# ── 儲存層類（v1.0 繼承） ─────────────────────────────────────────────────────

class RegistryCorruptedError(MlregError):
    """registry.json JSON 語法損毀，或 record 欄位驗證失敗。"""


class UnsupportedSchemaVersionError(MlregError):
    """registry.json 的 schema_version 不是 "1.0"。"""


class StorageWriteError(MlregError):
    """registry.json 寫入失敗，或 ID 碰撞超過最大重試次數。"""


class InvalidRegistryPathError(MlregError):
    """MLREG_REGISTRY_PATH 指向目錄、parent directory 不存在等非法路徑。"""


# ── 儲存層類（v2.0 新增） ─────────────────────────────────────────────────────

class UnsupportedBackendError(MlregError):
    """MLREG_BACKEND 環境變數設定為非法值。"""


class UnsupportedOutputFormatError(MlregError):
    """--output 指定不支援的格式值。"""
