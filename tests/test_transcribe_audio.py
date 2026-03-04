import json

import pytest

from whisper_batch_core import TranscriptSegment
import transcribe_audio


class _FakeTranscriptionResult:
    def __init__(self, text, segments):
        self.text = text
        self.segments = segments
        self.info = {}


def test_collect_supported_files_sorted_case_insensitive(tmp_path):
    for name in ["b.wav", "A.MP3", "a.wav", "B.MP3", "notes.txt"]:
        (tmp_path / name).write_text("x", encoding="utf-8")

    supported = transcribe_audio._collect_supported_files(tmp_path)
    assert [path.name for path in supported] == ["A.MP3", "a.wav", "B.MP3", "b.wav"]


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


def test_process_directory_reports_summary_with_skips(tmp_path, monkeypatch):
    (tmp_path / "good.wav").write_text("x", encoding="utf-8")
    (tmp_path / "bad.mp3").write_text("x", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("ignore", encoding="utf-8")

    def fake_load_model(*_, **__):
        return object()

    def fake_transcribe_file(audio_path, **kwargs):
        if audio_path.endswith("bad.mp3"):
            raise RuntimeError("boom")
        return _FakeTranscriptionResult("ok", [TranscriptSegment(start=0, end=0, text="ok")])

    monkeypatch.setattr(transcribe_audio, "load_model", fake_load_model)
    monkeypatch.setattr(transcribe_audio, "transcribe_file", fake_transcribe_file)

    summary = transcribe_audio.process_directory(str(tmp_path), output_format="txt")
    assert summary["total"] == 2
    assert summary["success"] == 1
    assert summary["failed"] == 1
    assert summary["skipped"] == 1


def test_process_directory_skips_existing_output_without_overwrite_flag(tmp_path, monkeypatch):
    (tmp_path / "clip.wav").write_text("x", encoding="utf-8")
    output_dir = tmp_path / "transcriptions"
    output_dir.mkdir()
    existing_output = output_dir / "clip_transcription.txt"
    existing_output.write_text("old transcription", encoding="utf-8")

    calls = []

    def fake_load_model(*_, **__):
        return object()

    def fake_transcribe_file(audio_path, **kwargs):
        calls.append(audio_path)
        return _FakeTranscriptionResult("new", [TranscriptSegment(start=0, end=0, text="new")])

    monkeypatch.setattr(transcribe_audio, "load_model", fake_load_model)
    monkeypatch.setattr(transcribe_audio, "transcribe_file", fake_transcribe_file)

    summary = transcribe_audio.process_directory(str(tmp_path), output_format="txt", overwrite=False)

    assert summary["total"] == 1
    assert summary["success"] == 0
    assert summary["failed"] == 0
    assert summary["skipped"] == 1
    assert calls == []
    assert existing_output.read_text(encoding="utf-8") == "old transcription"


def test_process_directory_overwrites_existing_output_with_overwrite_flag(tmp_path, monkeypatch):
    (tmp_path / "clip.wav").write_text("x", encoding="utf-8")
    output_dir = tmp_path / "transcriptions"
    output_dir.mkdir()
    existing_output = output_dir / "clip_transcription.txt"
    existing_output.write_text("old transcription", encoding="utf-8")

    monkeypatch.setattr(transcribe_audio, "load_model", lambda *_args, **_kwargs: object())

    def fake_transcribe_file(audio_path, **kwargs):
        return _FakeTranscriptionResult("new", [TranscriptSegment(start=0, end=0, text="new")])

    monkeypatch.setattr(transcribe_audio, "transcribe_file", fake_transcribe_file)

    summary = transcribe_audio.process_directory(
        str(tmp_path),
        output_format="txt",
        overwrite=True,
    )

    assert summary["total"] == 1
    assert summary["success"] == 1
    assert summary["failed"] == 0
    assert summary["skipped"] == 0
    assert "new" in existing_output.read_text(encoding="utf-8")


def test_process_directory_adds_elapsed_and_throughput_to_summary(tmp_path, monkeypatch):
    (tmp_path / "clip.wav").write_text("x", encoding="utf-8")
    monkeypatch.setattr(transcribe_audio, "load_model", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(
        transcribe_audio,
        "transcribe_file",
        lambda audio_path, **kwargs: _FakeTranscriptionResult("ok", [TranscriptSegment(start=0, end=0, text="ok")]),
    )

    fake_perf_counter = [0.0]

    def fake_perf_counter_seq():
        value = fake_perf_counter[0]
        fake_perf_counter[0] += 1.0
        return value

    monkeypatch.setattr(transcribe_audio.time, "perf_counter", fake_perf_counter_seq)

    summary = transcribe_audio.process_directory(str(tmp_path), summary_json=False)

    assert "elapsed_seconds" in summary
    assert summary["elapsed_seconds"] == 1.0
    assert "throughput_files_per_second" in summary


def test_process_directory_prints_summary_json_when_requested(tmp_path, monkeypatch, capsys):
    (tmp_path / "clip.wav").write_text("x", encoding="utf-8")
    monkeypatch.setattr(transcribe_audio, "load_model", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(
        transcribe_audio,
        "transcribe_file",
        lambda audio_path, **kwargs: _FakeTranscriptionResult("ok", [TranscriptSegment(start=0, end=0, text="ok")]),
    )
    monkeypatch.setattr(transcribe_audio.time, "perf_counter", lambda: 0.0)

    transcribe_audio.process_directory(str(tmp_path), summary_json=True)
    output = capsys.readouterr().out.strip().splitlines()[-1]
    summary = json.loads(output)

    assert summary["total"] == 1
    assert summary["success"] == 1
    assert summary["failed"] == 0
    assert summary["skipped"] == 0
    assert "elapsed_seconds" in summary
