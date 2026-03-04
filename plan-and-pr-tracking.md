# PR Roadmap and Merge Order

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
