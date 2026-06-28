import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tests.oracle.pennmush_softcode_oracle import (
    SoftcodeTrace,
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
                '"source_end":8,"function_name":"ADD","function_flags":1,'
                '"min_args":2,"max_args":2147483647}',
                '{"kind":"argument","depth":1,"argument_index":0,'
                '"source_start":4,"source_end":5,"raw":"1","value":"1"}',
                '{"kind":"terminator","depth":1,"source_start":5,'
                '"source_end":6,"terminator":",","tflags":12}',
                '{"kind":"argument","depth":1,"argument_index":1,'
                '"source_start":6,"source_end":7,"raw":"2","value":"2"}',
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
            min_args=2,
            max_args=2147483647,
        ),
        SoftcodeTraceEvent(
            kind="argument",
            depth=1,
            source_start=4,
            source_end=5,
            argument_index=0,
            raw="1",
            value="1",
        ),
        SoftcodeTraceEvent(
            kind="terminator",
            depth=1,
            source_start=5,
            source_end=6,
            terminator=",",
            tflags=12,
        ),
        SoftcodeTraceEvent(
            kind="argument",
            depth=1,
            source_start=6,
            source_end=7,
            argument_index=1,
            raw="2",
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
    function_event = _function_events(trace, "ADD")[0]
    argument_events = _argument_events(trace)
    terminator_events = _terminator_events(trace)

    assert trace.result == "3"
    assert function_event.source_start == 0
    assert function_event.source_end == 4
    assert function_event.min_args == 2
    assert function_event.max_args == 2147483647
    assert [(event.raw, event.value) for event in argument_events] == [
        ("1", "1"),
        ("2", "2"),
    ]
    assert [
        (event.source_start, event.source_end, event.terminator, event.tflags)
        for event in terminator_events
    ] == [(5, 6, ",", 12), (7, 8, ")", 12)]


@pytest.mark.skipif(
    not softcode_oracle_available(),
    reason="PennMUSH softcode trace oracle is not available",
)
def test_live_softcode_trace_reports_copied_literal_span() -> None:
    trace = run_softcode_trace("abc")
    literal_events = _literal_events(trace)

    assert trace.result == "abc"
    assert [
        (event.source_start, event.source_end, event.raw, event.value)
        for event in literal_events
    ] == [(0, 3, "abc", "abc")]


@pytest.mark.skipif(
    not softcode_oracle_available(),
    reason="PennMUSH softcode trace oracle is not available",
)
def test_live_softcode_trace_reports_brace_group_span() -> None:
    trace = run_softcode_trace("{abc}")
    brace_events = _events_by_kind(trace, "brace_group")

    assert trace.result == "abc"
    assert [(event.source_start, event.source_end) for event in brace_events] == [
        (0, 5)
    ]


@pytest.mark.skipif(
    not softcode_oracle_available(),
    reason="PennMUSH softcode trace oracle is not available",
)
def test_live_softcode_trace_reports_eval_group_span() -> None:
    trace = run_softcode_trace("[add(1,2)]")
    eval_events = _events_by_kind(trace, "eval_group")

    assert trace.result == "3"
    assert [(event.source_start, event.source_end) for event in eval_events] == [
        (0, 10)
    ]


@pytest.mark.skipif(
    not softcode_oracle_available(),
    reason="PennMUSH softcode trace oracle is not available",
)
def test_live_softcode_trace_reports_percent_substitutions() -> None:
    trace = run_softcode_trace("%r%b")
    percent_events = _events_by_kind(trace, "percent_sub")

    assert trace.result == "\n "
    assert [
        (event.source_start, event.source_end, event.raw, event.value)
        for event in percent_events
    ] == [(0, 2, "%r", "\n"), (2, 4, "%b", " ")]


@pytest.mark.skipif(
    not softcode_oracle_available(),
    reason="PennMUSH softcode trace oracle is not available",
)
def test_live_softcode_trace_reports_regedit_dollar_substitutions() -> None:
    trace = run_softcode_trace("regedit(foo123bar,(123),<$1>)")
    dollar_events = _events_by_kind(trace, "dollar_sub")

    assert trace.result == "foo<123>bar"
    assert [
        (event.source_start, event.source_end, event.raw, event.value)
        for event in dollar_events
    ] == [(-1, -1, "$1", "123")]


@pytest.mark.skipif(
    not softcode_oracle_available(),
    reason="PennMUSH softcode trace oracle is not available",
)
def test_live_softcode_trace_reports_escape_span() -> None:
    trace = run_softcode_trace(r"\%")
    escape_events = _events_by_kind(trace, "escape")

    assert trace.result == "%"
    assert [
        (event.source_start, event.source_end, event.raw, event.value)
        for event in escape_events
    ] == [(0, 2, r"\%", "%")]


@pytest.mark.skipif(
    not softcode_oracle_available(),
    reason="PennMUSH softcode trace oracle is not available",
)
def test_live_softcode_trace_reports_trailing_escape() -> None:
    trace = run_softcode_trace("abc\\")
    escape_events = _events_by_kind(trace, "escape")

    assert trace.result == "abc"
    assert [
        (event.source_start, event.source_end, event.raw, event.value)
        for event in escape_events
    ] == [(3, 4, "\\", "")]


@pytest.mark.skipif(
    not softcode_oracle_available(),
    reason="PennMUSH softcode trace oracle is not available",
)
def test_live_softcode_trace_reports_literal_mode_escape() -> None:
    trace = run_softcode_trace(r"lit(\%)")
    escape_events = _events_by_kind(trace, "escape")

    assert trace.result == r"\%"
    assert [
        (event.source_start, event.source_end, event.raw, event.value)
        for event in escape_events
    ] == [(4, 5, "\\", "\\")]


@pytest.mark.skipif(
    not softcode_oracle_available(),
    reason="PennMUSH softcode trace oracle is not available",
)
def test_live_softcode_trace_reports_function_arity_errors() -> None:
    trace = run_softcode_trace("add(1)")
    arity_events = _events_by_kind(trace, "arity_error")

    assert trace.result == "#-1 FUNCTION (ADD) EXPECTS AT LEAST 2 ARGUMENTS BUT GOT 1"
    assert [
        (
            event.source_start,
            event.source_end,
            event.function_name,
            event.min_args,
            event.max_args,
            event.actual_args,
            event.raw,
            event.value,
        )
        for event in arity_events
    ] == [
        (
            0,
            6,
            "ADD",
            2,
            2147483647,
            1,
            "add(1)",
            trace.result,
        )
    ]


@pytest.mark.skipif(
    not softcode_oracle_available(),
    reason="PennMUSH softcode trace oracle is not available",
)
def test_live_softcode_trace_reports_unknown_function_literal_fallback() -> None:
    trace = run_softcode_trace("qznotafunc(1,2)")
    unknown_events = _events_by_kind(trace, "unknown_function")

    assert trace.result == "qznotafunc(1,2)"
    assert [
        (
            event.depth,
            event.source_start,
            event.source_end,
            event.function_name,
            event.mandatory,
            event.raw,
            event.value,
        )
        for event in unknown_events
    ] == [
        (
            0,
            0,
            15,
            "QZNOTAFUNC",
            False,
            "qznotafunc(1,2)",
            "qznotafunc(1,2)",
        )
    ]


@pytest.mark.skipif(
    not softcode_oracle_available(),
    reason="PennMUSH softcode trace oracle is not available",
)
def test_live_softcode_trace_reports_mandatory_unknown_function_error() -> None:
    trace = run_softcode_trace("[qznotafunc(1,2)]")
    unknown_events = _events_by_kind(trace, "unknown_function")

    assert trace.result == "#-1 FUNCTION (QZNOTAFUNC) NOT FOUND"
    assert [
        (
            event.depth,
            event.source_start,
            event.source_end,
            event.function_name,
            event.mandatory,
            event.raw,
            event.value,
        )
        for event in unknown_events
    ] == [
        (
            1,
            1,
            16,
            "QZNOTAFUNC",
            True,
            "qznotafunc(1,2)",
            trace.result,
        )
    ]


@pytest.mark.skipif(
    not softcode_oracle_available(),
    reason="PennMUSH softcode trace oracle is not available",
)
def test_live_softcode_trace_reports_denied_disabled_function() -> None:
    trace = run_softcode_trace(
        "add(1,2)",
        restrict_lines=("restrict_function add nobody",),
    )
    denied_events = _events_by_kind(trace, "denied_function")

    assert trace.result == "#-1 FUNCTION DISABLED"
    assert [
        (
            event.source_start,
            event.source_end,
            event.function_name,
            event.min_args,
            event.max_args,
            event.actual_args,
            event.reason,
            event.raw,
            event.value,
        )
        for event in denied_events
    ] == [
        (
            0,
            8,
            "ADD",
            2,
            2147483647,
            2,
            "disabled",
            "add(1,2)",
            trace.result,
        )
    ]


@pytest.mark.skipif(
    not softcode_oracle_available(),
    reason="PennMUSH softcode trace oracle is not available",
)
def test_live_softcode_trace_reports_permission_denied_function() -> None:
    trace = run_softcode_trace("html(x)", executor="NOTHING")
    denied_events = _events_by_kind(trace, "denied_function")

    assert trace.result == "#-1 PERMISSION DENIED"
    assert [
        (
            event.source_start,
            event.source_end,
            event.function_name,
            event.min_args,
            event.max_args,
            event.actual_args,
            event.reason,
            event.raw,
            event.value,
        )
        for event in denied_events
    ] == [
        (
            0,
            7,
            "HTML",
            1,
            1,
            1,
            "permission",
            "html(x)",
            trace.result,
        )
    ]


@pytest.mark.skipif(
    not softcode_oracle_available(),
    reason="PennMUSH softcode trace oracle is not available",
)
def test_live_softcode_trace_reports_function_invocation_limit() -> None:
    trace = run_softcode_trace(
        "add(add(1,2),add(3,4))",
        config_lines=("function_invocation_limit 1",),
    )
    limit_events = _events_by_kind(trace, "function_limit")

    assert trace.result == "#-1 ARGUMENTS MUST BE NUMBERS"
    assert [
        (
            event.depth,
            event.source_start,
            event.source_end,
            event.function_name,
            event.min_args,
            event.max_args,
            event.reason,
            event.raw,
            event.value,
        )
        for event in limit_events
    ] == [
        (
            1,
            13,
            21,
            "ADD",
            2,
            2147483647,
            "invocation",
            "add(3,4)",
            "#-1 FUNCTION INVOCATION LIMIT EXCEEDED",
        )
    ]


@pytest.mark.skipif(
    not softcode_oracle_available(),
    reason="PennMUSH softcode trace oracle is not available",
)
def test_live_softcode_trace_reports_function_recursion_limit() -> None:
    trace = run_softcode_trace(
        "add(add(1,2),3)",
        config_lines=("function_recursion_limit 1",),
    )
    limit_events = _events_by_kind(trace, "function_limit")

    assert trace.result == "#-1 FUNCTION RECURSION LIMIT EXCEEDED"
    assert [
        (
            event.depth,
            event.source_start,
            event.source_end,
            event.function_name,
            event.min_args,
            event.max_args,
            event.reason,
            event.raw,
            event.value,
        )
        for event in limit_events
    ] == [
        (
            0,
            0,
            15,
            "ADD",
            2,
            2147483647,
            "recursion",
            "add(add(1,2),3)",
            trace.result,
        )
    ]


@pytest.mark.skipif(
    not softcode_oracle_available(),
    reason="PennMUSH softcode trace oracle is not available",
)
def test_live_softcode_trace_reports_literal_argument_without_inner_function() -> None:
    trace = run_softcode_trace("lit(add(1,2))")
    function_events = _function_events(trace)
    argument_events = _argument_events(trace)

    assert trace.result == "add(1,2)"
    assert [event.function_name for event in function_events] == ["LIT"]
    assert function_events[0].min_args == 1
    assert function_events[0].max_args == -1
    assert [
        (event.source_start, event.source_end, event.raw, event.value)
        for event in argument_events
    ] == [(4, 12, "add(1,2)", "add(1,2)")]


@pytest.mark.skipif(
    not softcode_oracle_available(),
    reason="PennMUSH softcode trace oracle is not available",
)
def test_live_softcode_trace_reports_noparse_argument_without_inner_function() -> None:
    trace = run_softcode_trace("@@(add(1,2))")
    function_events = _function_events(trace)
    argument_events = _argument_events(trace)

    assert trace.result == ""
    assert [event.function_name for event in function_events] == ["@@"]
    assert function_events[0].min_args == 1
    assert function_events[0].max_args == 2147483647
    assert [
        (event.source_start, event.source_end, event.raw, event.value)
        for event in argument_events
    ] == [(3, 11, "add(1,2)", "add(1,2)")]


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
    argument_raw_values = [
        event.raw for event in trace.events if event.kind == "argument"
    ]

    assert trace.result == str(left + right)
    assert len(function_events) == 1
    assert function_events[0].min_args == 2
    assert function_events[0].max_args == 2147483647
    assert argument_raw_values == [str(left), str(right)]
    assert argument_values == [str(left), str(right)]


def _function_events(
    trace: SoftcodeTrace,
    name: str | None = None,
) -> list[SoftcodeTraceEvent]:
    events = [event for event in trace.events if event.kind == "function"]
    if name is None:
        return events
    return [event for event in events if event.function_name == name]


def _argument_events(trace: SoftcodeTrace) -> list[SoftcodeTraceEvent]:
    return [event for event in trace.events if event.kind == "argument"]


def _events_by_kind(
    trace: SoftcodeTrace,
    kind: str,
) -> list[SoftcodeTraceEvent]:
    return [event for event in trace.events if event.kind == kind]


def _literal_events(trace: SoftcodeTrace) -> list[SoftcodeTraceEvent]:
    return [event for event in trace.events if event.kind == "literal"]


def _terminator_events(trace: SoftcodeTrace) -> list[SoftcodeTraceEvent]:
    return [event for event in trace.events if event.kind == "terminator"]
