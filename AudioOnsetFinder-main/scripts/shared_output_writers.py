"""Shared output helpers for standalone onset batch and report scripts.

When WildAudioWorlds' shared package tree is available, these helpers publish
final artifacts through the shared DataManager. Legacy standalone script usage
still falls back to direct local writes.
"""

from __future__ import annotations

import io
import os
import tempfile
from pathlib import Path
from typing import Any, Callable

try:
    from .shared_data_manager import SharedDataManager as _SharedDataManager
except ImportError:
    from shared_data_manager import SharedDataManager as _SharedDataManager


def _ensure_parent_dir(output_path: str | Path) -> None:
    parent_dir = Path(output_path).parent
    if str(parent_dir) and not parent_dir.exists():
        parent_dir.mkdir(parents=True, exist_ok=True)


def write_text_output(output_path: str | Path, content: str) -> None:
    _ensure_parent_dir(output_path)
    if _SharedDataManager is not None:
        _SharedDataManager.write_text_file(output_path, content)
        return

    with Path(output_path).open("w", encoding="utf-8") as handle:
        handle.write(content)


def write_csv_dataframe(output_path: str | Path, dataframe: Any, *, index: bool = False) -> None:
    _ensure_parent_dir(output_path)
    if _SharedDataManager is not None:
        _SharedDataManager.write_csv_dataframe(output_path, dataframe, index=index)
        return

    dataframe.to_csv(output_path, index=index)


def write_workbook_sheets(
    output_path: str | Path,
    workbook_sheets: dict[str, Any],
    *,
    postprocess_workbook: Callable[[Path], None] | None = None,
) -> None:
    import pandas as pd

    output_path_obj = Path(output_path)
    _ensure_parent_dir(output_path_obj)

    if _SharedDataManager is None and postprocess_workbook is None:
        with pd.ExcelWriter(output_path_obj, engine="openpyxl") as writer:
            for sheet_name, sheet_df in workbook_sheets.items():
                sheet_df.to_excel(writer, sheet_name=sheet_name, index=False)
        return

    temp_file = tempfile.NamedTemporaryFile(suffix=output_path_obj.suffix or ".xlsx", delete=False)
    temp_file_path = Path(temp_file.name)
    temp_file.close()
    try:
        with pd.ExcelWriter(temp_file_path, engine="openpyxl") as writer:
            for sheet_name, sheet_df in workbook_sheets.items():
                sheet_df.to_excel(writer, sheet_name=sheet_name, index=False)

        if postprocess_workbook is not None:
            postprocess_workbook(temp_file_path)

        workbook_bytes = temp_file_path.read_bytes()
        if _SharedDataManager is not None:
            _SharedDataManager.write_binary_file(output_path_obj, workbook_bytes)
        else:
            output_path_obj.write_bytes(workbook_bytes)
    finally:
        temp_file_path.unlink(missing_ok=True)


def save_matplotlib_figure(figure_or_module: Any, output_path: str | Path, **savefig_kwargs: Any) -> None:
    _ensure_parent_dir(output_path)
    if _SharedDataManager is not None:
        buffer = io.BytesIO()
        format_name = Path(output_path).suffix.lstrip(".").lower() or "png"
        figure_or_module.savefig(buffer, format=format_name, **savefig_kwargs)
        _SharedDataManager.write_binary_file(output_path, buffer.getvalue())
        return

    figure_or_module.savefig(output_path, **savefig_kwargs)


__all__ = [
    "save_matplotlib_figure",
    "save_openpyxl_workbook",
    "write_csv_dataframe",
    "write_text_output",
    "write_workbook_sheets",
]


def save_openpyxl_workbook(workbook: Any, output_path: str | Path) -> None:
    output_path_obj = Path(output_path)
    _ensure_parent_dir(output_path_obj)

    temp_file = tempfile.NamedTemporaryFile(suffix=output_path_obj.suffix or ".xlsx", delete=False)
    temp_file_path = Path(temp_file.name)
    temp_file.close()
    try:
        workbook.save(temp_file_path)
        workbook_bytes = temp_file_path.read_bytes()
        if _SharedDataManager is not None:
            _SharedDataManager.write_binary_file(output_path_obj, workbook_bytes)
        else:
            output_path_obj.write_bytes(workbook_bytes)
    finally:
        temp_file_path.unlink(missing_ok=True)