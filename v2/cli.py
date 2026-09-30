"""
cli.py — CLI_Layer：Typer app，5 個指令（v2.0）
v2.0 新增：compare 指令、--output 旗標、--soft 旗標、--show-archived 旗標
依賴：registry.py, exceptions.py
"""

from __future__ import annotations

import json
import sys
from typing import List, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

try:
    from exceptions import MlregError, UnsupportedOutputFormatError
    from registry import Registry
    from utils import parse_json_object
except ImportError:
    from .exceptions import MlregError, UnsupportedOutputFormatError
    from .registry import Registry
    from .utils import parse_json_object

app = typer.Typer(add_completion=False)
console = Console()
err_console = Console(stderr=True)

SUPPORTED_OUTPUT_FORMATS = ("table", "json")


def _handle_error(e: MlregError) -> None:
    err_console.print(str(e))
    raise typer.Exit(code=e.exit_code)


def _validate_output_format(output: str) -> None:
    if output not in SUPPORTED_OUTPUT_FORMATS:
        raise UnsupportedOutputFormatError(
            f"Error: Unsupported output format '{output}'. "
            f"Supported formats: {', '.join(SUPPORTED_OUTPUT_FORMATS)}."
        )


# ── register ──────────────────────────────────────────────────────────────────

@app.command()
def register(
    name: str = typer.Option(..., "--name", help="專案/模型群組名稱"),
    path: str = typer.Option(..., "--path", help="模型權重檔本地路徑"),
    version: Optional[str] = typer.Option(None, "--version", help="指定版本號；未指定時自動遞增"),
    metrics: Optional[str] = typer.Option(None, "--metrics", help="效能指標 JSON，預設 {}"),
    params: Optional[str] = typer.Option(None, "--params", help="訓練超參數 JSON，預設 {}"),
) -> None:
    """Register a new model version."""
    try:
        metrics_dict = parse_json_object(metrics) if metrics else {}
        params_dict = parse_json_object(params) if params else {}
        record = Registry().register(
            name=name,
            path=path,
            version=version,
            metrics=metrics_dict,
            hyperparameters=params_dict,
        )
    except MlregError as e:
        _handle_error(e)
        return

    console.print(f"Successfully registered model: {record.project_name}")
    console.print(f"   ID      : {record.id}")
    console.print(f"   Version : {record.version}")
    console.print(f"   Path    : {record.file_path}")


# ── list ──────────────────────────────────────────────────────────────────────

@app.command(name="list")
def list_models(
    name: Optional[str] = typer.Option(None, "--name", help="篩選指定 project_name"),
    sort_by: Optional[str] = typer.Option(None, "--sort-by", help="依指定 metric key 排序"),
    desc: bool = typer.Option(False, "--desc", is_flag=True, help="啟用降冪排序"),
    output: str = typer.Option("table", "--output", help="輸出格式：table（預設）或 json"),
    show_archived: bool = typer.Option(False, "--show-archived", is_flag=True, help="顯示已封存記錄"),
) -> None:
    """List registered models."""
    if desc and sort_by is None:
        err_console.print("Error: --desc requires --sort-by.")
        raise typer.Exit(code=1)

    try:
        _validate_output_format(output)
        records, sort_key_found = Registry().list_models(
            name=name, sort_by=sort_by, desc=desc, show_archived=show_archived
        )
    except MlregError as e:
        _handle_error(e)
        return

    if not sort_key_found:
        err_console.print(f"Warning: Sort key '{sort_by}' not found in any record.")

    if output == "json":
        # JSON 輸出：不含任何 Rich 裝飾字元
        print(json.dumps([r.to_dict() for r in records], ensure_ascii=False, indent=2))
        return

    # table 輸出（預設，與 v1.0 相容）
    if not records:
        if name:
            console.print("Info: No models found matching criteria.")
        else:
            console.print("Info: No models registered yet.")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("ID")
    table.add_column("Project Name")
    table.add_column("Version")
    table.add_column("File Path")
    table.add_column("Created At")
    if show_archived:
        table.add_column("Status")

    for r in records:
        if show_archived:
            status = "[archived]" if r.archived else ""
            table.add_row(r.id, r.project_name, r.version, r.file_path, r.created_at, status)
        else:
            table.add_row(r.id, r.project_name, r.version, r.file_path, r.created_at)

    console.print(table)


