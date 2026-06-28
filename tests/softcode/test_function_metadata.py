from pathlib import Path

import pytest

from mushy_peas.softcode.function_metadata import load_function_registry

FIXTURE = Path("tests/fixtures/softcode/pennmush-functions.json")


def test_fixture_records_pennmush_commit() -> None:
    registry = load_function_registry(FIXTURE)

    assert registry.pennmush_commit == (
        "3bff8ce292fc14bdb0cee8575fbff0628a2b1ea5"
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
