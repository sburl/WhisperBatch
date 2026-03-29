"""Tests for whisper_batch_core.diarize — speaker diarization alignment."""

import unittest
from unittest.mock import MagicMock, patch

from whisper_batch_core import TranscriptSegment
from whisper_batch_core.diarize import assign_speakers, diarize_segments


def _seg(start, end, text, speaker=None):
    return TranscriptSegment(start=start, end=end, text=text, speaker=speaker)


# --- Lightweight stand-ins for pyannote types ---

class MockSegment:
    """Mimics pyannote.core.Segment."""
    def __init__(self, start, end):
        self.start = start
        self.end = end


class MockAnnotation:
    """Mimics pyannote.core.Annotation with itertracks()."""
    def __init__(self, tracks):
        # tracks: list of (start, end, speaker_label)
        self._tracks = tracks

    def itertracks(self, yield_label=False):
        for start, end, speaker in self._tracks:
            seg = MockSegment(start, end)
            if yield_label:
                yield seg, None, speaker
            else:
                yield seg, None


# --- TranscriptSegment.with_speaker ---

class TestWithSpeaker(unittest.TestCase):
    def test_returns_new_instance_with_speaker(self):
        seg = _seg(1.0, 2.0, "hello")
        new = seg.with_speaker("Speaker 1")
        self.assertEqual(new.speaker, "Speaker 1")
        self.assertEqual(new.start, 1.0)
        self.assertEqual(new.end, 2.0)
        self.assertEqual(new.text, "hello")

    def test_original_unchanged(self):
        seg = _seg(1.0, 2.0, "hello")
        seg.with_speaker("Speaker 1")
        self.assertIsNone(seg.speaker)

    def test_default_speaker_is_none(self):
        seg = _seg(0.0, 1.0, "test")
        self.assertIsNone(seg.speaker)


# --- assign_speakers ---

class TestAssignSpeakers(unittest.TestCase):
    def test_single_segment_single_speaker(self):
        segments = [_seg(0.0, 5.0, "hello")]
        annotation = MockAnnotation([(0.0, 5.0, "SPEAKER_00")])
        result = assign_speakers(segments, annotation)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].speaker, "Speaker 1")
        self.assertEqual(result[0].text, "hello")

    def test_multiple_segments_multiple_speakers(self):
        segments = [
            _seg(0.0, 3.0, "first"),
            _seg(3.0, 6.0, "second"),
            _seg(6.0, 9.0, "third"),
        ]
        annotation = MockAnnotation([
            (0.0, 4.0, "SPEAKER_00"),
            (4.0, 9.0, "SPEAKER_01"),
        ])
        result = assign_speakers(segments, annotation)
        self.assertEqual(result[0].speaker, "Speaker 1")  # 0-3 fully in SPEAKER_00
        # seg [3,6] vs SPEAKER_00 [0,4] -> overlap=1s; vs SPEAKER_01 [4,9] -> overlap=2s
        self.assertEqual(result[1].speaker, "Speaker 2")
        self.assertEqual(result[2].speaker, "Speaker 2")  # 6-9 fully in SPEAKER_01

    def test_segment_max_overlap_wins(self):
        segments = [_seg(0.0, 10.0, "split")]
        annotation = MockAnnotation([
            (0.0, 7.0, "SPEAKER_00"),   # 7s overlap
            (7.0, 10.0, "SPEAKER_01"),  # 3s overlap
        ])
        result = assign_speakers(segments, annotation)
        self.assertEqual(result[0].speaker, "Speaker 1")

    def test_no_overlap_gets_unknown(self):
        segments = [_seg(10.0, 15.0, "late")]
        annotation = MockAnnotation([(0.0, 5.0, "SPEAKER_00")])
        result = assign_speakers(segments, annotation)
        self.assertEqual(result[0].speaker, "Unknown")

    def test_empty_segments(self):
        result = assign_speakers([], MockAnnotation([]))
        self.assertEqual(result, [])

    def test_empty_annotation(self):
        segments = [_seg(0.0, 1.0, "hello")]
        result = assign_speakers(segments, MockAnnotation([]))
        self.assertEqual(result[0].speaker, "Unknown")

    def test_speaker_labels_normalized(self):
        """Raw pyannote labels like SPEAKER_02 become 'Speaker 1', 'Speaker 2' etc."""
        segments = [
            _seg(0.0, 5.0, "a"),
            _seg(5.0, 10.0, "b"),
        ]
        annotation = MockAnnotation([
            (0.0, 5.0, "SPEAKER_02"),
            (5.0, 10.0, "SPEAKER_00"),
        ])
        result = assign_speakers(segments, annotation)
        # Sorted unique: SPEAKER_00, SPEAKER_02 -> Speaker 1, Speaker 2
        self.assertEqual(result[0].speaker, "Speaker 2")  # SPEAKER_02
        self.assertEqual(result[1].speaker, "Speaker 1")  # SPEAKER_00


