import unittest
import json

from transcribe_gui import (
    _effective_include_timestamps_for_output,
    _format_timestamp_with_millis,
    _render_output_text,
    _render_srt,
    _render_vtt,
    _result_to_json_payload,
)
from whisper_batch_core import DEFAULT_OUTPUT_FORMAT, render_plain_text, render_timestamped_text


class _FakeSegment:
    def __init__(self, start, end, text):
        self.start = start
        self.end = end
        self.text = text


class TestOutputFormatHelpers(unittest.TestCase):
    def setUp(self):
        self.segments = [
            _FakeSegment(0.0, 1.5, "Hello"),
            _FakeSegment(61.004, 61.999, "World"),
        ]

    def test_effective_include_timestamps_for_output(self):
        self.assertFalse(_effective_include_timestamps_for_output("srt", True))
        self.assertFalse(_effective_include_timestamps_for_output("vtt", True))
        self.assertFalse(_effective_include_timestamps_for_output("txt", False))
        self.assertFalse(_effective_include_timestamps_for_output("json", False))
        self.assertTrue(_effective_include_timestamps_for_output("txt", True))
        self.assertTrue(_effective_include_timestamps_for_output("json", True))

    def test_format_timestamp_with_millis(self):
        self.assertEqual(_format_timestamp_with_millis(1.999, ","), "00:00:01,999")
        self.assertEqual(_format_timestamp_with_millis(61.004, ","), "00:01:01,004")
        self.assertEqual(_format_timestamp_with_millis(3723.789, "."), "01:02:03.789")

    def test_render_vtt(self):
        expected = (
            "WEBVTT\n\n"
            "00:00:00.000 --> 00:00:01.500\nHello\n\n"
            "00:01:01.004 --> 00:01:01.999\nWorld"
        )
        self.assertEqual(_render_vtt(self.segments), expected)

    def test_render_srt(self):
        expected = (
            "1\n"
            "00:00:00,000 --> 00:00:01,500\n"
            "Hello\n\n"
            "2\n"
            "00:01:01,004 --> 00:01:01,999\n"
            "World"
        )
        self.assertEqual(_render_srt(self.segments), expected)

    def test_render_output_text_dispatch(self):
        self.assertEqual(
            _render_output_text(self.segments, DEFAULT_OUTPUT_FORMAT, False),
            render_plain_text(self.segments),
        )
        self.assertEqual(
            _render_output_text(self.segments, DEFAULT_OUTPUT_FORMAT, True),
            render_timestamped_text(self.segments),
        )

    def test_render_output_text_json(self):
        expected_text = "Hello World"
        expected_payload = _result_to_json_payload(self.segments)
        output_payload = _render_output_text(self.segments, "json", False)
        parsed = json.loads(output_payload)
        self.assertEqual(parsed["text"], expected_text)
        self.assertEqual(len(parsed["segments"]), 2)
        self.assertEqual(parsed["segments"][0]["text"], "Hello")
        self.assertAlmostEqual(parsed["segments"][0]["start"], 0.0)
        self.assertAlmostEqual(parsed["segments"][1]["end"], 61.999)

    def test_render_output_text_unknown_format_raises(self):
        with self.assertRaises(ValueError):
            _render_output_text(self.segments, "bogus", False)


if __name__ == "__main__":
    unittest.main()
