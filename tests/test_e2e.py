"""
test_e2e.py — E2E 測試案例 #1~#24
"""
import json
import re
import pytest
from .conftest import run


# ── 共用：從 register stdout 取得 ID ─────────────────────────────────────────
def extract_id(stdout: str) -> str:
    m = re.search(r"ID\s*:\s*(m_\d+_[0-9a-f]{4})", stdout)
    assert m, f"ID not found in stdout:\n{stdout}"
    return m.group(1)


# ── #1 register 成功 ──────────────────────────────────────────────────────────
def test_01_register_success(registry_env, dummy_pt):
    env, _ = registry_env
    r = run(["register", "--name", "pig-pose", "--path", dummy_pt], env)
    assert r.returncode == 0
    assert "Successfully registered" in r.stdout


# ── #2 register 路徑不存在 ────────────────────────────────────────────────────
def test_02_register_file_not_found(registry_env, tmp_path):
    env, _ = registry_env
    r = run(["register", "--name", "pig-pose", "--path", str(tmp_path / "nonexistent.pt")], env)
    assert r.returncode == 1
    assert "not found" in r.stderr


# ── #3 register metrics JSON 語法錯誤 ─────────────────────────────────────────
def test_03_register_invalid_json_syntax(registry_env, dummy_pt):
    env, _ = registry_env
    r = run(["register", "--name", "pig-pose", "--path", dummy_pt, "--metrics", "not-json"], env)
    assert r.returncode == 1
    assert "Invalid JSON syntax" in r.stderr


# ── #4 register metrics 非 object ─────────────────────────────────────────────
def test_04_register_metrics_not_object(registry_env, dummy_pt):
    env, _ = registry_env
    r = run(["register", "--name", "pig-pose", "--path", dummy_pt, "--metrics", "[1,2,3]"], env)
    assert r.returncode == 1
    assert "Expected a JSON object" in r.stderr


# ── #4b register metrics value 非數值 ────────────────────────────────────────
def test_04b_register_metrics_non_numeric(registry_env, dummy_pt):
    env, _ = registry_env
    r = run(["register", "--name", "pig-pose", "--path", dummy_pt,
             "--metrics", '{"acc":"high"}'], env)
    assert r.returncode == 1
    assert "Invalid metrics value" in r.stderr


# ── #5 register 缺少 --path ───────────────────────────────────────────────────
def test_05_register_missing_path(registry_env):
    env, _ = registry_env
    r = run(["register", "--name", "pig-pose"], env)
    assert r.returncode == 2
    assert "--path" in r.stderr


# ── #6 list 空 registry ───────────────────────────────────────────────────────
def test_06_list_empty_registry(registry_env):
    env, _ = registry_env
    r = run(["list"], env)
    assert r.returncode == 0
    assert "No models registered yet" in r.stdout


# ── #7 list 有記錄顯示表格欄位 ───────────────────────────────────────────────
def test_07_list_shows_table(registry_env, dummy_pt):
    env, _ = registry_env
    run(["register", "--name", "pig-pose", "--path", dummy_pt], env)
    run(["register", "--name", "pig-pose", "--path", dummy_pt], env)
    r = run(["list"], env)
    assert r.returncode == 0
    for col in ["ID", "Project Name", "Version", "File Path", "Created At"]:
        assert col in r.stdout


# ── #8 list --name 篩選 ───────────────────────────────────────────────────────
def test_08_list_filter_by_name(registry_env, dummy_pt):
    env, _ = registry_env
    run(["register", "--name", "pig-pose", "--path", dummy_pt], env)
    run(["register", "--name", "other-model", "--path", dummy_pt], env)
    r = run(["list", "--name", "pig-pose"], env)
    assert r.returncode == 0
    assert "pig-pose" in r.stdout
    assert "other-model" not in r.stdout


# ── #9 list --name 無結果 ─────────────────────────────────────────────────────
def test_09_list_filter_no_result(registry_env, dummy_pt):
    env, _ = registry_env
    run(["register", "--name", "pig-pose", "--path", dummy_pt], env)
    r = run(["list", "--name", "not-exist"], env)
    assert r.returncode == 0
    assert "No models found" in r.stdout


