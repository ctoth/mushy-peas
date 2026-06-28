import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tests.oracle.pennmush_softcode_oracle import (
    SoftcodeTraceEvent,
    parse_trace_output,
    run_softcode_trace,
    softcode_oracle_available,
)


def test_parse_trace_output_accepts_jsonl_contract() -> None:
    trace = parse_trace_output(
        "add(1,2)",
        "\n".join(
            (
                '{"kind":"enter","depth":0,"source_start":0,'
                '"source_end":8,"eflags":55,"tflags":0}',
                '{"kind":"function","depth":0,"source_start":0,'
                '"source_end":8,"function_name":"ADD","function_flags":1}',
                '{"kind":"argument","depth":1,"argument_index":0,'
                '"source_start":4,"source_end":5,"value":"1"}',
                '{"kind":"argument","depth":1,"argument_index":1,'
                '"source_start":6,"source_end":7,"value":"2"}',
                '{"kind":"exit","depth":0,"source_start":0,'
                '"source_end":8,"output_start":0,"output_end":1}',
                '{"kind":"result","value":"3"}',
            )
        ),
    )

    assert trace.source == "add(1,2)"
    assert trace.result == "3"
    assert trace.events == (
        SoftcodeTraceEvent(
            kind="enter",
            depth=0,
            source_start=0,
            source_end=8,
            eflags=55,
            tflags=0,
        ),
        SoftcodeTraceEvent(
            kind="function",
            depth=0,
            source_start=0,
            source_end=8,
            function_name="ADD",
            function_flags=1,
        ),
        SoftcodeTraceEvent(
            kind="argument",
            depth=1,
            source_start=4,
            source_end=5,
            argument_index=0,
            value="1",
        ),
        SoftcodeTraceEvent(
            kind="argument",
            depth=1,
            source_start=6,
            source_end=7,
            argument_index=1,
            value="2",
        ),
        SoftcodeTraceEvent(
            kind="exit",
            depth=0,
            source_start=0,
            source_end=8,
            output_start=0,
            output_end=1,
        ),
    )


def test_parse_trace_output_rejects_unknown_event_kind() -> None:
    with pytest.raises(ValueError, match="unexpected trace event kind"):
        parse_trace_output(
            "text",
            '{"kind":"surprise","depth":0}\n{"kind":"result","value":"text"}',
        )


def test_parse_trace_output_requires_result_event() -> None:
    with pytest.raises(ValueError, match="missing a result event"):
        parse_trace_output("text", '{"kind":"literal","depth":0,"raw":"text"}')


@pytest.mark.skipif(
    not softcode_oracle_available(),
    reason="PennMUSH softcode trace oracle is not available",
)
def test_live_softcode_trace_oracle_smoke() -> None:
    trace = run_softcode_trace("add(1,2)")

    assert trace.result == "3"
    assert any(event.kind == "function" for event in trace.events)


@pytest.mark.skipif(
    not softcode_oracle_available(),
    reason="PennMUSH softcode trace oracle is not available",
)
@settings(max_examples=5, deadline=None)
@given(st.integers(min_value=0, max_value=50), st.integers(min_value=0, max_value=50))
def test_generated_add_calls_trace_arguments(left: int, right: int) -> None:
    trace = run_softcode_trace(f"add({left},{right})")
    function_events = [
        event
        for event in trace.events
        if event.kind == "function" and event.function_name == "ADD"
    ]
    argument_values = [
        event.value for event in trace.events if event.kind == "argument"
    ]

    assert trace.result == str(left + right)
    assert len(function_events) == 1
    assert argument_values == [str(left), str(right)]
