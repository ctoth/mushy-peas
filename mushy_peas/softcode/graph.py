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
    PercentSub,
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
class AttributeReference:
    unit_id: str
    function_name: str
    span: Span
    attribute_span: Span
    object_span: Span | None = None
    object_ref: str | None = None
    attribute: str | None = None
    dynamic: bool = False
    reason: str | None = None


@dataclass(frozen=True)
class QRegisterReference:
    unit_id: str
    span: Span
    register: str | None
    operation: Literal["read", "write"]
    dynamic: bool = False
    reason: str | None = None


@dataclass(frozen=True)
class SemanticGraph:
    definitions: tuple[Definition, ...]
    references: tuple[Reference, ...]
    attribute_references: tuple[AttributeReference, ...]
    q_register_references: tuple[QRegisterReference, ...]


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
    attribute_references: list[AttributeReference] = []
    q_register_references: list[QRegisterReference] = []
    for unit in units:
        definition = _definition_for_unit(unit)
        if definition is not None:
            definitions.append(definition)
        if metadata is not None:
            document = parse_expression(unit.body, metadata=metadata)
            references.extend(_references_for_document(unit.id, unit.body, document))
            attribute_references.extend(
                _attribute_references_for_document(unit.id, unit.body, document)
            )
            q_register_references.extend(
                _q_register_references_for_document(unit.id, document)
            )
    return SemanticGraph(
        definitions=tuple(definitions),
        references=tuple(references),
        attribute_references=tuple(attribute_references),
        q_register_references=tuple(q_register_references),
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


def _attribute_references_for_document(
    unit_id: str,
    source: str,
    document: Document,
) -> tuple[AttributeReference, ...]:
    references: list[AttributeReference] = []
    for child in document.children:
        references.extend(_attribute_references_for_node(unit_id, source, child))
    return tuple(references)


def _q_register_references_for_document(
    unit_id: str,
    document: Document,
) -> tuple[QRegisterReference, ...]:
    references: list[QRegisterReference] = []
    for child in document.children:
        references.extend(_q_register_references_for_node(unit_id, child))
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


def _q_register_references_for_node(
    unit_id: str,
    node: Node,
) -> tuple[QRegisterReference, ...]:
    references: list[QRegisterReference] = []
    if isinstance(node, PercentSub):
        reference = _q_register_reference_for_percent_sub(unit_id, node)
        if reference is not None:
            references.append(reference)
    elif isinstance(node, FunctionCall):
        for argument in node.arguments:
            references.extend(_q_register_references_for_argument(unit_id, argument))
    elif isinstance(node, BraceGroup | EvalGroup):
        for child in node.children:
            references.extend(_q_register_references_for_node(unit_id, child))
    return tuple(references)


def _attribute_references_for_node(
    unit_id: str,
    source: str,
    node: Node,
) -> tuple[AttributeReference, ...]:
    references: list[AttributeReference] = []
    if isinstance(node, FunctionCall):
        if node.name == "GET":
            references.append(_attribute_reference_for_get(unit_id, source, node))
        elif node.name == "XGET":
            references.append(_attribute_reference_for_xget(unit_id, source, node))
        for argument in node.arguments:
            references.extend(
                _attribute_references_for_argument(unit_id, source, argument)
            )
    elif isinstance(node, BraceGroup | EvalGroup):
        for child in node.children:
            references.extend(_attribute_references_for_node(unit_id, source, child))
    return tuple(references)


def _q_register_references_for_argument(
    unit_id: str,
    argument: Argument,
) -> tuple[QRegisterReference, ...]:
    references: list[QRegisterReference] = []
    for child in argument.children:
        references.extend(_q_register_references_for_node(unit_id, child))
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


def _q_register_reference_for_percent_sub(
    unit_id: str,
    node: PercentSub,
) -> QRegisterReference | None:
    if len(node.raw) < 3 or node.raw[1] not in {"q", "Q"}:
        return None
    register = node.raw[2:]
    if register.startswith("<") and register.endswith(">"):
        register = register[1:-1]
    return QRegisterReference(
        unit_id=unit_id,
        span=node.span,
        register=register.casefold(),
        operation="read",
    )


def _attribute_references_for_argument(
    unit_id: str,
    source: str,
    argument: Argument,
) -> tuple[AttributeReference, ...]:
    references: list[AttributeReference] = []
    for child in argument.children:
        references.extend(_attribute_references_for_node(unit_id, source, child))
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


def _attribute_reference_for_get(
    unit_id: str,
    source: str,
    call: FunctionCall,
) -> AttributeReference:
    if not call.arguments:
        return AttributeReference(
            unit_id=unit_id,
            function_name=call.name,
            span=call.span,
            attribute_span=call.span,
            dynamic=True,
            reason="missing get() attribute",
        )
    attribute = _literal_argument(source, call.arguments[0])
    if attribute is None:
        return AttributeReference(
            unit_id=unit_id,
            function_name=call.name,
            span=call.span,
            attribute_span=call.arguments[0].span,
            dynamic=True,
            reason="dynamic get() attribute",
        )
    return AttributeReference(
        unit_id=unit_id,
        function_name=call.name,
        span=call.span,
        attribute_span=call.arguments[0].span,
        attribute=attribute,
    )


def _attribute_reference_for_xget(
    unit_id: str,
    source: str,
    call: FunctionCall,
) -> AttributeReference:
    if len(call.arguments) < 2:
        return AttributeReference(
            unit_id=unit_id,
            function_name=call.name,
            span=call.span,
            attribute_span=call.span,
            dynamic=True,
            reason="missing xget() object or attribute",
        )
    object_ref = _literal_argument(source, call.arguments[0])
    attribute = _literal_argument(source, call.arguments[1])
    if object_ref is None or attribute is None:
        return AttributeReference(
            unit_id=unit_id,
            function_name=call.name,
            span=call.span,
            object_span=call.arguments[0].span,
            attribute_span=call.arguments[1].span,
            dynamic=True,
            reason="dynamic xget() object or attribute",
        )
    return AttributeReference(
        unit_id=unit_id,
        function_name=call.name,
        span=call.span,
        object_span=call.arguments[0].span,
        attribute_span=call.arguments[1].span,
        object_ref=object_ref,
        attribute=attribute,
    )


def _literal_argument(source: str, argument: Argument) -> str | None:
    if len(argument.children) != 1 or not isinstance(argument.children[0], Text):
        return None
    return source[argument.span.start : argument.span.end].strip().casefold()


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
