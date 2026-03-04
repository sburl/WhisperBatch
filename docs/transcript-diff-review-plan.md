# Transcript diff and correction review mode

Purpose: prepare Big Vision task 5, a user-facing workflow for post-transcription review.

## Problem statement

- Transcripts are currently produced and consumed as final artifacts.
- Minor transcription defects require manual full-file rewrites with no structured correction history.

## Target model

Introduce an immutable original transcript + mutable review draft pair:

1. Store canonical output as produced by Whisper.
2. Store reviewer edits in `transcriptions/<stem>.review.jsonl` with:
   - `timestamp`
   - `segment_index`
   - `original_text`
   - `revised_text`
   - `reviewer_comment`
3. Reconstruct final review transcript from canonical+review records when requested.

## Delivery stages

### PR-BX-1: diff model and serialization
- Add `TranscriptSegmentReview` schema and serialization helper.
- Add deterministic ordering checks for segments.

### PR-BX-2: CLI + API entry points
- Add `--review-mode` CLI flag.
- Add optional `--review-output` target (default: local `*.review.jsonl`).
- Add `transcribe` API path to render review transcript with applied patches.

### PR-BX-3: GUI review list
- Add a minimal diff table with segment-level accept/reject actions.
- Persist review diffs to JSONL with minimal metadata.

## Acceptance criteria

- Original transcript outputs are never overwritten.
- Review diffs apply deterministically and are idempotent.
- If review data is missing/corrupt, system falls back to canonical transcript and reports checksum mismatch in summary metadata.
