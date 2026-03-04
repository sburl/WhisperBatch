# WhisperBatch Do-Work Queue and Roadmap

**Created:** 2026-03-03-16-56
**Last Updated:** 2026-03-03-16-56

Date: 2026-03-03

## Purpose

This queue keeps work focused and non-chaotic by separating:

- Immediate improvements (reliability, ergonomics, speed, quality)
- Big vision work (new feature direction and product expansion)
- Maintenance (housekeeping, security, and quality infrastructure)

All work is grouped into stages with 5-15 tasks each so each PR batch stays small.

## Priorities by category

## Improvements

1. Add deterministic file ordering in `process_directory` so transcriptions are processed in stable lexical order.
2. Return a clear summary from CLI after each directory run (`success`, `failed`, skipped, elapsed time).
3. Add explicit unsupported-directory and file-path validation with actionable error messages.
4. Add CLI flags for output format (`txt`, `json`, `srt`, `vtt`).
5. Add per-file retry support and exponential backoff for transient transcription failures.
6. Surface real-time model-download status in CLI and GUI.
7. Add output overwrite/append control and `--overwrite` safeguard.
8. Save model selection and timestamps options with each queue item in the GUI for reproducibility.
9. Add `--resume` mode for interrupted queue processing.
10. Add configurable worker concurrency for future GPU batching and queue parallelism.
11. Expose elapsed-time/throughput metrics in a small dashboard panel in GUI.
12. Add command-line JSON output for machine-readable summary reports.
13. Add `.whisperbatch` project config file support.
14. Add drag-drop folder import to the GUI queue.
15. Add “export everything” mode to bundle logs + outputs into one zip.
16. Add GUI output format selection (`txt`, `json`, `srt`, `vtt`) with queue-rendering parity.

## Implementation note

