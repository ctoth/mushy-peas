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


def parse_action_list(
    source: str,
    *,
    metadata: FunctionRegistry | None = None,
) -> ActionList:
    document = parse_expression(source, metadata=metadata)
    protected = _protected_offsets(document, len(source))
    statements: list[CommandStmt] = []
    separators: list[Span] = []
    start = 0
    for index, char in enumerate(source):
        if char == ";" and not protected[index]:
            statements.append(_parse_statement(source, start, index))
            separators.append(Span(index, index + 1))
            start = index + 1
    statements.append(_parse_statement(source, start, len(source)))
    return ActionList(
        span=Span(0, len(source)),
        statements=tuple(statements),
        separators=tuple(separators),
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
