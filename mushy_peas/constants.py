"""PennMUSH database constants."""

from typing import Final

OBJECT_TYPE_ROOM: Final[int] = 0x1
OBJECT_TYPE_THING: Final[int] = 0x2
OBJECT_TYPE_EXIT: Final[int] = 0x4
OBJECT_TYPE_PLAYER: Final[int] = 0x8
OBJECT_TYPE_GARBAGE: Final[int] = 0x10

CURRENT_DB_VERSION: Final[int] = 6

MAIL_FLAG_SUBJECT: Final[int] = 0x1
MAIL_FLAG_ALIASES: Final[int] = 0x2
MAIL_FLAG_NEW_EOD: Final[int] = 0x4
MAIL_FLAG_SENDER_CTIME: Final[int] = 0x8
MAIL_FLAGS_CURRENT: Final[int] = (
    MAIL_FLAG_SUBJECT
    | MAIL_FLAG_ALIASES
    | MAIL_FLAG_NEW_EOD
    | MAIL_FLAG_SENDER_CTIME
)

CHAT_FLAG_SPIFFY: Final[int] = 0x01
CHAT_FLAGS_CURRENT: Final[int] = CHAT_FLAG_SPIFFY

END_MARKER_CURRENT: Final[str] = "***END OF DUMP***"
END_MARKER_OLD: Final[str] = "*** END OF DUMP ***"
