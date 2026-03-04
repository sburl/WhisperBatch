import unittest
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from whisper_batch_core import (
    TranscriptSegment,
    SUPPORTED_MODELS,
    SUPPORTED_TASKS,
    build_output_metadata_path,
    resolve_output_metadata_path,
    format_timestamp,
    load_output_metadata,
    load_model,
    render_plain_text,
    render_timestamped_text,
    should_skip_output_due_to_metadata,
    get_model_cache_dir,
    get_model_cache_root,
    is_model_cached,
    DEFAULT_OUTPUT_FORMAT,
    transcribe_file,
    transcribe_segments,
    DEFAULT_MODEL_NAME,
    DEFAULT_TASK_NAME,
)


class FakeModel:
    def __init__(self, segments=None, info=None):
        self.segments = list(segments or [])
        self.info = info if info is not None else object()
        self.last_task = None

    def transcribe(self, _path, task=DEFAULT_TASK_NAME):
        self.last_task = task
        return self.segments, self.info


class TestCoreHelpers(unittest.TestCase):
    def test_load_output_metadata_returns_none_for_missing_file(self):
        missing_path = Path(tempfile.gettempdir()) / "whisperbatch_missing_metadata.json"
        if missing_path.exists():
            missing_path.unlink()

        self.assertIsNone(load_output_metadata(missing_path))

    def test_load_output_metadata_ignores_non_dict_payload(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as tmp_file:
            tmp_file.write("[]")
            tmp_file.flush()
            self.assertIsNone(load_output_metadata(Path(tmp_file.name)))

    def test_should_skip_output_due_to_metadata_matching(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as tmp_file:
            payload = {
                "source_path": "/audio.wav",
                "output_path": "/audio_transcription.txt",
                "model": "base",
                "include_timestamps": True,
                "output_format": "txt",
                "task": "transcribe",
                "language": "en",
            }
            import json

            json.dump(payload, tmp_file)
            tmp_file.flush()
            self.assertTrue(
                should_skip_output_due_to_metadata(
                    source_path="/audio.wav",
                    output_path="/audio_transcription.txt",
                    metadata_path=Path(tmp_file.name),
                    model_name="base",
                    include_timestamps=True,
                    output_format="txt",
                    task="transcribe",
                    language="en",
                )
            )

    def test_should_skip_output_due_to_metadata_supports_legacy_keys(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as tmp_file:
            payload = {
                "source_file": "/audio.wav",
                "output_file": "/audio_transcription.txt",
                "model": "base",
                "include_timestamps": False,
            }
            import json

            json.dump(payload, tmp_file)
            tmp_file.flush()
            self.assertTrue(
                should_skip_output_due_to_metadata(
                    source_path="/audio.wav",
                    output_path="/audio_transcription.txt",
                    metadata_path=Path(tmp_file.name),
                    model_name="base",
                    include_timestamps=False,
                    output_format="txt",
                )
            )

    def test_should_skip_output_due_to_metadata_defaults_output_format_to_constant(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as tmp_file:
            payload = {
                "source_path": "/audio.wav",
                "output_path": "/audio_transcription.txt",
                "model": "base",
                "include_timestamps": True,
                "language": "en",
                "task": "transcribe",
            }
            import json

            json.dump(payload, tmp_file)
            tmp_file.flush()
            self.assertTrue(
                should_skip_output_due_to_metadata(
                    source_path="/audio.wav",
                    output_path="/audio_transcription.txt",
                    metadata_path=Path(tmp_file.name),
                    model_name="base",
                    include_timestamps=True,
                    task="transcribe",
                    language="en",
                )
            )

    def test_should_skip_output_due_to_metadata_false_if_task_or_language_changes(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as tmp_file:
            payload = {
                "source_path": "/audio.wav",
                "output_path": "/audio_transcription.txt",
                "model": "base",
                "include_timestamps": True,
                "output_format": "txt",
                "task": "transcribe",
                "language": "en",
            }
            import json

            json.dump(payload, tmp_file)
            tmp_file.flush()
            self.assertFalse(
                should_skip_output_due_to_metadata(
                    source_path="/audio.wav",
                    output_path="/audio_transcription.txt",
                    metadata_path=Path(tmp_file.name),
                    model_name="base",
                    include_timestamps=True,
                    output_format="txt",
                    task="translate",
                    language="en",
                )
            )
            self.assertFalse(
                should_skip_output_due_to_metadata(
                    source_path="/audio.wav",
                    output_path="/audio_transcription.txt",
                    metadata_path=Path(tmp_file.name),
                    model_name="base",
                    include_timestamps=True,
                    output_format="txt",
                    task="transcribe",
                    language="de",
                )
            )

    def test_should_skip_output_due_to_metadata_false_if_option_changed(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as tmp_file:
            payload = {
                "source_path": "/audio.wav",
                "output_path": "/audio_transcription.txt",
                "model": "base",
                "include_timestamps": True,
                "output_format": "txt",
            }
            import json

            json.dump(payload, tmp_file)
            tmp_file.flush()
            self.assertFalse(
                should_skip_output_due_to_metadata(
                    source_path="/audio.wav",
                    output_path="/audio_transcription.txt",
                    metadata_path=Path(tmp_file.name),
                    model_name="large-v3",
                    include_timestamps=True,
                    output_format="txt",
                )
            )

    def test_should_skip_output_due_to_metadata_ignores_timestamps_for_subtitle_formats(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as tmp_file:
            payload = {
                "source_path": "/audio.wav",
                "output_path": "/audio_transcription.srt",
                "model": "base",
                "include_timestamps": True,
                "output_format": "srt",
            }
            import json

            json.dump(payload, tmp_file)
            tmp_file.flush()
            self.assertTrue(
                should_skip_output_due_to_metadata(
                    source_path="/audio.wav",
                    output_path="/audio_transcription.srt",
                    metadata_path=Path(tmp_file.name),
                    model_name="base",
                    include_timestamps=False,
                    output_format="srt",
                )
            )

    def test_should_skip_output_due_to_metadata_false_if_invalid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as tmp_file:
            tmp_file.write("not json")
            tmp_file.flush()
            self.assertFalse(
                should_skip_output_due_to_metadata(
                    source_path="/audio.wav",
                    output_path="/audio_transcription.txt",
                    metadata_path=Path(tmp_file.name),
                    model_name="base",
                    include_timestamps=True,
                    output_format="txt",
                )
            )

    def test_build_output_metadata_path(self):
        output_file = Path("/tmp", "speech_transcription.txt")
        expected = output_file.with_suffix(".txt.metadata.json")
        self.assertEqual(build_output_metadata_path(output_file), expected)

    def test_get_model_cache_root_prefers_hf_home(self):
        with patch.dict(os.environ, {"HF_HOME": "/custom/hf_home"}, clear=True):
            self.assertEqual(
                get_model_cache_root(),
                Path("/custom/hf_home") / "hub",
            )

    def test_get_model_cache_root_expands_hf_home_user_directory(self):
        with patch.dict(os.environ, {"HF_HOME": "~/hf-home"}, clear=True):
            self.assertEqual(
                get_model_cache_root(),
                Path.home() / "hf-home" / "hub",
            )

    def test_get_model_cache_root_expands_environment_variables(self):
        with patch.dict(
            os.environ,
            {"HOME": "/home/user", "HF_HOME": "$HOME/hf-home"},
            clear=True,
        ):
            self.assertEqual(
                get_model_cache_root(),
                Path("/home/user/hf-home") / "hub",
            )

    def test_get_model_cache_root_treats_blank_values_as_unset(self):
        with patch.dict(
            os.environ,
            {"HF_HOME": "   ", "HUGGINGFACE_HUB_CACHE": "\t", "XDG_CACHE_HOME": " "},
            clear=True,
        ), patch("whisper_batch_core.core.os.name", "posix"):
            self.assertEqual(
                get_model_cache_root(),
                Path.home() / ".cache" / "huggingface" / "hub",
            )

    def test_get_model_cache_root_prefers_hf_hub_cache(self):
        with patch.dict(
            os.environ,
            {"HF_HOME": "", "HUGGINGFACE_HUB_CACHE": "/custom/hub_cache"},
            clear=True,
        ):
            self.assertEqual(get_model_cache_root(), Path("/custom/hub_cache"))

    def test_get_model_cache_root_uses_xdg_cache_home(self):
        with patch.dict(
            os.environ,
            {"HF_HOME": "", "HUGGINGFACE_HUB_CACHE": "", "XDG_CACHE_HOME": "/custom/xdg"},
            clear=True,
        ), patch("whisper_batch_core.core.os.name", "posix"):
            self.assertEqual(
                get_model_cache_root(),
                Path("/custom/xdg") / "huggingface" / "hub",
            )

    def test_get_model_cache_root_prefers_localappdata_on_windows(self):
        with patch.dict(
            os.environ,
            {"HF_HOME": "", "HUGGINGFACE_HUB_CACHE": "", "LOCALAPPDATA": "/custom/localappdata"},
            clear=True,
        ), patch("whisper_batch_core.core.os.name", "nt"):
            self.assertEqual(
                get_model_cache_root(),
                Path("/custom/localappdata") / "huggingface" / "hub",
            )

    def test_get_model_cache_root_falls_back_to_default_windows_profile(self):
        with patch.dict(
            os.environ,
            {"HF_HOME": "", "HUGGINGFACE_HUB_CACHE": "", "LOCALAPPDATA": ""},
            clear=True,
        ), patch("whisper_batch_core.core.os.name", "nt"), patch("whisper_batch_core.core.Path.home", return_value=Path("/custom/home")):
            self.assertEqual(
                get_model_cache_root(),
                Path("/custom/home") / "AppData" / "Local" / "huggingface" / "hub",
            )

    def test_get_model_cache_dir_builds_faster_whisper_path(self):
        with patch("whisper_batch_core.core.get_model_cache_root", return_value=Path("/custom/hf_root")):
            self.assertEqual(
                get_model_cache_dir("large-v3"),
                Path("/custom/hf_root/models--Systran--faster-whisper-large-v3"),
            )

    def test_is_model_cached_checks_cache_directory_presence(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_root = Path(temp_dir)
            model_path = cache_root / "models--Systran--faster-whisper-base"

            with patch("whisper_batch_core.core.get_model_cache_root", return_value=cache_root):
                self.assertFalse(is_model_cached("base"))

                model_path.mkdir(parents=True)
                self.assertTrue(is_model_cached("base"))

    def test_resolve_output_metadata_path_prefers_new_style(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir, "speech_transcription.txt")
            legacy_metadata = output_file.with_name(f"{output_file.stem}.metadata.json")
            new_metadata = output_file.with_suffix(".txt.metadata.json")
            new_metadata.write_text("new", encoding="utf-8")
            legacy_metadata.write_text("legacy", encoding="utf-8")

            self.assertEqual(
                resolve_output_metadata_path(output_file),
                new_metadata,
            )

    def test_resolve_output_metadata_path_uses_legacy_when_new_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir, "speech_transcription.txt")
            legacy_metadata = output_file.with_name(f"{output_file.stem}.metadata.json")
            legacy_metadata.write_text("legacy", encoding="utf-8")

            self.assertEqual(
                resolve_output_metadata_path(output_file),
                legacy_metadata,
            )

    def test_resolve_output_metadata_path_uses_new_when_no_sidecar_exists(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir, "speech_transcription.txt")

            self.assertEqual(
                resolve_output_metadata_path(output_file),
                output_file.with_suffix(".txt.metadata.json"),
            )

    def test_load_model_uses_cpu_int8_on_darwin_arm64_auto(self):
        with patch("whisper_batch_core.core.WhisperModel") as mock_whisper_model, \
                patch("whisper_batch_core.core.platform.system", return_value="Darwin"), \
                patch("whisper_batch_core.core.platform.machine", return_value="arm64"):
            mock_model = MagicMock()
            mock_whisper_model.return_value = mock_model

            model = load_model("large-v3", device="auto")

            self.assertIs(model, mock_model)
            mock_whisper_model.assert_called_once_with(
                "large-v3",
                device="cpu",
                compute_type="int8",
            )

    def test_load_model_keeps_explicit_device(self):
        with patch("whisper_batch_core.core.WhisperModel") as mock_whisper_model, \
                patch("whisper_batch_core.core.platform.system", return_value="Darwin"), \
                patch("whisper_batch_core.core.platform.machine", return_value="arm64"):
            mock_model = MagicMock()
            mock_whisper_model.return_value = mock_model

            model = load_model("base", device="cpu", compute_type="float16")

            self.assertIs(model, mock_model)
            mock_whisper_model.assert_called_once_with("base", device="cpu", compute_type="float16")

    def test_load_model_wraps_model_load_failures(self):
        with patch("whisper_batch_core.core.WhisperModel") as mock_whisper_model:
            mock_whisper_model.side_effect = RuntimeError("download interrupted")

            with self.assertRaises(RuntimeError) as context:
                load_model("base")

            self.assertIn("Unable to load Whisper model 'base'", str(context.exception))
            self.assertIn("corrupted model cache", str(context.exception))

    def test_format_timestamp(self):
        self.assertEqual(format_timestamp(0), "00:00:00")
        self.assertEqual(format_timestamp(61), "00:01:01")
        self.assertEqual(format_timestamp(3661), "01:01:01")
        self.assertEqual(format_timestamp(7322.9), "02:02:02")

    def test_format_timestamp_edge_cases(self):
        self.assertEqual(format_timestamp(0.4), "00:00:00")
        self.assertEqual(format_timestamp(3599.9), "00:59:59")

    def test_format_timestamp_raises_for_invalid_values(self):
        with self.assertRaises(ValueError):
            format_timestamp("abc")

        with self.assertRaises(ValueError):
            format_timestamp(-1)

        with self.assertRaises(ValueError):
            format_timestamp(float("nan"))

    def test_render_plain_text(self):
        segments = [
            TranscriptSegment(0.1, 1.1, "  hello "),
            TranscriptSegment(2.0, 3.0, "world  "),
        ]
        self.assertEqual(render_plain_text(segments), "hello world")

    def test_render_plain_text_empty_segments(self):
        self.assertEqual(render_plain_text([]), "")

    def test_render_timestamped_text_empty_segments(self):
        self.assertEqual(render_timestamped_text([]), "")

    def test_render_timestamped_text(self):
        segments = [
            TranscriptSegment(0.0, 0.8, "  one "),
            TranscriptSegment(2.5, 5.2, " two "),
        ]
        expected = "[00:00:00 --> 00:00:00] one\n[00:00:02 --> 00:00:05] two"
        self.assertEqual(render_timestamped_text(segments), expected)

    def test_transcribe_segments(self):
        class FakeSegment:
            def __init__(self, start, end, text):
                self.start = start
                self.end = end
                self.text = text

        model = FakeModel(
            segments=[
                FakeSegment(0.0, 1.0, "a"),
                FakeSegment(1.5, 2.0, 3),
            ],
            info={"lang": "en"},
        )
        segments, info = transcribe_segments(model, "audio.wav")
        self.assertEqual(info, {"lang": "en"})
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0], TranscriptSegment(0.0, 1.0, "a"))
        self.assertEqual(segments[1], TranscriptSegment(1.5, 2.0, "3"))

    def test_transcribe_file_with_model_injection(self):
        model = FakeModel(segments=[TranscriptSegment(0.0, 1.0, "hello")], info={"ok": True})
        result = transcribe_file("audio.wav", include_timestamps=False, model=model)
        self.assertEqual(result.text, "hello")
        self.assertEqual(result.segments, [TranscriptSegment(0.0, 1.0, "hello")])
        self.assertEqual(result.info, {"ok": True})

    def test_transcribe_file_passes_task_argument(self):
        model = FakeModel(segments=[], info={"ok": True})
        transcribe_file("audio.wav", task="translate", model=model)
        self.assertEqual(model.last_task, "translate")

    def test_transcribe_file_uses_default_task_constant_when_unspecified(self):
        model = FakeModel(segments=[TranscriptSegment(0.0, 1.0, "hello")], info={"ok": True})
        transcribe_file("audio.wav", model=model)
        self.assertEqual(model.last_task, DEFAULT_TASK_NAME)

    @patch("whisper_batch_core.core.load_model")
    def test_transcribe_file_uses_core_default_model(self, mock_load_model):
        model = FakeModel(segments=[TranscriptSegment(0.0, 1.0, "hello")], info={"ok": True})
        mock_load_model.return_value = model

        result = transcribe_file("audio.wav", model=None, include_timestamps=False)

        mock_load_model.assert_called_once_with(
            DEFAULT_MODEL_NAME,
            device="auto",
            compute_type=None,
        )
        self.assertEqual(result.text, "hello")
        self.assertEqual(result.segments, [TranscriptSegment(0.0, 1.0, "hello")])

    def test_default_model_name_matches_supported_models_order(self):
        if SUPPORTED_MODELS:
            self.assertEqual(DEFAULT_MODEL_NAME, SUPPORTED_MODELS[-1])

    def test_supported_tasks_contains_expected_baseline_tasks(self):
        self.assertEqual({"translate", "transcribe"}, SUPPORTED_TASKS)

    def test_default_task_name_is_transcribe(self):
        self.assertEqual(DEFAULT_TASK_NAME, "transcribe")

    def test_default_output_format_is_txt(self):
        self.assertEqual(DEFAULT_OUTPUT_FORMAT, "txt")


if __name__ == "__main__":
    unittest.main()
