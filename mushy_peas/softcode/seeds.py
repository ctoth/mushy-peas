"""Corpus seed extraction for softcode parser tests."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from mushy_peas.errors import ParseError
from mushy_peas.main_reader import read_main_database_text
from mushy_peas.primitives import parse_labeled_line
from mushy_peas.softcode.inventory import line_spans, read_text_if_candidate
from mushy_peas.softcode.model import Span
from mushy_peas.softcode.units import extract_softcode_units

SeedKind = Literal[
    "wcnh_command_attr",
    "wcnh_function_attr",
    "mushcode_command_attr",
    "pennmush_test_expression",
    "pennmush_db_attribute",
]

THINK_TEST_RE = re.compile(
    r"test\('(?P<label>[^']+)'.*?'think (?P<expr>[^']*)'",
    re.DOTALL,
)


@dataclass(frozen=True)
class CorpusSeed:
    id: str
    kind: SeedKind
    text: str
    source_path: Path
    line_number: int
    source_span: Span
    label: str

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "text": self.text,
            "source_path": str(self.source_path),
            "line_number": self.line_number,
            "source_span": {
                "start": self.source_span.start,
                "end": self.source_span.end,
            },
            "label": self.label,
        }


@dataclass(frozen=True)
class CorpusSeedCollection:
    seeds: tuple[CorpusSeed, ...]
    max_per_kind: int

    def to_json(self) -> dict[str, Any]:
        return {
            "provenance": {
                "max_per_kind": self.max_per_kind,
                "notes": "Bounded deterministic seeds extracted from local corpora.",
            },
            "seeds": [seed.to_json() for seed in self.seeds],
        }


def collect_corpus_seeds(
    paths: Iterable[Path],
    *,
    max_per_kind: int = 50,
) -> CorpusSeedCollection:
    path_tuple = tuple(paths)
    units = extract_softcode_units(path_tuple).units
    seeds: list[CorpusSeed] = []
    for unit in units:
        kind = _unit_seed_kind(
            unit.profile_hint,
            unit.attribute_kind,
            unit.attribute_name,
            unit.command_pattern,
        )
        if kind is None:
            continue
        seeds.append(
            CorpusSeed(
                id=_seed_id(kind, unit.source_path, unit.line_number, unit.body),
                kind=kind,
                text=unit.body,
                source_path=unit.source_path,
                line_number=unit.line_number,
                source_span=unit.source_span,
                label=unit.attribute_name or unit.id,
            )
        )
    seeds.extend(_pennmush_test_expression_seeds(path_tuple))
    seeds.extend(_pennmush_db_attribute_seeds(path_tuple))
    return CorpusSeedCollection(
        seeds=_bounded_by_kind(seeds, max_per_kind),
        max_per_kind=max_per_kind,
    )


def write_corpus_seed_fixture(collection: CorpusSeedCollection, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(collection.to_json(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract bounded softcode seeds.")
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--max-per-kind", type=int, default=50)
    args = parser.parse_args(argv)

    collection = collect_corpus_seeds(args.paths, max_per_kind=args.max_per_kind)
    write_corpus_seed_fixture(collection, args.output)
    return 0


def _unit_seed_kind(
    profile_hint: str,
    attribute_kind: str,
    attribute_name: str | None,
    command_pattern: str | None,
) -> SeedKind | None:
    is_command_attribute = (
        attribute_name is not None and attribute_name.upper().startswith("CMD")
    )
    if profile_hint == "wcnh" and attribute_kind == "cmd" and is_command_attribute:
        return "wcnh_command_attr"
    if profile_hint == "wcnh" and attribute_kind == "fn":
        return "wcnh_function_attr"
    if (
        profile_hint == "volund-mushcode"
        and attribute_kind == "cmd"
        and (is_command_attribute or command_pattern is not None)
    ):
        return "mushcode_command_attr"
    return None


def _pennmush_test_expression_seeds(paths: tuple[Path, ...]) -> list[CorpusSeed]:
    seeds: list[CorpusSeed] = []
    for path in _iter_files(paths):
        if path.suffix.casefold() != ".t":
            continue
        text = read_text_if_candidate(path)
        if text is None:
            continue
        spans = line_spans(text)
        for line_number, (line, span) in enumerate(
            zip(text.splitlines(), spans, strict=True),
            start=1,
        ):
            match = THINK_TEST_RE.search(line)
            if match is None:
                continue
            expression = match.group("expr")
            label = match.group("label")
            seeds.append(
                CorpusSeed(
                    id=_seed_id(
                        "pennmush_test_expression",
                        path,
                        line_number,
                        expression,
                    ),
                    kind="pennmush_test_expression",
                    text=expression,
                    source_path=path,
                    line_number=line_number,
                    source_span=span,
                    label=label,
                )
            )
    return seeds


def _pennmush_db_attribute_seeds(paths: tuple[Path, ...]) -> list[CorpusSeed]:
    seeds: list[CorpusSeed] = []
    for path in _iter_files(paths):
        text = _read_current_main_db_text(path)
        if text is None:
            continue
        spans = line_spans(text)
        current_dbref: int | None = None
        remaining_attrs = 0
        pending_attr_name: str | None = None
        for line_number, (line, span) in enumerate(
            zip(text.splitlines(), spans, strict=True),
            start=1,
        ):
            stripped = line.lstrip(" ")
            if line.startswith("!"):
                current_dbref = _parse_dbref_header(line)
                remaining_attrs = 0
                pending_attr_name = None
                continue
            if current_dbref is None:
                continue
            if stripped.startswith("attrcount "):
                remaining_attrs = _parse_attrcount(line)
                pending_attr_name = None
                continue
            if remaining_attrs <= 0:
                continue
            if pending_attr_name is None and stripped.startswith("name "):
                pending_attr_name = _parse_quoted_label(line, "name")
                continue
            if pending_attr_name is not None and stripped.startswith("value "):
                value = _parse_quoted_label(line, "value")
                label = f"#{current_dbref}/{pending_attr_name}"
                seeds.append(
                    CorpusSeed(
                        id=_seed_id(
                            "pennmush_db_attribute",
                            path,
                            line_number,
                            value,
                        ),
                        kind="pennmush_db_attribute",
                        text=value,
                        source_path=path,
                        line_number=line_number,
                        source_span=span,
                        label=label,
                    )
                )
                remaining_attrs -= 1
                pending_attr_name = None
    return seeds


def _read_current_main_db_text(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if not text.startswith("+V"):
        return None
    try:
        read_main_database_text(text, source=str(path))
    except ParseError:
        return None
    return text


def _parse_dbref_header(line: str) -> int:
    try:
        return int(line[1:])
    except ValueError:
        return -1


def _parse_attrcount(line: str) -> int:
    label, value = parse_labeled_line(line, "int")
    if label != "attrcount":
        return 0
    return value


def _parse_quoted_label(line: str, expected_label: str) -> str:
    label, value = parse_labeled_line(line, "quoted")
    if label != expected_label:
        return ""
    return value


def _iter_files(paths: tuple[Path, ...]) -> Iterable[Path]:
    for path in paths:
        resolved = path.resolve()
        if resolved.is_file():
            yield resolved
            continue
        if not resolved.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(resolved):
            dirnames[:] = sorted(
                dirname
                for dirname in dirnames
                if dirname
                not in {
                    ".git",
                    ".hg",
                    ".mypy_cache",
                    ".pytest_cache",
                    ".ruff_cache",
                    ".svn",
                    "__pycache__",
                    "node_modules",
                }
            )
            for filename in sorted(filenames):
                yield Path(dirpath) / filename


def _bounded_by_kind(
    seeds: list[CorpusSeed],
    max_per_kind: int,
) -> tuple[CorpusSeed, ...]:
    grouped: dict[SeedKind, list[CorpusSeed]] = defaultdict(list)
    for seed in sorted(
        seeds,
        key=lambda item: (
            item.kind,
            str(item.source_path).casefold(),
            item.line_number,
        ),
    ):
        if len(grouped[seed.kind]) < max_per_kind:
            grouped[seed.kind].append(seed)
    return tuple(seed for kind in sorted(grouped) for seed in grouped[kind])


def _seed_id(kind: str, source_path: Path, line_number: int, text: str) -> str:
    key = f"{kind}:{source_path.resolve().as_posix().casefold()}:{line_number}:{text}"
    return f"seed:{hashlib.sha1(key.encode('utf-8')).hexdigest()[:16]}"


if __name__ == "__main__":
    raise SystemExit(main())
