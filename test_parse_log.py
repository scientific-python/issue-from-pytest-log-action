import re
import sys

import hypothesis.strategies as st
from hypothesis import given, note

import parse_logs

directory_re = r"(\w|-)+"
path_re = re.compile(rf"/?({directory_re}(/{directory_re})*/)?test_[A-Za-z0-9_]+\.py")
filepaths = st.from_regex(path_re, fullmatch=True)

group_re = r"Test[A-Za-z0-9_]+"
name_re = re.compile(rf"({group_re}::)*test_[A-Za-z0-9_]+")
names = st.from_regex(name_re, fullmatch=True)

variants = st.from_regex(re.compile(r"(\w+-)*\w+"), fullmatch=True)

messages = st.text()


def ansi_csi_escapes():
    parameter_bytes = st.lists(st.characters(min_codepoint=0x30, max_codepoint=0x3F))
    intermediate_bytes = st.lists(st.characters(min_codepoint=0x20, max_codepoint=0x2F))
    final_bytes = st.characters(min_codepoint=0x40, max_codepoint=0x7E)

    return st.builds(
        lambda *args: "".join(["\x1b[", *args]),
        parameter_bytes.map("".join),
        intermediate_bytes.map("".join),
        final_bytes,
    )


def ansi_c1_escapes():
    byte_ = st.characters(
        codec="ascii", min_codepoint=0x40, max_codepoint=0x5F, exclude_characters=["["]
    )
    return st.builds(lambda b: f"\x1b{b}", byte_)


def ansi_fe_escapes():
    return ansi_csi_escapes() | ansi_c1_escapes()


def preformatted_reports():
    return st.tuples(filepaths, names, variants | st.none(), messages).map(
        lambda x: parse_logs.PreformattedReport(*x)
    )


@given(filepaths, names, variants)
def test_parse_nodeid(path, name, variant):
    if variant is not None:
        nodeid = f"{path}::{name}[{variant}]"
    else:
        nodeid = f"{path}::{name}"

    note(f"nodeid: {nodeid}")

    expected = {"filepath": path, "name": name, "variant": variant}
    actual = parse_logs.parse_nodeid(nodeid)

    assert actual == expected


@given(st.lists(preformatted_reports()), st.integers(min_value=0))
def test_truncate(reports, max_chars):
    py_version = ".".join(str(part) for part in sys.version_info[:3])

    formatted = parse_logs.truncate(reports, max_chars=max_chars, py_version=py_version)

    assert formatted is None or len(formatted) <= max_chars


@given(st.lists(ansi_fe_escapes()).map("".join))
def test_strip_ansi_multiple(escapes):
    assert parse_logs.strip_ansi(escapes) == ""


@given(ansi_fe_escapes())
def test_strip_ansi(escape):
    message = f"some {escape}text"

    assert parse_logs.strip_ansi(message) == "some text"
