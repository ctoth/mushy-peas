"""Coverage and maturity reporting for softcode parsing."""

from __future__ import annotations

from dataclasses import dataclass

from mushy_peas.softcode.actions import parse_action_list, parse_command_attribute_body
from mushy_peas.softcode.function_metadata import FunctionRegistry
from mushy_peas.softcode.graph import (
    SemanticGraph,
    build_semantic_graph,
    collect_semantic_diagnostics,
)
from mushy_peas.softcode.model import (
    Argument,
    BraceGroup,
    Document,
    EvalGroup,
    FunctionCall,
    Node,
    Unknown,
)
from mushy_peas.softcode.parser import parse_expression
from mushy_peas.softcode.profiles import classify_profile
from mushy_peas.softcode.units import SoftcodeUnit


@dataclass(frozen=True)
class SoftcodeCoverageReport:
    unit_count: int
    expression_parsed_count: int
    action_parsed_count: int
    graph_definition_count: int
    graph_reference_count: int
    attribute_read_count: int
    attribute_write_count: int
    q_register_reference_count: int
    rpc_reference_count: int
    effect_count: int
    diagnostic_count: int
    unknown_node_count: int
    unsupported_categories: tuple[str, ...]


def build_softcode_coverage_report(
    units: tuple[SoftcodeUnit, ...],
    *,
    metadata: FunctionRegistry | None = None,
) -> SoftcodeCoverageReport:
    expression_parsed_count = 0
    action_parsed_count = 0
    unknown_node_count = 0
    for unit in units:
        document = parse_expression(unit.body, metadata=metadata)
        expression_parsed_count += 1
        unknown_node_count += _unknown_count(document)
        if classify_profile(unit).family == "command":
            _parse_action_unit(unit)
            action_parsed_count += 1
    graph = build_semantic_graph(units, metadata=metadata)
    diagnostics = collect_semantic_diagnostics(units)
    return SoftcodeCoverageReport(
        unit_count=len(units),
        expression_parsed_count=expression_parsed_count,
        action_parsed_count=action_parsed_count,
        graph_definition_count=len(graph.definitions),
        graph_reference_count=len(graph.references),
        attribute_read_count=len(graph.attribute_references),
        attribute_write_count=len(graph.attribute_writes),
        q_register_reference_count=len(graph.q_register_references),
        rpc_reference_count=len(graph.rpc_references),
        effect_count=len(graph.effects),
        diagnostic_count=len(diagnostics),
        unknown_node_count=unknown_node_count,
        unsupported_categories=_unsupported_categories(graph),
    )


def _parse_action_unit(unit: SoftcodeUnit) -> None:
    body = parse_command_attribute_body(unit.body)
    if body is None:
        parse_action_list(unit.body)


def _unknown_count(document: Document) -> int:
    return sum(_unknown_count_node(child) for child in document.children)


def _unknown_count_node(node: Node) -> int:
    if isinstance(node, Unknown):
        return 1
    if isinstance(node, FunctionCall):
        return sum(_unknown_count_argument(argument) for argument in node.arguments)
    if isinstance(node, BraceGroup | EvalGroup):
        return sum(_unknown_count_node(child) for child in node.children)
    return 0


def _unknown_count_argument(argument: Argument) -> int:
    return sum(_unknown_count_node(child) for child in argument.children)


def _unsupported_categories(graph: SemanticGraph) -> tuple[str, ...]:
    categories: set[str] = set()
    categories.update(
        reference.reason
        for reference in graph.references
        if reference.dynamic and reference.reason is not None
    )
    categories.update(
        reference.reason
        for reference in graph.attribute_references
        if reference.dynamic and reference.reason is not None
    )
    categories.update(
        reference.reason
        for reference in graph.attribute_writes
        if reference.dynamic and reference.reason is not None
    )
    categories.update(
        reference.reason
        for reference in graph.q_register_references
        if reference.dynamic and reference.reason is not None
    )
    categories.update(
        reference.reason
        for reference in graph.rpc_references
        if reference.dynamic and reference.reason is not None
    )
    return tuple(sorted(categories))
