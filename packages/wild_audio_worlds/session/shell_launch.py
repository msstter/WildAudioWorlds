"""Shared shell launch and attach CLI helpers."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Sequence


def _load_shell_launch_arg_map() -> dict[str, str]:
    config_path = Path(__file__).with_name("shell_launch_args.json")
    with config_path.open("r", encoding="utf-8") as handle:
        loaded = json.load(handle)
    return {
        str(key): str(value)
        for key, value in loaded.items()
        if isinstance(key, str) and isinstance(value, str)
    }


SHELL_LAUNCH_ARG_MAP = _load_shell_launch_arg_map()


def _text_or_empty(value: Any) -> str:
    return str(value or "").strip()


def build_shell_launch_cli_args(launch_request: dict[str, Any] | None) -> list[str]:
    request = launch_request if isinstance(launch_request, dict) else {}
    cli_args: list[str] = []
    for field_name, flag in SHELL_LAUNCH_ARG_MAP.items():
        value = _text_or_empty(request.get(field_name))
        if value:
            cli_args.extend([flag, value])
    return cli_args


def parse_shell_launch_cli_args(argv: Sequence[str] | None = None) -> tuple[dict[str, str], list[str]]:
    raw_argv = list(argv if argv is not None else sys.argv)
    if not raw_argv:
        raw_argv = [""]

    parsed: dict[str, str] = {}
    remaining = [raw_argv[0]]
    index = 1
    while index < len(raw_argv):
        token = _text_or_empty(raw_argv[index])
        matched_field = None
        matched_value = ""
        consumed_extra = False

        for field_name, flag in SHELL_LAUNCH_ARG_MAP.items():
            if token == flag:
                next_value = raw_argv[index + 1] if index + 1 < len(raw_argv) else ""
                matched_field = field_name
                matched_value = _text_or_empty(next_value)
                consumed_extra = index + 1 < len(raw_argv)
                break

            prefixed_flag = f"{flag}="
            if token.startswith(prefixed_flag):
                matched_field = field_name
                matched_value = _text_or_empty(token[len(prefixed_flag):])
                break

        if matched_field:
            if matched_value:
                parsed[matched_field] = matched_value
            if consumed_extra:
                index += 1
        else:
            remaining.append(raw_argv[index])

        index += 1

    if not parsed.get("sessionId"):
        return {}, remaining

    return parsed, remaining


__all__ = [
    "SHELL_LAUNCH_ARG_MAP",
    "build_shell_launch_cli_args",
    "parse_shell_launch_cli_args",
]