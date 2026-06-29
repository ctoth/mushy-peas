from pathlib import Path

from mushy_peas.softcode.function_metadata import FunctionMetadata, FunctionRegistry
from mushy_peas.softcode.graph import (
    build_semantic_graph,
    collect_semantic_diagnostics,
)
from mushy_peas.softcode.units import extract_softcode_units


def test_graph_extracts_wcnh_command_and_function_definitions(
    tmp_path: Path,
) -> None:
    root = tmp_path / "wcnh" / "systems" / "softcode"
    root.mkdir(parents=True)
    (root / "system.mush").write_text(
        "\n".join(
            (
                "&FN.HELPER #10=1",
                "&CMD.TEST #10=$test:u(fn.helper,1)",
                "&MAP.VALUE #10=ignored",
            )
        ),
        encoding="utf-8",
    )
    units = extract_softcode_units([root]).units

    graph = build_semantic_graph(units)

    assert {(item.name, item.family) for item in graph.definitions} == {
        ("cmd.test", "command"),
        ("fn.helper", "function"),
    }
    assert graph.references == ()


def test_graph_extracts_literal_u_references(tmp_path: Path) -> None:
    root = tmp_path / "wcnh" / "systems" / "softcode"
    root.mkdir(parents=True)
    (root / "system.mush").write_text(
        "&FN.CALLER #10=u(fn.helper,1)",
        encoding="utf-8",
    )
    unit = extract_softcode_units([root]).units[0]

    graph = build_semantic_graph((unit,), metadata=_u_registry())
    reference = graph.references[0]

    assert reference.unit_id == unit.id
    assert reference.function_name == "U"
    assert reference.span.start == 0
    assert reference.span.end == len("u(fn.helper,1)")
    assert reference.target_span.start == 2
    assert reference.target_span.end == 11
    assert reference.target == "fn.helper"
    assert reference.dynamic is False
    assert reference.reason is None


def test_graph_represents_dynamic_u_references_explicitly(tmp_path: Path) -> None:
    root = tmp_path / "wcnh" / "systems" / "softcode"
    root.mkdir(parents=True)
    (root / "system.mush").write_text(
        "&FN.CALLER #10=u(%q0,1)",
        encoding="utf-8",
    )
    unit = extract_softcode_units([root]).units[0]

    graph = build_semantic_graph((unit,), metadata=_u_registry())
    reference = graph.references[0]

    assert reference.unit_id == unit.id
    assert reference.function_name == "U"
    assert reference.target_span.start == 2
    assert reference.target_span.end == 5
    assert reference.target is None
    assert reference.dynamic is True
    assert reference.reason == "dynamic u() target"


def test_semantic_diagnostics_include_profile_warnings(tmp_path: Path) -> None:
    root = tmp_path / "wcnh" / "systems" / "softcode"
    root.mkdir(parents=True)
    (root / "system.mush").write_text(
        "&DATA.VALUE #10=anything",
        encoding="utf-8",
    )
    unit = extract_softcode_units([root]).units[0]

    diagnostics = collect_semantic_diagnostics((unit,))
    diagnostic = diagnostics[0]

    assert diagnostic.unit_id == unit.id
    assert diagnostic.span == unit.source_span
    assert diagnostic.code == "profile.warning"
    assert diagnostic.message == "unrecognized WCNH attribute prefix"
    assert diagnostic.evidence == "profile=wcnh"


def _u_registry() -> FunctionRegistry:
    return FunctionRegistry(
        pennmush_commit="test",
        functions={
            "U": FunctionMetadata(
                name="U",
                min_args=1,
                max_args=2,
                flags=0,
                flag_names=(),
                is_builtin=True,
            )
        },
    )
