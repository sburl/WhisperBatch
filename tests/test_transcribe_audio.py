import json

import pytest

from whisper_batch_core import TranscriptSegment
import transcribe_audio


class _FakeTranscriptionResult:
    def __init__(self, text, segments):
        self.text = text
        self.segments = segments
        self.info = {}


def test_output_formats_map_to_expected_file_types_and_payload(tmp_path, monkeypatch):
    (tmp_path / "clip.wav").write_text("clip", encoding="utf-8")
    segment = TranscriptSegment(start=0.1, end=1.2, text="Hello world.")

    def fake_load_model(*_, **__):
        return object()

    def fake_transcribe_file(audio_path, **kwargs):
        return _FakeTranscriptionResult("Hello world.", [segment])

    monkeypatch.setattr(transcribe_audio, "load_model", fake_load_model)
    monkeypatch.setattr(transcribe_audio, "transcribe_file", fake_transcribe_file)

    for output_format, suffix, should_be_json in [
        ("txt", ".txt", False),
        ("json", ".json", True),
        ("srt", ".srt", False),
        ("vtt", ".vtt", False),
    ]:
        transcribe_audio.process_directory(str(tmp_path), output_format=output_format)
        output_file = tmp_path / "transcriptions" / f"clip_transcription.{suffix}"
        assert output_file.exists()
        payload = output_file.read_text(encoding="utf-8")
        if should_be_json:
            parsed = json.loads(payload)
            assert parsed["text"] == "Hello world."
            assert parsed["segments"][0]["text"] == "Hello world."
        elif output_format == "txt":
            assert "[00:00:00 --> 00:00:01] Hello world." in payload
        elif output_format == "srt":
            assert payload.startswith("1\n00:00:000,100 --> 00:00:01,200")
        elif output_format == "vtt":
            assert payload.startswith("WEBVTT\n\n00:00:000.100 --> 00:00:01.200")
