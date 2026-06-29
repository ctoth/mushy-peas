from pathlib import Path

from mushy_peas.softcode.coverage_report import build_softcode_coverage_report
from mushy_peas.softcode.function_metadata import FunctionMetadata, FunctionRegistry
from mushy_peas.softcode.units import extract_softcode_units


def test_softcode_coverage_report_counts_units_parses_and_graph_edges(
    tmp_path: Path,
) -> None:
    root = tmp_path / "wcnh" / "systems" / "softcode"
    root.mkdir(parents=True)
    (root / "system.mush").write_text(
        "\n".join(
            (
                "&FN.HELPER #10=1",
                "&FN.CALLER #10=u(fn.helper,1) get(%q0)",
                "&CMD.TEST #10=$test:@pemit %#=hi;@set #10/DESC=value",
            )
        ),
        encoding="utf-8",
    )
    units = extract_softcode_units([root]).units

    report = build_softcode_coverage_report(units, metadata=_registry())

    assert report.unit_count == 3
    assert report.expression_parsed_count == 3
    assert report.action_parsed_count == 1
    assert report.graph_definition_count == 3
    assert report.graph_reference_count == 1
    assert report.attribute_read_count == 1
    assert report.attribute_write_count == 1
    assert report.q_register_reference_count == 1
    assert report.effect_count == 1
    assert report.diagnostic_count == 0
    assert report.unknown_node_count == 0
    assert report.unsupported_categories == ("dynamic get() attribute",)


def test_softcode_coverage_report_counts_profile_diagnostics(tmp_path: Path) -> None:
    root = tmp_path / "wcnh" / "systems" / "softcode"
    root.mkdir(parents=True)
    (root / "system.mush").write_text(
        "&DATA.VALUE #10=anything",
        encoding="utf-8",
    )
    units = extract_softcode_units([root]).units

    report = build_softcode_coverage_report(units)

    assert report.unit_count == 1
    assert report.expression_parsed_count == 1
    assert report.diagnostic_count == 1


def _registry() -> FunctionRegistry:
    return FunctionRegistry(
        pennmush_commit="test",
        functions={
            "GET": _function("GET"),
            "U": _function("U"),
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
