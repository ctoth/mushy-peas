import json
from pathlib import Path

from mushy_peas.softcode.units import (
    extract_softcode_units,
    render_softcode_unit_report,
)


def test_extract_softcode_units_recognizes_attribute_install_lines(
    tmp_path: Path,
) -> None:
    source = tmp_path / "system.mush"
    source.write_text(
        "\n".join(
            (
                "&CMD.TEST #10=$test *:@pemit %#=ok",
                "&FN.VALUE #10=add(1,2)",
            )
        ),
        encoding="utf-8",
    )

    collection = extract_softcode_units([tmp_path])
    units = collection.units

    assert len(units) == 2
    assert [unit.attribute_kind for unit in units] == ["cmd", "fn"]
    assert units[0].attribute_name == "CMD.TEST"
    assert units[0].object_ref == "#10"
    assert units[0].command_pattern == "$test *"
    assert units[0].body == "$test *:@pemit %#=ok"
    assert units[0].source_span.start == 0
    assert units[0].source_span.end == len("&CMD.TEST #10=$test *:@pemit %#=ok")


def test_extract_softcode_units_preserves_unrecognized_lines_as_raw(
    tmp_path: Path,
) -> None:
    source = tmp_path / "system.mush"
    source.write_text(
        "\n".join(
            (
                "@create Test Object",
                "&FN.VALUE #10=add(1,2)",
                "-",
            )
        ),
        encoding="utf-8",
    )

    collection = extract_softcode_units([tmp_path])

    assert [(unit.attribute_kind, unit.body) for unit in collection.units] == [
        ("raw", "@create Test Object"),
        ("fn", "add(1,2)"),
    ]


def test_extract_softcode_units_coalesces_dash_terminated_attribute_bodies(
    tmp_path: Path,
) -> None:
    source = tmp_path / "system.mush"
    source.write_text(
        "\n".join(
            (
                "&FN.MULTI #10=",
                "  add(1,",
                "      2)",
                "-",
                "&FN.SINGLE #10=add(3,4)",
                "-",
            )
        ),
        encoding="utf-8",
    )

    collection = extract_softcode_units([tmp_path])
    units = collection.units

    assert [(unit.attribute_name, unit.body) for unit in units] == [
        ("FN.MULTI", "  add(1,\n      2)"),
        ("FN.SINGLE", "add(3,4)"),
    ]
    assert units[0].source_span.start == 0
    assert units[0].source_span.end == len("&FN.MULTI #10=\n  add(1,\n      2)\n-")


def test_extract_softcode_units_types_multiline_install_commands(
    tmp_path: Path,
) -> None:
    source = tmp_path / "system.mush"
    source.write_text(
        "\n".join(
            (
                "@desc #10=",
                "  [center(Test,79,-)]%r",
                "  Done",
                "-",
            )
        ),
        encoding="utf-8",
    )

    collection = extract_softcode_units([tmp_path])
    unit = collection.units[0]

    assert len(collection.units) == 1
    assert unit.attribute_kind == "cmd"
    assert unit.attribute_name == "@DESC"
    assert unit.object_ref == "#10"
    assert unit.body == "  [center(Test,79,-)]%r\n  Done"
    assert unit.command_pattern is None
    assert unit.source_span.start == 0
    assert unit.source_span.end == len(
        "@desc #10=\n  [center(Test,79,-)]%r\n  Done\n-"
    )


def test_extract_softcode_units_types_single_line_install_commands(
    tmp_path: Path,
) -> None:
    source = tmp_path / "system.mush"
    source.write_text("@set #10/DESC=no_command", encoding="utf-8")

    collection = extract_softcode_units([tmp_path])
    unit = collection.units[0]

    assert unit.attribute_kind == "cmd"
    assert unit.attribute_name == "@SET"
    assert unit.object_ref == "#10/DESC"
    assert unit.body == "no_command"


def test_extract_softcode_units_has_stable_ids(tmp_path: Path) -> None:
    source = tmp_path / "system.mush"
    source.write_text("&FN.VALUE #10=add(1,2)", encoding="utf-8")

    first = extract_softcode_units([tmp_path])
    second = extract_softcode_units([tmp_path])

    assert [unit.id for unit in first.units] == [unit.id for unit in second.units]


def test_softcode_units_are_json_serializable(tmp_path: Path) -> None:
    source = tmp_path / "system.mush"
    source.write_text("&FN.VALUE #10=add(1,2)", encoding="utf-8")
    collection = extract_softcode_units([tmp_path])

    payload = collection.to_json()

    assert json.loads(json.dumps(payload)) == payload


def test_render_softcode_unit_report_is_deterministic(tmp_path: Path) -> None:
    source = tmp_path / "system.mush"
    source.write_text(
        "\n".join(("&CMD.TEST #10=$test:@pemit %#=ok", "raw line")),
        encoding="utf-8",
    )
    collection = extract_softcode_units([tmp_path])

    report = render_softcode_unit_report(collection)

    assert report == render_softcode_unit_report(collection)
    assert "# Softcode Unit Report" in report
    assert "- Units: 2" in report
    assert "- cmd: 1" in report
    assert "- raw: 1" in report
