"""Semantic graph extraction for softcode units."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from mushy_peas.softcode.function_metadata import FunctionRegistry
from mushy_peas.softcode.model import (
    Argument,
    BraceGroup,
    Document,
    EvalGroup,
    FunctionCall,
    Node,
    Span,
    Text,
)
from mushy_peas.softcode.parser import parse_expression
from mushy_peas.softcode.profiles import classify_profile
from mushy_peas.softcode.units import SoftcodeUnit

DefinitionFamily = Literal["command", "function"]


@dataclass(frozen=True)
class Definition:
    unit_id: str
    name: str
    family: DefinitionFamily
    span: Span


@dataclass(frozen=True)
class Reference:
    unit_id: str
    function_name: str
    span: Span
    target_span: Span
    target: str | None = None
    dynamic: bool = False
    reason: str | None = None


@dataclass(frozen=True)
class SemanticGraph:
    definitions: tuple[Definition, ...]
    references: tuple[Reference, ...]


@dataclass(frozen=True)
class Diagnostic:
    unit_id: str
    span: Span
    code: str
    message: str
    evidence: str


def build_semantic_graph(
    units: tuple[SoftcodeUnit, ...],
    *,
    metadata: FunctionRegistry | None = None,
) -> SemanticGraph:
    definitions: list[Definition] = []
    references: list[Reference] = []
    for unit in units:
        definition = _definition_for_unit(unit)
        if definition is not None:
            definitions.append(definition)
        if metadata is not None:
            document = parse_expression(unit.body, metadata=metadata)
            references.extend(_references_for_document(unit.id, unit.body, document))
    return SemanticGraph(
        definitions=tuple(definitions),
        references=tuple(references),
    )


def collect_semantic_diagnostics(
    units: tuple[SoftcodeUnit, ...],
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    for unit in units:
        classification = classify_profile(unit)
        for warning in classification.warnings:
            diagnostics.append(
                Diagnostic(
                    unit_id=unit.id,
                    span=unit.source_span,
                    code="profile.warning",
                    message=warning,
                    evidence=f"profile={classification.profile}",
                )
            )
    return tuple(diagnostics)


def _definition_for_unit(unit: SoftcodeUnit) -> Definition | None:
    classification = classify_profile(unit)
    if classification.profile != "wcnh":
        return None
    if classification.family not in {"command", "function"}:
        return None
    if unit.attribute_name is None:
        return None
    family: DefinitionFamily = (
        "command" if classification.family == "command" else "function"
    )
    return Definition(
        unit_id=unit.id,
        name=unit.attribute_name.casefold(),
        family=family,
        span=unit.source_span,
    )


def _references_for_document(
    unit_id: str,
    source: str,
    document: Document,
) -> tuple[Reference, ...]:
    references: list[Reference] = []
    for child in document.children:
        references.extend(_references_for_node(unit_id, source, child))
    return tuple(references)


def _references_for_node(
    unit_id: str,
    source: str,
    node: Node,
) -> tuple[Reference, ...]:
    references: list[Reference] = []
    if isinstance(node, FunctionCall):
        if node.name in {"U", "UFUN", "ULOCAL"}:
            references.append(_reference_for_user_function_call(unit_id, source, node))
        elif node.name == "TRIGGER":
            references.append(_reference_for_trigger_call(unit_id, source, node))
        for argument in node.arguments:
            references.extend(_references_for_argument(unit_id, source, argument))
    elif isinstance(node, BraceGroup | EvalGroup):
        for child in node.children:
            references.extend(_references_for_node(unit_id, source, child))
    return tuple(references)


def _references_for_argument(
    unit_id: str,
    source: str,
    argument: Argument,
) -> tuple[Reference, ...]:
    references: list[Reference] = []
    for child in argument.children:
        references.extend(_references_for_node(unit_id, source, child))
    return tuple(references)


def _reference_for_user_function_call(
    unit_id: str,
    source: str,
    call: FunctionCall,
) -> Reference:
    if not call.arguments:
        return Reference(
            unit_id=unit_id,
            function_name=call.name,
            span=call.span,
            target_span=call.span,
            dynamic=True,
            reason=f"missing {call.name.casefold()}() target",
        )
    target_arg = call.arguments[0]
    if len(target_arg.children) == 1 and isinstance(target_arg.children[0], Text):
        target = source[target_arg.span.start : target_arg.span.end].strip().casefold()
        return Reference(
            unit_id=unit_id,
            function_name=call.name,
            span=call.span,
            target_span=target_arg.span,
            target=target,
        )
    return Reference(
        unit_id=unit_id,
        function_name=call.name,
        span=call.span,
        target_span=target_arg.span,
        dynamic=True,
        reason=f"dynamic {call.name.casefold()}() target",
    )


def _reference_for_trigger_call(
    unit_id: str,
    source: str,
    call: FunctionCall,
) -> Reference:
    if not call.arguments:
        return Reference(
            unit_id=unit_id,
            function_name=call.name,
            span=call.span,
            target_span=call.span,
            dynamic=True,
            reason="missing trigger() target",
        )
    target_arg = call.arguments[0]
    if len(target_arg.children) == 1 and isinstance(target_arg.children[0], Text):
        target = source[target_arg.span.start : target_arg.span.end].strip().casefold()
        return Reference(
            unit_id=unit_id,
            function_name=call.name,
            span=call.span,
            target_span=target_arg.span,
            target=target,
        )
    return Reference(
        unit_id=unit_id,
        function_name=call.name,
        span=call.span,
        target_span=target_arg.span,
        dynamic=True,
        reason="dynamic trigger() target",
    )
