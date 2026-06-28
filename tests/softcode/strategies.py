"""Hypothesis strategies for softcode parser tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from hypothesis import strategies as st
from hypothesis.strategies import SearchStrategy

DEFAULT_CORPUS_SEED_FIXTURE = Path("tests/fixtures/softcode/corpus-seeds.json")


def corpus_seed_texts(
    fixture: Path = DEFAULT_CORPUS_SEED_FIXTURE,
) -> SearchStrategy[str]:
    seeds = _load_seed_texts(fixture)
    if not seeds:
        return st.just("")
    return st.sampled_from(seeds)


def _load_seed_texts(fixture: Path) -> list[str]:
    payload_any: Any = json.loads(fixture.read_text(encoding="utf-8"))
    if not isinstance(payload_any, dict):
        raise ValueError("corpus seed fixture must be a JSON object")
    payload = cast(dict[str, Any], payload_any)
    seeds_any = payload.get("seeds")
    if not isinstance(seeds_any, list):
        raise ValueError("corpus seed fixture must contain a seeds list")
    seeds = cast(list[object], seeds_any)
    texts: list[str] = []
    for seed_any in seeds:
        if not isinstance(seed_any, dict):
            raise ValueError("corpus seed entries must be JSON objects")
        seed = cast(dict[str, Any], seed_any)
        text = seed.get("text")
        if not isinstance(text, str):
            raise ValueError("corpus seed text must be a string")
        texts.append(text)
    return texts
