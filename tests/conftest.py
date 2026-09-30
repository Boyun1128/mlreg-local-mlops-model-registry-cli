"""
conftest.py — 共用 fixture
"""
import os
import subprocess
import sys
import pytest


@pytest.fixture
def registry_env(tmp_path):
    """每個測試使用獨立的暫存目錄，透過 MLREG_REGISTRY_PATH 隔離。"""
    registry_path = tmp_path / "registry.json"
    env = os.environ.copy()
    env["MLREG_REGISTRY_PATH"] = str(registry_path)
    return env, tmp_path


@pytest.fixture
def dummy_pt(tmp_path):
    """建立一個空的假模型檔案。"""
    pt = tmp_path / "dummy.pt"
    pt.write_bytes(b"")
    return str(pt)


def run(args: list[str], env: dict, cwd=None) -> subprocess.CompletedProcess:
    """執行 mlreg CLI，回傳 CompletedProcess。"""
    base = cwd or os.path.join(os.path.dirname(__file__), "..")
    cmd = [sys.executable, "v1/main.py"] + args
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
        cwd=base,
    )
