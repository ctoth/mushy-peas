from pathlib import Path

import pytest

from mushy_peas.softcode.function_metadata import (
    generate_function_metadata_fixture,
    load_function_registry,
)

FIXTURE = Path("tests/fixtures/softcode/pennmush-functions.json")


def test_fixture_records_pennmush_commit() -> None:
    registry = load_function_registry(FIXTURE)

    assert registry.pennmush_commit == (
        "4d1d4a9e5cfc3c227b213de242721092a970ad41"
    )


def test_add_metadata_is_available() -> None:
    registry = load_function_registry(FIXTURE)
    add = registry.require("add")

    assert add.name == "ADD"
    assert add.min_args == 2
    assert add.max_args == 2_147_483_647
    assert add.is_builtin


def test_fixture_contains_noparse_and_literal_functions() -> None:
    registry = load_function_registry(FIXTURE)

    assert registry.require("@@").is_noparse
    assert registry.require("lit").is_literal


def test_missing_required_function_fails_loudly() -> None:
    registry = load_function_registry(FIXTURE)

    with pytest.raises(KeyError, match="missing PennMUSH function metadata"):
        registry.require("definitely_not_a_function")


def test_generate_function_metadata_fixture_from_pennmush_source(
    tmp_path: Path,
) -> None:
    checkout = tmp_path / "pennmush"
    (checkout / "hdrs").mkdir(parents=True)
    (checkout / "src").mkdir()
    (checkout / "hdrs" / "function.h").write_text(
        "\n".join(
            (
                "#define FN_REG 0x0",
                "#define FN_NOPARSE 0x1",
                "#define FN_LITERAL 0x2",
                "#define FN_STRIPANSI 0x10000",
            )
        ),
        encoding="utf-8",
    )
    (checkout / "hdrs" / "conf.h").write_text(
        "#define MAX_STACK_ARGS 30\n",
        encoding="utf-8",
    )
    (checkout / "src" / "function.c").write_text(
        "\n".join(
            (
                "FUNTAB flist[] = {",
                '  {"@@", fun_null, 1, INT_MAX, FN_NOPARSE},',
                '  {"ADD", fun_add, 2, INT_MAX, FN_REG | FN_STRIPANSI},',
                '  {"LIT", fun_lit, 1, -1, FN_LITERAL},',
                '  {"UFUN", fun_ufun, 1, (MAX_STACK_ARGS + 1), FN_REG},',
                "  {NULL, NULL, 0, 0, 0}};",
            )
        ),
        encoding="utf-8",
    )

    payload = generate_function_metadata_fixture(
        checkout,
        pennmush_commit="abc123",
    )
    functions = {function["name"]: function for function in payload["functions"]}

    assert payload["provenance"]["pennmush_commit"] == "abc123"
    assert payload["flag_values"]["FN_STRIPANSI"] == 65_536
    assert functions["@@"]["flag_names"] == ["FN_NOPARSE"]
    assert functions["ADD"]["flags"] == 65_536
    assert functions["ADD"]["max_args"] == 2_147_483_647
    assert functions["LIT"]["max_args"] == -1
    assert functions["UFUN"]["max_args"] == 31
    assert all(function["is_builtin"] for function in functions.values())
