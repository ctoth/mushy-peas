from pathlib import Path

from mushy_peas.softcode import (
    BraceGroup,
    DollarSub,
    Escape,
    EvalGroup,
    FunctionCall,
    ParseMode,
    PercentSub,
    parse_expression,
    render,
)
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


def test_brace_group_parses_recursive_children() -> None:
    source = "{add(1,2)}"
    registry = load_function_registry(FIXTURE)
    document = parse_expression(source, metadata=registry)
    group = document.children[0]

    assert isinstance(group, BraceGroup)
    assert group.span.start == 0
    assert group.span.end == 10
    assert group.open_brace == 0
    assert group.close_brace == 9
    call = group.children[0]
    assert isinstance(call, FunctionCall)
    assert call.name == "ADD"
    assert render(document, source) == source


def test_eval_group_parses_recursive_children() -> None:
    source = "[add(1,2)]"
    registry = load_function_registry(FIXTURE)
    document = parse_expression(source, metadata=registry)
    group = document.children[0]

    assert isinstance(group, EvalGroup)
    assert group.span.start == 0
    assert group.span.end == 10
    assert group.open_bracket == 0
    assert group.close_bracket == 9
    call = group.children[0]
    assert isinstance(call, FunctionCall)
    assert call.name == "ADD"
    assert render(document, source) == source


def test_percent_substitution_parses_as_cst_node() -> None:
    source = "say %n"
    document = parse_expression(source)
    percent = document.children[1]

    assert isinstance(percent, PercentSub)
    assert percent.span.start == 4
    assert percent.span.end == 6
    assert percent.raw == "%n"
    assert render(document, source) == source


def test_percent_substitution_parses_three_character_family() -> None:
    source = "%vx"
    document = parse_expression(source)
    percent = document.children[0]

    assert isinstance(percent, PercentSub)
    assert percent.span.start == 0
    assert percent.span.end == 3
    assert percent.raw == "%vx"
    assert render(document, source) == source


def test_percent_substitution_parses_named_q_register() -> None:
    source = "%q<name>"
    document = parse_expression(source)
    percent = document.children[0]

    assert isinstance(percent, PercentSub)
    assert percent.span.start == 0
    assert percent.span.end == 8
    assert percent.raw == "%q<name>"
    assert render(document, source) == source


def test_escape_parses_as_cst_node() -> None:
    source = r"\%"
    document = parse_expression(source)
    escape = document.children[0]

    assert isinstance(escape, Escape)
    assert escape.span.start == 0
    assert escape.span.end == 2
    assert escape.raw == r"\%"
    assert render(document, source) == source


def test_trailing_escape_parses_as_cst_node() -> None:
    source = "abc\\"
    document = parse_expression(source)
    escape = document.children[1]

    assert isinstance(escape, Escape)
    assert escape.span.start == 3
    assert escape.span.end == 4
    assert escape.raw == "\\"
    assert render(document, source) == source


def test_dollar_substitution_is_text_by_default() -> None:
    source = "$look:@emit hi"
    document = parse_expression(source)

    assert render(document, source) == source
    assert len(document.children) == 1


def test_dollar_substitution_parses_when_enabled() -> None:
    source = "<$1> <$<name>>"
    document = parse_expression(source, mode=ParseMode(dollar_substitutions=True))

    assert isinstance(document.children[1], DollarSub)
    assert document.children[1].span.start == 1
    assert document.children[1].span.end == 3
    assert document.children[1].raw == "$1"
    assert isinstance(document.children[3], DollarSub)
    assert document.children[3].span.start == 6
    assert document.children[3].span.end == 13
    assert document.children[3].raw == "$<name>"
    assert render(document, source) == source
