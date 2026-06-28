from pathlib import Path

from mushy_peas.softcode import FunctionCall, parse_expression, render
from mushy_peas.softcode.function_metadata import load_function_registry

FIXTURE = Path("tests/fixtures/softcode/pennmush-functions.json")


def test_without_metadata_expression_is_plain_text() -> None:
    document = parse_expression("add(1,2)")

    assert len(document.children) == 1
    assert render(document, "add(1,2)") == "add(1,2)"


def test_known_function_call_parses_arguments() -> None:
    source = "add(1,2)"
    registry = load_function_registry(FIXTURE)
    document = parse_expression(source, metadata=registry)
    call = document.children[0]

    assert isinstance(call, FunctionCall)
    assert call.name == "ADD"
    assert call.name_span.start == 0
    assert call.name_span.end == 3
    assert call.open_paren == 3
    assert call.close_paren == 7
    assert [(arg.span.start, arg.span.end) for arg in call.arguments] == [
        (4, 5),
        (6, 7),
    ]
    assert render(document, source) == source


def test_nested_known_function_call_parses_recursively() -> None:
    source = "add(add(1,2),3)"
    registry = load_function_registry(FIXTURE)
    document = parse_expression(source, metadata=registry)
    outer = document.children[0]

    assert isinstance(outer, FunctionCall)
    inner = outer.arguments[0].children[0]
    assert isinstance(inner, FunctionCall)
    assert inner.name == "ADD"
    assert [(arg.span.start, arg.span.end) for arg in inner.arguments] == [
        (8, 9),
        (10, 11),
    ]
    assert render(document, source) == source
