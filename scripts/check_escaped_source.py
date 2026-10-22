#!/usr/bin/env python
"""Reject Python sources that were mangled by an HTML-escaped paste.

A file that contains ``-&gt;`` instead of ``->`` or ``&lt;`` instead of ``<``
fails with a SyntaxError hundreds of lines away from the paste. This hook
reports the cause instead of the symptom.

It uses the tokenizer rather than a text search, so an escaped entity inside a
string literal (legitimate when the program generates HTML) is not flagged: the
pattern only matches the token sequence ``& NAME(gt|lt|amp|...) ;`` in code.

    python scripts/check_escaped_source.py <file> [<file> ...]
"""

from __future__ import annotations

import sys
import tokenize

ENTITIES = {"gt", "lt", "amp", "quot", "apos", "nbsp"}


def check(path: str) -> list[str]:
    problems: list[str] = []
    try:
        with open(path, "rb") as fh:
            tokens = list(tokenize.tokenize(fh.readline))
    except (OSError, tokenize.TokenError, SyntaxError) as exc:
        return [f"{path}: cannot tokenize ({exc})"]

    for i in range(len(tokens) - 2):
        amp, name, semi = tokens[i], tokens[i + 1], tokens[i + 2]
        if (
            amp.type == tokenize.OP
            and amp.string == "&"
            and name.type == tokenize.NAME
            and name.string in ENTITIES
            and semi.type == tokenize.OP
            and semi.string == ";"
        ):
            problems.append(
                f"{path}:{amp.start[0]}: HTML-escaped entity '&{name.string};' in code"
            )
    return problems


def main(argv: list[str]) -> int:
    files = argv[1:]
    if not files:
        print("usage: check_escaped_source.py <file> [<file> ...]", file=sys.stderr)
        return 2
    problems: list[str] = []
    for target in files:
        problems.extend(check(target))
    for p in problems:
        print(p, file=sys.stderr)
    if problems:
        print(f"\n{len(problems)} escaped entity/entities found.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))