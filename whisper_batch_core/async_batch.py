from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Mapping, Optional

from .core import DEFAULT_OUTPUT_FORMAT


@dataclass(frozen=True)
class TranscriptionTask:
    """Deterministic task envelope for future parallel transcription pipelines."""

    index: int
    source_path: Path
    output_format: str = DEFAULT_OUTPUT_FORMAT
    metadata: Optional[Mapping[str, object]] = None


def build_stable_task_queue(source_paths: Iterable[Path]) -> List[TranscriptionTask]:
    """
    Build a stable, deterministic task queue from source paths.

    The queue is ordered with the same case-insensitive + case-sensitive
    tie-breaker strategy as the CLI directory path traversal.
    """
    sorted_paths = sorted(source_paths, key=lambda path: (str(path).lower(), str(path)))
    return [
        TranscriptionTask(index=index, source_path=Path(path))
        for index, path in enumerate(sorted_paths)
    ]


@dataclass(frozen=True)
class AsyncExecutionPolicy:
    requested_workers: int
    enabled: bool
    reason: Optional[str] = None


def evaluate_async_execution_policy(
    *,
    requested_workers: int,
    postprocess_command: Optional[str],
    postprocess_plugin: Optional[str],
) -> AsyncExecutionPolicy:
    """
    Evaluate whether the current run can safely transition to async execution.

    For this release, async is intentionally disabled while we keep ordering and
    recovery semantics simple.
    """
    if requested_workers <= 1:
        return AsyncExecutionPolicy(requested_workers=requested_workers, enabled=False, reason=None)

    if postprocess_command or postprocess_plugin:
        return AsyncExecutionPolicy(
            requested_workers=requested_workers,
            enabled=False,
            reason=(
                "Async execution is currently disabled when postprocess hooks are configured; "
                "hooks can change output side effects and need explicit thread-safety controls."
            ),
        )

    return AsyncExecutionPolicy(
        requested_workers=requested_workers,
        enabled=False,
        reason="Async execution is reserved for a future release.",
    )


def build_task_metadata(task: TranscriptionTask) -> dict:
    """Build a compact metadata payload suitable for resumability and logging."""
    return {
        "index": task.index,
        "source_path": str(task.source_path),
        "output_format": task.output_format,
    }
