"""Tests for whisper_batch_core.core — constants, helpers, and renderers."""

import math
import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from whisper_batch_core import (
    DEFAULT_MODEL_NAME,
    DEFAULT_OUTPUT_FORMAT,
    DEFAULT_TASK_NAME,
    MODEL_METADATA,
    SUPPORTED_EXTENSIONS,
    SUPPORTED_MODELS,
    SUPPORTED_OUTPUT_FORMATS,
    SUPPORTED_TASKS,
    TIMESTAMP_ONLY_OUTPUT_FORMATS,
    TranscriptSegment,
    format_timestamp,
    format_timestamp_with_millis,
    get_model_cache_dir,
    get_model_cache_root,
    is_model_cached,
    render_output_text,
    render_plain_text,
    render_srt,
    render_timestamped_text,
    render_vtt,
    result_to_json_payload,
    transcribe_file,
    transcribe_segments,
)


def _seg(start, end, text):
    return TranscriptSegment(start=start, end=end, text=text)


# --- Constants ---

class TestConstants(unittest.TestCase):
    def test_supported_models_is_tuple(self):
        self.assertIsInstance(SUPPORTED_MODELS, tuple)
        self.assertIn("base", SUPPORTED_MODELS)
        self.assertIn("large-v3", SUPPORTED_MODELS)

    def test_default_model_name_in_supported(self):
        self.assertIn(DEFAULT_MODEL_NAME, SUPPORTED_MODELS)

    def test_default_task_name(self):
        self.assertEqual(DEFAULT_TASK_NAME, "transcribe")
        self.assertIn(DEFAULT_TASK_NAME, SUPPORTED_TASKS)

    def test_default_output_format(self):
        self.assertEqual(DEFAULT_OUTPUT_FORMAT, "txt")
        self.assertIn(DEFAULT_OUTPUT_FORMAT, SUPPORTED_OUTPUT_FORMATS)

    def test_supported_output_formats(self):
        self.assertEqual(SUPPORTED_OUTPUT_FORMATS, {"txt", "json", "srt", "vtt"})

    def test_timestamp_only_formats_subset(self):
        self.assertTrue(TIMESTAMP_ONLY_OUTPUT_FORMATS.issubset(SUPPORTED_OUTPUT_FORMATS))

    def test_model_metadata_keys_match_models(self):
        self.assertEqual(set(MODEL_METADATA.keys()), set(SUPPORTED_MODELS))

    def test_supported_extensions_has_common_types(self):
        for ext in [".mp3", ".wav", ".mp4", ".mkv", ".flac"]:
            self.assertIn(ext, SUPPORTED_EXTENSIONS)


# --- format_timestamp ---

