"""PennMUSH softcode function metadata."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast


@dataclass(frozen=True)
class FunctionMetadata:
    name: str
    min_args: int
    max_args: int
    flags: int
    flag_names: tuple[str, ...]
    is_builtin: bool

    @property
    def is_noparse(self) -> bool:
        return "FN_NOPARSE" in self.flag_names

    @property
    def is_literal(self) -> bool:
        return "FN_LITERAL" in self.flag_names


@dataclass(frozen=True)
class FunctionRegistry:
    pennmush_commit: str
    functions: dict[str, FunctionMetadata]

    def get(self, name: str) -> FunctionMetadata | None:
        return self.functions.get(name.upper())

    def require(self, name: str) -> FunctionMetadata:
        normalized = name.upper()
        metadata = self.functions.get(normalized)
        if metadata is None:
            raise KeyError(f"missing PennMUSH function metadata: {normalized}")
        return metadata


def load_function_registry(path: Path) -> FunctionRegistry:
    payload = _load_json_object(path)
    provenance = _expect_object(payload, "provenance")
    pennmush_commit = _expect_str(provenance, "pennmush_commit")
    raw_functions = _expect_list(payload, "functions")
    functions: dict[str, FunctionMetadata] = {}
    for raw_function in raw_functions:
        function = _parse_function(_expect_payload_object(raw_function))
        functions[function.name] = function
    return FunctionRegistry(
        pennmush_commit=pennmush_commit,
        functions=functions,
    )


def _parse_function(payload: dict[str, Any]) -> FunctionMetadata:
    name = _expect_str(payload, "name")
    return FunctionMetadata(
        name=name,
        min_args=_expect_int(payload, "min_args"),
        max_args=_expect_int(payload, "max_args"),
        flags=_expect_int(payload, "flags"),
        flag_names=tuple(_expect_str_list(payload, "flag_names")),
        is_builtin=_expect_bool(payload, "is_builtin"),
    )


def _load_json_object(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        payload_any: Any = json.load(stream)
    return _expect_payload_object(payload_any)


def _expect_payload_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return cast(dict[str, Any], value)
    raise ValueError("expected JSON object")


def _expect_object(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if isinstance(value, dict):
        return cast(dict[str, Any], value)
    raise ValueError(f"{key} must be an object")


def _expect_list(payload: dict[str, Any], key: str) -> list[Any]:
    value = payload.get(key)
    if isinstance(value, list):
        return cast(list[Any], value)  # type: ignore[redundant-cast]
    raise ValueError(f"{key} must be a list")


def _expect_str_list(payload: dict[str, Any], key: str) -> list[str]:
    values = _expect_list(payload, key)
    if all(isinstance(value, str) for value in values):
        return cast(list[str], values)
    raise ValueError(f"{key} must be a list of strings")


def _expect_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if isinstance(value, str):
        return value
    raise ValueError(f"{key} must be a string")


def _expect_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, int):
        return value
    raise ValueError(f"{key} must be an int")


def _expect_bool(payload: dict[str, Any], key: str) -> bool:
    value = payload.get(key)
    if isinstance(value, bool):
        return value
    raise ValueError(f"{key} must be a bool")
