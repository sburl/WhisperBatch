from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class TranscriptSegment:
    start: float
    end: float
    text: str
    speaker: Optional[str] = None

    @classmethod
    def from_whisper(cls, segment: object) -> "TranscriptSegment":
        return cls(
            start=float(segment.start),
            end=float(segment.end),
            text=str(segment.text),
        )

    def with_speaker(self, speaker: str) -> "TranscriptSegment":
        """Return a new segment with the given speaker label."""
        return TranscriptSegment(
            start=self.start, end=self.end, text=self.text, speaker=speaker,
        )


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    segments: List[TranscriptSegment]
    info: object
