from pathlib import Path

from mushy_peas.softcode import Assignment, CommandName, parse_action_list
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
