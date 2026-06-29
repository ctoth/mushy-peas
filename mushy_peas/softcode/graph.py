"""Semantic graph extraction for softcode units."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from mushy_peas.softcode.actions import (
    ActionList,
    CommandArg,
    CommandStmt,
    parse_action_list,
    parse_command_attribute_body,
)
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
EffectKind = Literal["emit", "trigger", "wait"]


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
class AttributeWrite:
    unit_id: str
    span: Span
    target_span: Span
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
class RpcReference:
    unit_id: str
    span: Span
    endpoint_span: Span
    endpoint: str | None = None
    dynamic: bool = False
    reason: str | None = None


@dataclass(frozen=True)
class Effect:
    unit_id: str
    kind: EffectKind
    span: Span
    command_name: str
    target_span: Span | None = None


@dataclass(frozen=True)
class SemanticGraph:
    definitions: tuple[Definition, ...]
    references: tuple[Reference, ...]
    attribute_references: tuple[AttributeReference, ...]
    attribute_writes: tuple[AttributeWrite, ...]
    q_register_references: tuple[QRegisterReference, ...]
    rpc_references: tuple[RpcReference, ...]
    effects: tuple[Effect, ...]


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
    attribute_writes: list[AttributeWrite] = []
    q_register_references: list[QRegisterReference] = []
    rpc_references: list[RpcReference] = []
    effects: list[Effect] = []
    for unit in units:
        definition = _definition_for_unit(unit)
        if definition is not None:
            definitions.append(definition)
        effects.extend(_effects_for_unit(unit))
        attribute_writes.extend(_attribute_writes_for_unit(unit))
        references.extend(_action_references_for_unit(unit))
        if metadata is not None:
            document = parse_expression(unit.body, metadata=metadata)
            references.extend(_references_for_document(unit.id, unit.body, document))
            attribute_references.extend(
                _attribute_references_for_document(unit.id, unit.body, document)
            )
            q_register_references.extend(
                _q_register_references_for_document(unit.id, unit.body, document)
            )
            rpc_references.extend(
                _rpc_references_for_document(unit.id, unit.body, document)
            )
    return SemanticGraph(
        definitions=tuple(definitions),
        references=tuple(references),
        attribute_references=tuple(attribute_references),
        attribute_writes=tuple(attribute_writes),
        q_register_references=tuple(q_register_references),
        rpc_references=tuple(rpc_references),
        effects=tuple(effects),
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


def _effects_for_unit(unit: SoftcodeUnit) -> tuple[Effect, ...]:
    classification = classify_profile(unit)
    if classification.profile != "wcnh" or classification.family != "command":
        return ()
    command_body = parse_command_attribute_body(unit.body)
    action_list = (
        command_body.actions
        if command_body is not None
        else parse_action_list(unit.body)
    )
    return _effects_for_action_list(unit.id, action_list)


def _attribute_writes_for_unit(unit: SoftcodeUnit) -> tuple[AttributeWrite, ...]:
    classification = classify_profile(unit)
    if classification.profile != "wcnh" or classification.family != "command":
        return ()
    command_body = parse_command_attribute_body(unit.body)
    action_list = (
        command_body.actions
        if command_body is not None
        else parse_action_list(unit.body)
    )
    return _attribute_writes_for_action_list(unit.id, unit.body, action_list)


def _action_references_for_unit(unit: SoftcodeUnit) -> tuple[Reference, ...]:
    classification = classify_profile(unit)
    if classification.profile != "wcnh" or classification.family != "command":
        return ()
    command_body = parse_command_attribute_body(unit.body)
    action_list = (
        command_body.actions
        if command_body is not None
        else parse_action_list(unit.body)
    )
    return _action_references_for_action_list(unit.id, unit.body, action_list)


def _effects_for_action_list(
    unit_id: str,
    action_list: ActionList,
) -> tuple[Effect, ...]:
    effects: list[Effect] = []
    for statement in action_list.statements:
        effects.extend(_effects_for_statement(unit_id, statement))
    return tuple(effects)


def _attribute_writes_for_action_list(
    unit_id: str,
    source: str,
    action_list: ActionList,
) -> tuple[AttributeWrite, ...]:
    writes: list[AttributeWrite] = []
    for statement in action_list.statements:
        writes.extend(_attribute_writes_for_statement(unit_id, source, statement))
    return tuple(writes)


def _action_references_for_action_list(
    unit_id: str,
    source: str,
    action_list: ActionList,
) -> tuple[Reference, ...]:
    references: list[Reference] = []
    for statement in action_list.statements:
        references.extend(_action_references_for_statement(unit_id, source, statement))
    return tuple(references)


def _effects_for_statement(unit_id: str, statement: CommandStmt) -> tuple[Effect, ...]:
    if statement.command_name is None:
        return ()
    command_name = statement.command_name.text.casefold()
    if command_name in {"@emit", "think"}:
        return (
            Effect(
                unit_id=unit_id,
                kind="emit",
                span=statement.span,
                command_name=statement.command_name.text,
            ),
        )
    if command_name == "@pemit":
        target_span = (
            None if statement.assignment is None else statement.assignment.lhs.span
        )
        return (
            Effect(
                unit_id=unit_id,
                kind="emit",
                span=statement.span,
                command_name=statement.command_name.text,
                target_span=target_span,
            ),
        )
    if statement.trigger is not None:
        return (
            Effect(
                unit_id=unit_id,
                kind="trigger",
                span=statement.trigger.span,
                command_name=statement.trigger.command_name.text,
                target_span=statement.trigger.target.span,
            ),
        )
    if statement.wait is not None:
        nested: tuple[Effect, ...] = ()
        if statement.wait.nested_action_block is not None:
            nested = _effects_for_action_list(
                unit_id,
                statement.wait.nested_action_block.actions,
            )
        return (
            Effect(
                unit_id=unit_id,
                kind="wait",
                span=statement.wait.span,
                command_name=statement.wait.command_name.text,
                target_span=statement.wait.delay.span,
            ),
            *nested,
        )
    return ()


def _action_references_for_statement(
    unit_id: str,
    source: str,
    statement: CommandStmt,
) -> tuple[Reference, ...]:
    references: list[Reference] = []
    if statement.trigger is not None:
        references.append(
            _reference_for_trigger_command(unit_id, source, statement.trigger.target)
        )
    if statement.wait is not None and statement.wait.nested_action_block is not None:
        references.extend(
            _action_references_for_action_list(
                unit_id,
                source,
                statement.wait.nested_action_block.actions,
            )
        )
    if (
        statement.dolist is not None
        and statement.dolist.nested_action_block is not None
    ):
        references.extend(
            _action_references_for_action_list(
                unit_id,
                source,
                statement.dolist.nested_action_block.actions,
            )
        )
    if statement.switch is not None:
        for case in statement.switch.cases:
            if case.nested_action_block is not None:
                references.extend(
                    _action_references_for_action_list(
                        unit_id,
                        source,
                        case.nested_action_block.actions,
                    )
                )
    return tuple(references)


def _reference_for_trigger_command(
    unit_id: str,
    source: str,
    target_arg: CommandArg,
) -> Reference:
    target = _literal_command_arg(source, target_arg)
    if target is None:
        return Reference(
            unit_id=unit_id,
            function_name="@TRIGGER",
            span=target_arg.span,
            target_span=target_arg.span,
            dynamic=True,
            reason="dynamic @trigger target",
        )
    return Reference(
        unit_id=unit_id,
        function_name="@TRIGGER",
        span=target_arg.span,
        target_span=target_arg.span,
        target=target,
    )


def _attribute_writes_for_statement(
    unit_id: str,
    source: str,
    statement: CommandStmt,
) -> tuple[AttributeWrite, ...]:
    if statement.command_name is None or statement.assignment is None:
        return ()
    command_base = statement.command_name.text.casefold().split("/", maxsplit=1)[0]
    if command_base != "@set":
        return ()
    target = source[
        statement.assignment.lhs.span.start : statement.assignment.lhs.span.end
    ].strip()
    object_ref, separator, attribute = target.partition("/")
    if not separator or not object_ref or not attribute:
        return (
            AttributeWrite(
                unit_id=unit_id,
                span=statement.span,
                target_span=statement.assignment.lhs.span,
                dynamic=True,
                reason="dynamic @set target",
            ),
        )
    return (
        AttributeWrite(
            unit_id=unit_id,
            span=statement.span,
            target_span=statement.assignment.lhs.span,
            object_ref=object_ref.casefold(),
            attribute=attribute.casefold(),
        ),
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
    source: str,
    document: Document,
) -> tuple[QRegisterReference, ...]:
    references: list[QRegisterReference] = []
    for child in document.children:
        references.extend(_q_register_references_for_node(unit_id, source, child))
    return tuple(references)


def _rpc_references_for_document(
    unit_id: str,
    source: str,
    document: Document,
) -> tuple[RpcReference, ...]:
    references: list[RpcReference] = []
    for child in document.children:
        references.extend(_rpc_references_for_node(unit_id, source, child))
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


def _rpc_references_for_node(
    unit_id: str,
    source: str,
    node: Node,
) -> tuple[RpcReference, ...]:
    references: list[RpcReference] = []
    if isinstance(node, FunctionCall):
        if node.name == "RPC":
            references.append(_rpc_reference_for_call(unit_id, source, node))
        for argument in node.arguments:
            references.extend(_rpc_references_for_argument(unit_id, source, argument))
    elif isinstance(node, BraceGroup | EvalGroup):
        for child in node.children:
            references.extend(_rpc_references_for_node(unit_id, source, child))
    return tuple(references)


def _q_register_references_for_node(
    unit_id: str,
    source: str,
    node: Node,
) -> tuple[QRegisterReference, ...]:
    references: list[QRegisterReference] = []
    if isinstance(node, PercentSub):
        reference = _q_register_reference_for_percent_sub(unit_id, node)
        if reference is not None:
            references.append(reference)
    elif isinstance(node, FunctionCall):
        if node.name == "SETQ":
            references.append(_q_register_reference_for_setq(unit_id, source, node))
        for argument in node.arguments:
            references.extend(
                _q_register_references_for_argument(unit_id, source, argument)
            )
    elif isinstance(node, BraceGroup | EvalGroup):
        for child in node.children:
            references.extend(_q_register_references_for_node(unit_id, source, child))
    return tuple(references)


def _rpc_references_for_argument(
    unit_id: str,
    source: str,
    argument: Argument,
) -> tuple[RpcReference, ...]:
    references: list[RpcReference] = []
    for child in argument.children:
        references.extend(_rpc_references_for_node(unit_id, source, child))
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
    source: str,
    argument: Argument,
) -> tuple[QRegisterReference, ...]:
    references: list[QRegisterReference] = []
    for child in argument.children:
        references.extend(_q_register_references_for_node(unit_id, source, child))
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


def _q_register_reference_for_setq(
    unit_id: str,
    source: str,
    call: FunctionCall,
) -> QRegisterReference:
    if not call.arguments:
        return QRegisterReference(
            unit_id=unit_id,
            span=call.span,
            register=None,
            operation="write",
            dynamic=True,
            reason="missing setq() register",
        )
    register = _literal_argument(source, call.arguments[0])
    if register is None:
        return QRegisterReference(
            unit_id=unit_id,
            span=call.arguments[0].span,
            register=None,
            operation="write",
            dynamic=True,
            reason="dynamic setq() register",
        )
    return QRegisterReference(
        unit_id=unit_id,
        span=call.arguments[0].span,
        register=register,
        operation="write",
    )


def _rpc_reference_for_call(
    unit_id: str,
    source: str,
    call: FunctionCall,
) -> RpcReference:
    if not call.arguments:
        return RpcReference(
            unit_id=unit_id,
            span=call.span,
            endpoint_span=call.span,
            dynamic=True,
            reason="missing rpc() endpoint",
        )
    endpoint = _literal_argument(source, call.arguments[0])
    if endpoint is None:
        return RpcReference(
            unit_id=unit_id,
            span=call.span,
            endpoint_span=call.arguments[0].span,
            dynamic=True,
            reason="dynamic rpc() endpoint",
        )
    return RpcReference(
        unit_id=unit_id,
        span=call.span,
        endpoint_span=call.arguments[0].span,
        endpoint=endpoint,
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


def _literal_command_arg(source: str, argument: CommandArg) -> str | None:
    raw = source[argument.span.start : argument.span.end]
    document = parse_expression(raw)
    if len(document.children) != 1 or not isinstance(document.children[0], Text):
        return None
    return raw.strip().casefold()


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
