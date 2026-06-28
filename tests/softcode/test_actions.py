from pathlib import Path

from mushy_peas.softcode import (
    Assignment,
    CommandName,
    CommandPattern,
    NestedActionBlock,
    RegexCommandPattern,
    parse_action_list,
    parse_command_attribute_body,
)
from mushy_peas.softcode.function_metadata import load_function_registry

FIXTURE = Path("tests/fixtures/softcode/pennmush-functions.json")


def test_action_list_splits_top_level_semicolons() -> None:
    source = "@emit one; @emit two"
    action_list = parse_action_list(source)

    assert [(stmt.span.start, stmt.span.end) for stmt in action_list.statements] == [
        (0, 9),
        (10, 20),
    ]
    assert [(span.start, span.end) for span in action_list.separators] == [(9, 10)]


def test_action_list_does_not_split_inside_braces_or_eval_groups() -> None:
    source = "@wait 1={@emit one;@emit two};@emit done [setq(0,a;b)]"
    action_list = parse_action_list(source)

    assert [(stmt.span.start, stmt.span.end) for stmt in action_list.statements] == [
        (0, 29),
        (30, len(source)),
    ]
    assert [(span.start, span.end) for span in action_list.separators] == [(29, 30)]


def test_action_list_does_not_split_inside_known_function_args() -> None:
    source = "@emit cat(add(1;2),3);@emit done"
    registry = load_function_registry(FIXTURE)
    action_list = parse_action_list(source, metadata=registry)

    assert [(stmt.span.start, stmt.span.end) for stmt in action_list.statements] == [
        (0, 21),
        (22, len(source)),
    ]
    assert [(span.start, span.end) for span in action_list.separators] == [(21, 22)]


def test_action_list_does_not_split_escaped_semicolon() -> None:
    source = r"@emit one\;still one;@emit two"
    action_list = parse_action_list(source)

    assert [(stmt.span.start, stmt.span.end) for stmt in action_list.statements] == [
        (0, 20),
        (21, len(source)),
    ]
    assert [(span.start, span.end) for span in action_list.separators] == [(20, 21)]


def test_action_list_classifies_command_name() -> None:
    source = "  think add(1,2)"
    action_list = parse_action_list(source)
    statement = action_list.statements[0]

    assert isinstance(statement.command_name, CommandName)
    assert statement.command_name.text == "think"
    assert statement.command_name.span.start == 2
    assert statement.command_name.span.end == 7
    assert statement.argument is not None
    assert statement.argument.span.start == 8
    assert statement.argument.span.end == len(source)


def test_action_list_classifies_simple_assignment() -> None:
    source = "@pemit %#=hello"
    action_list = parse_action_list(source)
    statement = action_list.statements[0]

    assert statement.command_name is not None
    assert statement.command_name.text == "@pemit"
    assert isinstance(statement.assignment, Assignment)
    assert statement.assignment.lhs.span.start == 7
    assert statement.assignment.lhs.span.end == 9
    assert statement.assignment.equals == 9
    assert statement.assignment.rhs.span.start == 10
    assert statement.assignment.rhs.span.end == len(source)


def test_command_attribute_body_classifies_pattern_and_actions() -> None:
    source = "$test *:@pemit %#=ok;@emit done"
    body = parse_command_attribute_body(source)

    assert body is not None
    assert isinstance(body.pattern, CommandPattern)
    assert body.pattern.text == "$test *"
    assert body.pattern.span.start == 0
    assert body.pattern.span.end == 7
    assert body.separator.start == 7
    assert body.separator.end == 8
    assert [(stmt.span.start, stmt.span.end) for stmt in body.actions.statements] == [
        (8, 20),
        (21, len(source)),
    ]


def test_command_attribute_body_classifies_regex_pattern() -> None:
    source = "$^look (.+)$:@pemit %#=%1"
    body = parse_command_attribute_body(source)

    assert body is not None
    assert isinstance(body.pattern, RegexCommandPattern)
    assert body.pattern.text == "$^look (.+)$"
    assert body.separator.start == 12
    assert body.actions.statements[0].span.start == 13


def test_assignment_classifies_nested_action_block() -> None:
    source = "@wait 1={@emit one;@emit two}"
    action_list = parse_action_list(source)
    assignment = action_list.statements[0].assignment

    assert assignment is not None
    assert isinstance(assignment.nested_action_block, NestedActionBlock)
    block = assignment.nested_action_block
    assert block.span.start == 8
    assert block.span.end == len(source)
    assert block.open_brace == 8
    assert block.close_brace == len(source) - 1
    assert [(stmt.span.start, stmt.span.end) for stmt in block.actions.statements] == [
        (9, 18),
        (19, 28),
    ]
    assert [(span.start, span.end) for span in block.actions.separators] == [(18, 19)]