# ── info ──────────────────────────────────────────────────────────────────────

@app.command()
def info(
    id: str = typer.Option(..., "--id", help="查詢指定 ID 的模型完整資訊"),
    output: str = typer.Option("table", "--output", help="輸出格式：table（預設）或 json"),
) -> None:
    """Show detailed info for a model."""
    try:
        _validate_output_format(output)
        record = Registry().get_model(id)
    except MlregError as e:
        _handle_error(e)
        return

    if output == "json":
        print(json.dumps(record.to_dict(), ensure_ascii=False, indent=2))
        return

    # table 輸出（預設，與 v1.0 相容）
    lines = [
        f"ID             : {record.id}",
        f"Project Name   : {record.project_name}",
        f"Version        : {record.version}",
        f"File Path      : {record.file_path}",
        f"Created At     : {record.created_at}",
        f"Status         : {'archived' if record.archived else 'active'}",
        "",
        "Metrics:",
    ]
    if record.metrics:
        for k, v in record.metrics.items():
            lines.append(f"  {k:<14} : {v}")
    else:
        lines.append("  (none)")

    lines += ["", "Hyperparameters:"]
    if record.hyperparameters:
        for k, v in record.hyperparameters.items():
            lines.append(f"  {k:<14} : {v}")
    else:
        lines.append("  (none)")

    panel = Panel("\n".join(lines), title=f"Model Info: {record.id}")
    console.print(panel)


# ── delete ────────────────────────────────────────────────────────────────────

@app.command()
def delete(
    id: str = typer.Option(..., "--id", help="刪除指定 ID 的模型紀錄"),
    soft: bool = typer.Option(False, "--soft", is_flag=True, help="軟刪除（封存）而非硬刪除"),
) -> None:
    """Delete (or archive) a model record."""
    try:
        Registry().delete_model(id, soft=soft)
    except MlregError as e:
        _handle_error(e)
        return

    if soft:
        console.print(f"Successfully archived model: {id}")
    else:
        console.print(f"Successfully deleted model: {id}")


# ── compare ───────────────────────────────────────────────────────────────────

@app.command()
def compare(
    ids: List[str] = typer.Option(..., "--id", help="要比較的模型 ID（至少 2 個，可重複使用）"),
    output: str = typer.Option("table", "--output", help="輸出格式：table（預設）或 json"),
) -> None:
    """Compare multiple model versions side by side."""
    try:
        _validate_output_format(output)
        records = Registry().compare_models(ids)
    except MlregError as e:
        _handle_error(e)
        return

    if output == "json":
        print(json.dumps([r.to_dict() for r in records], ensure_ascii=False, indent=2))
        return

    # 收集所有 metrics 與 hyperparameters 的 key（保持插入順序）
    all_metric_keys: list[str] = []
    all_param_keys: list[str] = []
    for r in records:
        for k in r.metrics:
            if k not in all_metric_keys:
                all_metric_keys.append(k)
        for k in r.hyperparameters:
            if k not in all_param_keys:
                all_param_keys.append(k)

    # 建立 Rich Table
    table = Table(show_header=True, header_style="bold")
    table.add_column("Field", style="bold")
    for r in records:
        table.add_column(r.id)

    # 基本欄位
    def _row(label: str, getter) -> None:
        table.add_row(label, *[str(getter(r)) for r in records])

    _row("Project Name", lambda r: r.project_name)
    _row("Version", lambda r: r.version)
    _row("File Path", lambda r: r.file_path)
    _row("Created At", lambda r: r.created_at)
    _row("Status", lambda r: "archived" if r.archived else "active")

    # Metrics
    if all_metric_keys:
        table.add_row("[Metrics]", *["" for _ in records])
        for k in all_metric_keys:
            table.add_row(
                f"  {k}",
                *[str(r.metrics[k]) if k in r.metrics else "\u2014" for r in records],
            )

    # Hyperparameters
    if all_param_keys:
        table.add_row("[Hyperparameters]", *["" for _ in records])
        for k in all_param_keys:
            table.add_row(
                f"  {k}",
                *[str(r.hyperparameters[k]) if k in r.hyperparameters else "\u2014" for r in records],
            )

    console.print(table)
