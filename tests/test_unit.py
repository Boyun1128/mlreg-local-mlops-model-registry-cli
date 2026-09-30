"""
test_unit.py — Unit 測試 #4c, #4d, #25, #26, #27, #32
"""
import math
import pytest
from unittest.mock import patch

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from v1.utils import parse_json_object, validate_path, validate_metrics, generate_id
from v1.exceptions import JsonTypeError, MetricsValidationError, StorageWriteError


# ── #4c metrics NaN ───────────────────────────────────────────────────────────
def test_4c_metrics_nan():
    with pytest.raises(MetricsValidationError):
        validate_metrics({"acc": float("nan")})


# ── #4d metrics Infinity ──────────────────────────────────────────────────────
def test_4d_metrics_infinity():
    with pytest.raises(MetricsValidationError):
        validate_metrics({"acc": float("inf")})

    with pytest.raises(MetricsValidationError):
        validate_metrics({"acc": float("-inf")})


# ── #25 parse_json_object 正常 ────────────────────────────────────────────────
def test_25_parse_json_object_valid():
    result = parse_json_object('{"a": 1}')
    assert result == {"a": 1}


# ── #26 parse_json_object 非 object ──────────────────────────────────────────
def test_26_parse_json_object_array():
    with pytest.raises(JsonTypeError):
        parse_json_object("[1, 2]")


# ── #27 validate_path 存在 ────────────────────────────────────────────────────
def test_27_validate_path_exists(tmp_path):
    pt = tmp_path / "dummy.pt"
    pt.write_bytes(b"")
    validate_path(str(pt))  # 不應拋出例外


# ── #32 generate_id 碰撞重試超限 ─────────────────────────────────────────────
def test_32_generate_id_collision_exceeded():
    fixed_id = "m_1710903810_a3f2"
    existing = {fixed_id}

    with patch("v1.utils.time.time", return_value=1710903810), \
         patch("v1.utils.random.randbytes", return_value=b"\xa3\xf2"):
        with pytest.raises(StorageWriteError):
            generate_id(existing)
