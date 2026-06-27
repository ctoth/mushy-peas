import pytest

from tests.oracle.pennmush_oracle import (
    BaselineDatabases,
    OracleRun,
    assert_oracle_success,
    load_baseline_databases,
    oracle_available,
    run_load_oracle,
)

pytestmark = pytest.mark.skipif(
    not oracle_available(),
    reason="PennMUSH WSL oracle is not available",
)


@pytest.fixture(scope="module")
def baseline() -> BaselineDatabases:
    return load_baseline_databases()


def test_oracle_uncompressed_main_mail_chat(
    baseline: BaselineDatabases,
) -> None:
    run = run_load_oracle(
        main_text=baseline.main_text,
        mail=baseline.mail,
        chat=baseline.chat,
        compression="none",
    )

    assert_oracle_success(run)


def test_oracle_gzip_main_mail_chat(baseline: BaselineDatabases) -> None:
    run = run_load_oracle(
        main_text=baseline.main_text,
        mail=baseline.mail,
        chat=baseline.chat,
        compression="gzip",
    )

    assert_oracle_success(run)


def test_oracle_bzip2_main_mail_chat(baseline: BaselineDatabases) -> None:
    run = run_load_oracle(
        main_text=baseline.main_text,
        mail=baseline.mail,
        chat=baseline.chat,
        compression="bzip2",
    )

    assert_oracle_success(run)


def test_oracle_rejects_partial_mail_or_chat_load(
    baseline: BaselineDatabases,
) -> None:
    run = run_load_oracle(
        main_text=baseline.main_text,
        mail=baseline.mail,
        chat=baseline.chat,
        compression="none",
    )
    run = OracleRun(
        game_dir=run.game_dir,
        log=run.log + "\nERROR: Unable to read mail database! Continuing.\n",
    )

    with pytest.raises(AssertionError, match="Unable to read mail database"):
        assert_oracle_success(run)
