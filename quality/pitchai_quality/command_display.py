# Copyright (c) 2026 PitchAI. All rights reserved.
"""Print a gate's command without spelling out its complete source-file list.

Every gate receives each Python file as an argument. Printed whole, that is a single
log line of hundreds of kilobytes, and the AX41 repository runners never log past
it: the job stalls at the first such gate until its timeout. The printed form keeps
the program and its options and names the files by count and digest, and shows any
single argument longer than 200 characters by length and digest. When the options
alone pass 1000 characters (generated --extend-per-file-ignores pairs), the first 12
are shown and the rest are named by count and digest. The command that runs is
unchanged.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

SOURCE_SUFFIXES = (".py", ".pyi")
DIGEST_LENGTH = 16
MAX_ARGUMENT = 200
MAX_OPTIONS = 1000
SHOWN_OPTIONS = 12


def displayed_command(command: Sequence[str]) -> str:
    """Return the command with its trailing source-file arguments summarized.

    Returns:
        The program and options, then the number of source files and the SHA-256 of their newline-joined list.
    """
    split = len(command)
    while split and command[split - 1].endswith(SOURCE_SUFFIXES):
        split -= 1
    files = command[split:]
    options = [_shown_argument(argument) for argument in command[:split]]
    if len(" ".join(options)) > MAX_OPTIONS:
        rest = options[SHOWN_OPTIONS:]
        digest = hashlib.sha256("\n".join(rest).encode()).hexdigest()[:DIGEST_LENGTH]
        options = [*options[:SHOWN_OPTIONS], f"[{len(rest)} more arguments, sha256 {digest}]"]
    if not files:
        return " ".join(options)
    digest = hashlib.sha256("\n".join(files).encode()).hexdigest()[:DIGEST_LENGTH]
    return f"{' '.join(options)} [{len(files)} source files, list sha256 {digest}]"


def _shown_argument(argument: str) -> str:
    if len(argument) <= MAX_ARGUMENT:
        return argument
    digest = hashlib.sha256(argument.encode()).hexdigest()[:DIGEST_LENGTH]
    return f"[{len(argument)}-character argument, sha256 {digest}]"
