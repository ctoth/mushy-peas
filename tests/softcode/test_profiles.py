from pathlib import Path

from mushy_peas.softcode import classify_profile
from mushy_peas.softcode.units import extract_softcode_units


def test_wcnh_profile_classifies_attribute_prefixes(tmp_path: Path) -> None:
    root = tmp_path / "wcnh" / "systems" / "softcode"
    root.mkdir(parents=True)
    (root / "system.mush").write_text(
        "\n".join(
            (
                "&CMD.TEST #10=$test:@pemit %#=ok",
                "&FN.VALUE #10=add(1,2)",
                "&MAP.VALUE #10=one two",
                "&FILTER.VALUE #10=match",
            )
        ),
        encoding="utf-8",
    )
    units = extract_softcode_units([root]).units

    assert [classify_profile(unit).family for unit in units] == [
        "command",
        "function",
        "map",
        "filter",
    ]


def test_profile_classification_is_independent_from_cst_success(
    tmp_path: Path,
) -> None:
    root = tmp_path / "wcnh" / "systems" / "softcode"
    root.mkdir(parents=True)
    (root / "broken.mush").write_text(
        "&CMD.BROKEN #10=[add(1,2)",
        encoding="utf-8",
    )
    unit = extract_softcode_units([root]).units[0]

    classification = classify_profile(unit)

    assert classification.profile == "wcnh"
    assert classification.family == "command"
    assert classification.warnings == ()


def test_wcnh_profile_warns_on_unrecognized_attribute_prefix(tmp_path: Path) -> None:
    root = tmp_path / "wcnh" / "systems" / "softcode"
    root.mkdir(parents=True)
    (root / "unknown.mush").write_text(
        "&DATA.VALUE #10=anything",
        encoding="utf-8",
    )
    unit = extract_softcode_units([root]).units[0]

    classification = classify_profile(unit)

    assert classification.family == "unknown"
    assert classification.warnings == ("unrecognized WCNH attribute prefix",)