# ── #10 list --sort-by --desc 排序驗證 ───────────────────────────────────────
def test_10_list_sort_by_desc(registry_env, dummy_pt):
    env, tmp_path = registry_env
    for score in [0.9, 0.95, 0.8]:
        run(["register", "--name", "test", "--path", dummy_pt,
             "--metrics", f'{{"mAP_50": {score}}}'], env)

    r_list = run(["list", "--sort-by", "mAP_50", "--desc"], env)
    assert r_list.returncode == 0

    # 從 registry.json 取得所有 ID 與對應 mAP_50
    import json as _json
    reg = _json.loads((tmp_path / "registry.json").read_text())
    id_to_score = {m["id"]: m["metrics"]["mAP_50"] for m in reg["models"]}

    # list 輸出中出現的 ID 順序（Rich table 可能截斷，用前綴比對）
    lines = [l for l in r_list.stdout.splitlines() if "m_" in l]
    ordered_scores = []
    for line in lines:
        for mid, score in id_to_score.items():
            if mid[:12] in line or mid in line:
                ordered_scores.append(score)
                break

    assert ordered_scores == sorted(ordered_scores, reverse=True)


# ── #11 info 成功 ─────────────────────────────────────────────────────────────
def test_11_info_success(registry_env, dummy_pt):
    env, _ = registry_env
    r_reg = run(["register", "--name", "pig-pose", "--path", dummy_pt,
                 "--metrics", '{"mAP_50": 0.95}'], env)
    mid = extract_id(r_reg.stdout)

    r = run(["info", "--id", mid], env)
    assert r.returncode == 0
    for field in ["ID", "Project Name", "Version", "File Path", "Created At", "Metrics", "Hyperparameters"]:
        assert field in r.stdout


# ── #12 info ID 不存在 ────────────────────────────────────────────────────────
def test_12_info_id_not_found(registry_env):
    env, _ = registry_env
    r = run(["info", "--id", "m_9999999999_0000"], env)
    assert r.returncode == 1
    assert "not found" in r.stderr


# ── #13a delete 成功 ──────────────────────────────────────────────────────────
def test_13a_delete_success(registry_env, dummy_pt):
    env, _ = registry_env
    r_reg = run(["register", "--name", "pig-pose", "--path", dummy_pt], env)
    mid = extract_id(r_reg.stdout)

    r = run(["delete", "--id", mid], env)
    assert r.returncode == 0
    assert "Successfully deleted" in r.stdout


# ── #13b delete 後 list 不含已刪除 ID ────────────────────────────────────────
def test_13b_list_after_delete(registry_env, dummy_pt):
    env, _ = registry_env
    r_reg = run(["register", "--name", "pig-pose", "--path", dummy_pt], env)
    mid = extract_id(r_reg.stdout)
    run(["delete", "--id", mid], env)

    r = run(["list"], env)
    assert mid not in r.stdout


# ── #14 delete ID 不存在 ──────────────────────────────────────────────────────
def test_14_delete_id_not_found(registry_env):
    env, _ = registry_env
    r = run(["delete", "--id", "m_9999999999_0000"], env)
    assert r.returncode == 1
    assert "not found" in r.stderr


# ── #15 版本號自動遞增 ────────────────────────────────────────────────────────
def test_15_auto_version_increment(registry_env, dummy_pt):
    env, _ = registry_env
    versions = []
    for _ in range(3):
        r = run(["register", "--name", "test", "--path", dummy_pt], env)
        assert r.returncode == 0
        m = re.search(r"Version\s*:\s*(v\d+)", r.stdout)
        versions.append(m.group(1))
    assert versions == ["v1", "v2", "v3"]


# ── #16 版本號重複衝突 ────────────────────────────────────────────────────────
def test_16_version_conflict(registry_env, dummy_pt):
    env, _ = registry_env
    run(["register", "--name", "test", "--path", dummy_pt, "--version", "v1"], env)
    r = run(["register", "--name", "test", "--path", dummy_pt, "--version", "v1"], env)
    assert r.returncode == 1
    assert "already exists" in r.stderr