class TestFormatTimestamp(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(format_timestamp(0), "00:00:00")

    def test_seconds_only(self):
        self.assertEqual(format_timestamp(45), "00:00:45")

    def test_minutes_and_seconds(self):
        self.assertEqual(format_timestamp(125), "00:02:05")

    def test_hours(self):
        self.assertEqual(format_timestamp(3661), "01:01:01")

    def test_float_truncates(self):
        self.assertEqual(format_timestamp(59.9), "00:00:59")

    def test_negative_raises(self):
        with self.assertRaises(ValueError):
            format_timestamp(-1)

    def test_nan_raises(self):
        with self.assertRaises(ValueError):
            format_timestamp(float("nan"))

    def test_inf_raises(self):
        with self.assertRaises(ValueError):
            format_timestamp(float("inf"))

    def test_non_numeric_raises(self):
        with self.assertRaises(ValueError):
            format_timestamp("abc")


# --- format_timestamp_with_millis ---

class TestFormatTimestampWithMillis(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(format_timestamp_with_millis(0), "00:00:00,000")

    def test_with_millis(self):
        self.assertEqual(format_timestamp_with_millis(1.5), "00:00:01,500")

    def test_dot_separator(self):
        self.assertEqual(format_timestamp_with_millis(1.5, "."), "00:00:01.500")

    def test_hours(self):
        self.assertEqual(format_timestamp_with_millis(3661.123), "01:01:01,123")


# --- Renderers ---

class TestRenderers(unittest.TestCase):
    def setUp(self):
        self.segments = [
            _seg(0.0, 2.5, " Hello world "),
            _seg(2.5, 5.0, " Goodbye "),
        ]

    def test_render_plain_text(self):
        result = render_plain_text(self.segments)
        self.assertEqual(result, "Hello world Goodbye")

    def test_render_timestamped_text(self):
        result = render_timestamped_text(self.segments)
        self.assertIn("[00:00:00 --> 00:00:02]", result)
        self.assertIn("Hello world", result)

    def test_render_srt(self):
        result = render_srt(self.segments)
        lines = result.split("\n")
        self.assertEqual(lines[0], "1")
        self.assertIn("-->", lines[1])
        self.assertEqual(lines[2], "Hello world")
        self.assertEqual(lines[3], "")
        self.assertEqual(lines[4], "2")

    def test_render_vtt(self):
        result = render_vtt(self.segments)
        self.assertTrue(result.startswith("WEBVTT"))
        self.assertIn(".", result)  # VTT uses dot separator

    def test_result_to_json_payload(self):
        payload = result_to_json_payload(self.segments)
        self.assertEqual(payload["text"], "Hello world Goodbye")
        self.assertEqual(len(payload["segments"]), 2)
        self.assertEqual(payload["segments"][0]["start"], 0.0)
        self.assertEqual(payload["segments"][0]["text"], "Hello world")


# --- render_output_text dispatcher ---

class TestRenderOutputText(unittest.TestCase):
    def setUp(self):
        self.segments = [_seg(0.0, 1.0, " Test ")]

    def test_txt_with_timestamps(self):
        result = render_output_text(self.segments, "txt", include_timestamps=True)
        self.assertIn("[00:00:00 --> 00:00:01]", result)

    def test_txt_without_timestamps(self):
        result = render_output_text(self.segments, "txt", include_timestamps=False)
        self.assertEqual(result, "Test")

    def test_json_format(self):
        import json
        result = render_output_text(self.segments, "json")
        parsed = json.loads(result)
        self.assertIn("text", parsed)
        self.assertIn("segments", parsed)

    def test_srt_format(self):
        result = render_output_text(self.segments, "srt")
        self.assertIn("1\n", result)
        self.assertIn("-->", result)

    def test_vtt_format(self):
        result = render_output_text(self.segments, "vtt")
        self.assertTrue(result.startswith("WEBVTT"))

    def test_unsupported_format_raises(self):
        with self.assertRaises(ValueError):
            render_output_text(self.segments, "xml")


# --- Cache helpers ---

class TestCacheHelpers(unittest.TestCase):
    def test_get_model_cache_dir_contains_model_name(self):
        path = get_model_cache_dir("base")
        self.assertIn("faster-whisper-base", str(path))

    def test_get_model_cache_root_default(self):
        with patch.dict(os.environ, {}, clear=True):
            root = get_model_cache_root()
            self.assertIn("huggingface", str(root))

    def test_get_model_cache_root_hf_home(self):
        with patch.dict(os.environ, {"HF_HOME": "/tmp/hf_test"}, clear=True):
            root = get_model_cache_root()
            self.assertEqual(root, Path("/tmp/hf_test/hub"))

    def test_is_model_cached_returns_bool(self):
        result = is_model_cached("nonexistent-model-xyz")
        self.assertFalse(result)


# --- Transcription with mock model ---

class TestTranscribeSegments(unittest.TestCase):
    def test_transcribe_segments_converts_whisper_output(self):
        mock_seg = MagicMock()
        mock_seg.start = 0.0
        mock_seg.end = 1.0
        mock_seg.text = "hello"
        mock_info = MagicMock()

        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([mock_seg], mock_info)

        segments, info = transcribe_segments(mock_model, "/fake.wav")
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].text, "hello")
        self.assertEqual(segments[0].start, 0.0)

    def test_transcribe_file_with_mock(self):
        mock_seg = MagicMock()
        mock_seg.start = 0.0
        mock_seg.end = 2.0
        mock_seg.text = " test output "
        mock_info = MagicMock()

        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([mock_seg], mock_info)

        result = transcribe_file("/fake.wav", model=mock_model)
        self.assertIn("test output", result.text)
        self.assertEqual(len(result.segments), 1)


if __name__ == "__main__":
    unittest.main()
