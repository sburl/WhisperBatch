"""Tests for transcribe_audio.py — CLI processing logic."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from whisper_batch_core import TranscriptSegment, TranscriptionResult

from transcribe_audio import (
    _build_output_file_path,
    process_directory,
    transcribe_audio,
)


class TestBuildOutputFilePath(unittest.TestCase):
    def test_default_occurrence(self):
        path = _build_output_file_path(Path("/out"), "clip", "txt")
        self.assertEqual(path, Path("/out/clip_transcription.txt"))

    def test_occurrence_1_no_suffix(self):
        path = _build_output_file_path(Path("/out"), "clip", "txt", 1)
        self.assertEqual(path, Path("/out/clip_transcription.txt"))

    def test_occurrence_2_adds_suffix(self):
        path = _build_output_file_path(Path("/out"), "clip", "txt", 2)
        self.assertEqual(path, Path("/out/clip_transcription_2.txt"))

    def test_json_format(self):
        path = _build_output_file_path(Path("/out"), "speech", "json")
        self.assertEqual(path, Path("/out/speech_transcription.json"))

    def test_srt_format(self):
        path = _build_output_file_path(Path("/out"), "vid", "srt", 3)
        self.assertEqual(path, Path("/out/vid_transcription_3.srt"))


class TestProcessDirectory(unittest.TestCase):
    def test_nonexistent_directory_raises(self):
        with self.assertRaises(ValueError):
            process_directory("/nonexistent/path/xyz")

    def test_file_not_directory_raises(self):
        with tempfile.NamedTemporaryFile() as f:
            with self.assertRaises(ValueError):
                process_directory(f.name)

    def test_invalid_model_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(ValueError) as ctx:
                process_directory(tmpdir, model_name="invalid-model")
            self.assertIn("Unsupported model", str(ctx.exception))

    def test_empty_directory_returns_zero_summary(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = process_directory(tmpdir)
            self.assertEqual(result["total"], 0)
            self.assertEqual(result["success"], 0)

    def test_expanduser_works(self):
        # Just verify it doesn't crash on ~ path (will raise "not found" since
        # ~/nonexistent_whisperbatch_test_dir doesn't exist)
        with self.assertRaises(ValueError):
            process_directory("~/nonexistent_whisperbatch_test_dir")

    @patch("transcribe_audio.load_model")
    @patch("transcribe_audio.transcribe_file")
    def test_processes_audio_files(self, mock_transcribe, mock_load):
        mock_model = MagicMock()
        mock_load.return_value = mock_model

        seg = TranscriptSegment(start=0.0, end=1.0, text="hello")
        mock_transcribe.return_value = TranscriptionResult(
            text="hello", segments=[seg], info=MagicMock(),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "test.mp3").write_text("fake")
            (Path(tmpdir) / "test.txt").write_text("not audio")

            result = process_directory(tmpdir, model_name="base")

            self.assertEqual(result["success"], 1)
            self.assertEqual(result["total"], 1)
            output_file = Path(tmpdir) / "transcriptions" / "test_transcription.txt"
            self.assertTrue(output_file.exists())

    @patch("transcribe_audio.load_model")
    @patch("transcribe_audio.transcribe_file")
    def test_same_stem_disambiguation(self, mock_transcribe, mock_load):
        mock_model = MagicMock()
        mock_load.return_value = mock_model

        seg = TranscriptSegment(start=0.0, end=1.0, text="content")
        mock_transcribe.return_value = TranscriptionResult(
            text="content", segments=[seg], info=MagicMock(),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "clip.mp3").write_text("fake")
            (Path(tmpdir) / "clip.wav").write_text("fake")

            result = process_directory(tmpdir, model_name="base")

            self.assertEqual(result["success"], 2)
            out_dir = Path(tmpdir) / "transcriptions"
            files = sorted(f.name for f in out_dir.iterdir())
            self.assertEqual(len(files), 2)
            # One should be clip_transcription.txt, other clip_transcription_2.txt
            self.assertIn("clip_transcription.txt", files)
            self.assertIn("clip_transcription_2.txt", files)

    @patch("transcribe_audio.load_model")
    @patch("transcribe_audio.transcribe_file")
    def test_deterministic_file_order(self, mock_transcribe, mock_load):
        mock_load.return_value = MagicMock()
        processed_files = []

        def capture_transcribe(path, **kwargs):
            processed_files.append(Path(path).name)
            seg = TranscriptSegment(start=0.0, end=1.0, text="x")
            return TranscriptionResult(text="x", segments=[seg], info=MagicMock())

        mock_transcribe.side_effect = capture_transcribe

        with tempfile.TemporaryDirectory() as tmpdir:
            for name in ["C.mp3", "a.mp3", "B.mp3"]:
                (Path(tmpdir) / name).write_text("fake")

            process_directory(tmpdir, model_name="base")

            # Should be sorted case-insensitively: a, B, C
            self.assertEqual(processed_files, ["a.mp3", "B.mp3", "C.mp3"])

    @patch("transcribe_audio.load_model")
    @patch("transcribe_audio.transcribe_file")
    def test_failed_file_counted(self, mock_transcribe, mock_load):
        mock_load.return_value = MagicMock()
        mock_transcribe.side_effect = RuntimeError("model error")

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "bad.mp3").write_text("fake")

            result = process_directory(tmpdir, model_name="base")

            self.assertEqual(result["failed"], 1)
            self.assertEqual(result["success"], 0)


if __name__ == "__main__":
    unittest.main()
