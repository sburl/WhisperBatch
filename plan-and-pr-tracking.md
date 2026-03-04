# PR Roadmap and Merge Order

**Created:** 2026-03-04-06-40
**Last Updated:** 2026-03-03-21-51

## Current open PR inventory

| PR | Branch | Title | Priority | Merge dependency notes |
|---|---|---|---|---|
| 33 | `pr-ez-expanduser-dir-path` | feat(cli): expand user home in directory path | High | No hard dependency; merge when review is complete. |
| 32 | `pr-dw-ci-setuptools` | ci: install setuptools/wheel before dependency install | High | Can be merged early; low risk foundation for CI robustness. |
| 31 | `pr-dv-cli-model-validation` | feat(cli): validate model names in directory processing | Medium | Should be paired with core-constant cleanup (`29`) and any future model-constant changes. |
| 30 | `pr-dr-cli-timestamp-constant` | refactor(cli): reuse shared timestamp-only output constants | Medium | Depends on shared-constant availability in core (`29`) and is safe after that. |
| 29 | `pr-dq-cli-core-constants` | feat(core): restore shared constants and metadata helpers | High | Core dependency for CLI consistency PRs (`30`, `31`, `28`, `27`). |
| 28 | `pr-dk-cli-summary-json` | feat(cli): add optional JSON summary output with timing | Medium | No hard dependency if core constants merge (`29`) is present. |
| 27 | `pr-dj-cli-overwrite` | feat(cli): add overwrite control for existing outputs | Medium | No hard dependency; ensure file output behavior with validation PRs. |
| 26 | `pr-26-setup-python-version-guard` | chore(setup): guard unsupported python versions before venv | High | Foundation for setup resilience. |
| 25 | `pr-25-ignore-transcriptions` | chore(gitignore): ignore generated transcriptions artifacts | Medium | Safe independent cleanup. |
| 24 | `pr-24-readme-quickstart-path` | docs: correct README quickstart clone path | Low | Documentation only; can merge anytime. |
| 23 | `pr-23-setup-torch-pin` | chore(setup): align torch pin with Apple Silicon guidance | High | Foundation for setup and install reliability on macOS arm64. |
| 22 | `pr-22-torch-warning-2-4-1` | fix(gui): update arm64 torch reinstall guidance | High | Keep aligned with torch setup updates (`23`). |
| 21 | `pr-21-readme-sync` | docs: sync README with current project status | Low | Safe after larger behavior/setup changes land. |
| 20 | `pr-20-ci-split` | ci: split PR and nightly checks | High | Useful before scaling security/perf/e2e test additions. |
| 19 | `pr-19-cli-workflow-stacked` | feat(cli): expand process workflow, outputs, and resilience | Medium | May conflict with `27/28/30/31`; review sequencing with smaller CLI patches. |
| 18 | `pr-18-core-metadata` | feat(core): add cache metadata helpers and shared constants | Medium | Overlaps with `29`; reconcile before both merge. |
| 17 | `pr-17-build-runtime` | chore(build): update runtime deps and setup flow | High | Core dependency for smooth development and CI stability. |
| 16 | `pr-16-doc-design-plans` | docs: add future architecture feature blueprints | Low | Documentation reference for long-term stage planning. |
| 15 | `test-local` | chore(docs): add planning and PR tracking artifacts | Medium | Historical baseline for this plan; depends on project-wide naming conventions. |
| 14 | `pr-bi-ci-dev-dependency-install` | ci: install dependencies from requirements-dev | Medium | Supports richer quality gates and PR checks. |
| 13 | `pr-bj-dev-tooling-manifest` | chore(dev): add pinned dev tooling manifest | Medium | Helps reproducible local + CI tooling. |
| 12 | `pr-br-postprocess-plugin-samples` | feat(plugin): add sample postprocess plugins and tests | Medium | Independent feature + docs; can follow core testing/CI setup. |
| 11 | `pr-bn-ci-secret-scan` | test(ci): add secret scanner unit tests | High | Stronger security posture for future automation. |
| 10 | `pr-ca-async-envelope` | feat(core): add async task envelope contract and tests | Medium | Core utility to support staged async improvements. |
| 9 | `pr-de-gui-output-format-tests` | test(gui): add output-format rendering helper tests | Medium | Nice companion to GUI output feature work. |
| 8 | `pr-dd-gui-output-format` | feat(ui): add GUI output-format rendering parity | Medium | Should align with output format tests (`9`) and `33` for CLI path handling. |
| 6 | `dependabot/pip/numpy-2.0.2` | Bump numpy from 1.24.3 to 2.0.2 | Medium | Security and maintenance dependency updates; review with lockfile constraints. |
| 5 | `dependabot/pip/requests-2.32.5` | Bump requests from 2.31.0 to 2.32.5 | Medium | Dependency maintenance. |
| 4 | `dependabot/pip/tqdm-4.67.3` | Bump tqdm from 4.66.1 to 4.67.3 | Low | Dependency maintenance. |
| 3 | `dependabot/pip/librosa-0.11.0` | Bump librosa from 0.10.1 to 0.11.0 | Low | Dependency maintenance. |
| 2 | `dependabot/pip/faster-whisper-1.2.1` | Bump faster-whisper from 1.0.3 to 1.2.1 | Medium | Core dependency; should be sequenced with core/API compatibility checks. |

