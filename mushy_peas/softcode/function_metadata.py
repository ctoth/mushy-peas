"""PennMUSH softcode function metadata."""

from __future__ import annotations

import argparse
import json
import re
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


def generate_function_metadata_fixture(
    pennmush_checkout: Path,
    *,
    pennmush_commit: str,
) -> dict[str, Any]:
    flag_values = _parse_flag_values(pennmush_checkout / "hdrs" / "function.h")
    constants = {
        "INT_MAX": 2_147_483_647,
        "MAX_STACK_ARGS": _parse_max_stack_args(pennmush_checkout / "hdrs" / "conf.h"),
    }
    functions = _parse_function_table(
        pennmush_checkout / "src" / "function.c",
        flag_values=flag_values,
        constants=constants,
    )
    return {
        "provenance": {
            "pennmush_commit": pennmush_commit,
            "source_files": [
                str((pennmush_checkout / "hdrs" / "function.h").as_posix()),
                str((pennmush_checkout / "hdrs" / "conf.h").as_posix()),
                str((pennmush_checkout / "src" / "function.c").as_posix()),
            ],
            "notes": "Generated from PennMUSH function table source.",
        },
        "flag_values": dict(sorted(flag_values.items())),
        "functions": [
            _function_to_json(function)
            for function in sorted(functions, key=lambda item: item.name)
        ],
    }


def write_function_metadata_fixture(
    pennmush_checkout: Path,
    output_path: Path,
    *,
    pennmush_commit: str,
) -> None:
    payload = generate_function_metadata_fixture(
        pennmush_checkout,
        pennmush_commit=pennmush_commit,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate PennMUSH softcode function metadata.",
    )
    parser.add_argument("pennmush_checkout", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--pennmush-commit", required=True)
    args = parser.parse_args(argv)

    write_function_metadata_fixture(
        args.pennmush_checkout,
        args.output,
        pennmush_commit=args.pennmush_commit,
    )
    return 0


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


def _function_to_json(function: FunctionMetadata) -> dict[str, Any]:
    return {
        "name": function.name,
        "min_args": function.min_args,
        "max_args": function.max_args,
        "flags": function.flags,
        "flag_names": list(function.flag_names),
        "is_builtin": function.is_builtin,
    }


def _parse_flag_values(path: Path) -> dict[str, int]:
    values: dict[str, int] = {}
    pattern = re.compile(r"^#define\s+(FN_[A-Z0-9_]+)\s+(0x[0-9A-Fa-f]+|\d+)\b")
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = pattern.match(line)
        if match is None:
            continue
        values[match.group(1)] = int(match.group(2), 0)
    return values


def _parse_max_stack_args(path: Path) -> int:
    text = path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"#define\s+MAX_STACK_ARGS\s+\\?\s*\n?\s*(\d+)\b", text)
    if match is None:
        raise ValueError("MAX_STACK_ARGS definition not found")
    return int(match.group(1))


def _parse_function_table(
    path: Path,
    *,
    flag_values: dict[str, int],
    constants: dict[str, int],
) -> tuple[FunctionMetadata, ...]:
    source = path.read_text(encoding="utf-8", errors="replace")
    text = _strip_c_comments(_strip_debug_preprocessor_blocks(source))
    table = _extract_function_table(text)
    entry_pattern = re.compile(
        r'\{\s*"(?P<name>[^"]+)"\s*,'
        r"\s*(?P<implementation>[A-Za-z0-9_]+)\s*,"
        r"\s*(?P<min_args>[^,]+)\s*,"
        r"\s*(?P<max_args>[^,]+)\s*,"
        r"\s*(?P<flags>.*?)\s*\}",
        re.DOTALL,
    )
    functions: dict[str, FunctionMetadata] = {}
    for match in entry_pattern.finditer(table):
        name = match.group("name").upper()
        flag_names, flags = _evaluate_flags(match.group("flags"), flag_values)
        functions[name] = FunctionMetadata(
            name=name,
            min_args=_evaluate_int_expression(match.group("min_args"), constants),
            max_args=_evaluate_int_expression(match.group("max_args"), constants),
            flags=flags,
            flag_names=flag_names,
            is_builtin=True,
        )
    return tuple(functions.values())


def _strip_c_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)


def _strip_debug_preprocessor_blocks(text: str) -> str:
    text = re.sub(
        r"#if\s+defined\(ANSI_DEBUG\)\s+\|\|\s+defined\(DEBUG_PENNMUSH\)"
        r".*?#endif",
        "",
        text,
        flags=re.DOTALL,
    )
    return re.sub(r"#ifdef\s+DEBUG_PENNMUSH.*?#endif", "", text, flags=re.DOTALL)


def _extract_function_table(text: str) -> str:
    start_match = re.search(r"FUNTAB\s+flist\[\]\s*=\s*\{", text)
    if start_match is None:
        raise ValueError("FUNTAB flist table not found")
    end_match = re.search(r"\{\s*NULL\s*,\s*NULL\s*,\s*0\s*,\s*0\s*,\s*0\s*\}", text)
    if end_match is None or end_match.start() <= start_match.end():
        raise ValueError("FUNTAB flist terminator not found")
    return text[start_match.end() : end_match.start()]


def _evaluate_flags(
    expression: str,
    flag_values: dict[str, int],
) -> tuple[tuple[str, ...], int]:
    names = tuple(
        token.strip()
        for token in expression.replace("\n", " ").split("|")
        if token.strip()
    )
    flags = 0
    for name in names:
        if name not in flag_values:
            raise ValueError(f"unknown function flag: {name}")
        flags |= flag_values[name]
    return names, flags


def _evaluate_int_expression(expression: str, constants: dict[str, int]) -> int:
    value = 0
    sign = 1
    token = ""
    for char in expression.strip().replace("(", "").replace(")", ""):
        if char in "+-":
            if token.strip():
                value += sign * _evaluate_int_token(token.strip(), constants)
            token = ""
            sign = 1 if char == "+" else -1
        else:
            token += char
    if token.strip():
        value += sign * _evaluate_int_token(token.strip(), constants)
    return value


def _evaluate_int_token(token: str, constants: dict[str, int]) -> int:
    if token in constants:
        return constants[token]
    return int(token, 0)


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


if __name__ == "__main__":
    raise SystemExit(main())
