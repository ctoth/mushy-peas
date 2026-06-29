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


def test_graph_extracts_literal_ufun_and_ulocal_references(tmp_path: Path) -> None:
    root = tmp_path / "wcnh" / "systems" / "softcode"
    root.mkdir(parents=True)
    (root / "system.mush").write_text(
        "&FN.CALLER #10=ufun(fn.helper,1) [ulocal(fn.local,2)]",
        encoding="utf-8",
    )
    unit = extract_softcode_units([root]).units[0]

    graph = build_semantic_graph((unit,), metadata=_user_function_registry())

    assert [
        (reference.function_name, reference.target, reference.dynamic)
        for reference in graph.references
    ] == [
        ("UFUN", "fn.helper", False),
        ("ULOCAL", "fn.local", False),
    ]


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


def test_graph_represents_dynamic_ufun_references_explicitly(tmp_path: Path) -> None:
    root = tmp_path / "wcnh" / "systems" / "softcode"
    root.mkdir(parents=True)
    (root / "system.mush").write_text(
        "&FN.CALLER #10=ufun(%q0,1)",
        encoding="utf-8",
    )
    unit = extract_softcode_units([root]).units[0]

    graph = build_semantic_graph((unit,), metadata=_user_function_registry())
    reference = graph.references[0]

    assert reference.function_name == "UFUN"
    assert reference.target is None
    assert reference.dynamic is True
    assert reference.reason == "dynamic ufun() target"


def test_graph_extracts_literal_trigger_references(tmp_path: Path) -> None:
    root = tmp_path / "wcnh" / "systems" / "softcode"
    root.mkdir(parents=True)
    (root / "system.mush").write_text(
        "&FN.CALLER #10=trigger(#10/fn.helper,1)",
        encoding="utf-8",
    )
    unit = extract_softcode_units([root]).units[0]

    graph = build_semantic_graph((unit,), metadata=_trigger_registry())
    reference = graph.references[0]

    assert reference.unit_id == unit.id
    assert reference.function_name == "TRIGGER"
    assert reference.target_span.start == 8
    assert reference.target_span.end == 21
    assert reference.target == "#10/fn.helper"
    assert reference.dynamic is False
    assert reference.reason is None


def test_graph_represents_dynamic_trigger_references_explicitly(
    tmp_path: Path,
) -> None:
    root = tmp_path / "wcnh" / "systems" / "softcode"
    root.mkdir(parents=True)
    (root / "system.mush").write_text(
        "&FN.CALLER #10=trigger(%q0,1)",
        encoding="utf-8",
    )
    unit = extract_softcode_units([root]).units[0]

    graph = build_semantic_graph((unit,), metadata=_trigger_registry())
    reference = graph.references[0]

    assert reference.function_name == "TRIGGER"
    assert reference.target is None
    assert reference.dynamic is True
    assert reference.reason == "dynamic trigger() target"


def test_graph_extracts_literal_get_and_xget_attribute_references(
    tmp_path: Path,
) -> None:
    root = tmp_path / "wcnh" / "systems" / "softcode"
    root.mkdir(parents=True)
    (root / "system.mush").write_text(
        "&FN.CALLER #10=get(me/name) [xget(#10,desc)]",
        encoding="utf-8",
    )
    unit = extract_softcode_units([root]).units[0]

    graph = build_semantic_graph((unit,), metadata=_attribute_registry())

    assert [
        (
            reference.function_name,
            reference.object_ref,
            reference.attribute,
            reference.dynamic,
        )
        for reference in graph.attribute_references
    ] == [
        ("GET", None, "me/name", False),
        ("XGET", "#10", "desc", False),
    ]
    get_ref = graph.attribute_references[0]
    assert get_ref.attribute_span.start == 4
    assert get_ref.attribute_span.end == 11
    xget_ref = graph.attribute_references[1]
    assert xget_ref.object_span is not None
    assert xget_ref.object_span.start == 19
    assert xget_ref.object_span.end == 22
    assert xget_ref.attribute_span.start == 23
    assert xget_ref.attribute_span.end == 27


def test_graph_represents_dynamic_get_attribute_references_explicitly(
    tmp_path: Path,
) -> None:
    root = tmp_path / "wcnh" / "systems" / "softcode"
    root.mkdir(parents=True)
    (root / "system.mush").write_text(
        "&FN.CALLER #10=get(%q0)",
        encoding="utf-8",
    )
    unit = extract_softcode_units([root]).units[0]

    graph = build_semantic_graph((unit,), metadata=_attribute_registry())
    reference = graph.attribute_references[0]

    assert reference.function_name == "GET"
    assert reference.attribute is None
    assert reference.dynamic is True
    assert reference.reason == "dynamic get() attribute"


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
        functions={"U": _function("U")},
    )


def _user_function_registry() -> FunctionRegistry:
    return FunctionRegistry(
        pennmush_commit="test",
        functions={
            "UFUN": _function("UFUN"),
            "ULOCAL": _function("ULOCAL"),
        },
    )


def _trigger_registry() -> FunctionRegistry:
    return FunctionRegistry(
        pennmush_commit="test",
        functions={"TRIGGER": _function("TRIGGER")},
    )


def _attribute_registry() -> FunctionRegistry:
    return FunctionRegistry(
        pennmush_commit="test",
        functions={
            "GET": _function("GET"),
            "XGET": _function("XGET"),
        },
    )


def _function(name: str) -> FunctionMetadata:
    return FunctionMetadata(
        name=name,
        min_args=1,
        max_args=2,
        flags=0,
        flag_names=(),
        is_builtin=True,
    )
