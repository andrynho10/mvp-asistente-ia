import re
from typing import Iterable


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def remove_bullet_prefixes(text: str) -> str:
    pattern = r"^\s*[-*•]\s+"
    lines = [re.sub(pattern, "", line) for line in text.splitlines()]
    return "\n".join(lines)


def clean_text(text: str, pipeline: Iterable = None) -> str:
    steps = list(pipeline) if pipeline else [remove_bullet_prefixes, normalize_whitespace]
    cleaned = text
    for fn in steps:
        cleaned = fn(cleaned)
    return cleaned