## Recommended merge order (next 10)

1. #33 — expanduser CLI path handling
2. #26 — setup Python version guard
3. #17 — build/runtime setup hardening
4. #23 — torch pin updates
5. #22 — torch remediation guidance
6. #32 — CI setuptools/wheel guard
7. #20 — CI split (PR-only + nightly)
8. #11 — secret-scan tests
9. #29 — shared core constants
10. #31 — CLI model validation
11. #30 — shared timestamp format constants
12. #27 — CLI overwrite control
13. #28 — JSON summary and timing

## Merge order after initial core stabilization

1. #18 or #29 conflict reconciliation (choose one base and rebalance before merge)
2. #19 — CLI workflow expansion
3. #14 — dev dependency install in CI
4. #13 — pinned local tooling
5. #12 — postprocess sample plugins
6. #9 and #8 — GUI format tests and implementation
7. #21 and #24 — documentation sync follow-up
8. #16 and #15 — planning and future architecture context

## Big-feature planning (new work queue)

This queue is split into stages with a minimum of 5 and a maximum of 15 tasks each.

### Stage 1: Stability and foundations
1. Add deterministic CLI test coverage for `process_directory` success and failure paths.
2. Add GUI and CLI unit tests around supported media extension handling.
3. Add tests that validate `transcribe_file` with timestamp on/off and malformed inputs.
4. Add minimal CI for PR-only tests (lint + unit subset).
5. Add nightly CI job for longer regression and multi-file scenarios.
6. Add a dedicated `requirements-dev.txt` with pinned test/dev tools.
7. Implement a small test fixture generator for fake Whisper models.
8. Standardize logging output across CLI and GUI worker code paths.
9. Add consistent `Path` normalization (tilde expansion + absolute path canonicalization).
10. Define shared constants for model names and valid output formats in core.

### Stage 2: Quality and bug-hardening
1. Add strict validation for directory arguments and output directory permissions.
2. Normalize and sort file discovery in CLI/GUI for deterministic execution.
3. Improve error aggregation so failed files still produce clear run summaries.
4. Ensure timestamp output is identical across plain/text/GUI rendering.
5. Add guardrails for missing FFmpeg dependencies with user-friendly errors.
6. Add per-file timing and aggregate JSON summary output.
7. Add overwrite policy options (`skip`, `replace`, `timestamped`) for all outputs.
8. Add cancellation handling for CLI batch runs with resumable state.
9. Add regression tests for unsupported compute/device combinations.
10. Add defensive path handling for non-ASCII filenames and symlinks.

### Stage 3: Performance and resilience
1. Add async worker queue for CLI to match GUI parallel behavior.
2. Add configurable concurrency limits for batch transcription.
3. Cache loaded model instances across directory runs where safe.
4. Add per-output artifact cleanup for partial/interrupted runs.
5. Add optional transcription resume support from last completed file.
6. Add lightweight progress heartbeat and ETA smoothing.
7. Add optional output compression for very large transcription artifacts.
8. Add model warmup step with progress and fallback messaging.
9. Add integration tests that mock long-running jobs to validate pause/resume logic.
10. Add stress-profile fixture and benchmark script for model/runtime matrix.

### Stage 4: Security and operations
1. Add input-path allowlist/denylist for batch jobs to reduce accidental exfiltration risk.
2. Add secret scanners in pre-commit and pre-push hooks for changed files.
3. Add checksum verification for dependency installation manifests.
4. Add audit logging for model download and local cache writes.
5. Add least-privilege execution mode for temporary transcriptions.
6. Add explicit file permission checks before write operations.
7. Add CI secret-detection gate on all pull requests.
8. Add package-safety scan on schedule and PR (dependency CVE check).
9. Introduce pinned runtime version floor policy docs and enforcement.
10. Add incident-response checklist for corrupted model cache and unsafe filesystem states.

### Stage 5: Product vision
1. Add post-process plugin discovery and built-in plugin gallery.
2. Add optional translation and diarization output modes.
3. Add speaker-segment tagging and export-friendly speaker labels.
4. Add transcript review mode with inline corrections and re-export.
5. Add alignment with SRT/VTT timestamp export and styling options.
6. Add API endpoint mode (small local HTTP service).
7. Add batch scheduling by filename pattern and date range.
8. Add configurable profile presets (speed, accuracy, memory).
9. Add cloud-backed queue mode for long-running transcriptions.
10. Add first-class support for multi-language batch metadata and QA reporting.
