"""PennMUSH softcode parse-trace oracle support.

This module is intentionally separate from the server-load oracle. The load
oracle proves database acceptance; this oracle is for machine-readable
`process_expression()` parse decisions.
"""

import json
import shlex
from dataclasses import dataclass
from typing import Any, Literal, TypeAlias, cast

from tests.oracle.pennmush_oracle import (
    DEFAULT_WSL_CHECKOUT,
    oracle_available,
    prepare_oracle_game_dir,
    read_wsl_text,
    run_wsl_command,
)

TraceEventKind: TypeAlias = Literal[
    "arity_error",
    "enter",
    "exit",
    "escape",
    "literal",
    "percent_sub",
    "brace_group",
    "eval_group",
    "function",
    "argument",
    "terminator",
    "unknown_function",
]

TRACE_GAME_NAME = "softcode-trace"


@dataclass(frozen=True)
class SoftcodeTraceEvent:
    kind: TraceEventKind
    depth: int
    source_start: int | None = None
    source_end: int | None = None
    output_start: int | None = None
    output_end: int | None = None
    eflags: int | None = None
    tflags: int | None = None
    function_name: str | None = None
    function_flags: int | None = None
    min_args: int | None = None
    max_args: int | None = None
    actual_args: int | None = None
    argument_index: int | None = None
    mandatory: bool | None = None
    terminator: str | None = None
    raw: str | None = None
    value: str | None = None


@dataclass(frozen=True)
class SoftcodeTrace:
    source: str
    result: str
    events: tuple[SoftcodeTraceEvent, ...]


def softcode_oracle_available() -> bool:
    return oracle_available()


def run_softcode_trace(
    source: str,
    *,
    eflags: str = "PE_DEFAULT",
    tflags: str = "PT_DEFAULT",
) -> SoftcodeTrace:
    game_dir = prepare_oracle_game_dir(TRACE_GAME_NAME, compression="none")
    command = (
        f"cd {shlex.quote(game_dir)} && "
        f"{shlex.quote(DEFAULT_WSL_CHECKOUT)}/src/netmud "
        f"--no-session --softcode-trace-jsonl "
        f"--eflags {shlex.quote(eflags)} --tflags {shlex.quote(tflags)} "
        "mush.cnf"
    )
    completed = run_wsl_command(
        command,
        input_data=source.encode("utf-8"),
        check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace")
        stdout = completed.stdout.decode("utf-8", errors="replace")
        raise RuntimeError(
            f"PennMUSH softcode oracle failed with exit "
            f"{completed.returncode}: stdout={stdout} stderr={stderr}"
        )
    log = read_wsl_text(f"{game_dir}/log/netmush.log")
    return parse_trace_output(source, _json_lines(log))


def parse_trace_output(source: str, output: str) -> SoftcodeTrace:
    result: str | None = None
    events: list[SoftcodeTraceEvent] = []
    for line in output.splitlines():
        payload_any: Any = json.loads(line)
        if not isinstance(payload_any, dict):
            raise ValueError("trace line must be a JSON object")
        payload = cast(dict[str, Any], payload_any)
        if payload.get("kind") == "result":
            result = _expect_optional_str(payload, "value")
            continue
        events.append(_parse_event(payload))
    if result is None:
        raise ValueError("trace output is missing a result event")
    return SoftcodeTrace(source=source, result=result, events=tuple(events))


def _json_lines(log: str) -> str:
    return "\n".join(line for line in log.splitlines() if line.startswith("{"))


def _parse_event(payload: dict[str, Any]) -> SoftcodeTraceEvent:
    kind = _expect_kind(payload)
    depth = _expect_int(payload, "depth")
    return SoftcodeTraceEvent(
        kind=kind,
        depth=depth,
        source_start=_expect_optional_int(payload, "source_start"),
        source_end=_expect_optional_int(payload, "source_end"),
        output_start=_expect_optional_int(payload, "output_start"),
        output_end=_expect_optional_int(payload, "output_end"),
        eflags=_expect_optional_int(payload, "eflags"),
        tflags=_expect_optional_int(payload, "tflags"),
        function_name=_expect_optional_str(payload, "function_name"),
        function_flags=_expect_optional_int(payload, "function_flags"),
        min_args=_expect_optional_int(payload, "min_args"),
        max_args=_expect_optional_int(payload, "max_args"),
        actual_args=_expect_optional_int(payload, "actual_args"),
        argument_index=_expect_optional_int(payload, "argument_index"),
        mandatory=_expect_optional_bool(payload, "mandatory"),
        terminator=_expect_optional_str(payload, "terminator"),
        raw=_expect_optional_str(payload, "raw"),
        value=_expect_optional_str(payload, "value"),
    )


def _expect_kind(payload: dict[str, Any]) -> TraceEventKind:
    value = payload.get("kind")
    match value:
        case (
            "arity_error"
            | "enter"
            | "exit"
            | "escape"
            | "literal"
            | "percent_sub"
            | "brace_group"
            | "eval_group"
            | "function"
            | "argument"
            | "terminator"
            | "unknown_function"
        ):
            return cast(TraceEventKind, value)
        case _:
            raise ValueError(f"unexpected trace event kind: {value!r}")


def _expect_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, int):
        return value
    raise ValueError(f"{key} must be an int")


def _expect_optional_int(payload: dict[str, Any], key: str) -> int | None:
    value = payload.get(key)
    if value is None or isinstance(value, int):
        return value
    raise ValueError(f"{key} must be an int or null")


def _expect_optional_bool(payload: dict[str, Any], key: str) -> bool | None:
    value = payload.get(key)
    if value is None or isinstance(value, bool):
        return value
    raise ValueError(f"{key} must be a bool or null")


def _expect_optional_str(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None or isinstance(value, str):
        return value
    raise ValueError(f"{key} must be a string or null")
