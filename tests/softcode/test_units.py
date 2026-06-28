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
        ("raw", "-"),
    ]


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
