"""Application models and validators for django__django-11099."""

import re


def validate_username(username: str) -> bool:
    pattern = r"^[a-zA-Z0-9_]+$"
    return re.match(pattern, username) is not None
