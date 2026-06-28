from pathlib import Path

from mushy_peas.softcode.inventory import (
    collect_softcode_inventory,
    render_inventory_report,
)


def test_collect_softcode_inventory_counts_attribute_units(tmp_path: Path) -> None:
    source = tmp_path / "system.mush"
    source.write_text(
        "\n".join(
            (
                "&CMD.TEST #10=$test:@pemit %#=ok",
                "&FN.VALUE #10=add(1,2)",
                "&MAP.DOC #10=iter(lattr(me/doc.*),##)",
                "&FILTER.VISIBLE #10=hasflag(%0,connected)",
                "&DOC.VALUE #10=doc text",
                "&DATA #10=#11",
                "&LOCK.CMD #10=owner(%#)",
                "&OTHER #10=value",
            )
        ),
        encoding="utf-8",
    )

    inventory = collect_softcode_inventory([tmp_path])

    root = inventory.roots[0]
    assert root.exists is True
    assert inventory.file_count == 1
    assert inventory.candidate_unit_count == 8
    assert inventory.file_kind_counts() == {"softcode": 1}
    assert inventory.unit_kind_counts() == {
        "cmd": 1,
        "data": 1,
        "doc": 1,
        "filter": 1,
        "fn": 1,
        "lock": 1,
        "map": 1,
        "unknown": 1,
    }


def test_collect_softcode_inventory_classifies_text_softcode(tmp_path: Path) -> None:
    source = tmp_path / "Who Renderer - WHO.txt"
    source.write_text(
        "\n".join(
            (
                "@@ DEPENDENCIES: Core",
                "th u(NEWCOBJ,Who Renderer <WHO>)",
                "&FUN`WHO`MAIN [u(cobj,who)]=u(sortname,lwho())",
            )
        ),
        encoding="utf-8",
    )

    inventory = collect_softcode_inventory([tmp_path])

    assert inventory.file_kind_counts() == {"softcode": 1}
    assert inventory.unit_kind_counts() == {"fn": 1}


def test_collect_softcode_inventory_reports_missing_root(tmp_path: Path) -> None:
    missing = tmp_path / "missing"

    inventory = collect_softcode_inventory([missing])

    assert inventory.file_count == 0
    assert inventory.candidate_unit_count == 0
    assert inventory.roots[0].path == missing.resolve()
    assert inventory.roots[0].exists is False


def test_collect_softcode_inventory_reports_skipped_directories(
    tmp_path: Path,
) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "ignored.mush").write_text("&FN.X #1=1", encoding="utf-8")
    (tmp_path / "kept.mush").write_text("&FN.Y #1=2", encoding="utf-8")

    inventory = collect_softcode_inventory([tmp_path])
    root = inventory.roots[0]

    assert inventory.file_count == 1
    assert inventory.candidate_unit_count == 1
    assert len(root.skipped_directories) == 1
    assert root.skipped_directories[0].path == tmp_path / ".git"


def test_render_inventory_report_is_deterministic(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Notes", encoding="utf-8")
    (tmp_path / "system.mush").write_text("&FN.X #1=1", encoding="utf-8")
    inventory = collect_softcode_inventory([tmp_path])

    report = render_inventory_report(inventory)

    assert report == render_inventory_report(inventory)
    assert "# Softcode Inventory Report" in report
    assert "- Files: 2" in report
    assert "- Candidate softcode units: 1" in report
    assert "- documentation: 1" in report
    assert "- softcode: 1" in report
