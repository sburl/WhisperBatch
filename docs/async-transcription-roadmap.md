# WhisperBatch asynchronous transcription roadmap

**Created:** 2026-03-03-17-23
**Last Updated:** 2026-03-03-17-23

This is a follow-up exploration plan for Stage 4 task 7 (`max-workers` intent).
The current CLI and GUI currently keep transcription single-threaded and set aside
`max-workers` as a future knob. This document defines a controlled way to evolve
from intent to implementation.

## Goals

- Preserve current one-model-per-run behavior and output ordering guarantees.
- Increase throughput on larger directories and when model download is already
  complete.
- Keep failure handling and resume semantics unchanged (`failures`, `postmortem.jsonl`).
- Avoid introducing non-deterministic output ordering before a migration is complete.

## Proposed phases

1. Internal execution contract
   - Introduce an internal `TranscribeTask` type with:
     - `index` (stable ordering),
     - `source_path`,
     - `output_path`,
     - `metadata`.
   - Keep path-resolution and metadata construction in the main thread.
   - Move only the transcribe + hook execution into workers.

2. Bounded worker pool
   - Use a bounded queue with up to `max_workers` worker threads.
   - Only enable parallelism when all supported files share the same model and
     `--task`, `--language`, `--output-format` to keep cache sharing behavior predictable.
   - Log and reject unsupported mix that would break current resume assumptions.

3. Failure aggregation
   - Preserve per-file failure reporting in the same `failures` array.
   - Emit worker exceptions into a consistent failure envelope before merge.
   - Keep `postmortem.jsonl` as the post-run source of truth for failed runs.

4. Deterministic completion
   - Write outputs to temporary file names first and rename once complete.
   - Keep final directory summary consistent with input ordering for resumability and auditability.

5. Gradual rollout
   - Default to current single-worker mode.
   - Enable worker pool only when all of these are true:
     - `max_workers > 1`,
     - `--dry-run` mode is not requested (future flag),
     - plugin hook is explicitly verified as thread-safe (see follow-up flag).

## Immediate follow-up PR (PR-BT) scope

This roadmap is considered implemented as a follow-up plan when converted into a concrete PR plan. The next PR should be tightly scoped to:

1. Add an internal execution contract module in `whisper_batch_core`.
   - Introduce `TranscriptionTask` and `TranscriptionOutcome` typed containers in a module that is imported but not yet defaulted on.
   - Keep all contract members immutable while in queue to prevent accidental mutation from worker threads.
2. Add a lightweight queue adapter layer with deterministic scheduling.
   - Single-process coordinator builds the ordered task list once and hands indexes to workers.
   - Worker dispatch preserves input index so summaries and resume metadata can remain ordered.
3. Add compatibility guardrails.
   - Reject async mode unless model/task/profile/output options are uniform across a batch.
   - Add a short-circuit path when plugin hooks are not marked as `thread_safe`.
4. Add a test seam.
   - Add deterministic ordering assertions around task queue indexes before any asynchronous implementation is activated.

If this PR is too large, split into:
- PR-BT.1: task contract + deterministic scheduler tests.
- PR-BT.2: guarded async execution gate + queue ordering metadata.
- PR-BT.3: plugin/thread-safety contract extension.

### PR-BT acceptance criteria

- No change to default behavior (single-worker path stays default and stable).
- No nondeterministic reordering in any existing summary, manifest, or output path.
- Failure path still emits `failures` summary entries and `postmortem.jsonl` records.
- Any unsupported async-activation guard should fail fast with one-line rationale in logs.

## Risks to address

- Hook safety: `postprocess_command` may invoke shared command-line tools and may need explicit serialization.
- GPU memory pressure: each worker currently would require separate inference context.
- Metadata sidecars: multiple workers writing the same model/metadata path requires
  per-task directory locks or unique temp paths.

## Non-goals for this phase

- No change to current CLI behavior in this stage.
- No auto-tuning of `max_workers`.
- No process-based multiprocessing yet; threadpool-first keeps model and memory
  behavior easier to reason about before process-level parallelization.
