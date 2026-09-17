from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TranscriptSegment:
    start: float
    end: float
    text: str

    @classmethod
    def from_whisper(cls, segment: object) -> TranscriptSegment:
        return cls(
            start=float(segment.start),
            end=float(segment.end),
            text=str(segment.text),
        )


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    segments: list[TranscriptSegment]
    info: object
