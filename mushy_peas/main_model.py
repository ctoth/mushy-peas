"""Dataclasses for PennMUSH main object databases."""

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class PennFlag:
    name: str
    letter: str
    types: tuple[str, ...] = ()
    perms: tuple[str, ...] = ()
    negate_perms: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class PennAttribute:
    name: str
    flags: tuple[str, ...] = ()
    creator: int = -1
    data: str = ""
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class PennLock:
    type: str
    creator: int
    flags: tuple[str, ...]
    derefs: int
    key: str


@dataclass(frozen=True)
class PennObject:
    dbref: int
    name: str
    location: int
    contents: int
    exits: int
    next: int
    parent: int
    locks: dict[str, PennLock] = field(default_factory=dict[str, PennLock])
    owner: int = -1
    zone: int = -1
    pennies: int = 0
    type: int = 0
    flags: tuple[str, ...] = ()
    powers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    created: int = 0
    modified: int = 0
    attributes: dict[str, PennAttribute] = field(
        default_factory=dict[str, PennAttribute]
    )


@dataclass(frozen=True)
class PennMainDatabase:
    raw_dbflags: int
    dbversion: int | None
    savedtime: str
    flags: dict[str, PennFlag] = field(default_factory=dict[str, PennFlag])
    powers: dict[str, PennFlag] = field(default_factory=dict[str, PennFlag])
    attributes: dict[str, PennAttribute] = field(
        default_factory=dict[str, PennAttribute]
    )
    objects: dict[int, PennObject] = field(default_factory=dict[int, PennObject])
    object_count: int = 0
    line_ending: str = "\n"
    format_kind: Literal["main-current", "main-oldstyle"] = "main-current"
