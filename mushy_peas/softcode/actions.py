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
class CommandStmt:
    span: Span


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
            statements.append(CommandStmt(span=Span(start, index)))
            separators.append(Span(index, index + 1))
            start = index + 1
    statements.append(CommandStmt(span=Span(start, len(source))))
    return ActionList(
        span=Span(0, len(source)),
        statements=tuple(statements),
        separators=tuple(separators),
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
