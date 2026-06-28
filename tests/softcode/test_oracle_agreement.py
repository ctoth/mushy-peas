from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from mushy_peas.softcode import FunctionCall, parse_expression, render
from mushy_peas.softcode.function_metadata import load_function_registry
from mushy_peas.softcode.model import Argument, Document, Node
from tests.oracle.pennmush_softcode_oracle import (
    SoftcodeTraceEvent,
    run_softcode_trace,
    softcode_oracle_available,
)

FIXTURE = Path("tests/fixtures/softcode/pennmush-functions.json")


@pytest.mark.skipif(
    not softcode_oracle_available(),
    reason="PennMUSH softcode trace oracle is not available",
)
@settings(max_examples=5, deadline=None)
@given(st.integers(min_value=0, max_value=50), st.integers(min_value=0, max_value=50))
def test_generated_add_calls_match_oracle_argument_boundaries(
    left: int,
    right: int,
) -> None:
    source = f"add({left},{right})"
    registry = load_function_registry(FIXTURE)
    document = parse_expression(source, metadata=registry)
    trace = run_softcode_trace(source)
    call = _function_calls(document)[0]
    function_event = _trace_events(trace.events, "function")[0]
    argument_events = _trace_events(trace.events, "argument")

    assert render(document, source) == source
    assert function_event.function_name == call.name
    assert function_event.source_start == call.name_span.start
    assert function_event.source_end == call.open_paren + 1
    assert [
        (event.source_start, event.source_end, event.value)
        for event in argument_events
    ] == [
        (argument.span.start, argument.span.end, render(argument, source))
        for argument in call.arguments
    ]


def _function_calls(document: Document) -> list[FunctionCall]:
    calls: list[FunctionCall] = []
    for child in document.children:
        _collect_function_calls(child, calls)
    return calls


def _collect_function_calls(node: Node, calls: list[FunctionCall]) -> None:
    if isinstance(node, FunctionCall):
        calls.append(node)
        for argument in node.arguments:
            _collect_function_calls(argument, calls)
    elif isinstance(node, Argument):
        for child in node.children:
            _collect_function_calls(child, calls)


def _trace_events(
    events: tuple[SoftcodeTraceEvent, ...],
    kind: str,
) -> list[SoftcodeTraceEvent]:
    return [event for event in events if event.kind == kind]
