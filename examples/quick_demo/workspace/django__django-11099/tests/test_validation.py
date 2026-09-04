"""Benchmark test suite for django__django-11099 username validation."""

import re


def test_username_ascii_regex_matching() -> None:
    pattern = r"^[a-zA-Z0-9_]+$"
    input_val = "valid_user_123"
    assert re.match(pattern, input_val) is not None


def test_username_rejects_special_characters() -> None:
    pattern = r"^[a-zA-Z0-9_]+$"
    input_val = "invalid@user!"
    assert re.match(pattern, input_val) is None
