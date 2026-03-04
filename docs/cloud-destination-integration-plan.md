# Cloud destination upload integration plan

**Created:** 2026-03-03-17-23
**Last Updated:** 2026-03-03-17-23

Purpose: define an incremental path for Big Vision task 2 (optional cloud upload integration)
that keeps current behavior stable while introducing a testable abstraction.

## Design goal

Add optional, opt-in upload of transcription artifacts to an external destination
without changing default local behavior.

- Maintain deterministic local filesystem outputs exactly as today.
- Enable upload as a post-run artifact fanout step, not as a replacement for local files.
- Keep credentials and signing material entirely outside source control.

## Minimal contract

Introduce an internal destination abstraction with a narrow interface:

1. `resolve_destination_config(config: dict) -> UploadTarget`
2. `validate_destination_config(target: UploadTarget, *, dry_run: bool) -> ValidationResult`
3. `upload_artifacts(target: UploadTarget, files: list[Path], metadata: dict) -> list[UploadResult]`

The contract should be backend-agnostic and should include:
- provider enum (`local`, `s3`, `gcs`, `azure`).
- path prefix / bucket semantics.
- manifest output path for upload receipts.
- retry count and timeout values.

## Delivery milestones

### PR-BU1 — abstraction + local destination hardening
- Add `UploadTarget` dataclass and local destination implementation.
- Add a no-op/no-op with full interface and validation tests.

### PR-BU2 — upload manifest + CLI/config surface
- Add `.whisperbatch` + CLI keys:
  - `upload.destination`
  - `upload.provider`
  - `upload.credentials_ref` (indirect reference only)
  - `upload.prefix`
- Produce `upload_manifest.json` in `transcriptions/` for each run.

### PR-BU3 — S3 implementation (first external backend)
- Add strict, minimal dependency policy (`boto3` optional path only when destination enabled).
- Implement deterministic object key derivation from local relative paths.
- Add failure mapping into existing `failures` + `postmortem.jsonl`.

### PR-BU4 — test and security hardening
- Add integration tests around:
  - missing credentials short-circuit
  - retry/backoff behavior
  - upload manifest writes and failure capture
- Add docs for secure credential handling and blast-radius guidance.

## Security considerations

- Do not accept raw credentials in `.whisperbatch` payload.
- Accept credential references only (env var names / secret-manager refs).
- Write upload receipts with redacted URLs/hostnames only.
- Never include full object ACL or policy payload in exception messages.

## Risk controls

- Keep S3/GCS implementation behind explicit opt-in flag/setting.
- Require `--enable-upload` style explicit boolean in first shipped version.
- Fail closed on unknown provider values with a schema-validated error.
- Keep network-related exceptions as per-file failure entries and continue processing.

## Acceptance criteria

- Existing local runs are unchanged when no upload destination is configured.
- Upload mode preserves ordering of generated local artifacts.
- Any upload failure is isolated per destination and recorded in run summary.
- No credentials are ever serialized into logs, summaries, or manifests.
