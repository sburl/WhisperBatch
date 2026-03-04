import pytest

import transcribe_audio


class _FakeTranscriptionResult:
    def __init__(self, text):
        self.text = text


def test_collect_supported_files_sorted_with_case_tiebreaker(tmp_path):
    files = ["notes.txt", "a.mp3", "B.wav", "a.WAV", "b.mp3"]
    for name in files:
        (tmp_path / name).write_text("content", encoding="utf-8")

    sorted_files, skipped = transcribe_audio._collect_supported_files(tmp_path)
    sorted_names = [path.name for path in sorted_files]

    assert sorted_names == ["a.mp3", "a.WAV", "b.mp3", "B.wav"]
    assert skipped == 1


def test_process_directory_raises_when_path_is_not_directory(tmp_path):
    file_path = tmp_path / "leaf.wav"
    file_path.write_text("audio", encoding="utf-8")

    with pytest.raises(ValueError, match="Not a directory"):
        transcribe_audio.process_directory(str(file_path))


def test_process_directory_reports_success_and_failure_without_halting(tmp_path, monkeypatch):
    (tmp_path / "good.wav").write_text("good", encoding="utf-8")
    (tmp_path / "bad.mp3").write_text("bad", encoding="utf-8")

    def fake_load_model(*_, **__):
        return object()

    def fake_transcribe_file(audio_path, *, model_name="large-v3", include_timestamps=True, device="auto", model=None, task="transcribe"):
        if audio_path.endswith("bad.mp3"):
            raise RuntimeError("boom")
        return _FakeTranscriptionResult("ok")

    monkeypatch.setattr(transcribe_audio, "load_model", fake_load_model)
    monkeypatch.setattr(transcribe_audio, "transcribe_file", fake_transcribe_file)

    summary = transcribe_audio.process_directory(str(tmp_path))

    assert summary == {"total": 2, "success": 1, "failed": 1, "skipped": 0}
    assert (tmp_path / "transcriptions" / "good_transcription.txt").exists()
    assert not (tmp_path / "transcriptions" / "bad_transcription.txt").exists()
