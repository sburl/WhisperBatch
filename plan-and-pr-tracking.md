# WhisperBatch Improvement Plan and PR Tracking

**Created:** 2026-03-03-16-56
**Last Updated:** 2026-03-03-16-56

Date: 2026-03-03

## Ground Rules

- Keep PRs small and tightly scoped.
- Each PR should do one kind of change.
- Review loop before merge:
  1) internal self-review,
  2) Gemini review via CLI command,
  3) incorporate feedback,
  4) final go/no-go.
- Track all stages, PRs, and outcomes here.

## Current repository PR audit (remote PRs)

| PR # | Title | State | Base | Risk | My initial assessment |
|---|---|---|---|---|---|
| 7 | Add Dependabot | MERGED | main | Low | Already merged; keep as historical precedent. |
| 2 | Bump faster-whisper 1.0.3 -> 1.2.1 | OPEN / BLOCKED | main | Medium | Safe-looking dependency bump, but should be reviewed against pinned assumptions and runtime compatibility. |
| 6 | Bump numpy 1.24.3 -> 2.0.2 | OPEN / BLOCKED | main | Medium-High | Potential Python compatibility impact (3.8 support) and transitive dependency churn. |
| 3 | Bump librosa 0.10.1 -> 0.11.0 | OPEN / BLOCKED | main | Medium | Should be evaluated with same model pipeline compatibility checks. |
| 5 | Bump requests 2.31.0 -> 2.32.5 | OPEN / BLOCKED | main | Low | Low risk, mostly security/stability improvements. |
| 4 | Bump tqdm 4.66.1 -> 4.67.3 | OPEN / BLOCKED | main | Low | Very low risk formatting/output changes only. |

### PR review outcomes and planned in-repo mirror decisions

- PR-requests (`requests==2.32.5`): **Review result: accept-with-follow-up**. Gemini flagged potential Python floor and TLS/session behavior risks. Follow-up: verify Python version policy before final merge.
- PR-tqdm (`tqdm==4.67.3`): **Review result: approve**. Low-risk output behavior change; keep as dependency hygiene.
- PR-librosa (`librosa==0.11.0`): **Review result: proceed with caution**. Potential numerical and dependency implications; verify preprocessing assumptions.
- PR-faster-whisper (`faster-whisper==1.2.1`): **Review result: recommended with follow-up**. Requires environment validation (CUDA path) and VAD behavior verification.
- PR-numpy (`numpy==2.0.2`): **Pending / likely hold** until matrix is validated (ABI/API break risk).

### Note on current blocks

All open dependency PRs are blocked in merge state (no checks currently reported). With no CI to validate, we should treat them as unmerged candidates and manually incorporate validated updates in a staged local sequence.

## PR Tracking Table (for work to execute)

- `status`: `Planned` | `In progress` | `Done` | `Needs follow-up`.
- `review`: `Pending` | `Gemini requested` | `Gemini approved` | `Needs rework`.

