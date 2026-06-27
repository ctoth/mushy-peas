"""Reusable Hypothesis strategies for mushy-peas tests."""

from hypothesis import strategies as st
from hypothesis.strategies import SearchStrategy


def quoted_text() -> SearchStrategy[str]:
    alphabet = st.characters(
        min_codepoint=0x20,
        max_codepoint=0xFF,
        blacklist_characters="\r\n",
    ) | st.sampled_from(["\t"])
    return st.text(alphabet=alphabet, max_size=80)


def dbrefs() -> SearchStrategy[int]:
    return st.integers(min_value=-2, max_value=1_000_000)


def dbflags() -> SearchStrategy[int]:
    return st.integers(min_value=-5, max_value=1_000_000)
