# Copyright (c) 2026 PitchAI. All rights reserved.
"""Declare a process edge, the only place where a broad exception handler may stand.

Copy this file unchanged into the application package. The strict kit's
process-edges gate honours ``@process_edge`` only when it is imported from a
module whose file is byte-identical to the kit's own copy.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Callable

type EdgeKind = Literal["cli", "worker_loop", "http_boundary", "job", "best_effort"]

PROCESS_EDGES: dict[str, EdgeKind] = {}


def process_edge[**P, R](kind: EdgeKind) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Mark a CLI entry, worker loop, HTTP boundary, job runner or best-effort step as a process edge.

    Returns:
        A decorator that records the edge and returns the function unchanged.
    """

    def mark(function: Callable[P, R]) -> Callable[P, R]:
        PROCESS_EDGES[f"{function.__module__}.{function.__qualname__}"] = kind
        return function

    return mark


def fail_job[R](
    logger: logging.Logger,
    error: BaseException,
    record_failure: Callable[[BaseException], R],
    *,
    message: str = "job failed",
    level: int = logging.ERROR,
) -> R:
    """Log a failed job with its traceback and record the failure, so the loop serves the next job.

    Only a best_effort edge may lower the level, and only to logging.WARNING.

    Returns:
        Whatever record_failure returns, such as the job's failed result, so a job edge may return it.
    """
    logger.log(level, message, exc_info=error)
    return record_failure(error)
