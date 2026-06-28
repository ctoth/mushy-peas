"""Profile-specific softcode unit classification."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from mushy_peas.softcode.units import SoftcodeUnit

ProfileName = Literal["pennmush-core", "wcnh", "volund-mushcode", "unknown"]
ProfileFamily = Literal[
    "command",
    "function",
    "map",
    "filter",
    "unknown",
]


@dataclass(frozen=True)
class ProfileClassification:
    profile: ProfileName
    family: ProfileFamily
    warnings: tuple[str, ...] = ()


def classify_profile(unit: SoftcodeUnit) -> ProfileClassification:
    profile = _profile_name(unit.profile_hint)
    if profile == "wcnh":
        return _classify_wcnh(unit)
    return ProfileClassification(profile=profile, family="unknown")


def _classify_wcnh(unit: SoftcodeUnit) -> ProfileClassification:
    prefix = _attribute_prefix(unit.attribute_name)
    match prefix:
        case "cmd":
            return ProfileClassification(profile="wcnh", family="command")
        case "fn":
            return ProfileClassification(profile="wcnh", family="function")
        case "map":
            return ProfileClassification(profile="wcnh", family="map")
        case "filter":
            return ProfileClassification(profile="wcnh", family="filter")
        case _:
            return ProfileClassification(
                profile="wcnh",
                family="unknown",
                warnings=("unrecognized WCNH attribute prefix",),
            )


def _attribute_prefix(attribute_name: str | None) -> str | None:
    if not attribute_name:
        return None
    return re.split(r"[.`_-]", attribute_name.casefold(), maxsplit=1)[0]


def _profile_name(profile_hint: str) -> ProfileName:
    match profile_hint:
        case "pennmush-core" | "wcnh" | "volund-mushcode":
            return profile_hint
        case _:
            return "unknown"