# --- load_diarization_pipeline ---

class TestLoadPipeline(unittest.TestCase):
    def test_missing_pyannote_raises_runtime_error(self):
        with patch.dict("sys.modules", {"pyannote": None, "pyannote.audio": None}):
            from whisper_batch_core.diarize import _check_pyannote_available
            with self.assertRaises(RuntimeError) as ctx:
                _check_pyannote_available()
            self.assertIn("pyannote.audio", str(ctx.exception))
            self.assertIn("pip install", str(ctx.exception))

    def test_load_calls_from_pretrained(self):
        mock_pipeline_cls = MagicMock()
        with patch("whisper_batch_core.diarize._check_pyannote_available"):
            # Pipeline is imported inside the function via "from pyannote.audio import Pipeline"
            # so we mock the import mechanism
            mock_pyannote_audio = MagicMock()
            mock_pyannote_audio.Pipeline = mock_pipeline_cls
            with patch.dict("sys.modules", {
                "pyannote": MagicMock(),
                "pyannote.audio": mock_pyannote_audio,
            }):
                from importlib import reload
                import whisper_batch_core.diarize as dmod
                reload(dmod)  # Force re-import with mocked modules
                dmod.load_diarization_pipeline("hf_test_token")
                mock_pipeline_cls.from_pretrained.assert_called_once_with(
                    "pyannote/speaker-diarization-3.1",
                    use_auth_token="hf_test_token",
                )


# --- diarize_segments integration ---

class TestDiarizeSegments(unittest.TestCase):
    @patch("whisper_batch_core.diarize.load_diarization_pipeline")
    def test_full_flow_with_provided_pipeline(self, mock_load):
        mock_pipeline = MagicMock()
        mock_pipeline.return_value = MockAnnotation([
            (0.0, 3.0, "SPEAKER_00"),
            (3.0, 6.0, "SPEAKER_01"),
        ])

        segments = [_seg(0.0, 3.0, "first"), _seg(3.0, 6.0, "second")]
        result = diarize_segments(segments, "/fake.wav", "hf_token", pipeline=mock_pipeline)

        self.assertEqual(result[0].speaker, "Speaker 1")
        self.assertEqual(result[1].speaker, "Speaker 2")
        mock_load.assert_not_called()  # Pipeline was provided, no loading

    def test_missing_token_raises(self):
        with patch.dict("os.environ", {}, clear=False):
            # Ensure HF_TOKEN is not set
            import os
            old = os.environ.pop("HF_TOKEN", None)
            try:
                with self.assertRaises(ValueError) as ctx:
                    diarize_segments([], "/fake.wav", "")
                self.assertIn("HuggingFace token", str(ctx.exception))
            finally:
                if old is not None:
                    os.environ["HF_TOKEN"] = old


if __name__ == "__main__":
    unittest.main()
