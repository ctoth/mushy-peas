"""Structural AST projections from the lossless softcode CST."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

from mushy_peas.softcode.actions import (
    ActionList,
    Assignment,
    DolistCommand,
    SwitchCase,
    SwitchCommand,
    TriggerCommand,
    WaitCommand,
)
from mushy_peas.softcode.actions import (
    CommandStmt as CstCommandStmt,
)
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


@dataclass(frozen=True)
class AstActionList:
    span: Span
    cst: ActionList
    statements: tuple[ActionStmt, ...]


@dataclass(frozen=True)
class CommandStmt:
    span: Span
    cst: CstCommandStmt
    command_name: str | None


@dataclass(frozen=True)
class AssignmentStmt:
    span: Span
    cst: Assignment
    lhs: Span
    rhs: Span


@dataclass(frozen=True)
class TriggerStmt:
    span: Span
    cst: TriggerCommand
    target: Span
    arguments: Span | None


@dataclass(frozen=True)
class DolistStmt:
    span: Span
    cst: DolistCommand
    list_expr: Span
    body: Span


@dataclass(frozen=True)
class WaitStmt:
    span: Span
    cst: WaitCommand
    delay: Span
    body: Span


@dataclass(frozen=True)
class EmitStmt:
    span: Span
    cst: CstCommandStmt
    command_name: str
    target: Span | None = None
    message: Span | None = None


@dataclass(frozen=True)
class SwitchCaseView:
    span: Span
    cst: SwitchCase
    pattern: Span
    action: Span | None


@dataclass(frozen=True)
class SwitchStmt:
    span: Span
    cst: SwitchCommand
    subject: Span
    cases: tuple[SwitchCaseView, ...]


@dataclass(frozen=True)
class DynamicExpr:
    span: Span
    cst: CstCommandStmt
    reason: str


ActionStmt: TypeAlias = (
    CommandStmt
    | AssignmentStmt
    | TriggerStmt
    | DolistStmt
    | WaitStmt
    | EmitStmt
    | SwitchStmt
    | DynamicExpr
)


def build_ast_view(document: Document) -> AstDocument:
    return AstDocument(
        span=document.span,
        cst=document,
        expressions=tuple(_project_node(child) for child in document.children),
    )


def build_action_ast_view(action_list: ActionList) -> AstActionList:
    return AstActionList(
        span=action_list.span,
        cst=action_list,
        statements=tuple(
            _project_action_statement(stmt) for stmt in action_list.statements
        ),
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


def _project_action_statement(statement: CstCommandStmt) -> ActionStmt:
    if statement.switch is not None:
        return SwitchStmt(
            span=statement.switch.span,
            cst=statement.switch,
            subject=statement.switch.subject.span,
            cases=tuple(_project_switch_case(case) for case in statement.switch.cases),
        )
    if statement.dolist is not None:
        return DolistStmt(
            span=statement.dolist.span,
            cst=statement.dolist,
            list_expr=statement.dolist.list_expr.span,
            body=statement.dolist.body.span,
        )
    if statement.wait is not None:
        return WaitStmt(
            span=statement.wait.span,
            cst=statement.wait,
            delay=statement.wait.delay.span,
            body=statement.wait.body.span,
        )
    if statement.trigger is not None:
        arguments = (
            None
            if statement.trigger.arguments is None
            else statement.trigger.arguments.span
        )
        return TriggerStmt(
            span=statement.trigger.span,
            cst=statement.trigger,
            target=statement.trigger.target.span,
            arguments=arguments,
        )
    emit = _project_emit_statement(statement)
    if emit is not None:
        return emit
    if statement.assignment is not None:
        return AssignmentStmt(
            span=statement.assignment.span,
            cst=statement.assignment,
            lhs=statement.assignment.lhs.span,
            rhs=statement.assignment.rhs.span,
        )
    if statement.command_name is not None:
        return CommandStmt(
            span=statement.span,
            cst=statement,
            command_name=statement.command_name.text,
        )
    return DynamicExpr(
        span=statement.span,
        cst=statement,
        reason="empty command statement",
    )


def _project_emit_statement(statement: CstCommandStmt) -> EmitStmt | None:
    if statement.command_name is None:
        return None
    command_name = statement.command_name.text.casefold()
    if command_name in {"@emit", "think"}:
        return EmitStmt(
            span=statement.span,
            cst=statement,
            command_name=statement.command_name.text,
            message=None if statement.argument is None else statement.argument.span,
        )
    if command_name != "@pemit":
        return None
    return EmitStmt(
        span=statement.span,
        cst=statement,
        command_name=statement.command_name.text,
        target=None if statement.assignment is None else statement.assignment.lhs.span,
        message=None if statement.assignment is None else statement.assignment.rhs.span,
    )


def _project_switch_case(case: SwitchCase) -> SwitchCaseView:
    return SwitchCaseView(
        span=case.span,
        cst=case,
        pattern=case.pattern.span,
        action=None if case.action is None else case.action.span,
    )