| Order | PR ID | Scope | Files | Planned status | Review status | Merge intent |
|---|---|---|---|---|---|---|
| 1 | PR-A | Baseline docs + planning artifacts | `user-questions-and-answers.md`, `plan-and-pr-tracking.md` | Done | Pending | No code behavior change |
| 2 | PR-B | Mirror dependency PRs for `requirements.txt` (`faster-whisper`, `tqdm`, `requests`) | `requirements.txt`, `pyproject.toml` | Done | Pending (Gemini quota) | Library floor aligned to `>=3.9` and dependencies mirrored with current pin set |
| 3 | PR-C | Optional numpy bump decision + compatibility fallback strategy | `requirements.txt`, `pyproject.toml`, `.github/workflows/ci.yml`, `setup.sh`, `transcribe_gui.py`, `README.md` | Done | Gemini approved | Raises Python floor to 3.9 and aligns NumPy 2.0.x support with torch and environment setup/docs. |
| 4 | PR-E | Add local CI workflow (PR and nightly split) | `.github/workflows/ci.yml` | Done | Gemini approved | Mandatory foundation for future PRs |
| 5 | PR-F | CLI/GUI/packaging validation improvements and bug hardening | `transcribe_audio.py`, `transcribe_gui.py`, `whisper_batch_core/*` | Done | Gemini approved | Incremental after CI exists |
| 6 | PR-G | Dead code pass (GUI cleanup) | `transcribe_gui.py` | Done | Pending | Removed dead UI estimate helpers and no-op state paths. Continue core cleanup in follow-up PRs |
| 7 | PR-G1 | Shared model metadata source-of-truth | `whisper_batch_core/core.py`, `transcribe_audio.py`, `transcribe_gui.py` | Done | Pending | `SUPPORTED_MODELS` is now defined in core and consumed by CLI/GUI |
| 8 | PR-H | Simplification/refactor pass (readability + function boundaries) | `transcribe_gui.py` | Done | Pending | Shared model metadata constant extraction in GUI |
| 9 | PR-I | Do-work queue and stage planning system | `do-work-queue.md` | Done | Gemini approved | Align future work with explicit roadmap and execution order |
| 10 | PR-J | Add CI secret scanning guardrail | `scripts/ci_secret_scan.py`, `.github/workflows/ci.yml` | Done | Gemini approved | Adds lightweight secret scanning in PR and nightly CI |
| 11 | PR-K | Expand core helper edge-case tests | `tests/test_core.py` | Done | Gemini approved | Adds core helper invariants and load_model/model-task coverage |
| 12 | PR-L | Add output overwrite guard for CLI batch runs | `transcribe_audio.py`, `tests/test_transcribe_audio.py` | Done | Gemini approved | Adds `--overwrite` and skip behavior for existing outputs |
| 13 | PR-M | Harden CLI input validation and actionable error messages | `transcribe_audio.py`, `tests/test_transcribe_audio.py` | Done | Gemini approved | Adds validation for model name, retry settings, and directory argument consistency |
| 14 | PR-N | Improve CLI completion summary output | `transcribe_audio.py`, `tests/test_transcribe_audio.py` | Done | Gemini approved | Adds `elapsed_seconds` and `success` summary metrics for each directory run |
| 15 | PR-O | Add CLI output format options (`txt/json/srt/vtt`) | `transcribe_audio.py`, `tests/test_transcribe_audio.py` | Done | Pending (Gemini quota) | Adds `--output-format` with renderer support and format-specific file output |
| 16 | PR-P | Add machine-readable summary output mode | `transcribe_audio.py`, `tests/test_transcribe_audio.py` | Done | Pending (Gemini quota) | Adds `--summary-json` for downstream automation consumption |
| 17 | PR-Q | Add throughput metrics to CLI summary | `transcribe_audio.py`, `tests/test_transcribe_audio.py` | Done | Pending (Gemini quota) | Adds `throughput_files_per_second` and prints throughput in final summary |
| 18 | PR-R | Add nightly dependency vulnerability scan to CI | `.github/workflows/ci.yml` | Done | Pending (Gemini quota) | Adds `pip-audit` to nightly checks |
| 19 | PR-S | Expand CLI docs for output formats, retries, and machine-readable summaries | `README.md` | Done | Pending (Gemini quota) | Keeps docs aligned with current CLI behavior |
| 20 | PR-T | Add nightly static security scan to CI | `.github/workflows/ci.yml` | Done | Pending (Gemini quota) | Adds `bandit` scan over CLI + core modules |
| 21 | PR-U | Add package entry points for installed CLI commands | `pyproject.toml`, `transcribe_audio.py`, `tests/test_transcribe_audio.py`, `README.md` | Done | Pending (Gemini quota) | Adds `whisper-batch` and `whisperbatch` console scripts |
| 22 | PR-V | Make setup install package in editable mode | `setup.sh` | Done | Pending (Gemini quota) | Ensures console scripts are available after setup |
| 23 | PR-W | Add CLI argument handling regression tests | `tests/test_transcribe_audio.py` | Done | Pending (Gemini quota) | Adds coverage for `--help` and invalid argument behavior |
| 24 | PR-X | Remove leftover GUI dead paths (model progress + elapsed-file timer state) | `transcribe_gui.py` | Done | Pending (Gemini quota) | Simplifies queue message flow and drops no-op time-estimate/progress pathways |
| 25 | PR-Y | Refactor duplicated GUI ffprobe checks into shared helper | `transcribe_gui.py` | Done | Pending (Gemini quota) | Reduces duplicate audio-duration probing logic in file validation and processing |
| 26 | PR-Z | Tighten GUI audio validation and row insertion consistency | `transcribe_gui.py` | Done | Pending (Gemini quota) | Adds filename context to invalid audio-duration errors, removes unreachable exception handling, and consolidates file-row insertion logic |
| 27 | PR-AA | Add PR CI lint check | `.github/workflows/ci.yml` | Done | Pending (Gemini quota) | Adds `ruff` check to PR CI for fast quality feedback before merge |
| 28 | PR-AC | Remove dead GUI progress UI path | `transcribe_gui.py` | Done | Pending (Gemini quota) | Removes hidden progress widgets and queue paths now that progress tracking is not surfaced |
| 29 | PR-AD | Add exponential retry backoff and CLI override control | `transcribe_audio.py`, `tests/test_transcribe_audio.py`, `README.md` | Done | Pending (Gemini quota) | Adds configurable retry backoff multiplier and coverage for retry delay growth under transient failures |
| 30 | PR-AE | Shift heavy security scans to nightly CI | `.github/workflows/ci.yml` | Done | Pending (Gemini quota) | Keeps PR checks fast and runs `bandit`/`pip-audit` only in scheduled/manual nightly checks |
| 31 | PR-AF | Align CLI model argument choices with shared model constants | `transcribe_audio.py`, `tests/test_transcribe_audio.py` | Done | Pending (Gemini quota) | Uses `SUPPORTED_MODELS` in CLI parser and validates all supported model values in tests |
| 32 | PR-AG | Add coverage for output write exceptions in batch processing | `tests/test_transcribe_audio.py` | Done | Pending (Gemini quota) | Ensures write-path exceptions are counted as failed transcriptions and surfaced as failed summaries |
| 33 | PR-AH | Expand nightly Python compatibility matrix to 3.13 | `.github/workflows/ci.yml` | Done | Pending (Gemini quota) | Aligns nightly matrix with documented supported Python versions |
| 34 | PR-AI | Add GUI progress metrics label and failed/throughput counters | `transcribe_gui.py` | Done | Pending (Gemini quota) | Adds real-time progress, failed count, and throughput updates in GUI status panel |
| 35 | PR-AJ | Add GUI overwrite toggle and skip-existing output behavior | `transcribe_gui.py` | Done | Pending (Gemini quota) | Adds per-run overwrite control with explicit default skip behavior for existing transcription outputs |
| 36 | PR-AK | Persist per-item GUI transcription metadata for reproducibility | `transcribe_gui.py` | Done | Pending (Gemini quota) | Writes `.metadata.json` sidecar files containing model/timestamps/overwrite options for each processed file |
| 37 | PR-AL | Add `.whisperbatch` config support and CLI output metadata sidecars | `transcribe_audio.py`, `tests/test_transcribe_audio.py`, `README.md` | Done | Pending (Gemini quota) | Adds automatic `.whisperbatch` config discovery with explicit CLI override and writes per-output metadata JSON files |
| 38 | PR-AM | Add resume-mode support using metadata for interrupted batch runs | `transcribe_audio.py`, `transcribe_gui.py`, `tests/test_transcribe_audio.py`, `README.md` | Done | Pending (Gemini quota) | Adds `--resume`/`resume` support to skip matching completed outputs in CLI and GUI when metadata indicates prior completion |
| 39 | PR-AO | Normalize metadata sidecar compatibility + overwrite-resume precedence across CLI + GUI | `transcribe_audio.py`, `transcribe_gui.py`, `tests/test_transcribe_audio.py`, `tests/test_core.py` | Done | Pending (Gemini quota) | Shared metadata helpers now keep legacy resume reads, always write new-style sidecars, and give overwrite precedence over resume skipping |
| 40 | PR-AP | Add GUI folder import support with recursive scan and dedupe | `transcribe_gui.py` | Done | Pending (Gemini quota) | Adds recursive folder selection for supported media, duplicate path filtering, and shared file-add validation for both file and folder inputs |
| 41 | PR-AQ | Share output format constants in `whisper_batch_core` | `whisper_batch_core/core.py`, `whisper_batch_core/__init__.py`, `transcribe_audio.py` | Done | Pending (Gemini quota) | Consolidates `SUPPORTED_OUTPUT_FORMATS` as a shared constant used by CLI validation and parser choices |
| 42 | PR-AR | Add `--max-workers` concurrency intent flag (single-worker default) | `transcribe_audio.py`, `tests/test_transcribe_audio.py` | Done | Pending (Gemini quota) | Adds concurrency configuration surface, validation, and merge strategy placeholder while preserving current single-thread behavior |
| 43 | PR-AS | Document `--max-workers` and add config validation tests | `README.md`, `tests/test_transcribe_audio.py` | Done | Pending (Gemini quota) | Adds docs and tests for config-driven `max_workers` and invalid max-workers config handling |
| 44 | PR-AT | Add post-process hook CLI/config support | `transcribe_audio.py`, `tests/test_transcribe_audio.py`, `README.md` | Done | Pending | Adds `--postprocess-cmd` and `.whisperbatch` `postprocess_command` support with hook execution and failure behavior |
| 45 | PR-AU | Add export bundle command | `transcribe_audio.py`, `tests/test_transcribe_audio.py`, `README.md` | Done | Pending | Adds `--export-bundle` and config `export_bundle` to package outputs and `run_summary.json` into a zip archive |
| 46 | PR-AV | Add optional language/task preset controls | `transcribe_audio.py`, `tests/test_transcribe_audio.py`, `README.md` | Done | Pending | Adds `--language`/`--task` and config equivalents, with metadata passthrough to transcription calls |
| 47 | PR-AW | Add language and speaker profile presets | `transcribe_audio.py`, `tests/test_transcribe_audio.py`, `README.md` | Done | Pending (Gemini quota) | Adds `--language-profile` and `--speaker-profile` with profile definitions in `.whisperbatch` |
| 48 | PR-AX | Fix profile model override to feed runtime model_name (with CLI precedence) | `transcribe_audio.py`, `tests/test_transcribe_audio.py`, `README.md` | Done | Pending (Gemini quota) | Ensures `model` in profiles is applied as execution model, and CLI `--model` still wins |
| 49 | PR-AY | Ensure resume honors metadata mismatch before overwrite-skipping | `transcribe_audio.py`, `tests/test_transcribe_audio.py` | Done | Pending (Gemini quota) | Reorders resume/overwrite checks so stale outputs are retried when resume is enabled and overwrite is disabled |
| 50 | PR-BB | Stabilize processing order for case-variant filenames | `transcribe_audio.py`, `transcribe_gui.py`, `tests/test_transcribe_audio.py` | Done | Pending (Gemini quota) | Sorts supported files deterministically with stable tie-breakers for case-sensitive filesystem variation |
| 51 | PR-BD | Stabilize export bundle file ordering with deterministic case-variant handling | `transcribe_audio.py`, `tests/test_transcribe_audio.py` | Done | Pending (Gemini quota) | Applies stable tie-breakers to ZIP export file ordering to avoid nondeterministic ordering in case-variant path collisions |
| 52 | PR-BE | Align GUI default model with CLI default model behavior | `transcribe_gui.py` | Done | Pending (Gemini quota) | Sets GUI initial model selection to `large-v3` to match CLI/default runtime baseline |
| 53 | PR-BF | Align GUI timestamps default with CLI behavior | `transcribe_gui.py` | Done | Pending (Gemini quota) | Sets GUI default timestamp toggle to enabled to match CLI include-timestamps default |
| 54 | PR-BG | Keep GUI default model selection tied to model constant order | `transcribe_gui.py` | Done | Pending (Gemini quota) | Uses `SUPPORTED_MODELS[-1]` for GUI default to preserve “largest/most-capable” default if model list changes |
| 55 | PR-BH | Add development dependency manifest for tooling | `requirements-dev.txt`, `README.md` | Done | Pending (Gemini quota) | Adds a dedicated dev requirements file and documents local install for lint/security/CI tooling |
| 56 | PR-BI | Standardize CI dependency installation via requirements-dev | `.github/workflows/ci.yml`, `requirements-dev.txt` | Done | Pending (Gemini quota) | Installs runtime + dev tooling from one manifest and removes inline dependency bootstrapping in CI steps |
| 57 | PR-BJ | Add pip-tools to dev manifest for reproducible tooling workflows | `requirements-dev.txt`, `README.md` | Done | Pending (Gemini quota) | Adds `pip-tools` to dev install path and documents lockfile workflow guidance |
| 58 | PR-BK | Add actionable model-load failure context for cache/download issues | `whisper_batch_core/core.py`, `tests/test_core.py` | Done | Pending (Gemini quota) | Wraps model initialization failures with actionable guidance and adds regression test coverage |
| 59 | PR-BL | Add model-load failure playbook in docs | `README.md` | Done | Pending (Gemini quota) | Adds concise incident-response guidance for model cache/download corruption scenarios |
| 60 | PR-BM | Add nightly formatting checks to CI | `.github/workflows/ci.yml` | Done | Pending (Gemini quota) | Adds `ruff format --check` in nightly pipeline to enforce style baseline without blocking PR flow |
| 61 | PR-BN | Add unit tests for CI secret scanner | `tests/test_ci_secret_scan.py` | Done | Pending (Gemini quota) | Covers ignore rules, pattern match behavior, and CLI return status for clean vs. secret-detected trees |
| 62 | PR-BO | Disambiguate output filenames for colliding stems | `transcribe_audio.py`, `tests/test_transcribe_audio.py` | Done | Pending (Gemini quota) | Ensures files like `speech.mp3` and `speech.wav` no longer share the same output filename |
| 63 | PR-BP | Add runtime Python version guard and policy docs | `transcribe_audio.py`, `README.md` | Done | Pending (Gemini quota) | Rejects unsupported Python at CLI startup and documents the explicit 3.9–3.13 support policy |
| 64 | PR-BQ | Add optional Python post-processing plugin hook | `transcribe_audio.py`, `tests/test_transcribe_audio.py`, `README.md` | Done | Pending (Gemini quota) | Adds `--postprocess-plugin` and `.whisperbatch` `postprocess_plugin` support with importable callable contract |
| 65 | PR-BR | Add plugin contract docs and sample post-process plugin module | `README.md`, `docs/postprocess-plugin-contract.md`, `sample_postprocess_plugins.py`, `tests/test_postprocess_plugins.py` | Done | Pending (Gemini quota) | Adds reference documentation, sample plugins, and tests for `--postprocess-plugin` |
| 66 | PR-BS | Add postmortem failure logging for failed files | `transcribe_audio.py`, `tests/test_transcribe_audio.py` | Done | Pending (Gemini quota) | Adds `failures` summary entries and a JSONL postmortem log for failed file runs |
| 67 | PR-BT | Prepare async/transcoding follow-up PR for Stage 4 task 7 | `docs/async-transcription-roadmap.md` | Done | Pending (Gemini quota) | Expands the async roadmap with concrete, acceptance-checked PR scoping for staged async worker execution |
| 68 | PR-BU | Design optional cloud destination integration | `docs/cloud-destination-integration-plan.md` | Done | Pending (Gemini quota) | Defines provider-agnostic upload abstraction and staged rollout for optional S3/GCS cloud destinations |
| 69 | PR-BV | Design shared output folder mode with provenance metadata | `docs/team-shared-output-folder-mode-plan.md` | Done | Pending (Gemini quota) | Adds a multi-stage design for centralized output roots and immutable provenance tracking with explicit overwrite/safety constraints |
| 70 | PR-BW | Design multilingual translation presets for one-click workflow | `docs/translation-presets-integration-plan.md` | Done | Pending (Gemini quota) | Adds staged model/profile resolution and manifest-safe translation preset behavior design |
| 71 | PR-BX | Design transcript diff and correction review mode | `docs/transcript-diff-review-plan.md` | Done | Pending (Gemini quota) | Proposes immutable transcript + mutable review patch storage and idempotent review replay |
| 72 | PR-BY | Design speaker-segmentation with optional speaker tagging | `docs/speaker-segmentation-plan.md` | Done | Pending (Gemini quota) | Adds staged plan for safe feature-gated speaker attribution and output schema extension |
| 73 | PR-BZ | Design remote model backend abstraction | `docs/remote-model-backend-abstraction-plan.md` | Done | Pending (Gemini quota) | Defines adapter contract and phased rollout for local + remote transcription backends without changing defaults |
| 74 | PR-CA | Add stable async task envelope and deterministic queue builder | `whisper_batch_core/async_batch.py`, `transcribe_audio.py`, `tests/test_async_batch.py` | Done | Pending (Gemini quota) | Adds `TranscriptionTask` + deterministic queue helper used by directory processing as groundwork for async execution |
| 75 | PR-CB | Add async execution policy guardrails and explicit rationale messaging | `whisper_batch_core/async_batch.py`, `transcribe_audio.py`, `tests/test_async_batch.py`, `whisper_batch_core/__init__.py` | Done | Pending (Gemini quota) | Adds async-readiness policy checks and consistent status messaging when multi-worker runs are intentionally not yet supported |
| 76 | PR-CC | Add per-segment annotation export (`.csv` / `.jsonl`) for downstream indexing | `transcribe_audio.py`, `tests/test_transcribe_audio.py`, `README.md` | Done | Pending (Gemini quota) | Adds `--annotation-export` support with CSV/JSONL output and summary metadata for segment-level index-friendly exports |
| 77 | PR-CD | Surface CLI model cache/download status and load timing | `transcribe_audio.py`, `tests/test_transcribe_audio.py`, `README.md` | Done | Pending (Gemini quota) | Adds explicit cache-hit/miss detection, cache path messaging, and model load timing for first-run transparency |
| 78 | PR-CE | Share model cache path helpers in `whisper_batch_core` for CLI and GUI | `whisper_batch_core/core.py`, `whisper_batch_core/__init__.py`, `transcribe_audio.py`, `transcribe_gui.py`, `tests/test_core.py`, `tests/test_transcribe_audio.py` | Done | Pending (Gemini quota) | Centralizes model cache location resolution and cache-presence checks for both CLI and GUI and updates tests accordingly |
| 79 | PR-CF | Add GUI model cache/download status + load timing | `transcribe_gui.py` | Done | Pending | Adds shared cache-path detection messages and per-run timing feedback for GUI model loading |
| 80 | PR-CG | Align cache-clear docs with env-aware cache root resolution | `README.md`, `tests/test_core.py` | Done | Pending | Expands troubleshooting docs and adds Windows/fallback cache-root tests in core helper coverage |
| 81 | PR-CH | Normalize model-cache env roots in `whisper_batch_core` helpers | `whisper_batch_core/core.py`, `tests/test_core.py` | Done | Pending | Expands cache-root helper to expand env/user paths for HF cache variables and adds regression test coverage |
| 82 | PR-CJ | Centralize CLI model default constant | `transcribe_audio.py`, `tests/test_transcribe_audio.py` | Done | Pending (Gemini quota) | Introduces `DEFAULT_MODEL_NAME` for CLI model defaults, runtime signatures, and regression tests for source-of-truth behavior |
| 83 | PR-CK | Share default model constant in core and GUI | `whisper_batch_core/core.py`, `whisper_batch_core/__init__.py`, `transcribe_audio.py`, `transcribe_gui.py` | Done | Pending (Gemini quota) | Exports `DEFAULT_MODEL_NAME` from core and removes hardcoded fallback model literals from CLI/GUI defaults |
| 84 | PR-CL | Centralize `SUPPORTED_TASKS` in `whisper_batch_core` | `whisper_batch_core/core.py`, `whisper_batch_core/__init__.py`, `transcribe_audio.py`, `tests/test_core.py`, `tests/test_transcribe_audio.py` | Done | Pending (Gemini quota) | Shares supported task set with CLI validation/help, and keeps task options anchored to one source of truth |
| 85 | PR-CM | Derive CLI help text from shared constants | `transcribe_audio.py`, `tests/test_transcribe_audio.py` | Done | Pending (Gemini quota) | Uses shared output/task constants for help messages to avoid drift as constants evolve |
| 86 | PR-CN | Centralize default task constant usage in core and CLI | `whisper_batch_core/core.py`, `whisper_batch_core/__init__.py`, `transcribe_audio.py`, `tests/test_core.py`, `tests/test_transcribe_audio.py` | Done | Pending (Gemini quota) | Reuses `DEFAULT_TASK_NAME` in core/CLI defaults and test assertions to prevent drift if the default task changes |
| 87 | PR-CO | Use shared default task constant in GUI transcription path | `transcribe_gui.py` | Done | Pending (Gemini quota) | Reuses `DEFAULT_TASK_NAME` for GUI transcribe_segments calls to keep task behavior aligned with CLI/default constants |
| 88 | PR-CY | Centralize default output format constant and defaults usage | `whisper_batch_core/core.py`, `whisper_batch_core/__init__.py`, `whisper_batch_core/async_batch.py`, `transcribe_audio.py`, `transcribe_gui.py`, `tests/test_async_batch.py`, `tests/test_core.py` | Done | Pending (Gemini quota) | Introduces `DEFAULT_OUTPUT_FORMAT` and applies it consistently across CLI defaults, async task defaults, runtime signatures, and GUI metadata/output behavior |
| 89 | PR-CZ | Fix output-format timestamp handling path in transcription loop | `transcribe_audio.py`, `whisper_batch_core/core.py`, `tests/test_transcribe_audio.py`, `tests/test_core.py` | Done | Pending (Gemini quota) | Ensures `include_timestamps` is correctly propagated for each output format, aligns resume behavior for subtitle outputs, and centralizes formatter handling helpers |
| 90 | PR-DA | Align resume overwrite precedence with stale metadata behavior | `transcribe_audio.py`, `transcribe_gui.py`, `tests/test_transcribe_audio.py` | Done | Pending (Gemini quota) | Allows stale/invalid metadata to trigger reprocessing under resume mode, even when overwrite is disabled, while preserving skip semantics for exact matches |
| 91 | PR-DD | Add GUI output format selection and rendering parity | `transcribe_gui.py` | Done | Pending (Gemini quota) | Adds GUI output-format chooser, output renderer dispatch, and output/metadata handling aligned with format-specific timestamp/resume behavior |
| 92 | PR-DE | Add unit tests for GUI output-format renderer helpers | `tests/test_transcribe_gui_output_formats.py` | Done | Pending (Gemini quota) | Adds focused tests for renderer dispatch, timestamp formatting, subtitle rendering, and resume-safe timestamp defaults |
| 93 | PR-DG | Add CLI output-format flags and renderers | `transcribe_audio.py`, `tests/test_transcribe_audio.py` | Done | Pending (Gemini quota) | Adds `--output-format` with TXT/JSON/SRT/VTT rendering and format-specific output extension handling |
| 94 | PR-DH | Stabilize CLI input ordering in `process_directory` | `transcribe_audio.py`, `tests/test_transcribe_audio.py` | Done | Pending (Gemini quota) | Sorts supported media files case-insensitive with deterministic tie-breakers before batch processing |
| 95 | PR-DI | Add CLI directory summary output and validation | `transcribe_audio.py`, `tests/test_transcribe_audio.py` | Done | Pending (Gemini quota) | Adds deterministic file validation summary counts, non-directory guard, and graceful failure counting for batch runs |
| 96 | PR-DJ | Add `--overwrite` guardrail for existing transcript outputs | `transcribe_audio.py`, `tests/test_transcribe_audio.py` | Done | Pending (Gemini quota) | Adds `--overwrite` CLI flag, skip behavior for existing outputs, and overwrite-enabled update coverage |

### PR-E execution notes

- Added GitHub Actions workflow with two jobs:
  - `pr-checks`: lightweight checks for PR/push (`3.9`/`3.12`) including tests + syntax validation.
  - `nightly-checks`: scheduled weekly run (`Mon 03:00 UTC`) with broader matrix (`3.9`-`3.13`) and CLI smoke coverage.

## Stage flow

Detailed stage definitions are tracked in [do-work-queue.md](/Users/sba/Documents/Developer/NotActive/WhisperBatch/do-work-queue.md).
That file is now the canonical roadmap source and should be treated as the source of truth for execution order.

## Repeat cadence (as requested)

For stages after merge:

- Re-run assessment pass (bug/edge cases, security, CI adequacy, dead code, simplification), then continue.
- Document every notable finding and add a follow-up PR task.
