"""Structural AST projections from the lossless softcode CST."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

from mushy_peas.softcode.model import (
    Argument,
    BraceGroup,
    Document,
    DollarSub,
    EvalGroup,
    FunctionCall,
    Node,
    PercentSub,
    Span,
    Unknown,
)


@dataclass(frozen=True)
class AstDocument:
    span: Span
    cst: Document
    expressions: tuple[Expr, ...]


@dataclass(frozen=True)
class FunctionExpr:
    span: Span
    cst: FunctionCall
    name: str
    arguments: tuple[tuple[Expr, ...], ...]


@dataclass(frozen=True)
class SubstitutionExpr:
    span: Span
    cst: PercentSub | DollarSub
    substitution_kind: Literal["percent", "dollar"]
    raw: str


@dataclass(frozen=True)
class BraceExpr:
    span: Span
    cst: BraceGroup
    expressions: tuple[Expr, ...]


@dataclass(frozen=True)
class EvalExpr:
    span: Span
    cst: EvalGroup
    expressions: tuple[Expr, ...]


@dataclass(frozen=True)
class UnknownExpr:
    span: Span
    cst: Node
    reason: str


Expr: TypeAlias = FunctionExpr | SubstitutionExpr | BraceExpr | EvalExpr | UnknownExpr


def build_ast_view(document: Document) -> AstDocument:
    return AstDocument(
        span=document.span,
        cst=document,
        expressions=tuple(_project_node(child) for child in document.children),
    )


def _project_node(node: Node) -> Expr:
    if isinstance(node, FunctionCall):
        return FunctionExpr(
            span=node.span,
            cst=node,
            name=node.name,
            arguments=tuple(_project_argument(argument) for argument in node.arguments),
        )
    if isinstance(node, PercentSub):
        return SubstitutionExpr(
            span=node.span,
            cst=node,
            substitution_kind="percent",
            raw=node.raw,
        )
    if isinstance(node, DollarSub):
        return SubstitutionExpr(
            span=node.span,
            cst=node,
            substitution_kind="dollar",
            raw=node.raw,
        )
    if isinstance(node, BraceGroup):
        return BraceExpr(
            span=node.span,
            cst=node,
            expressions=tuple(_project_node(child) for child in node.children),
        )
    if isinstance(node, EvalGroup):
        return EvalExpr(
            span=node.span,
            cst=node,
            expressions=tuple(_project_node(child) for child in node.children),
        )
    if isinstance(node, Unknown):
        return UnknownExpr(span=node.span, cst=node, reason=node.reason)
    return UnknownExpr(
        span=node.span,
        cst=node,
        reason=f"unsupported CST node: {node.kind}",
    )


def _project_argument(argument: Argument) -> tuple[Expr, ...]:
    return tuple(_project_node(child) for child in argument.children)
