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


@dataclass(frozen=True)
class CommandStmt:
    span: Span
    command_name: CommandName | None = None
    argument: CommandArg | None = None
    assignment: Assignment | None = None


@dataclass(frozen=True)
class ActionList:
    span: Span
    statements: tuple[CommandStmt, ...]
    separators: tuple[Span, ...]


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
        )
    assignment = Assignment(
        span=Span(argument_start, end),
        lhs=CommandArg(span=Span(argument_start, equals)),
        equals=equals,
        rhs=CommandArg(span=Span(equals + 1, end)),
    )
    return CommandStmt(
        span=span,
        command_name=command_name,
        argument=argument,
        assignment=assignment,
    )


def _skip_spaces(source: str, start: int, end: int) -> int:
    index = start
    while index < end and source[index].isspace():
        index += 1
    return index


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
