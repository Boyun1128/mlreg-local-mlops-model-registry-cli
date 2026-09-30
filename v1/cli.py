"""
cli.py — CLI_Layer：Typer app，4 個指令
依賴：registry.py, exceptions.py
"""

from __future__ import annotations

import sys
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

try:
    from exceptions import MlregError
    from registry import Registry
    from utils import parse_json_object
except ImportError:
    from .exceptions import MlregError
    from .registry import Registry
    from .utils import parse_json_object

app = typer.Typer(add_completion=False)
console = Console()
err_console = Console(stderr=True)


def _handle_error(e: MlregError) -> None:
    err_console.print(str(e))
    raise typer.Exit(code=e.exit_code)


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
) -> None:
    """List registered models."""
    if desc and sort_by is None:
        err_console.print("Error: --desc requires --sort-by.")
        raise typer.Exit(code=1)

    try:
        records, sort_key_found = Registry().list_models(
            name=name, sort_by=sort_by, desc=desc
        )
    except MlregError as e:
        _handle_error(e)
        return

    if not sort_key_found:
        err_console.print(f"Warning: Sort key '{sort_by}' not found in any record.")

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

    for r in records:
        table.add_row(r.id, r.project_name, r.version, r.file_path, r.created_at)

    console.print(table)


# ── info ──────────────────────────────────────────────────────────────────────

@app.command()
def info(
    id: str = typer.Option(..., "--id", help="查詢指定 ID 的模型完整資訊"),
) -> None:
    """Show detailed info for a model."""
    try:
        record = Registry().get_model(id)
    except MlregError as e:
        _handle_error(e)
        return

    lines = [
        f"ID             : {record.id}",
        f"Project Name   : {record.project_name}",
        f"Version        : {record.version}",
        f"File Path      : {record.file_path}",
        f"Created At     : {record.created_at}",
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
) -> None:
    """Delete a model record (does not delete the actual file)."""
    try:
        Registry().delete_model(id)
    except MlregError as e:
        _handle_error(e)
        return

    console.print(f"Successfully deleted model: {id}")