# ── #17 --desc 無 --sort-by ───────────────────────────────────────────────────
def test_17_desc_without_sort_by(registry_env):
    env, _ = registry_env
    r = run(["list", "--desc"], env)
    assert r.returncode == 1
    assert "--desc requires --sort-by" in r.stderr


# ── #18 --sort-by 部分 record 缺 key ─────────────────────────────────────────
def test_18_sort_by_partial_missing_key(registry_env, dummy_pt):
    env, _ = registry_env
    # 兩筆有 mAP_50，一筆沒有
    r1 = run(["register", "--name", "test", "--path", dummy_pt,
              "--metrics", '{"mAP_50": 0.9}'], env)
    r2 = run(["register", "--name", "test", "--path", dummy_pt,
              "--metrics", '{"mAP_50": 0.8}'], env)
    r3 = run(["register", "--name", "test", "--path", dummy_pt], env)

    id_no_metric = extract_id(r3.stdout)

    r = run(["list", "--sort-by", "mAP_50"], env)
    assert r.returncode == 0

    # list 最後一行含有 id_no_metric（缺值排末尾）
    lines = [l for l in r.stdout.splitlines() if "m_" in l]
    assert any(id_no_metric[:12] in l or id_no_metric in l for l in [lines[-1]])


# ── #19 registry.json 結構損毀 ───────────────────────────────────────────────
def test_19_corrupted_registry(registry_env):
    env, tmp_path = registry_env
    reg_path = tmp_path / "registry.json"
    reg_path.write_text('{"schema_version":"1.0","models":null}')

    r = run(["list"], env)
    assert r.returncode == 1
    assert "corrupted" in r.stderr


# ── #20 delete 後版本號從 v1 重新開始 ────────────────────────────────────────
def test_20_version_reuse_after_delete(registry_env, dummy_pt):
    env, _ = registry_env
    r1 = run(["register", "--name", "test", "--path", dummy_pt], env)
    mid = extract_id(r1.stdout)
    run(["delete", "--id", mid], env)

    r2 = run(["register", "--name", "test", "--path", dummy_pt], env)
    assert r2.returncode == 0
    assert "v1" in r2.stdout


# ── #21 --sort-by key 完全不存在（Warning） ───────────────────────────────────
def test_21_sort_by_key_not_found_warning(registry_env, dummy_pt):
    env, _ = registry_env
    run(["register", "--name", "test", "--path", dummy_pt], env)
    r = run(["list", "--sort-by", "unknown_key"], env)
    assert r.returncode == 0
    assert "Sort key 'unknown_key' not found" in r.stderr


# ── #22 MLREG_REGISTRY_PATH 為目錄 ───────────────────────────────────────────
def test_22_registry_path_is_directory(tmp_path):
    import os
    env = os.environ.copy()
    env["MLREG_REGISTRY_PATH"] = str(tmp_path)  # 目錄
    r = run(["list"], env)
    assert r.returncode == 1
    assert "is a directory" in r.stderr


# ── #23 MLREG_REGISTRY_PATH 自訂路徑 ─────────────────────────────────────────
def test_23_custom_registry_path(tmp_path, dummy_pt):
    import os
    custom = tmp_path / "custom" / "reg.json"
    custom.parent.mkdir(parents=True)
    env = os.environ.copy()
    env["MLREG_REGISTRY_PATH"] = str(custom)

    r = run(["register", "--name", "test", "--path", dummy_pt], env)
    assert r.returncode == 0
    assert custom.exists()


# ── #23b MLREG_REGISTRY_PATH parent dir 不存在 ───────────────────────────────
def test_23b_registry_path_parent_not_exist(tmp_path):
    import os
    env = os.environ.copy()
    env["MLREG_REGISTRY_PATH"] = str(tmp_path / "nonexistent" / "reg.json")
    r = run(["list"], env)
    assert r.returncode == 1
    assert "does not exist" in r.stderr


# ── #24 schema_version 不支援 ────────────────────────────────────────────────
def test_24_unsupported_schema_version(registry_env):
    env, tmp_path = registry_env
    reg_path = tmp_path / "registry.json"
    reg_path.write_text('{"schema_version":"2.0","models":[]}')

    r = run(["list"], env)
    assert r.returncode == 1
    assert "Unsupported schema version" in r.stderr