Stage 1 task 5 (core helper edge-case tests) is covered by [PR-K](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Stage 1 task 6 (dependency + secret scan in CI) is covered by [PR-J](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Stage 2 task 7 (overwrite and output safety controls) is now covered by [PR-L](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute), [PR-AJ](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute), and [PR-DJ](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Stage 1 task 3 (validation and actionable errors) is covered by [PR-M](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Stage 1 task 2 (CLI summary output) is covered by [PR-N](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute) and now [PR-DI](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Stage 1 task 4 (output format flags) is now covered by [PR-DG](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Stage 2 task 1 (retry handling for transient failures) is now covered by [PR-AD](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Stage 2 task 5 (machine-readable summary output) is covered by [PR-P](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Stage 2 task 4 (duration/throughput metrics visibility) is now covered by [PR-AI](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Stage 2 task 6 (CLI usage and debugging examples) is covered by [PR-S](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Improvements task 10 (configurable worker concurrency for future GPU batching) is now covered by [PR-AR](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute) and [PR-AS](plan-and-pr-tracking.md#pr-as).
Stage 4 task 14 (dependency vulnerability scan) is covered by [PR-R](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Stage 1 task 1 (deterministic file ordering in process_directory) is now covered by [PR-DH](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Stage 3 task 2 (project config support) is now covered by [PR-AL](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Stage 3 task 3 (resume mode and resume metadata usage) is now covered by [PR-AM](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute), including GUI resume behavior and metadata-aware task skipping.
Stage 3 task 4 (plugin hook points for post-processing) is now covered by [PR-AT](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Stage 3 task 5 (export everything into one bundle) is now covered by [PR-AU](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Stage 3 task 7 (integration tests for format/export correctness) is now covered by [PR-AU](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Stage 3 task 6 (speaker and language profile presets) is now covered by [PR-AW](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Improvements task 16 (GUI output format selection) is now covered by [PR-DD](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute), with rendering-helper tests in [PR-DE](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Maintenance task 14 (dependency vulnerability scan in nightly CI) is now also covered by [PR-AE](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Maintenance task 11 (explicit Python version policy and rationale) is now covered by [PR-BP](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Stage 4 task 9 (shared model metadata/constants) is covered by [PR-G1](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Maintenance task 8 (remove dead code and dead imports from GUI event handlers) is covered by [PR-X](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute) and [PR-Z](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Maintenance task 7 (package entry points) is covered by [PR-U](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Maintenance task 11 (reproducible dev environment guidance) is partly covered by [PR-V](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Maintenance task 3 (CLI test for --help plus invalid arguments) is covered by [PR-W](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Maintenance task 6 (minimal static format/lint check in PR CI) is covered by [PR-AA](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Maintenance task 8 (remove dead code and dead imports from GUI event handlers) is now additionally covered by [PR-AC](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Maintenance task 4 (mutation-style exception path tests) is partially covered by [PR-AG](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Maintenance task 13 (nightly compatibility smoke for all supported Python versions) is now covered by [PR-AH](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Stage 2 task 3 (per-item metadata/model/timestamp options in GUI/CLI pathways) is now covered by [PR-AK](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Improvements task 14 (drag-drop folder import to GUI queue) is now covered by [PR-AP](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Maintenance task 9 (move repeated constants into shared module) is now covered by [PR-AQ](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Maintenance task 9 (move repeated constants into shared module) is now also covered by [PR-CN](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Maintenance task 9 (move repeated constants into shared module) is now also covered by [PR-CO](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Maintenance task 3 (expand unit tests for edge cases in whisper_batch_core helpers) is now also covered by [PR-CY](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Big Vision task 1 (plugin interface for post-transcription processors) is now covered by [PR-BQ](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Stage 4 task 5 (minimal plugin docs and extension contract) is now covered by [PR-BR](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Stage 5 task 1 (build first post-transcription plugin) is now covered by [PR-BR](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Stage 4 task 6 (small postmortem logging standard) is now covered by [PR-BS](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Stage 4 task 7 (follow-up for async/transcoding pipeline exploration) is now covered by [PR-BT](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute), [PR-CA](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute), and [PR-CB](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Big Vision task 2 (optional cloud upload integration) is now covered by [PR-BU](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Big Vision task 3 (team shared output folder mode with provenance metadata) is now covered by [PR-BV](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Big Vision task 4 (multilingual translation profile presets) is now covered by [PR-BW](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Big Vision task 5 (transcript diff and correction review mode) is now covered by [PR-BX](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Big Vision task 6 (speaker-segmentation support with optional speaker tagging) is now covered by [PR-BY](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Big Vision task 7 (remote model backend abstraction) is now covered by [PR-BZ](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Big Vision task 13 (annotation export in CSV/JSONL) is now covered by [PR-CC](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Improvements task 6 (real-time model-download status in CLI and GUI) is now covered by [PR-CD](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute), [PR-CE](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute), and [PR-CF](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).
Output-format timestamp propagation correctness is now covered by [PR-CZ](plan-and-pr-tracking.md#pr-tracking-table-for-work-to-execute).

## Big Vision

1. Add a plugin interface for post-transcription processors (redaction, summaries, punctuation).
2. Add optional cloud upload integration (S3 / GCS) for outputs.
3. Add team shared output folder mode with provenance metadata.
4. Add multilingual translation profile presets in a single click.
5. Add transcript diff and correction review mode.
6. Add speaker-segmentation support with optional speaker tagging.
7. Add remote model backend abstraction (local whisper + API fallback).
8. Add web-based control panel with optional local-only web server.
9. Add timeline explorer preview in GUI using media waveform thumbnails.
10. Add accessibility mode: high-contrast theme + large font + keyboard-first flow.
11. Add queue templates and saved presets for recurring jobs.
12. Add first-class CLI+GUI integration tests with fake models for reproducibility.
13. Add annotation export in CSV/JSONL for downstream search and indexing.
14. Add optional auto-split on silence and voice activity detection tuning UI.
15. Add collaborative session mode with job handoff metadata.

## Maintenance

1. Expand unit tests for edge cases in `whisper_batch_core` helpers.
2. Add integration tests around path filtering and output path conflicts.
3. Add CLI test for `--help` plus invalid arguments.
4. Add mutation-style tests for common exception paths.
5. Add secret scanning in local CI (`trufflehog` or simple regex baseline).
6. Add a minimal static format/lint check in PR CI.
7. Add Python package metadata for CLI entry points.
8. Remove dead code and dead imports from GUI event handlers.
9. Move repeated constants into a shared config module.
10. Refactor GUI file model to isolate queue operations from rendering code.
11. Document explicit Python version policy (supported versions and rationale).
12. Add reproducible dev environment guidance (`requirements-dev.txt`, pinned pip-tools).
13. Add nightly compatibility smoke test for all supported Python versions.
14. Add vulnerability scan in CI for Python dependencies.
15. Add an incident playbook for model download failures and corrupt caches.

## Stage execution plan

### Stage 1 – Foundation hardening (5-6 tasks)
1. Implement deterministic processing order.
2. Improve input validation and error messaging.
3. Add robust CLI summary output.
4. Expand `transcribe_audio` directory handling tests.
5. Expand `core` helper edge-case tests (empty segments, invalid seconds).
6. Add dependency + secret scan to CI.

### Stage 2 – User experience stabilization (5-6 tasks)
1. Add retry handling for transient failures.
2. Add overwrite and output safety controls.
3. Add per-item queue metadata and per-file options in GUI.
4. Add duration/throughput metrics visibility.
5. Add machine-readable job summary output mode.
6. Improve README usage examples around recovery and debugging.

### Stage 3 – Output and workflow expansion (6-7 tasks)
1. Add JSON/SRT/VTT output types.
2. Add config file support and queue presets.
3. Add resume mode and resume metadata.
4. Add plugin hook points for post-processing.
5. Add export bundle command.
6. Add speaker and language profile presets.
7. Add integration tests for format/export correctness.

### Stage 4 – Maintainability and architecture (6-7 tasks)
1. Split GUI and core concerns into clearer modules.
2. Remove dead-code paths and simplify event handling.
3. Add lint/format baseline and cleanups.
4. Add nightlies for full matrix and dependency vulnerability scan.
5. Add minimal plugin docs and extension contract.
6. Add small postmortem logging standard.
7. Prepare follow-up PR for asynchronous/transcoding pipeline exploration.

### Stage 5 – Big vision pilots (5-7 tasks)
1. Build first post-transcription plugin (summary or clean-up).
2. Add optional cloud destination integration (opt-in backend).
3. Build web/API control surface MVP.
4. Add speaker workflow prototype for future differentiation.
5. Add shared session export/import format.
6. Add annotation/metadata export (CSV/JSONL).
7. Measure adoption of vision items against acceptance criteria.

## Merge order (working)

1. PR-A: baseline docs + PR tracking system
2. PR-B: dependency PR mirror into `requirements.txt`
3. PR-C: NumPy compatibility decision path (explicit policy first, if needed)
4. PR-E: local CI split
5. PR-F: validation + bug hardening tests and behavior tweaks
6. PR-G: GUI dead-code cleanup
7. PR-G1: core dead-code cleanup
8. PR-H: simplification/refactor passes
9. PR-I: roadmap + do-work queue execution plan
10. PR-R: dependency vulnerability scan in nightly CI
11. PR-S: expanded CLI docs for new output/retry/summary flows
12. PR-T: add static security scan to nightly CI
13. PR-U: add package entry points for installed CLI commands
14. PR-V: install package in editable mode during setup
15. PR-W: add CLI argument handling regression tests
16. PR-X: remove GUI dead paths in progress/tracking state
17. PR-Y: refactor GUI ffprobe duration probing into shared helper
18. PR-Z: tighten GUI ffprobe error handling with filename-aware messages
19. PR-AA: add ruff lint check to PR CI
20. PR-AC: remove dead GUI progress UI path
21. PR-AD: add exponential retry backoff controls and tests
22. PR-AE: shift resource-heavy security scans into nightly CI
23. PR-AF: align CLI model choices with shared SUPPORTED_MODELS source
24. PR-AG: harden write-failure exception handling with coverage
25. PR-AH: expand nightly Python matrix to 3.13
26. PR-AI: add GUI progress and throughput metrics label updates
27. PR-AJ: add GUI overwrite toggle and skip-by-default output behavior
28. PR-AK: persist per-item GUI transcription metadata for reproducibility
29. PR-AL: add `.whisperbatch` config file defaults with CLI overrides
30. PR-AO: metadata sidecar compatibility + overwrite/resume precedence across CLI + GUI
31. PR-AP: add GUI folder import with recursive discovery and duplicate filtering
32. PR-AQ: share output-format constants in `whisper_batch_core`
33. PR-AR: add `--max-workers` as a concurrency intent flag in CLI
34. PR-AS: document `--max-workers` and add config validation tests
35. PR-AT: add configurable post-process hook command support (`--postprocess-cmd` and config)
36. PR-AU: add export bundle command for completed directory runs
37. PR-AV: add optional language hint support for transcription runs
38. PR-AW: add language and speaker profile preset support (`language_profile`, `speaker_profile`)
39. PR-AX: apply profile model selection to runtime model_name and preserve CLI override order
40. PR-AY: enforce resume precedence on stale metadata when overwrite is disabled
41. PR-BB: stabilize processing order for case-variant filenames
42. PR-BD: stabilize export bundle file ordering with case-variant tie-breakers
43. PR-BE: align GUI default model with CLI default
44. PR-BF: align GUI timestamp default with CLI default
45. PR-BG: keep GUI default model selection tied to model list ordering
46. PR-BI: standardize CI dependency installs via requirements-dev manifest
47. PR-BJ: include pip-tools in dev manifest for reproducible tooling workflows
48. PR-BK: add actionable model load failure context (corrupt cache/download issues)
49. PR-BL: add model-load failure playbook for cache/download incidents
50. PR-BM: run nightly code format checks in CI
51. PR-BN: add unit tests for CI secret scan script behavior
52. PR-BO: disambiguate output filenames when input stems collide
53. PR-BP: add runtime Python version support policy and startup guard
54. PR-BQ: add optional Python post-processing plugin hook
55. PR-BR: add plugin contract docs and sample post-process plugin module
56. PR-BS: add postmortem failure logging for failed files
57. PR-BT: prepare follow-up PR for asynchronous/transcoding pipeline exploration
58. PR-BU: design phase for optional cloud upload destination integration
59. PR-BV: design phase for shared output folder mode with provenance metadata
60. PR-BW: design phase for translation preset integration
61. PR-BX: design phase for transcript diff and correction review mode
62. PR-BY: design phase for speaker segmentation and optional tagging
63. PR-BZ: design phase for remote model backend abstraction
64. PR-CA: add stable async transcription task envelope and queue builder
65. PR-CB: add async execution policy guardrails and explicit rationale messaging
66. PR-CC: add per-segment annotation export (CSV/JSONL)
67. PR-CD: surface CLI model cache status and load/download timing before transcription
68. PR-CE: share model cache root/path helpers in `whisper_batch_core` and use from CLI + GUI
69. PR-CF: surface cache-hit/miss + model load timing in GUI load flow
70. PR-CG: align cache clear guidance with env-var-aware cache resolution
71. PR-CH: normalize cache-root env values in `whisper_batch_core` helpers
72. PR-CJ: centralize CLI default model constant usage in `transcribe_audio.py`
73. PR-CK: share default model constant in core and GUI initialization
74. PR-CL: centralize supported task constants in core and CLI
75. PR-CM: drive CLI help text from shared constants
76. PR-CN: share default task constant across core and CLI signatures
77. PR-CO: apply shared default task constant in GUI transcription calls
78. PR-CY: centralize default output format usage and remove duplicated default literals
79. PR-CZ: fix output timestamp propagation by output format
80. PR-DA: align resume overwrite precedence with stale metadata behavior
81. PR-DD: add GUI output format selection and rendering parity
