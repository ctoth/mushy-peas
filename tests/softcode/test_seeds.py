import json
from pathlib import Path

from hypothesis import given, settings

from mushy_peas.softcode.seeds import collect_corpus_seeds
from tests.softcode.strategies import corpus_seed_texts


def test_collect_corpus_seeds_records_source_provenance(tmp_path: Path) -> None:
    wcnh = tmp_path / "wcnh" / "systems" / "softcode"
    mushcode = tmp_path / "mushcode"
    pennmush = tmp_path / "pennmush" / "test"
    wcnh.mkdir(parents=True)
    mushcode.mkdir()
    pennmush.mkdir(parents=True)
    (wcnh / "system.mush").write_text(
        "\n".join(
            (
                "&CMD.TEST #10=$test:@pemit %#=ok",
                "&FN.VALUE #10=add(1,2)",
            )
        ),
        encoding="utf-8",
    )
    (mushcode / "Who Renderer - WHO.txt").write_text(
        "&CMD`+WHO`MAIN [u(cobj,who)]=@pemit %#=u(FUN`WHO`MAIN)",
        encoding="utf-8",
    )
    (pennmush / "testmath.t").write_text(
        "test('add.1', $god, 'think add(1,2)', '3');",
        encoding="utf-8",
    )

    collection = collect_corpus_seeds([wcnh, mushcode, pennmush], max_per_kind=5)
    seeds = {seed.kind: seed for seed in collection.seeds}

    assert set(seeds) == {
        "mushcode_command_attr",
        "pennmush_test_expression",
        "wcnh_command_attr",
        "wcnh_function_attr",
    }
    assert seeds["wcnh_command_attr"].text == "$test:@pemit %#=ok"
    assert seeds["wcnh_function_attr"].text == "add(1,2)"
    assert seeds["mushcode_command_attr"].label == "CMD`+WHO`MAIN"
    assert seeds["pennmush_test_expression"].text == "add(1,2)"
    assert seeds["pennmush_test_expression"].label == "add.1"
    assert all(
        seed.source_span.end >= seed.source_span.start for seed in seeds.values()
    )


def test_collect_corpus_seeds_is_bounded_per_kind(tmp_path: Path) -> None:
    wcnh = tmp_path / "wcnh" / "systems" / "softcode"
    wcnh.mkdir(parents=True)
    (wcnh / "system.mush").write_text(
        "\n".join(f"&FN.VALUE{i} #10=add({i},1)" for i in range(5)),
        encoding="utf-8",
    )

    collection = collect_corpus_seeds([wcnh], max_per_kind=2)

    assert len(collection.seeds) == 2
    assert {seed.kind for seed in collection.seeds} == {"wcnh_function_attr"}


def test_collect_corpus_seeds_ignores_typed_install_commands(
    tmp_path: Path,
) -> None:
    wcnh = tmp_path / "wcnh" / "systems" / "softcode"
    wcnh.mkdir(parents=True)
    (wcnh / "system.mush").write_text(
        "\n".join(
            (
                "@desc #10=",
                "  add(1,2)",
                "-",
            )
        ),
        encoding="utf-8",
    )

    collection = collect_corpus_seeds([wcnh])

    assert collection.seeds == ()


def test_corpus_seed_collection_is_json_serializable(tmp_path: Path) -> None:
    wcnh = tmp_path / "wcnh" / "systems" / "softcode"
    wcnh.mkdir(parents=True)
    (wcnh / "system.mush").write_text("&FN.VALUE #10=add(1,2)", encoding="utf-8")
    collection = collect_corpus_seeds([wcnh])
    payload = collection.to_json()

    assert json.loads(json.dumps(payload)) == payload


@settings(max_examples=3)
@given(corpus_seed_texts())
def test_corpus_seed_strategy_loads_generated_fixture(seed: str) -> None:
    assert isinstance(seed, str)
