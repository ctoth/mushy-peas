"""Lossless action-list parsing for PennMUSH command bodies."""

from __future__ import annotations

from dataclasses import dataclass

from mushy_peas.softcode.function_metadata import FunctionRegistry
from mushy_peas.softcode.model import (
    BraceGroup,
    Document,
    Escape,
    EvalGroup,
    FunctionCall,
    Node,
    Span,
)
from mushy_peas.softcode.parser import parse_expression


@dataclass(frozen=True)
class CommandName:
    span: Span
    text: str


@dataclass(frozen=True)
class CommandPattern:
    span: Span
    text: str


@dataclass(frozen=True)
class RegexCommandPattern:
    span: Span
    text: str


@dataclass(frozen=True)
class CommandArg:
    span: Span


@dataclass(frozen=True)
class Assignment:
    span: Span
    lhs: CommandArg
    equals: int
    rhs: CommandArg
    nested_action_block: NestedActionBlock | None = None


@dataclass(frozen=True)
class TriggerCommand:
    span: Span
    command_name: CommandName
    target: CommandArg
    equals: int | None = None
    arguments: CommandArg | None = None


@dataclass(frozen=True)
class DolistCommand:
    span: Span
    command_name: CommandName
    list_expr: CommandArg
    equals: int
    body: CommandArg
    nested_action_block: NestedActionBlock | None = None


@dataclass(frozen=True)
class CommandStmt:
    span: Span
    command_name: CommandName | None = None
    argument: CommandArg | None = None
    assignment: Assignment | None = None
    dolist: DolistCommand | None = None
    trigger: TriggerCommand | None = None


@dataclass(frozen=True)
class ActionList:
    span: Span
    statements: tuple[CommandStmt, ...]
    separators: tuple[Span, ...]


@dataclass(frozen=True)
class NestedActionBlock:
    span: Span
    open_brace: int
    actions: ActionList
    close_brace: int


@dataclass(frozen=True)
class CommandAttributeBody:
    span: Span
    pattern: CommandPattern | RegexCommandPattern
    separator: Span
    actions: ActionList


def parse_action_list(
    source: str,
    *,
    metadata: FunctionRegistry | None = None,
    start: int = 0,
    end: int | None = None,
) -> ActionList:
    action_end = len(source) if end is None else end
    segment = source[start:action_end]
    document = parse_expression(segment, metadata=metadata)
    protected = _protected_offsets(document, len(segment))
    statements: list[CommandStmt] = []
    separators: list[Span] = []
    statement_start = start
    for local_index, char in enumerate(segment):
        index = start + local_index
        if char == ";" and not protected[local_index]:
            statements.append(_parse_statement(source, statement_start, index))
            separators.append(Span(index, index + 1))
            statement_start = index + 1
    statements.append(_parse_statement(source, statement_start, action_end))
    return ActionList(
        span=Span(start, action_end),
        statements=tuple(statements),
        separators=tuple(separators),
    )


def parse_command_attribute_body(
    source: str,
    *,
    metadata: FunctionRegistry | None = None,
) -> CommandAttributeBody | None:
    if not source.startswith("$"):
        return None
    separator = source.find(":")
    if separator == -1:
        return None
    pattern_text = source[:separator]
    pattern_span = Span(0, separator)
    if pattern_text.startswith("$^"):
        pattern: CommandPattern | RegexCommandPattern = RegexCommandPattern(
            span=pattern_span,
            text=pattern_text,
        )
    else:
        pattern = CommandPattern(span=pattern_span, text=pattern_text)
    return CommandAttributeBody(
        span=Span(0, len(source)),
        pattern=pattern,
        separator=Span(separator, separator + 1),
        actions=parse_action_list(source, metadata=metadata, start=separator + 1),
    )


def _parse_statement(source: str, start: int, end: int) -> CommandStmt:
    span = Span(start, end)
    command_start = _skip_spaces(source, start, end)
    if command_start >= end:
        return CommandStmt(span=span)
    command_end = command_start
    while command_end < end and not source[command_end].isspace():
        command_end += 1
    command_name = CommandName(
        span=Span(command_start, command_end),
        text=source[command_start:command_end],
    )
    argument_start = _skip_spaces(source, command_end, end)
    if argument_start >= end:
        return CommandStmt(span=span, command_name=command_name)
    argument = CommandArg(span=Span(argument_start, end))
    equals = source.find("=", argument_start, end)
    if equals == -1:
        return CommandStmt(
            span=span,
            command_name=command_name,
            argument=argument,
            trigger=_parse_trigger_command(
                span,
                command_name,
                target=argument,
                assignment=None,
            ),
        )
    assignment = Assignment(
        span=Span(argument_start, end),
        lhs=CommandArg(span=Span(argument_start, equals)),
        equals=equals,
        rhs=CommandArg(span=Span(equals + 1, end)),
        nested_action_block=_parse_nested_action_block(source, equals + 1, end),
    )
    return CommandStmt(
        span=span,
        command_name=command_name,
        argument=argument,
        assignment=assignment,
        dolist=_parse_dolist_command(span, command_name, assignment),
        trigger=_parse_trigger_command(
            span,
            command_name,
            target=assignment.lhs,
            assignment=assignment,
        ),
    )


def _skip_spaces(source: str, start: int, end: int) -> int:
    index = start
    while index < end and source[index].isspace():
        index += 1
    return index


def _parse_trigger_command(
    span: Span,
    command_name: CommandName,
    *,
    target: CommandArg,
    assignment: Assignment | None,
) -> TriggerCommand | None:
    if command_name.text.casefold() not in {"@trigger", "@tr"}:
        return None
    if assignment is None:
        return TriggerCommand(
            span=span,
            command_name=command_name,
            target=target,
        )
    return TriggerCommand(
        span=span,
        command_name=command_name,
        target=target,
        equals=assignment.equals,
        arguments=assignment.rhs,
    )


def _parse_dolist_command(
    span: Span,
    command_name: CommandName,
    assignment: Assignment,
) -> DolistCommand | None:
    if command_name.text.casefold() not in {"@dolist", "@dol"}:
        return None
    return DolistCommand(
        span=span,
        command_name=command_name,
        list_expr=assignment.lhs,
        equals=assignment.equals,
        body=assignment.rhs,
        nested_action_block=assignment.nested_action_block,
    )


def _parse_nested_action_block(
    source: str,
    start: int,
    end: int,
) -> NestedActionBlock | None:
    rhs_start = _skip_spaces(source, start, end)
    rhs_end = end
    while rhs_end > rhs_start and source[rhs_end - 1].isspace():
        rhs_end -= 1
    if rhs_end - rhs_start < 2:
        return None
    if source[rhs_start] != "{" or source[rhs_end - 1] != "}":
        return None
    return NestedActionBlock(
        span=Span(rhs_start, rhs_end),
        open_brace=rhs_start,
        actions=parse_action_list(source, start=rhs_start + 1, end=rhs_end - 1),
        close_brace=rhs_end - 1,
    )


def _protected_offsets(document: Document, length: int) -> list[bool]:
    protected = [False] * length
    for child in document.children:
        _mark_protected(child, protected)
    return protected


def _mark_protected(node: Node, protected: list[bool]) -> None:
    if isinstance(node, BraceGroup | EvalGroup | FunctionCall | Escape):
        for index in range(node.span.start, node.span.end):
            protected[index] = True
        return
    children = getattr(node, "children", ())
    for child in children:
        _mark_protected(child, protected)
