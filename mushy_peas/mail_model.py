"""Dataclasses for PennMUSH mail databases."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PennMailAlias:
    owner: int
    name: str
    description: str
    name_flags: int
    member_flags: int
    members: tuple[int, ...] = ()


@dataclass(frozen=True)
class PennMailMessage:
    to: int
    from_: int
    from_ctime: int
    time_text: str
    subject: str
    body: str
    read_flags: int


@dataclass(frozen=True)
class PennMailDatabase:
    raw_mail_flags: int
    aliases: list[PennMailAlias] = field(default_factory=list[PennMailAlias])
    messages: list[PennMailMessage] = field(default_factory=list[PennMailMessage])
    eod: str = "***END OF DUMP***"
    line_ending: str = "\n"
