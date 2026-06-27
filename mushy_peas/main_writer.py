"""Writer for current PennMUSH main object databases."""

from mushy_peas.main_model import PennAttribute, PennFlag, PennMainDatabase
from mushy_peas.primitives import write_dbref, write_quoted_string


def write_global_lists(database: PennMainDatabase) -> str:
    return "\n".join(
        (
            write_flag_section("+FLAGS LIST", database.flags),
            write_flag_section("+POWER LIST", database.powers),
            write_attribute_section(database.attributes),
        )
    )


def write_flag_section(section_header: str, flags: dict[str, PennFlag]) -> str:
    lines: list[str] = [section_header]
    lines.append(f"flagcount {len(flags)}")
    for flag in flags.values():
        lines.extend(
            (
                f" name {write_quoted_string(flag.name)}",
                f"  letter {write_quoted_string(flag.letter)}",
                f"  type {write_quoted_string(_join_words(flag.types))}",
                f"  perms {write_quoted_string(_join_words(flag.perms))}",
                "  negate_perms "
                f"{write_quoted_string(_join_words(flag.negate_perms))}",
            )
        )

    alias_count = sum(len(flag.aliases) for flag in flags.values())
    lines.append(f"flagaliascount {alias_count}")
    for flag in flags.values():
        for alias in flag.aliases:
            lines.extend(
                (
                    f" name {write_quoted_string(flag.name)}",
                    f"  alias {write_quoted_string(alias)}",
                )
            )

    return "\n".join(lines)


def write_attribute_section(attributes: dict[str, PennAttribute]) -> str:
    lines: list[str] = ["+ATTRIBUTES LIST"]
    lines.append(f"attrcount {len(attributes)}")
    for attribute in attributes.values():
        lines.extend(
            (
                f" name {write_quoted_string(attribute.name)}",
                f"  flags {write_quoted_string(_join_words(attribute.flags))}",
                f"  creator {write_dbref(attribute.creator)}",
                f"  data {write_quoted_string(attribute.data)}",
            )
        )

    alias_count = sum(len(attribute.aliases) for attribute in attributes.values())
    lines.append(f"attraliascount {alias_count}")
    for attribute in attributes.values():
        for alias in attribute.aliases:
            lines.extend(
                (
                    f" name {write_quoted_string(attribute.name)}",
                    f"  alias {write_quoted_string(alias)}",
                )
            )

    return "\n".join(lines)


def _join_words(words: tuple[str, ...]) -> str:
    return " ".join(words)
