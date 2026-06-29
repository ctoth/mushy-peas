from pathlib import Path

from mushy_peas.softcode import (
    Assignment,
    CommandName,
    CommandPattern,
    DolistCommand,
    NestedActionBlock,
    RegexCommandPattern,
    SwitchCase,
    SwitchCommand,
    TriggerCommand,
    WaitCommand,
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


def test_action_list_classifies_trigger_command() -> None:
    source = "@trigger #10/ATTR=one,two"
    action_list = parse_action_list(source)
    statement = action_list.statements[0]

    assert isinstance(statement.trigger, TriggerCommand)
    trigger = statement.trigger
    assert trigger.span.start == 0
    assert trigger.span.end == len(source)
    assert trigger.command_name.text == "@trigger"
    assert trigger.target.span.start == 9
    assert trigger.target.span.end == 17
    assert trigger.equals == 17
    assert trigger.arguments is not None
    assert trigger.arguments.span.start == 18
    assert trigger.arguments.span.end == len(source)


def test_action_list_classifies_trigger_without_arguments() -> None:
    source = "@tr #10/ATTR"
    action_list = parse_action_list(source)
    trigger = action_list.statements[0].trigger

    assert isinstance(trigger, TriggerCommand)
    assert trigger.command_name.text == "@tr"
    assert trigger.target.span.start == 4
    assert trigger.target.span.end == len(source)
    assert trigger.equals is None
    assert trigger.arguments is None


def test_action_list_classifies_dolist_command() -> None:
    source = "@dolist one two three=@emit ##"
    action_list = parse_action_list(source)
    statement = action_list.statements[0]

    assert isinstance(statement.dolist, DolistCommand)
    dolist = statement.dolist
    assert dolist.span.start == 0
    assert dolist.span.end == len(source)
    assert dolist.command_name.text == "@dolist"
    assert dolist.list_expr.span.start == 8
    assert dolist.list_expr.span.end == 21
    assert dolist.equals == 21
    assert dolist.body.span.start == 22
    assert dolist.body.span.end == len(source)
    assert dolist.nested_action_block is None


def test_action_list_classifies_dolist_nested_action_body() -> None:
    source = "@dol one two={@emit ##;@emit done}"
    action_list = parse_action_list(source)
    dolist = action_list.statements[0].dolist

    assert isinstance(dolist, DolistCommand)
    assert isinstance(dolist.nested_action_block, NestedActionBlock)
    block = dolist.nested_action_block
    assert block.span.start == 13
    assert block.span.end == len(source)
    assert [(stmt.span.start, stmt.span.end) for stmt in block.actions.statements] == [
        (14, 22),
        (23, 33),
    ]


def test_action_list_classifies_wait_command() -> None:
    source = "@wait 5=@emit done"
    action_list = parse_action_list(source)
    statement = action_list.statements[0]

    assert isinstance(statement.wait, WaitCommand)
    wait = statement.wait
    assert wait.span.start == 0
    assert wait.span.end == len(source)
    assert wait.command_name.text == "@wait"
    assert wait.delay.span.start == 6
    assert wait.delay.span.end == 7
    assert wait.equals == 7
    assert wait.body.span.start == 8
    assert wait.body.span.end == len(source)
    assert wait.nested_action_block is None


def test_action_list_classifies_wait_nested_action_body() -> None:
    source = "@wa 1={@emit one;@emit two}"
    action_list = parse_action_list(source)
    wait = action_list.statements[0].wait

    assert isinstance(wait, WaitCommand)
    assert isinstance(wait.nested_action_block, NestedActionBlock)
    block = wait.nested_action_block
    assert block.span.start == 6
    assert block.span.end == len(source)
    assert [(stmt.span.start, stmt.span.end) for stmt in block.actions.statements] == [
        (7, 16),
        (17, 26),
    ]


def test_action_list_classifies_switch_command_cases() -> None:
    source = "@switch foo=bar,@emit yes,baz,@emit no"
    action_list = parse_action_list(source)
    statement = action_list.statements[0]

    assert isinstance(statement.switch, SwitchCommand)
    switch = statement.switch
    assert switch.command_name.text == "@switch"
    assert switch.subject.span.start == 8
    assert switch.subject.span.end == 11
    assert switch.equals == 11
    assert len(switch.cases) == 2
    first = switch.cases[0]
    assert isinstance(first, SwitchCase)
    assert first.pattern.span.start == 12
    assert first.pattern.span.end == 15
    assert first.separator is not None
    assert first.separator.start == 15
    assert first.action is not None
    assert first.action.span.start == 16
    assert first.action.span.end == 25
    second = switch.cases[1]
    assert second.pattern.span.start == 26
    assert second.pattern.span.end == 29
    assert second.action is not None
    assert second.action.span.start == 30
    assert second.action.span.end == len(source)


def test_switch_cases_do_not_split_commas_inside_braced_actions() -> None:
    source = "@sw foo=bar,{@emit one,two;@emit done},baz,@emit no"
    action_list = parse_action_list(source)
    switch = action_list.statements[0].switch

    assert isinstance(switch, SwitchCommand)
    assert len(switch.cases) == 2
    first = switch.cases[0]
    assert first.action is not None
    assert first.action.span.start == 12
    assert first.action.span.end == 38
    assert isinstance(first.nested_action_block, NestedActionBlock)
    block = first.nested_action_block
    assert [(stmt.span.start, stmt.span.end) for stmt in block.actions.statements] == [
        (13, 26),
        (27, 37),
    ]


def test_switch_cases_preserve_odd_trailing_pattern() -> None:
    source = "@switch foo=bar,@emit yes,default"
    action_list = parse_action_list(source)
    switch = action_list.statements[0].switch

    assert isinstance(switch, SwitchCommand)
    assert len(switch.cases) == 2
    trailing = switch.cases[1]
    assert trailing.pattern.span.start == 26
    assert trailing.pattern.span.end == len(source)
    assert trailing.separator is None
    assert trailing.action is None
