import tempfile
import io
import csv
import json
import zipfile
import sys
import unittest
from pathlib import Path
from unittest.mock import ANY, patch

import transcribe_audio


class Result:
    def __init__(self, text):
        self.text = text


class Segment:
    def __init__(self, start, end, text):
        self.start = start
        self.end = end
        self.text = text


class ResultWithSegments:
    def __init__(self, text, segments):
        self.text = text
        self.segments = segments
        self.info = object()


class AudioTests(unittest.TestCase):
    def test_process_directory_requires_existing_directory(self):
        with self.assertRaises(ValueError):
            transcribe_audio.process_directory("/definitely-does-not-exist")

    def test_process_directory_rejects_invalid_model_name(self):
        with self.assertRaises(ValueError) as ctx:
            transcribe_audio.process_directory("/tmp", model_name="bad-model")
        self.assertIn("Unsupported model", str(ctx.exception))

    def test_process_directory_rejects_negative_retries(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(ValueError) as ctx:
                transcribe_audio.process_directory(temp_dir, retries=-1)
            self.assertIn("--retries", str(ctx.exception))

    def test_process_directory_rejects_non_boolean_timestamps(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(ValueError) as ctx:
                transcribe_audio.process_directory(
                    temp_dir,
                    include_timestamps="yes"
                )
            self.assertIn("--timestamps", str(ctx.exception))

    def test_process_directory_rejects_negative_retry_delay(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(ValueError) as ctx:
                transcribe_audio.process_directory(temp_dir, retry_delay=-1)
            self.assertIn("--retry-delay", str(ctx.exception))

    def test_process_directory_rejects_invalid_max_workers(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(ValueError) as ctx:
                transcribe_audio.process_directory(temp_dir, max_workers=0)
            self.assertIn("--max-workers", str(ctx.exception))

    def test_process_directory_rejects_invalid_output_format(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(ValueError) as ctx:
                transcribe_audio.process_directory(temp_dir, output_format="invalid")
            self.assertIn("Unsupported output format", str(ctx.exception))

    def test_process_directory_rejects_invalid_annotation_export(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(ValueError) as ctx:
                transcribe_audio.process_directory(temp_dir, annotation_export="")
            self.assertIn("--annotation-export", str(ctx.exception))

    def test_process_directory_rejects_invalid_annotation_export_extension(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(ValueError) as ctx:
                transcribe_audio.process_directory(temp_dir, annotation_export="audit.txt")
            self.assertIn("--annotation-export", str(ctx.exception))

    def test_process_directory_rejects_non_directory_path(self):
        with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
            with self.assertRaises(ValueError):
                transcribe_audio.process_directory(tmp.name)

    @patch("transcribe_audio.transcribe_file")
    @patch("transcribe_audio.load_model")
    def test_process_directory_processes_supported_files(self, mock_load_model, mock_transcribe_file):
        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "c.wav").write_text("dummy", encoding="utf-8")
            Path(temp_dir, "a.wav").write_text("dummy", encoding="utf-8")
            Path(temp_dir, "b.txt").write_text("ignore", encoding="utf-8")

            model = object()
            mock_load_model.return_value = model
            mock_transcribe_file.return_value = Result("ok")

            summary = transcribe_audio.process_directory(temp_dir, include_timestamps=True)

            mock_load_model.assert_called_once_with("large-v3", device="auto")
            self.assertEqual(summary["total"], 2)
            self.assertEqual(summary["processed"], 2)
            self.assertEqual(summary["failed"], 0)
            self.assertEqual(summary["skipped"], 0)
            self.assertEqual(summary["max_workers"], 1)
            self.assertTrue(summary["success"])
            self.assertGreaterEqual(summary["elapsed_seconds"], 0)
            self.assertGreaterEqual(summary["throughput_files_per_second"], 0)

            call_paths = [Path(call.args[0]).name for call in mock_transcribe_file.call_args_list]
            self.assertEqual(call_paths, ["a.wav", "c.wav"])
            mock_transcribe_file.assert_any_call(
                str(Path(temp_dir, "a.wav")),
                model_name="large-v3",
                include_timestamps=True,
                device="auto",
                model=model,
                task="transcribe",
            )
            mock_transcribe_file.assert_any_call(
                str(Path(temp_dir, "c.wav")),
                model_name="large-v3",
                include_timestamps=True,
                device="auto",
                model=model,
                task="transcribe",
            )

    @patch("transcribe_audio.load_model")
    @patch("transcribe_audio.transcribe_file")
    def test_process_directory_reports_model_cache_miss(self, mock_transcribe_file, mock_load_model):
        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")

            mock_load_model.return_value = object()
            mock_transcribe_file.return_value = Result("ok")

            with patch("transcribe_audio.get_model_cache_dir", return_value=Path("/tmp/fake-model-cache")):
                with patch("transcribe_audio.print") as mock_print, patch(
                    "transcribe_audio.is_model_cached", return_value=False
                ):
                    summary = transcribe_audio.process_directory(temp_dir, model_name="base")

            self.assertEqual(summary["processed"], 1)
            self.assertTrue(summary["success"])
            logs = "\n".join(
                str(call.args[0]) for call in mock_print.call_args_list if call.args
            )
            self.assertIn("not cached locally yet", logs)
            self.assertIn("/tmp/fake-model-cache", logs)

    @patch("transcribe_audio.load_model")
    @patch("transcribe_audio.transcribe_file")
    def test_process_directory_reports_model_cache_hit(self, mock_transcribe_file, mock_load_model):
        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")

            mock_load_model.return_value = object()
            mock_transcribe_file.return_value = Result("ok")

            with patch("transcribe_audio.get_model_cache_dir", return_value=Path("/tmp/fake-model-cache")):
                with patch("transcribe_audio.is_model_cached", return_value=True):
                    with patch("transcribe_audio.print") as mock_print:
                        summary = transcribe_audio.process_directory(temp_dir, model_name="base")

            self.assertEqual(summary["processed"], 1)
            logs = "\n".join(
                str(call.args[0]) for call in mock_print.call_args_list if call.args
            )
            self.assertIn("Found cached model 'base'", logs)
            self.assertIn("/tmp/fake-model-cache", logs)

    @patch("transcribe_audio.transcribe_file")
    @patch("transcribe_audio.load_model")
    def test_process_directory_order_is_deterministic_with_case_variants(
        self,
        mock_load_model,
        mock_transcribe_file,
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "a.wav").write_text("dummy", encoding="utf-8")
            Path(temp_dir, "A.WAV").write_text("dummy", encoding="utf-8")
            Path(temp_dir, "b.wav").write_text("dummy", encoding="utf-8")

            mock_load_model.return_value = object()
            mock_transcribe_file.return_value = Result("ok")

            transcribe_audio.process_directory(temp_dir)

            call_paths = [Path(call.args[0]).name for call in mock_transcribe_file.call_args_list]
            self.assertEqual(call_paths, ["A.WAV", "a.wav", "b.wav"])

    @patch("transcribe_audio.transcribe_file")
    @patch("transcribe_audio.load_model")
    def test_process_directory_is_case_insensitive_for_extensions(self, mock_load_model, mock_transcribe_file):
        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.WAV").write_text("dummy", encoding="utf-8")

            mock_load_model.return_value = object()
            mock_transcribe_file.return_value = Result("ok")

            summary = transcribe_audio.process_directory(temp_dir)

            self.assertEqual(summary["total"], 1)
            self.assertEqual(summary["processed"], 1)

    @patch("transcribe_audio.transcribe_file")
    @patch("transcribe_audio.load_model")
    def test_process_directory_respects_requested_max_workers(self, mock_load_model, mock_transcribe_file):
        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")

            mock_load_model.return_value = object()
            mock_transcribe_file.return_value = Result("hello")

            summary = transcribe_audio.process_directory(temp_dir, max_workers=3)

            self.assertEqual(summary["max_workers"], 3)

    @patch("transcribe_audio._run_postprocess_hook")
    @patch("transcribe_audio.transcribe_file")
    @patch("transcribe_audio.load_model")
    def test_process_directory_runs_postprocess_command(self, mock_load_model, mock_transcribe_file, mock_postprocess):
        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")

            mock_load_model.return_value = object()
            mock_transcribe_file.return_value = Result("hello")

            summary = transcribe_audio.process_directory(
                temp_dir,
                model_name="base",
                postprocess_command="python -m scripts.postprocess",
            )

            output_file = Path(temp_dir, "transcriptions", "speech_transcription.txt")
            self.assertEqual(summary["processed"], 1)
            self.assertEqual(summary["failed"], 0)
            self.assertTrue(output_file.exists())
            mock_postprocess.assert_called_once_with(
                output_file,
                "python -m scripts.postprocess",
            )

    @patch("transcribe_audio._load_postprocess_plugin")
    @patch("transcribe_audio.transcribe_file")
    @patch("transcribe_audio.load_model")
    def test_process_directory_runs_postprocess_plugin(self, mock_load_model, mock_transcribe_file, mock_load_plugin):
        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")

            mock_load_model.return_value = object()
            mock_transcribe_file.return_value = Result("hello")
            plugin_handler = mock_load_plugin.return_value

            summary = transcribe_audio.process_directory(
                temp_dir,
                model_name="base",
                postprocess_plugin="plugin_mod:postprocess_output",
            )

            output_file = Path(temp_dir, "transcriptions", "speech_transcription.txt")
            self.assertEqual(summary["processed"], 1)
            self.assertEqual(summary["failed"], 0)
            self.assertTrue(output_file.exists())
            plugin_handler.assert_called_once()
            plugin_args = plugin_handler.call_args.args
            self.assertEqual(plugin_args[0], str(output_file))
            metadata = plugin_args[1]
            self.assertIsInstance(metadata, dict)
            self.assertEqual(metadata["model"], "base")
            self.assertEqual(metadata["task"], "transcribe")

    @patch("transcribe_audio._load_postprocess_plugin")
    @patch("transcribe_audio.transcribe_file")
    @patch("transcribe_audio.load_model")
    def test_postprocess_plugin_is_loaded_once_for_multiple_files(self, mock_load_model, mock_transcribe_file, mock_load_plugin):
        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")
            Path(temp_dir, "interview.wav").write_text("dummy", encoding="utf-8")

            mock_load_model.return_value = object()
            mock_transcribe_file.return_value = Result("hello")
            plugin_handler = mock_load_plugin.return_value

            summary = transcribe_audio.process_directory(
                temp_dir,
                model_name="base",
                postprocess_plugin="plugin_mod:postprocess_output",
            )

            self.assertEqual(summary["processed"], 2)
            self.assertEqual(summary["failed"], 0)
            mock_load_plugin.assert_called_once_with("plugin_mod:postprocess_output")
            self.assertEqual(plugin_handler.call_count, 2)

    @patch("transcribe_audio.process_directory")
    def test_main_rejects_invalid_postprocess_plugin(self, mock_process_directory):
        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")

            with patch.object(
                sys,
                "argv",
                [
                    "transcribe_audio.py",
                    temp_dir,
                    "--postprocess-plugin",
                    "plugin_mod",
                ],
            ):
                self.assertEqual(transcribe_audio.main(), 1)

        mock_process_directory.assert_not_called()

    @patch("transcribe_audio._run_postprocess_hook")
    @patch("transcribe_audio.transcribe_file")
    @patch("transcribe_audio.load_model")
    def test_postprocess_command_failure_marks_file_as_failed(self, mock_load_model, mock_transcribe_file, mock_postprocess):
        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")

            mock_load_model.return_value = object()
            mock_transcribe_file.return_value = Result("hello")
            mock_postprocess.side_effect = RuntimeError("boom")

            summary = transcribe_audio.process_directory(
                temp_dir,
                model_name="base",
                postprocess_command="false",
                retries=0,
            )

            self.assertEqual(summary["processed"], 0)
            self.assertEqual(summary["failed"], 1)
            self.assertFalse(summary["success"])

    @patch("transcribe_audio._load_postprocess_plugin")
    @patch("transcribe_audio.transcribe_file")
    @patch("transcribe_audio.load_model")
    def test_postprocess_plugin_failure_marks_file_as_failed(self, mock_load_model, mock_transcribe_file, mock_load_plugin):
        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")

            mock_load_model.return_value = object()
            mock_transcribe_file.return_value = Result("hello")
            mock_load_plugin.return_value.side_effect = RuntimeError("boom")

            summary = transcribe_audio.process_directory(
                temp_dir,
                model_name="base",
                postprocess_plugin="plugin_mod:postprocess_output",
                retries=0,
            )

            self.assertEqual(summary["processed"], 0)
            self.assertEqual(summary["failed"], 1)
            self.assertFalse(summary["success"])

    @patch("transcribe_audio.transcribe_file")
    @patch("transcribe_audio.load_model")
    def test_process_directory_records_failed_file_summary(self, mock_load_model, mock_transcribe_file):
        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")

            mock_load_model.return_value = object()
            mock_transcribe_file.side_effect = RuntimeError("transcribe failed")

            summary = transcribe_audio.process_directory(
                temp_dir,
                model_name="base",
                retries=0,
            )

            self.assertEqual(summary["processed"], 0)
            self.assertEqual(summary["failed"], 1)
            self.assertEqual(len(summary["failures"]), 1)
            failure = summary["failures"][0]
            self.assertEqual(failure["file"], str(Path(temp_dir, "speech.wav")))
            self.assertEqual(failure["error_type"], "RuntimeError")
            self.assertEqual(failure["attempts"], 1)

    @patch("transcribe_audio.transcribe_file")
    @patch("transcribe_audio.load_model")
    def test_process_directory_writes_postmortem_log(self, mock_load_model, mock_transcribe_file):
        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")

            mock_load_model.return_value = object()
            mock_transcribe_file.side_effect = RuntimeError("boom")

            summary = transcribe_audio.process_directory(
                temp_dir,
                model_name="base",
                retries=0,
            )

            self.assertEqual(summary["failed"], 1)
            postmortem_path = Path(temp_dir, "transcriptions", "postmortem.jsonl")
            self.assertTrue(postmortem_path.exists())
            lines = postmortem_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            failure_record = json.loads(lines[0])
            self.assertEqual(failure_record["error_type"], "RuntimeError")
            self.assertEqual(failure_record["source_path"], str(Path(temp_dir, "speech.wav")))
            self.assertEqual(failure_record["file"], str(Path(temp_dir, "speech.wav")))

    def test_process_directory_rejects_invalid_export_bundle(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")

            with self.assertRaises(ValueError) as ctx:
                transcribe_audio.process_directory(temp_dir, export_bundle="")
            self.assertIn("--export-bundle", str(ctx.exception))

    def test_process_directory_rejects_invalid_language(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")

            with self.assertRaises(ValueError) as ctx:
                transcribe_audio.process_directory(temp_dir, language="")
            self.assertIn("--language", str(ctx.exception))

    @patch("transcribe_audio.transcribe_file")
    @patch("transcribe_audio.load_model")
    def test_process_directory_uses_language_hint(self, mock_load_model, mock_transcribe_file):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir, "speech.wav")
            input_path.write_text("dummy", encoding="utf-8")

            mock_load_model.return_value = object()
            mock_transcribe_file.return_value = Result("hello")

            summary = transcribe_audio.process_directory(
                temp_dir,
                model_name="base",
                language="en",
            )

            self.assertEqual(summary["processed"], 1)
            mock_transcribe_file.assert_called_once_with(
                str(input_path),
                model_name="base",
                include_timestamps=True,
                device="auto",
                model=ANY,
                task="transcribe",
                language="en",
            )

    @patch("transcribe_audio.transcribe_file")
    @patch("transcribe_audio.load_model")
    def test_process_directory_uses_task_override(self, mock_load_model, mock_transcribe_file):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir, "speech.wav")
            input_path.write_text("dummy", encoding="utf-8")

            mock_load_model.return_value = object()
            mock_transcribe_file.return_value = Result("hello")

            transcribe_audio.process_directory(
                temp_dir,
                model_name="base",
                task="translate",
            )

            mock_transcribe_file.assert_called_once_with(
                str(input_path),
                model_name="base",
                include_timestamps=True,
                device="auto",
                model=ANY,
                task="translate",
            )

    @patch("transcribe_audio._export_bundle")
    @patch("transcribe_audio.transcribe_file")
    @patch("transcribe_audio.load_model")
    def test_process_directory_exports_bundle(self, mock_load_model, mock_transcribe_file, mock_export_bundle):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir, "speech.wav")
            input_path.write_text("dummy", encoding="utf-8")

            mock_load_model.return_value = object()
            mock_transcribe_file.return_value = Result("hello")

            transcribe_audio.process_directory(
                temp_dir,
                model_name="base",
                export_bundle="run_bundle.zip",
            )

            output_file = Path(temp_dir, "transcriptions", "speech_transcription.txt")
            self.assertTrue(output_file.exists())
            mock_export_bundle.assert_called_once()
            self.assertEqual(
                mock_export_bundle.call_args.args[0],
                Path(temp_dir, "run_bundle.zip"),
            )

            summary = mock_export_bundle.call_args.args[2]
            self.assertEqual(summary["total"], 1)
            self.assertEqual(summary["processed"], 1)
            self.assertEqual(summary["failed"], 0)
            self.assertEqual(summary["success"], True)

    @patch("transcribe_audio.transcribe_file")
    @patch("transcribe_audio.load_model")
    def test_process_directory_export_bundle_includes_summary_file(self, mock_load_model, mock_transcribe_file):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir, "speech.wav")
            input_path.write_text("dummy", encoding="utf-8")
            bundle_path = Path(temp_dir, "bundle")

            mock_load_model.return_value = object()
            mock_transcribe_file.return_value = Result("hello")

            transcribe_audio.process_directory(
                temp_dir,
                model_name="base",
                export_bundle=str(bundle_path),
            )

            actual_bundle = Path(temp_dir, "bundle.zip")
            self.assertTrue(actual_bundle.exists())
            with zipfile.ZipFile(actual_bundle, "r") as archive:
                names = set(archive.namelist())
                self.assertIn("transcriptions/speech_transcription.txt", names)
                self.assertIn("run_summary.json", names)
                run_summary = json.loads(archive.read("run_summary.json").decode("utf-8"))
                self.assertEqual(run_summary["processed"], 1)
                self.assertEqual(run_summary["failed"], 0)

    @patch("transcribe_audio.transcribe_file")
    @patch("transcribe_audio.load_model")
    def test_process_directory_export_bundle_with_json_output(self, mock_load_model, mock_transcribe_file):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir, "speech.wav")
            input_path.write_text("dummy", encoding="utf-8")
            result_path = Path(temp_dir, "bundle.json.zip")

            mock_load_model.return_value = object()
            mock_transcribe_file.return_value = ResultWithSegments(
                "hello",
                [Segment(0.0, 1.234, "hello")],
            )

            transcribe_audio.process_directory(
                temp_dir,
                model_name="base",
                output_format="json",
                export_bundle=str(result_path),
            )

            self.assertTrue(result_path.exists())
            with zipfile.ZipFile(result_path, "r") as archive:
                names = set(archive.namelist())
                self.assertIn("transcriptions/speech_transcription.json", names)
                run_summary = json.loads(archive.read("run_summary.json").decode("utf-8"))
                self.assertEqual(run_summary["output_format"], "json")

    @patch("transcribe_audio.zipfile.ZipFile")
    def test_export_bundle_writes_files_in_stable_case_variant_order(self, mock_zipfile):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir, "transcriptions")
            output_dir.mkdir()
            output_a = output_dir / "a_transcription.txt"
            output_b_upper = output_dir / "B_TRANSCRIPTION.txt"
            output_c = output_dir / "c_transcription.txt"
            output_a.write_text("a", encoding="utf-8")
            output_b_upper.write_text("b", encoding="utf-8")
            output_c.write_text("c", encoding="utf-8")

            expected_paths = sorted(
                [output_a, output_b_upper, output_c],
                key=lambda p: (str(p).lower(), str(p)),
            )

            summary = {
                "total": 3,
                "processed": 3,
                "failed": 0,
                "skipped": 0,
                "elapsed_seconds": 0.1,
                "success": True,
                "throughput_files_per_second": 30.0,
            }
            bundle_path = Path(temp_dir, "bundle.zip")
            transcribe_audio._export_bundle(bundle_path, Path(temp_dir), summary)

            archive = mock_zipfile.return_value.__enter__.return_value
            write_calls = [call.args[0] for call in archive.write.call_args_list]
            self.assertEqual([Path(call) for call in write_calls], expected_paths)

    @patch("transcribe_audio._export_bundle")
    @patch("transcribe_audio.load_model")
    def test_process_directory_exports_bundle_with_no_supported_files(self, mock_load_model, mock_export_bundle):
        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "notes.txt").write_text("ignore", encoding="utf-8")
            mock_load_model.return_value = object()

            transcribe_audio.process_directory(
                temp_dir,
                export_bundle="run_bundle",
            )

            mock_export_bundle.assert_called_once_with(
                Path(temp_dir, "run_bundle.zip"),
                Path(temp_dir),
                ANY,
            )

    @patch("transcribe_audio.print")
    @patch("transcribe_audio.transcribe_file")
    @patch("transcribe_audio.load_model")
    def test_main_emits_json_summary(self, mock_load_model, mock_transcribe_file, mock_print):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir, "speech.wav")
            input_path.write_text("dummy", encoding="utf-8")

            mock_load_model.return_value = object()
            mock_transcribe_file.return_value = Result("hello")

            with patch.object(sys, "argv", ["transcribe_audio.py", temp_dir, "--summary-json"]):
                exit_code = transcribe_audio.main()

            self.assertEqual(exit_code, 0)
            summary = json.loads(mock_print.call_args_list[-1].args[0])
            self.assertEqual(summary["processed"], 1)
            self.assertTrue(summary["success"])

    def test_process_directory_returns_counts_on_empty_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "notes.txt").write_text("ignore", encoding="utf-8")

            summary = transcribe_audio.process_directory(temp_dir)

            self.assertEqual(summary["total"], 0)
            self.assertEqual(summary["processed"], 0)
            self.assertEqual(summary["failed"], 0)
            self.assertEqual(summary["skipped"], 0)
            self.assertTrue(summary["success"])
            self.assertGreaterEqual(summary["elapsed_seconds"], 0)
            self.assertEqual(summary["throughput_files_per_second"], 0.0)

    @patch("transcribe_audio.transcribe_file")
    @patch("transcribe_audio.load_model")
    def test_output_is_written(self, mock_load_model, mock_transcribe_file):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir, "speech.mp3")
            input_path.write_text("dummy", encoding="utf-8")

            mock_load_model.return_value = object()
            mock_transcribe_file.return_value = Result("hello")

            transcribe_audio.process_directory(temp_dir, model_name="base", include_timestamps=False)

            output_file = Path(temp_dir, "transcriptions", "speech_transcription.txt")
            self.assertTrue(output_file.exists())
            self.assertEqual(output_file.read_text(encoding="utf-8"), "hello")

    @patch("transcribe_audio.transcribe_file")
    @patch("transcribe_audio.load_model")
    def test_output_paths_are_disambiguated_for_colliding_stems(self, mock_load_model, mock_transcribe_file):
        with tempfile.TemporaryDirectory() as temp_dir:
            mp3_input = Path(temp_dir, "speech.mp3")
            wav_input = Path(temp_dir, "speech.wav")
            mp3_input.write_text("dummy", encoding="utf-8")
            wav_input.write_text("dummy", encoding="utf-8")

            mock_load_model.return_value = object()
            mock_transcribe_file.return_value = Result("hello")

            transcribe_audio.process_directory(temp_dir, model_name="base", include_timestamps=False)

            default_output = Path(temp_dir, "transcriptions", "speech_transcription.txt")
            duplicate_output = Path(temp_dir, "transcriptions", "speech_transcription_2.txt")
            self.assertTrue(default_output.exists())
            self.assertTrue(duplicate_output.exists())
            self.assertEqual(mock_transcribe_file.call_count, 2)

    @patch("transcribe_audio.transcribe_file")
    @patch("transcribe_audio.load_model")
    def test_resume_skips_colliding_stem_outputs(self, mock_load_model, mock_transcribe_file):
        with tempfile.TemporaryDirectory() as temp_dir:
            mp3_input = Path(temp_dir, "speech.mp3")
            wav_input = Path(temp_dir, "speech.wav")
            mp3_input.write_text("dummy", encoding="utf-8")
            wav_input.write_text("dummy", encoding="utf-8")

            mock_load_model.return_value = object()
            mock_transcribe_file.return_value = Result("hello")

            transcribe_audio.process_directory(
                temp_dir,
                model_name="base",
                include_timestamps=False,
                overwrite=True,
            )
            mock_transcribe_file.reset_mock()

            summary = transcribe_audio.process_directory(
                temp_dir,
                model_name="base",
                include_timestamps=False,
                resume=True,
            )

            self.assertEqual(summary["processed"], 0)
            self.assertEqual(summary["skipped"], 2)
            self.assertEqual(summary["failed"], 0)
            self.assertEqual(mock_transcribe_file.call_count, 0)

    @patch("transcribe_audio.transcribe_file")
    @patch("transcribe_audio.load_model")
    def test_output_metadata_is_written(self, mock_load_model, mock_transcribe_file):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir, "speech.mp3")
            input_path.write_text("dummy", encoding="utf-8")

            mock_load_model.return_value = object()
            mock_transcribe_file.return_value = Result("hello")

            transcribe_audio.process_directory(
                temp_dir,
                model_name="base",
                include_timestamps=False,
                language="en",
                overwrite=True,
                retries=1,
                retry_delay=0,
                output_format="txt",
            )

            output_file = Path(temp_dir, "transcriptions", "speech_transcription.txt")
            metadata_file = output_file.with_suffix(".txt.metadata.json")
            self.assertTrue(metadata_file.exists())
            metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
            self.assertEqual(metadata["source_path"], str(input_path))
            self.assertEqual(metadata["output_path"], str(output_file))
            self.assertEqual(metadata["model"], "base")
            self.assertFalse(metadata["include_timestamps"])
            self.assertEqual(metadata["task"], "transcribe")
            self.assertEqual(metadata["language"], "en")
            self.assertTrue(metadata["overwrite"])
            self.assertEqual(metadata["retries"], 1)
            self.assertEqual(metadata["retry_delay"], 0)
            self.assertEqual(metadata["output_format"], "txt")
            self.assertIn("processed_at", metadata)

    @patch("transcribe_audio.transcribe_file")
    @patch("transcribe_audio.load_model")
    def test_output_format_json_is_written(self, mock_load_model, mock_transcribe_file):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir, "speech.mp3")
            input_path.write_text("dummy", encoding="utf-8")

            mock_load_model.return_value = object()
            mock_transcribe_file.return_value = ResultWithSegments(
                "hello",
                [Segment(0.0, 1.234, "hello")],
            )

            transcribe_audio.process_directory(temp_dir, model_name="base", output_format="json")

            output_file = Path(temp_dir, "transcriptions", "speech_transcription.json")
            self.assertTrue(output_file.exists())
            payload = json.loads(output_file.read_text(encoding="utf-8"))
            self.assertEqual(payload["text"], "hello")
            self.assertEqual(payload["segments"][0]["start"], 0.0)
            self.assertEqual(payload["segments"][0]["end"], 1.234)

    @patch("transcribe_audio.transcribe_file")
    @patch("transcribe_audio.load_model")
    def test_output_timestamp_setting_passed_to_transcribe_file(self, mock_load_model, mock_transcribe_file):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir, "speech.mp3")
            input_path.write_text("dummy", encoding="utf-8")

            mock_load_model.return_value = object()
            mock_transcribe_file.return_value = ResultWithSegments(
                "hello",
                [Segment(0.0, 1.234, "hello")],
            )

            output_format_cases = [
                ("txt", False, False),
                ("json", False, False),
                ("srt", False, False),
                ("vtt", False, False),
                ("txt", True, True),
                ("json", True, True),
                ("srt", True, False),
                ("vtt", True, False),
            ]
            for output_format, requested_timestamps, expected_timestamps in output_format_cases:
                with self.subTest(output_format=output_format, include_timestamps=requested_timestamps):
                    mock_transcribe_file.reset_mock()
                    transcribe_audio.process_directory(
                        temp_dir,
                        model_name="base",
                        include_timestamps=requested_timestamps,
                        output_format=output_format,
                        overwrite=True,
                    )
                    call_kwargs = mock_transcribe_file.call_args.kwargs
                    self.assertEqual(
                        call_kwargs["include_timestamps"],
                        expected_timestamps,
                    )
                    metadata_file = Path(
                        temp_dir,
                        "transcriptions",
                        f"speech_transcription.{output_format}.metadata.json",
                    )
                    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
                    self.assertEqual(
                        metadata["include_timestamps"],
                        expected_timestamps,
                    )

    @patch("transcribe_audio.transcribe_file")
    @patch("transcribe_audio.load_model")
    def test_process_directory_exports_annotation_csv(self, mock_load_model, mock_transcribe_file):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir, "speech.mp3")
            input_path.write_text("dummy", encoding="utf-8")

            mock_load_model.return_value = object()
            mock_transcribe_file.return_value = ResultWithSegments(
                "hello",
                [Segment(0.0, 1.234, "hello"), Segment(1.5, 2.25, "next")],
            )

            summary = transcribe_audio.process_directory(
                temp_dir,
                model_name="base",
                output_format="txt",
                annotation_export="annotations.csv",
            )

            annotation_file = Path(temp_dir, "annotations.csv")
            self.assertTrue(annotation_file.exists())
            with open(annotation_file, "r", encoding="utf-8", newline="") as fp:
                rows = list(csv.DictReader(fp))
            self.assertEqual(len(rows), 2)
            self.assertEqual(summary["annotation_records"], 2)
            self.assertEqual(summary["annotation_export"], str(annotation_file))
            self.assertEqual(rows[0]["segment_index"], "1")
            self.assertEqual(rows[0]["start_seconds"], "0.0")
            self.assertEqual(rows[0]["end_seconds"], "1.234")

    @patch("transcribe_audio.transcribe_file")
    @patch("transcribe_audio.load_model")
    def test_process_directory_exports_annotation_jsonl(self, mock_load_model, mock_transcribe_file):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir, "speech.mp3")
            input_path.write_text("dummy", encoding="utf-8")

            mock_load_model.return_value = object()
            mock_transcribe_file.return_value = ResultWithSegments(
                "hello",
                [Segment(0.0, 1.0, "hello")],
            )

            summary = transcribe_audio.process_directory(
                temp_dir,
                model_name="base",
                output_format="txt",
                annotation_export="annotations.jsonl",
            )

            annotation_file = Path(temp_dir, "annotations.jsonl")
            self.assertTrue(annotation_file.exists())
            lines = annotation_file.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            record = json.loads(lines[0])
            self.assertEqual(summary["annotation_records"], 1)
            self.assertEqual(summary["annotation_export"], str(annotation_file))
            self.assertEqual(record["source_path"], str(input_path))
            self.assertEqual(record["segment_index"], 1)

    @patch("transcribe_audio.transcribe_file")
    @patch("transcribe_audio.load_model")
    def test_output_format_srt_is_written(self, mock_load_model, mock_transcribe_file):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir, "speech.mp3")
            input_path.write_text("dummy", encoding="utf-8")

            mock_load_model.return_value = object()
            mock_transcribe_file.return_value = ResultWithSegments(
                "hello",
                [Segment(0.0, 1.234, "hello")],
            )

            transcribe_audio.process_directory(temp_dir, model_name="base", output_format="srt")

            output_file = Path(temp_dir, "transcriptions", "speech_transcription.srt")
            self.assertTrue(output_file.exists())
            self.assertIn("1", output_file.read_text(encoding="utf-8"))
            self.assertIn("00:00:00,000 --> 00:00:01,234", output_file.read_text(encoding="utf-8"))
            self.assertIn("hello", output_file.read_text(encoding="utf-8"))

    @patch("transcribe_audio.transcribe_file")
    @patch("transcribe_audio.load_model")
    def test_output_format_vtt_is_written(self, mock_load_model, mock_transcribe_file):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir, "speech.mp3")
            input_path.write_text("dummy", encoding="utf-8")

            mock_load_model.return_value = object()
            mock_transcribe_file.return_value = ResultWithSegments(
                "hello",
                [Segment(0.0, 1.234, "hello")],
            )

            transcribe_audio.process_directory(temp_dir, model_name="base", output_format="vtt")

            output_file = Path(temp_dir, "transcriptions", "speech_transcription.vtt")
            self.assertTrue(output_file.exists())
            self.assertIn("WEBVTT", output_file.read_text(encoding="utf-8"))
            self.assertIn("00:00:00.000 --> 00:00:01.234", output_file.read_text(encoding="utf-8"))
            self.assertIn("hello", output_file.read_text(encoding="utf-8"))

    @patch("transcribe_audio.transcribe_file")
    @patch("transcribe_audio.load_model")
    def test_output_is_skipped_without_overwrite(self, mock_load_model, mock_transcribe_file):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir, "speech.mp3")
            input_path.write_text("dummy", encoding="utf-8")

            output_dir = Path(temp_dir, "transcriptions")
            output_dir.mkdir()
            output_file = output_dir / "speech_transcription.txt"
            output_file.write_text("existing", encoding="utf-8")

            mock_load_model.return_value = object()
            mock_transcribe_file.return_value = Result("hello")

            summary = transcribe_audio.process_directory(temp_dir, model_name="base", include_timestamps=False)

            self.assertEqual(summary["total"], 1)
            self.assertEqual(summary["processed"], 0)
            self.assertEqual(summary["skipped"], 1)
            self.assertEqual(summary["failed"], 0)
            self.assertTrue(summary["success"])
            self.assertGreaterEqual(summary["elapsed_seconds"], 0)
            self.assertEqual(output_file.read_text(encoding="utf-8"), "existing")
            mock_transcribe_file.assert_not_called()

    @patch("transcribe_audio.transcribe_file")
    @patch("transcribe_audio.load_model")
    def test_output_is_overwritten_when_requested(self, mock_load_model, mock_transcribe_file):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir, "speech.mp3")
            input_path.write_text("dummy", encoding="utf-8")

            output_dir = Path(temp_dir, "transcriptions")
            output_dir.mkdir()
            output_file = output_dir / "speech_transcription.txt"
            output_file.write_text("existing", encoding="utf-8")

            mock_load_model.return_value = object()
            mock_transcribe_file.return_value = Result("hello")

            summary = transcribe_audio.process_directory(
                temp_dir,
                model_name="base",
                include_timestamps=False,
                overwrite=True,
            )

            self.assertEqual(summary["total"], 1)
            self.assertEqual(summary["processed"], 1)
            self.assertEqual(summary["skipped"], 0)
            self.assertEqual(summary["failed"], 0)
            self.assertTrue(summary["success"])
            self.assertGreaterEqual(summary["elapsed_seconds"], 0)
            self.assertEqual(output_file.read_text(encoding="utf-8"), "hello")

    @patch("transcribe_audio.transcribe_file")
    @patch("transcribe_audio.load_model")
    def test_resume_skips_file_with_matching_metadata(self, mock_load_model, mock_transcribe_file):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir, "speech.mp3")
            input_path.write_text("dummy", encoding="utf-8")

            output_dir = Path(temp_dir, "transcriptions")
            output_dir.mkdir()
            output_file = output_dir / "speech_transcription.txt"
            output_file.write_text("existing", encoding="utf-8")
            metadata_path = output_file.with_suffix(".txt.metadata.json")
            metadata_path.write_text(
                json.dumps(
                    {
                        "source_path": str(input_path),
                        "output_path": str(output_file),
                        "model": "base",
                        "include_timestamps": True,
                        "overwrite": False,
                        "retries": 0,
                        "retry_delay": 1.0,
                        "retry_backoff": 2.0,
                        "output_format": "txt",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            mock_load_model.return_value = object()
            mock_transcribe_file.return_value = Result("hello")

            summary = transcribe_audio.process_directory(
                temp_dir,
                model_name="base",
                include_timestamps=True,
                resume=True,
            )

            self.assertEqual(summary["total"], 1)
            self.assertEqual(summary["processed"], 0)
            self.assertEqual(summary["skipped"], 1)
            self.assertEqual(summary["failed"], 0)
            self.assertTrue(summary["success"])
            self.assertGreaterEqual(summary["elapsed_seconds"], 0)
            self.assertEqual(output_file.read_text(encoding="utf-8"), "existing")
            mock_transcribe_file.assert_not_called()

    @patch("transcribe_audio.transcribe_file")
    @patch("transcribe_audio.load_model")
    def test_resume_skips_subtitle_outputs_when_timestamps_request_differs(self, mock_load_model, mock_transcribe_file):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir, "speech.mp3")
            input_path.write_text("dummy", encoding="utf-8")

            output_dir = Path(temp_dir, "transcriptions")
            output_dir.mkdir()
            output_file = output_dir / "speech_transcription.srt"
            output_file.write_text("existing", encoding="utf-8")
            metadata_path = output_file.with_suffix(".srt.metadata.json")
            metadata_path.write_text(
                json.dumps(
                    {
                        "source_path": str(input_path),
                        "output_path": str(output_file),
                        "model": "base",
                        "include_timestamps": False,
                        "overwrite": False,
                        "retries": 0,
                        "retry_delay": 1.0,
                        "retry_backoff": 2.0,
                        "output_format": "srt",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            mock_load_model.return_value = object()
            mock_transcribe_file.return_value = Result("hello")

            summary = transcribe_audio.process_directory(
                temp_dir,
                model_name="base",
                include_timestamps=True,
                output_format="srt",
                resume=True,
            )

            self.assertEqual(summary["total"], 1)
            self.assertEqual(summary["processed"], 0)
            self.assertEqual(summary["skipped"], 1)
            self.assertEqual(summary["failed"], 0)
            self.assertTrue(summary["success"])
            self.assertGreaterEqual(summary["elapsed_seconds"], 0)
            self.assertEqual(output_file.read_text(encoding="utf-8"), "existing")
            mock_transcribe_file.assert_not_called()

    @patch("transcribe_audio.transcribe_file")
    @patch("transcribe_audio.load_model")
    def test_resume_does_not_skip_when_overwrite_is_enabled(self, mock_load_model, mock_transcribe_file):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir, "speech.mp3")
            input_path.write_text("dummy", encoding="utf-8")

            output_dir = Path(temp_dir, "transcriptions")
            output_dir.mkdir()
            output_file = output_dir / "speech_transcription.txt"
            output_file.write_text("existing", encoding="utf-8")
            metadata_path = output_file.with_suffix(".txt.metadata.json")
            metadata_path.write_text(
                json.dumps(
                    {
                        "source_path": str(input_path),
                        "output_path": str(output_file),
                        "model": "base",
                        "include_timestamps": True,
                        "overwrite": False,
                        "retries": 0,
                        "retry_delay": 1.0,
                        "retry_backoff": 2.0,
                        "output_format": "txt",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            mock_load_model.return_value = object()
            mock_transcribe_file.return_value = Result("hello")

            summary = transcribe_audio.process_directory(
                temp_dir,
                model_name="base",
                include_timestamps=True,
                overwrite=True,
                resume=True,
            )

            self.assertEqual(summary["total"], 1)
            self.assertEqual(summary["processed"], 1)
            self.assertEqual(summary["skipped"], 0)
            self.assertEqual(summary["failed"], 0)
            self.assertTrue(summary["success"])
            self.assertGreaterEqual(summary["elapsed_seconds"], 0)
            self.assertEqual(output_file.read_text(encoding="utf-8"), "hello")

    @patch("transcribe_audio.transcribe_file")
    @patch("transcribe_audio.load_model")
    def test_resume_skips_file_with_legacy_metadata_filename(self, mock_load_model, mock_transcribe_file):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir, "speech.mp3")
            input_path.write_text("dummy", encoding="utf-8")

            output_dir = Path(temp_dir, "transcriptions")
            output_dir.mkdir()
            output_file = output_dir / "speech_transcription.txt"
            output_file.write_text("existing", encoding="utf-8")
            metadata_path = output_file.with_name(f"{output_file.stem}.metadata.json")
            metadata_path.write_text(
                json.dumps(
                    {
                        "source_path": str(input_path),
                        "output_path": str(output_file),
                        "model": "base",
                        "include_timestamps": True,
                        "overwrite": False,
                        "retries": 0,
                        "retry_delay": 1.0,
                        "retry_backoff": 2.0,
                        "output_format": "txt",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            mock_load_model.return_value = object()
            mock_transcribe_file.return_value = Result("hello")

            summary = transcribe_audio.process_directory(
                temp_dir,
                model_name="base",
                include_timestamps=True,
                resume=True,
            )

            self.assertEqual(summary["total"], 1)
            self.assertEqual(summary["processed"], 0)
            self.assertEqual(summary["skipped"], 1)
            self.assertEqual(summary["failed"], 0)
            self.assertTrue(summary["success"])
            self.assertGreaterEqual(summary["elapsed_seconds"], 0)
            self.assertEqual(output_file.read_text(encoding="utf-8"), "existing")
            mock_transcribe_file.assert_not_called()

    @patch("transcribe_audio.transcribe_file")
    @patch("transcribe_audio.load_model")
    def test_resume_reprocesses_if_metadata_is_stale(self, mock_load_model, mock_transcribe_file):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir, "speech.mp3")
            input_path.write_text("dummy", encoding="utf-8")

            output_dir = Path(temp_dir, "transcriptions")
            output_dir.mkdir()
            output_file = output_dir / "speech_transcription.txt"
            output_file.write_text("existing", encoding="utf-8")
            metadata_path = output_file.with_suffix(".txt.metadata.json")
            metadata_path.write_text(
                json.dumps(
                    {
                        "source_path": str(input_path),
                        "output_path": str(output_file),
                        "model": "tiny",
                        "include_timestamps": True,
                        "overwrite": False,
                        "retries": 0,
                        "retry_delay": 1.0,
                        "retry_backoff": 2.0,
                        "output_format": "txt",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            mock_load_model.return_value = object()
            mock_transcribe_file.return_value = Result("hello")

            summary = transcribe_audio.process_directory(
                temp_dir,
                model_name="base",
                include_timestamps=True,
                overwrite=True,
                resume=True,
            )

            self.assertEqual(summary["total"], 1)
            self.assertEqual(summary["processed"], 1)
            self.assertEqual(summary["skipped"], 0)
            self.assertEqual(summary["failed"], 0)
            self.assertTrue(summary["success"])
            self.assertGreaterEqual(summary["elapsed_seconds"], 0)
            self.assertEqual(output_file.read_text(encoding="utf-8"), "hello")
            mock_transcribe_file.assert_called_once_with(
                str(input_path),
                model_name="base",
                include_timestamps=True,
                device="auto",
                model=ANY,
                task="transcribe",
            )

    @patch("transcribe_audio.transcribe_file")
    @patch("transcribe_audio.load_model")
    def test_resume_reprocesses_if_metadata_is_stale_without_overwrite(self, mock_load_model, mock_transcribe_file):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir, "speech.mp3")
            input_path.write_text("dummy", encoding="utf-8")

            output_dir = Path(temp_dir, "transcriptions")
            output_dir.mkdir()
            output_file = output_dir / "speech_transcription.txt"
            output_file.write_text("existing", encoding="utf-8")
            metadata_path = output_file.with_suffix(".txt.metadata.json")
            metadata_path.write_text(
                json.dumps(
                    {
                        "source_path": str(input_path),
                        "output_path": str(output_file),
                        "model": "tiny",
                        "include_timestamps": True,
                        "overwrite": False,
                        "retries": 0,
                        "retry_delay": 1.0,
                        "retry_backoff": 2.0,
                        "output_format": "txt",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            mock_load_model.return_value = object()
            mock_transcribe_file.return_value = Result("hello")

            summary = transcribe_audio.process_directory(
                temp_dir,
                model_name="base",
                include_timestamps=True,
                resume=True,
            )

            self.assertEqual(summary["total"], 1)
            self.assertEqual(summary["processed"], 1)
            self.assertEqual(summary["skipped"], 0)
            self.assertEqual(summary["failed"], 0)
            self.assertTrue(summary["success"])
            self.assertGreaterEqual(summary["elapsed_seconds"], 0)
            self.assertEqual(output_file.read_text(encoding="utf-8"), "hello")
            mock_transcribe_file.assert_called_once_with(
                str(input_path),
                model_name="base",
                include_timestamps=True,
                device="auto",
                model=ANY,
                task="transcribe",
            )

    @patch("transcribe_audio.transcribe_file")
    @patch("transcribe_audio.load_model")
    def test_resume_reprocesses_when_metadata_is_invalid(self, mock_load_model, mock_transcribe_file):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir, "speech.mp3")
            input_path.write_text("dummy", encoding="utf-8")

            output_dir = Path(temp_dir, "transcriptions")
            output_dir.mkdir()
            output_file = output_dir / "speech_transcription.txt"
            output_file.write_text("existing", encoding="utf-8")
            metadata_path = output_file.with_suffix(".txt.metadata.json")
            metadata_path.write_text("not json", encoding="utf-8")

            mock_load_model.return_value = object()
            mock_transcribe_file.return_value = Result("hello")

            summary = transcribe_audio.process_directory(
                temp_dir,
                model_name="base",
                include_timestamps=True,
                overwrite=True,
                resume=True,
            )

            self.assertEqual(summary["total"], 1)
            self.assertEqual(summary["processed"], 1)
            self.assertEqual(summary["skipped"], 0)
            self.assertEqual(summary["failed"], 0)
            self.assertTrue(summary["success"])
            self.assertGreaterEqual(summary["elapsed_seconds"], 0)
            self.assertEqual(output_file.read_text(encoding="utf-8"), "hello")
            mock_transcribe_file.assert_called_once_with(
                str(input_path),
                model_name="base",
                include_timestamps=True,
                device="auto",
                model=ANY,
                task="transcribe",
            )

    @patch("transcribe_audio.transcribe_file")
    @patch("transcribe_audio.load_model")
    def test_resume_reprocesses_without_overwrite_when_metadata_is_invalid(
        self,
        mock_load_model,
        mock_transcribe_file,
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir, "speech.mp3")
            input_path.write_text("dummy", encoding="utf-8")

            output_dir = Path(temp_dir, "transcriptions")
            output_dir.mkdir()
            output_file = output_dir / "speech_transcription.txt"
            output_file.write_text("existing", encoding="utf-8")
            metadata_path = output_file.with_suffix(".txt.metadata.json")
            metadata_path.write_text("not json", encoding="utf-8")

            mock_load_model.return_value = object()
            mock_transcribe_file.return_value = Result("hello")

            summary = transcribe_audio.process_directory(
                temp_dir,
                model_name="base",
                include_timestamps=True,
                resume=True,
            )

            self.assertEqual(summary["total"], 1)
            self.assertEqual(summary["processed"], 1)
            self.assertEqual(summary["skipped"], 0)
            self.assertEqual(summary["failed"], 0)
            self.assertTrue(summary["success"])
            self.assertGreaterEqual(summary["elapsed_seconds"], 0)
            self.assertEqual(output_file.read_text(encoding="utf-8"), "hello")
            mock_transcribe_file.assert_called_once_with(
                str(input_path),
                model_name="base",
                include_timestamps=True,
                device="auto",
                model=ANY,
                task="transcribe",
            )

    @patch("transcribe_audio.transcribe_file")
    @patch("transcribe_audio.load_model")
    def test_resume_reprocesses_for_subtitle_output_when_metadata_is_invalid(
        self,
        mock_load_model,
        mock_transcribe_file,
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir, "speech.mp3")
            input_path.write_text("dummy", encoding="utf-8")

            output_dir = Path(temp_dir, "transcriptions")
            output_dir.mkdir()
            output_file = output_dir / "speech_transcription.srt"
            output_file.write_text("existing", encoding="utf-8")
            metadata_path = output_file.with_suffix(".srt.metadata.json")
            metadata_path.write_text("not json", encoding="utf-8")

            mock_load_model.return_value = object()
            mock_transcribe_file.return_value = ResultWithSegments(
                "hello",
                [Segment(0.0, 1.234, "hello")],
            )

            summary = transcribe_audio.process_directory(
                temp_dir,
                model_name="base",
                include_timestamps=True,
                output_format="srt",
                resume=True,
            )

            self.assertEqual(summary["total"], 1)
            self.assertEqual(summary["processed"], 1)
            self.assertEqual(summary["skipped"], 0)
            self.assertEqual(summary["failed"], 0)
            self.assertTrue(summary["success"])
            self.assertGreaterEqual(summary["elapsed_seconds"], 0)
            self.assertIn("00:00:00,000 -->", output_file.read_text(encoding="utf-8"))
            mock_transcribe_file.assert_called_once_with(
                str(input_path),
                model_name="base",
                include_timestamps=False,
                device="auto",
                model=ANY,
                task="transcribe",
            )

    @patch("transcribe_audio.transcribe_file")
    @patch("transcribe_audio.load_model")
    def test_transient_failure_is_retried(self, mock_load_model, mock_transcribe_file):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir, "speech.mp3")
            input_path.write_text("dummy", encoding="utf-8")

            mock_load_model.return_value = object()
            mock_transcribe_file.side_effect = [Exception("interrupted"), Result("hello")]

            summary = transcribe_audio.process_directory(
                temp_dir,
                model_name="base",
                include_timestamps=False,
                retries=1,
                retry_delay=0,
            )

            self.assertEqual(summary["processed"], 1)
            self.assertEqual(summary["failed"], 0)
            self.assertTrue(summary["success"])
            self.assertGreaterEqual(summary["elapsed_seconds"], 0)
            self.assertEqual(mock_transcribe_file.call_count, 2)

    @patch("transcribe_audio.transcribe_file")
    @patch("transcribe_audio.load_model")
    def test_transient_failures_exhaust_retries(self, mock_load_model, mock_transcribe_file):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir, "speech.mp3")
            input_path.write_text("dummy", encoding="utf-8")

            mock_load_model.return_value = object()
            mock_transcribe_file.side_effect = Exception("interrupted")

            summary = transcribe_audio.process_directory(
                temp_dir,
                model_name="base",
                include_timestamps=False,
                retries=1,
                retry_delay=0,
            )

            self.assertEqual(summary["processed"], 0)
            self.assertEqual(summary["failed"], 1)
            self.assertFalse(summary["success"])
            self.assertGreaterEqual(summary["elapsed_seconds"], 0)
            self.assertEqual(mock_transcribe_file.call_count, 2)

    @patch("transcribe_audio.time.sleep")
    @patch("transcribe_audio.transcribe_file")
    @patch("transcribe_audio.load_model")
    def test_retry_uses_exponential_backoff(self, mock_load_model, mock_transcribe_file, mock_sleep):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir, "speech.wav")
            input_path.write_text("dummy", encoding="utf-8")

            mock_load_model.return_value = object()
            mock_transcribe_file.side_effect = [Exception("interrupted"), Exception("interrupted"), Result("hello")]

            summary = transcribe_audio.process_directory(
                temp_dir,
                model_name="base",
                include_timestamps=False,
                retries=2,
                retry_delay=0.5,
                retry_backoff=2.0,
            )

            self.assertEqual(summary["processed"], 1)
            self.assertEqual(summary["failed"], 0)
            self.assertEqual(mock_transcribe_file.call_count, 3)
            self.assertEqual(mock_sleep.call_count, 2)
            self.assertEqual(mock_sleep.call_args_list[0].args[0], 0.5)
            self.assertEqual(mock_sleep.call_args_list[1].args[0], 1.0)

    @patch("transcribe_audio.transcribe_file")
    @patch("transcribe_audio.load_model")
    def test_output_write_failure_is_marked_failed(self, mock_load_model, mock_transcribe_file):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir, "speech.wav")
            input_path.write_text("dummy", encoding="utf-8")

            mock_load_model.return_value = object()
            mock_transcribe_file.return_value = Result("hello")

            with patch("builtins.open", side_effect=PermissionError("no write access")):
                summary = transcribe_audio.process_directory(
                    temp_dir,
                    model_name="base",
                    include_timestamps=False,
                    retries=0,
                )

            self.assertEqual(summary["processed"], 0)
            self.assertEqual(summary["failed"], 1)
            self.assertFalse(summary["success"])

    def test_rejects_invalid_retry_backoff(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                transcribe_audio.process_directory(temp_dir, retry_backoff=0)
            self.assertIn("--retry-backoff", str(ctx.exception))

    def test_runtime_python_version_check_accepts_supported_version(self):
        with patch("transcribe_audio.sys.version_info", (3, 13, 0, "final", 0)):
            transcribe_audio._validate_runtime_python_version()

    def test_runtime_python_version_check_rejects_old_python(self):
        with patch("transcribe_audio.sys.version_info", (3, 8, 0, "final", 0)):
            with self.assertRaises(RuntimeError) as ctx:
                transcribe_audio._validate_runtime_python_version()
            self.assertIn("Unsupported Python version 3.8", str(ctx.exception))

    def test_runtime_python_version_check_rejects_future_python(self):
        with patch("transcribe_audio.sys.version_info", (3, 14, 0, "final", 0)):
            with self.assertRaises(RuntimeError) as ctx:
                transcribe_audio._validate_runtime_python_version()
            self.assertIn("currently validates only up to Python 3.13", str(ctx.exception))

    @patch("transcribe_audio._validate_runtime_python_version")
    def test_main_rejects_unsupported_python_version(self, mock_validate_python):
        mock_validate_python.side_effect = RuntimeError("Unsupported Python version 3.14")
        with patch.object(sys, "argv", ["transcribe_audio.py", "."]):
            exit_code = transcribe_audio.main()

        self.assertEqual(exit_code, 1)
        mock_validate_python.assert_called_once_with()

    @patch("transcribe_audio.main")
    def test_cli_entrypoint_exits_with_main_return_code(self, mock_main):
        mock_main.return_value = 7
        with self.assertRaises(SystemExit) as ctx:
            transcribe_audio.cli()

        self.assertEqual(ctx.exception.code, 7)
        mock_main.assert_called_once_with()

    @patch("transcribe_audio.process_directory")
    @patch("transcribe_audio.print")
    def test_main_accepts_supported_models(self, mock_print, mock_process_directory):
        summary = {
            "total": 1,
            "processed": 1,
            "failed": 0,
            "skipped": 0,
            "elapsed_seconds": 0,
            "success": True,
            "throughput_files_per_second": 1.0,
        }
        mock_process_directory.return_value = summary

        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")

            for model_name in transcribe_audio.SUPPORTED_MODELS:
                mock_process_directory.reset_mock()
                with self.subTest(model=model_name), patch.object(
                    sys, "argv", ["transcribe_audio.py", temp_dir, "--model", model_name]
                ):
                    self.assertEqual(transcribe_audio.main(), 0)
                    self.assertEqual(
                        mock_process_directory.call_args.kwargs["model_name"],
                        model_name,
                    )

    @patch("transcribe_audio.process_directory")
    def test_main_uses_directory_config_defaults(self, mock_process_directory):
        summary = {
            "total": 1,
            "processed": 1,
            "failed": 0,
            "skipped": 0,
            "elapsed_seconds": 0,
            "success": True,
            "throughput_files_per_second": 1.0,
        }
        mock_process_directory.return_value = summary

        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")
            config = {
                "model": "base",
                "timestamps": False,
                "overwrite": True,
                "retries": 2,
                "retry_delay": 0.5,
                "retry_backoff": 3.0,
                "output_format": "json",
            }
            Path(temp_dir, ".whisperbatch").write_text(json.dumps(config), encoding="utf-8")

            with patch.object(sys, "argv", ["transcribe_audio.py", temp_dir]):
                self.assertEqual(transcribe_audio.main(), 0)

            call_kwargs = mock_process_directory.call_args.kwargs
            self.assertEqual(call_kwargs["model_name"], "base")
            self.assertFalse(call_kwargs["include_timestamps"])
            self.assertTrue(call_kwargs["overwrite"])
            self.assertEqual(call_kwargs["retries"], 2)
            self.assertEqual(call_kwargs["retry_delay"], 0.5)
            self.assertEqual(call_kwargs["retry_backoff"], 3.0)
            self.assertEqual(call_kwargs["output_format"], "json")

    @patch("transcribe_audio.process_directory")
    def test_main_cli_overrides_config(self, mock_process_directory):
        summary = {
            "total": 1,
            "processed": 1,
            "failed": 0,
            "skipped": 0,
            "elapsed_seconds": 0,
            "success": True,
            "throughput_files_per_second": 1.0,
        }
        mock_process_directory.return_value = summary

        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")
            Path(temp_dir, ".whisperbatch").write_text(
                json.dumps(
                    {
                        "model": "base",
                        "timestamps": False,
                        "retries": 1,
                        "output_format": "json",
                    }
                ),
                encoding="utf-8",
            )
            with patch.object(
                sys,
                "argv",
                [
                    "transcribe_audio.py",
                    temp_dir,
                    "--model",
                    "medium",
                    "--timestamps",
                    "--retries",
                    "3",
                ],
            ):
                self.assertEqual(transcribe_audio.main(), 0)

            call_kwargs = mock_process_directory.call_args.kwargs
            self.assertEqual(call_kwargs["model_name"], "medium")
            self.assertTrue(call_kwargs["include_timestamps"])
            self.assertEqual(call_kwargs["retries"], 3)

    @patch("transcribe_audio.process_directory")
    def test_main_reads_explicit_config_path(self, mock_process_directory):
        summary = {
            "total": 1,
            "processed": 1,
            "failed": 0,
            "skipped": 0,
            "elapsed_seconds": 0,
            "success": True,
            "throughput_files_per_second": 1.0,
        }
        mock_process_directory.return_value = summary

        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, dir=temp_dir) as config_file:
                json.dump({"model": "small"}, config_file, ensure_ascii=False)
                config_path = config_file.name

            with patch.object(
                sys,
                "argv",
                [
                    "transcribe_audio.py",
                    temp_dir,
                    "--config",
                    config_path,
                ],
            ):
                self.assertEqual(transcribe_audio.main(), 0)

            call_kwargs = mock_process_directory.call_args.kwargs
            self.assertEqual(call_kwargs["model_name"], "small")

    @patch("transcribe_audio.process_directory")
    def test_main_uses_resume_from_cli(self, mock_process_directory):
        summary = {
            "total": 1,
            "processed": 1,
            "failed": 0,
            "skipped": 0,
            "elapsed_seconds": 0,
            "success": True,
            "throughput_files_per_second": 1.0,
        }
        mock_process_directory.return_value = summary

        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")

            with patch.object(
                sys,
                "argv",
                [
                    "transcribe_audio.py",
                    temp_dir,
                    "--resume",
                ],
            ):
                self.assertEqual(transcribe_audio.main(), 0)

        call_kwargs = mock_process_directory.call_args.kwargs
        self.assertTrue(call_kwargs["resume"])

    @patch("transcribe_audio.process_directory")
    def test_main_uses_max_workers(self, mock_process_directory):
        summary = {
            "total": 1,
            "processed": 1,
            "failed": 0,
            "skipped": 0,
            "elapsed_seconds": 0,
            "success": True,
            "throughput_files_per_second": 1.0,
        }
        mock_process_directory.return_value = summary

        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")

            with patch.object(
                sys,
                "argv",
                [
                    "transcribe_audio.py",
                    temp_dir,
                    "--max-workers",
                    "4",
                ],
            ):
                self.assertEqual(transcribe_audio.main(), 0)

        call_kwargs = mock_process_directory.call_args.kwargs
        self.assertEqual(call_kwargs["max_workers"], 4)

    @patch("transcribe_audio.process_directory")
    def test_main_uses_max_workers_from_config(self, mock_process_directory):
        summary = {
            "total": 1,
            "processed": 1,
            "failed": 0,
            "skipped": 0,
            "elapsed_seconds": 0,
            "success": True,
            "throughput_files_per_second": 1.0,
        }
        mock_process_directory.return_value = summary

        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")
            Path(temp_dir, ".whisperbatch").write_text(
                json.dumps(
                    {
                        "max_workers": 2,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch.object(
                sys,
                "argv",
                [
                    "transcribe_audio.py",
                    temp_dir,
                ],
            ):
                self.assertEqual(transcribe_audio.main(), 0)

            call_kwargs = mock_process_directory.call_args.kwargs
            self.assertEqual(call_kwargs["max_workers"], 2)

    @patch("transcribe_audio.process_directory")
    def test_main_uses_export_bundle_from_config(self, mock_process_directory):
        summary = {
            "total": 1,
            "processed": 1,
            "failed": 0,
            "skipped": 0,
            "elapsed_seconds": 0,
            "success": True,
            "throughput_files_per_second": 1.0,
        }
        mock_process_directory.return_value = summary

        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")
            Path(temp_dir, ".whisperbatch").write_text(
                json.dumps(
                    {
                        "export_bundle": "run_bundle.zip",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch.object(
                sys,
                "argv",
                [
                    "transcribe_audio.py",
                    temp_dir,
                ],
            ):
                self.assertEqual(transcribe_audio.main(), 0)

            call_kwargs = mock_process_directory.call_args.kwargs
            self.assertEqual(call_kwargs["export_bundle"], "run_bundle.zip")

    @patch("transcribe_audio.process_directory")
    def test_main_uses_export_bundle_from_cli(self, mock_process_directory):
        summary = {
            "total": 1,
            "processed": 1,
            "failed": 0,
            "skipped": 0,
            "elapsed_seconds": 0,
            "success": True,
            "throughput_files_per_second": 1.0,
        }
        mock_process_directory.return_value = summary

        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")

            with patch.object(
                sys,
                "argv",
                [
                    "transcribe_audio.py",
                    temp_dir,
                    "--export-bundle",
                    "run_bundle.zip",
                ],
            ):
                self.assertEqual(transcribe_audio.main(), 0)

            call_kwargs = mock_process_directory.call_args.kwargs
            self.assertEqual(call_kwargs["export_bundle"], "run_bundle.zip")

    @patch("transcribe_audio.process_directory")
    def test_main_uses_annotation_export(self, mock_process_directory):
        summary = {
            "total": 1,
            "processed": 1,
            "failed": 0,
            "skipped": 0,
            "elapsed_seconds": 0,
            "success": True,
            "throughput_files_per_second": 1.0,
        }
        mock_process_directory.return_value = summary

        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")

            with patch.object(
                sys,
                "argv",
                [
                    "transcribe_audio.py",
                    temp_dir,
                    "--annotation-export",
                    "run_annotations.jsonl",
                ],
            ):
                self.assertEqual(transcribe_audio.main(), 0)

            call_kwargs = mock_process_directory.call_args.kwargs
            self.assertEqual(call_kwargs["annotation_export"], "run_annotations.jsonl")

    @patch("transcribe_audio.process_directory")
    def test_main_uses_language_from_config(self, mock_process_directory):
        summary = {
            "total": 1,
            "processed": 1,
            "failed": 0,
            "skipped": 0,
            "elapsed_seconds": 0,
            "success": True,
            "throughput_files_per_second": 1.0,
        }
        mock_process_directory.return_value = summary

        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")
            Path(temp_dir, ".whisperbatch").write_text(
                json.dumps(
                    {
                        "language": "en",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch.object(
                sys,
                "argv",
                [
                    "transcribe_audio.py",
                    temp_dir,
                ],
            ):
                self.assertEqual(transcribe_audio.main(), 0)

            call_kwargs = mock_process_directory.call_args.kwargs
            self.assertEqual(call_kwargs["language"], "en")

    @patch("transcribe_audio.process_directory")
    def test_main_uses_language_from_cli(self, mock_process_directory):
        summary = {
            "total": 1,
            "processed": 1,
            "failed": 0,
            "skipped": 0,
            "elapsed_seconds": 0,
            "success": True,
            "throughput_files_per_second": 1.0,
        }
        mock_process_directory.return_value = summary

        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")

            with patch.object(
                sys,
                "argv",
                [
                    "transcribe_audio.py",
                    temp_dir,
                    "--language",
                    "fr",
                ],
            ):
                self.assertEqual(transcribe_audio.main(), 0)

            call_kwargs = mock_process_directory.call_args.kwargs
            self.assertEqual(call_kwargs["language"], "fr")

    @patch("transcribe_audio.process_directory")
    def test_main_uses_language_profile_from_config(self, mock_process_directory):
        summary = {
            "total": 1,
            "processed": 1,
            "failed": 0,
            "skipped": 0,
            "elapsed_seconds": 0,
            "success": True,
            "throughput_files_per_second": 1.0,
        }
        mock_process_directory.return_value = summary

        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")
            Path(temp_dir, ".whisperbatch").write_text(
                json.dumps(
                    {
                        "language_profiles": {
                            "spanish-interview": {
                                "language": "es",
                                "task": "transcribe",
                            },
                        },
                        "language_profile": "spanish-interview",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch.object(
                sys,
                "argv",
                [
                    "transcribe_audio.py",
                    temp_dir,
                ],
            ):
                self.assertEqual(transcribe_audio.main(), 0)

            call_kwargs = mock_process_directory.call_args.kwargs
            self.assertEqual(call_kwargs["language"], "es")
            self.assertEqual(call_kwargs["task"], "transcribe")

    @patch("transcribe_audio.process_directory")
    def test_main_uses_language_profile_model_override_from_config(self, mock_process_directory):
        summary = {
            "total": 1,
            "processed": 1,
            "failed": 0,
            "skipped": 0,
            "elapsed_seconds": 0,
            "success": True,
            "throughput_files_per_second": 1.0,
        }
        mock_process_directory.return_value = summary

        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")
            Path(temp_dir, ".whisperbatch").write_text(
                json.dumps(
                    {
                        "model": "tiny",
                        "language_profiles": {
                            "spanish-interview": {
                                "model": "base",
                                "language": "es",
                                "task": "transcribe",
                            },
                        },
                        "language_profile": "spanish-interview",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch.object(
                sys,
                "argv",
                [
                    "transcribe_audio.py",
                    temp_dir,
                ],
            ):
                self.assertEqual(transcribe_audio.main(), 0)

            call_kwargs = mock_process_directory.call_args.kwargs
            self.assertEqual(call_kwargs["model_name"], "base")
            self.assertEqual(call_kwargs["language"], "es")
            self.assertEqual(call_kwargs["task"], "transcribe")

    @patch("transcribe_audio.process_directory")
    def test_main_cli_overrides_profile_model(self, mock_process_directory):
        summary = {
            "total": 1,
            "processed": 1,
            "failed": 0,
            "skipped": 0,
            "elapsed_seconds": 0,
            "success": True,
            "throughput_files_per_second": 1.0,
        }
        mock_process_directory.return_value = summary

        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")
            Path(temp_dir, ".whisperbatch").write_text(
                json.dumps(
                    {
                        "model": "tiny",
                        "language_profiles": {
                            "spanish-interview": {
                                "model": "base",
                                "language": "es",
                                "task": "translate",
                            },
                        },
                        "language_profile": "spanish-interview",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch.object(
                sys,
                "argv",
                [
                    "transcribe_audio.py",
                    temp_dir,
                    "--language-profile",
                    "spanish-interview",
                    "--model",
                    "small",
                ],
            ):
                self.assertEqual(transcribe_audio.main(), 0)

            call_kwargs = mock_process_directory.call_args.kwargs
            self.assertEqual(call_kwargs["model_name"], "small")
            self.assertEqual(call_kwargs["language"], "es")
            self.assertEqual(call_kwargs["task"], "translate")

    @patch("transcribe_audio.process_directory")
    def test_main_language_profile_cli_sets_model(self, mock_process_directory):
        summary = {
            "total": 1,
            "processed": 1,
            "failed": 0,
            "skipped": 0,
            "elapsed_seconds": 0,
            "success": True,
            "throughput_files_per_second": 1.0,
        }
        mock_process_directory.return_value = summary

        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")
            Path(temp_dir, ".whisperbatch").write_text(
                json.dumps(
                    {
                        "language_profiles": {
                            "spanish-interview": {
                                "model": "base",
                                "language": "es",
                                "task": "translate",
                            },
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch.object(
                sys,
                "argv",
                [
                    "transcribe_audio.py",
                    temp_dir,
                    "--language-profile",
                    "spanish-interview",
                ],
            ):
                self.assertEqual(transcribe_audio.main(), 0)

            call_kwargs = mock_process_directory.call_args.kwargs
            self.assertEqual(call_kwargs["model_name"], "base")
            self.assertEqual(call_kwargs["language"], "es")

    @patch("transcribe_audio.process_directory")
    def test_main_uses_speaker_profile_from_config(self, mock_process_directory):
        summary = {
            "total": 1,
            "processed": 1,
            "failed": 0,
            "skipped": 0,
            "elapsed_seconds": 0,
            "success": True,
            "throughput_files_per_second": 1.0,
        }
        mock_process_directory.return_value = summary

        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")
            Path(temp_dir, ".whisperbatch").write_text(
                json.dumps(
                    {
                        "language": "en",
                        "task": "transcribe",
                        "speaker_profiles": {
                            "guest": {
                                "language": "fr",
                                "task": "translate",
                            },
                        },
                        "speaker_profile": "guest",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch.object(
                sys,
                "argv",
                [
                    "transcribe_audio.py",
                    temp_dir,
                ],
            ):
                self.assertEqual(transcribe_audio.main(), 0)

            call_kwargs = mock_process_directory.call_args.kwargs
            self.assertEqual(call_kwargs["language"], "fr")
            self.assertEqual(call_kwargs["task"], "translate")

    @patch("transcribe_audio.process_directory")
    def test_main_uses_language_profile_from_cli(self, mock_process_directory):
        summary = {
            "total": 1,
            "processed": 1,
            "failed": 0,
            "skipped": 0,
            "elapsed_seconds": 0,
            "success": True,
            "throughput_files_per_second": 1.0,
        }
        mock_process_directory.return_value = summary

        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")
            Path(temp_dir, ".whisperbatch").write_text(
                json.dumps(
                    {
                        "language_profiles": {
                            "spanish-interview": {
                                "language": "es",
                            },
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch.object(
                sys,
                "argv",
                [
                    "transcribe_audio.py",
                    temp_dir,
                    "--language-profile",
                    "spanish-interview",
                ],
            ):
                self.assertEqual(transcribe_audio.main(), 0)

            call_kwargs = mock_process_directory.call_args.kwargs
            self.assertEqual(call_kwargs["language"], "es")

    @patch("transcribe_audio.process_directory")
    def test_main_uses_speaker_profile_from_cli(self, mock_process_directory):
        summary = {
            "total": 1,
            "processed": 1,
            "failed": 0,
            "skipped": 0,
            "elapsed_seconds": 0,
            "success": True,
            "throughput_files_per_second": 1.0,
        }
        mock_process_directory.return_value = summary

        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")
            Path(temp_dir, ".whisperbatch").write_text(
                json.dumps(
                    {
                        "speaker_profiles": {
                            "guest": {
                                "task": "translate",
                                "language": "de",
                            },
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch.object(
                sys,
                "argv",
                [
                    "transcribe_audio.py",
                    temp_dir,
                    "--speaker-profile",
                    "guest",
                ],
            ):
                self.assertEqual(transcribe_audio.main(), 0)

            call_kwargs = mock_process_directory.call_args.kwargs
            self.assertEqual(call_kwargs["language"], "de")
            self.assertEqual(call_kwargs["task"], "translate")

    @patch("transcribe_audio.process_directory")
    def test_main_speaker_profile_cli_sets_model(self, mock_process_directory):
        summary = {
            "total": 1,
            "processed": 1,
            "failed": 0,
            "skipped": 0,
            "elapsed_seconds": 0,
            "success": True,
            "throughput_files_per_second": 1.0,
        }
        mock_process_directory.return_value = summary

        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")
            Path(temp_dir, ".whisperbatch").write_text(
                json.dumps(
                    {
                        "model": "tiny",
                        "speaker_profiles": {
                            "guest": {
                                "model": "base",
                                "language": "fr",
                                "task": "translate",
                            },
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch.object(
                sys,
                "argv",
                [
                    "transcribe_audio.py",
                    temp_dir,
                    "--speaker-profile",
                    "guest",
                ],
            ):
                self.assertEqual(transcribe_audio.main(), 0)

            call_kwargs = mock_process_directory.call_args.kwargs
            self.assertEqual(call_kwargs["model_name"], "base")
            self.assertEqual(call_kwargs["language"], "fr")
            self.assertEqual(call_kwargs["task"], "translate")

    @patch("transcribe_audio.process_directory")
    def test_main_rejects_unknown_language_profile_from_config(self, mock_process_directory):
        summary = {
            "total": 1,
            "processed": 1,
            "failed": 0,
            "skipped": 0,
            "elapsed_seconds": 0,
            "success": True,
            "throughput_files_per_second": 1.0,
        }
        mock_process_directory.return_value = summary

        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")
            Path(temp_dir, ".whisperbatch").write_text(
                json.dumps(
                    {
                        "language_profiles": {
                            "spanish": {"language": "es"},
                        },
                        "language_profile": "not-a-profile",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch.object(
                sys,
                "argv",
                [
                    "transcribe_audio.py",
                    temp_dir,
                ],
            ):
                self.assertEqual(transcribe_audio.main(), 1)

            mock_process_directory.assert_not_called()

    @patch("transcribe_audio.process_directory")
    def test_main_rejects_unknown_speaker_profile_from_cli(self, mock_process_directory):
        summary = {
            "total": 1,
            "processed": 1,
            "failed": 0,
            "skipped": 0,
            "elapsed_seconds": 0,
            "success": True,
            "throughput_files_per_second": 1.0,
        }
        mock_process_directory.return_value = summary

        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")
            Path(temp_dir, ".whisperbatch").write_text(
                json.dumps(
                    {
                        "speaker_profiles": {
                            "guest": {"language": "en"},
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch.object(
                sys,
                "argv",
                [
                    "transcribe_audio.py",
                    temp_dir,
                    "--speaker-profile",
                    "unknown",
                ],
            ):
                self.assertEqual(transcribe_audio.main(), 1)

            mock_process_directory.assert_not_called()

    @patch("transcribe_audio.process_directory")
    def test_main_rejects_invalid_export_bundle_from_config(self, mock_process_directory):
        summary = {
            "total": 1,
            "processed": 1,
            "failed": 0,
            "skipped": 0,
            "elapsed_seconds": 0,
            "success": True,
            "throughput_files_per_second": 1.0,
        }
        mock_process_directory.return_value = summary

        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")
            Path(temp_dir, ".whisperbatch").write_text(
                json.dumps(
                    {
                        "export_bundle": "",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch.object(
                sys,
                "argv",
                [
                    "transcribe_audio.py",
                    temp_dir,
                ],
            ):
                self.assertEqual(transcribe_audio.main(), 1)

            mock_process_directory.assert_not_called()

    @patch("transcribe_audio.process_directory")
    def test_main_rejects_invalid_language_from_config(self, mock_process_directory):
        summary = {
            "total": 1,
            "processed": 1,
            "failed": 0,
            "skipped": 0,
            "elapsed_seconds": 0,
            "success": True,
            "throughput_files_per_second": 1.0,
        }
        mock_process_directory.return_value = summary

        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")
            Path(temp_dir, ".whisperbatch").write_text(
                json.dumps(
                    {
                        "language": "",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch.object(
                sys,
                "argv",
                [
                    "transcribe_audio.py",
                    temp_dir,
                ],
            ):
                self.assertEqual(transcribe_audio.main(), 1)

            mock_process_directory.assert_not_called()

    @patch("transcribe_audio.process_directory")
    def test_main_uses_task_from_config(self, mock_process_directory):
        summary = {
            "total": 1,
            "processed": 1,
            "failed": 0,
            "skipped": 0,
            "elapsed_seconds": 0,
            "success": True,
            "throughput_files_per_second": 1.0,
        }
        mock_process_directory.return_value = summary

        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")
            Path(temp_dir, ".whisperbatch").write_text(
                json.dumps(
                    {
                        "task": "translate",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch.object(
                sys,
                "argv",
                [
                    "transcribe_audio.py",
                    temp_dir,
                ],
            ):
                self.assertEqual(transcribe_audio.main(), 0)

            call_kwargs = mock_process_directory.call_args.kwargs
            self.assertEqual(call_kwargs["task"], "translate")

    @patch("transcribe_audio.process_directory")
    def test_main_uses_task_from_cli(self, mock_process_directory):
        summary = {
            "total": 1,
            "processed": 1,
            "failed": 0,
            "skipped": 0,
            "elapsed_seconds": 0,
            "success": True,
            "throughput_files_per_second": 1.0,
        }
        mock_process_directory.return_value = summary

        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")

            with patch.object(
                sys,
                "argv",
                [
                    "transcribe_audio.py",
                    temp_dir,
                    "--task",
                    "translate",
                ],
            ):
                self.assertEqual(transcribe_audio.main(), 0)

            call_kwargs = mock_process_directory.call_args.kwargs
            self.assertEqual(call_kwargs["task"], "translate")

    @patch("transcribe_audio.process_directory")
    def test_main_rejects_invalid_task_from_config(self, mock_process_directory):
        summary = {
            "total": 1,
            "processed": 1,
            "failed": 0,
            "skipped": 0,
            "elapsed_seconds": 0,
            "success": True,
            "throughput_files_per_second": 1.0,
        }
        mock_process_directory.return_value = summary

        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")
            Path(temp_dir, ".whisperbatch").write_text(
                json.dumps(
                    {
                        "task": "not-real",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch.object(
                sys,
                "argv",
                [
                    "transcribe_audio.py",
                    temp_dir,
                ],
            ):
                self.assertEqual(transcribe_audio.main(), 1)

            mock_process_directory.assert_not_called()

    @patch("transcribe_audio.process_directory")
    def test_main_uses_postprocess_command_from_config(self, mock_process_directory):
        summary = {
            "total": 1,
            "processed": 1,
            "failed": 0,
            "skipped": 0,
            "elapsed_seconds": 0,
            "success": True,
            "throughput_files_per_second": 1.0,
        }
        mock_process_directory.return_value = summary

        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")
            Path(temp_dir, ".whisperbatch").write_text(
                json.dumps(
                    {
                        "postprocess_command": "python -m scripts.postprocess",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch.object(
                sys,
                "argv",
                [
                    "transcribe_audio.py",
                    temp_dir,
                ],
            ):
                self.assertEqual(transcribe_audio.main(), 0)

            call_kwargs = mock_process_directory.call_args.kwargs
            self.assertEqual(call_kwargs["postprocess_command"], "python -m scripts.postprocess")

    @patch("transcribe_audio.process_directory")
    def test_main_uses_postprocess_command_from_cli(self, mock_process_directory):
        summary = {
            "total": 1,
            "processed": 1,
            "failed": 0,
            "skipped": 0,
            "elapsed_seconds": 0,
            "success": True,
            "throughput_files_per_second": 1.0,
        }
        mock_process_directory.return_value = summary

        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")

            with patch.object(
                sys,
                "argv",
                [
                    "transcribe_audio.py",
                    temp_dir,
                    "--postprocess-cmd",
                    "echo done",
                ],
            ):
                self.assertEqual(transcribe_audio.main(), 0)

            call_kwargs = mock_process_directory.call_args.kwargs
            self.assertEqual(call_kwargs["postprocess_command"], "echo done")

    @patch("transcribe_audio.process_directory")
    def test_main_uses_postprocess_plugin_from_config(self, mock_process_directory):
        summary = {
            "total": 1,
            "processed": 1,
            "failed": 0,
            "skipped": 0,
            "elapsed_seconds": 0,
            "success": True,
            "throughput_files_per_second": 1.0,
        }
        mock_process_directory.return_value = summary

        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")
            Path(temp_dir, ".whisperbatch").write_text(
                json.dumps(
                    {
                        "postprocess_plugin": "plugins.rewrite:post_hook",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch.object(
                sys,
                "argv",
                [
                    "transcribe_audio.py",
                    temp_dir,
                ],
            ):
                self.assertEqual(transcribe_audio.main(), 0)

            call_kwargs = mock_process_directory.call_args.kwargs
            self.assertEqual(call_kwargs["postprocess_plugin"], "plugins.rewrite:post_hook")

    @patch("transcribe_audio.process_directory")
    def test_main_uses_postprocess_plugin_from_cli(self, mock_process_directory):
        summary = {
            "total": 1,
            "processed": 1,
            "failed": 0,
            "skipped": 0,
            "elapsed_seconds": 0,
            "success": True,
            "throughput_files_per_second": 1.0,
        }
        mock_process_directory.return_value = summary

        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")

            with patch.object(
                sys,
                "argv",
                [
                    "transcribe_audio.py",
                    temp_dir,
                    "--postprocess-plugin",
                    "plugins.rewrite:post_hook",
                ],
            ):
                self.assertEqual(transcribe_audio.main(), 0)

            call_kwargs = mock_process_directory.call_args.kwargs
            self.assertEqual(call_kwargs["postprocess_plugin"], "plugins.rewrite:post_hook")

    @patch("transcribe_audio.process_directory")
    def test_main_rejects_invalid_postprocess_plugin_from_config(self, mock_process_directory):
        summary = {
            "total": 1,
            "processed": 1,
            "failed": 0,
            "skipped": 0,
            "elapsed_seconds": 0,
            "success": True,
            "throughput_files_per_second": 1.0,
        }
        mock_process_directory.return_value = summary

        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")
            Path(temp_dir, ".whisperbatch").write_text(
                json.dumps(
                    {
                        "postprocess_plugin": "broken",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch.object(
                sys,
                "argv",
                [
                    "transcribe_audio.py",
                    temp_dir,
                ],
            ):
                self.assertEqual(transcribe_audio.main(), 1)

            mock_process_directory.assert_not_called()

    def test_main_rejects_missing_postprocess_plugin_module(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")

            with patch.object(
                sys,
                "argv",
                [
                    "transcribe_audio.py",
                    temp_dir,
                    "--postprocess-plugin",
                    "missing_module:transform_output",
                ],
            ):
                self.assertEqual(transcribe_audio.main(), 1)

    @patch("transcribe_audio.process_directory")
    def test_main_rejects_invalid_postprocess_command_from_config(self, mock_process_directory):
        summary = {
            "total": 1,
            "processed": 1,
            "failed": 0,
            "skipped": 0,
            "elapsed_seconds": 0,
            "success": True,
            "throughput_files_per_second": 1.0,
        }
        mock_process_directory.return_value = summary

        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")
            Path(temp_dir, ".whisperbatch").write_text(
                json.dumps(
                    {
                        "postprocess_command": "",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch.object(
                sys,
                "argv",
                [
                    "transcribe_audio.py",
                    temp_dir,
                ],
            ):
                self.assertEqual(transcribe_audio.main(), 1)

            mock_process_directory.assert_not_called()

    @patch("transcribe_audio.process_directory")
    def test_main_rejects_invalid_max_workers_from_config(self, mock_process_directory):
        summary = {
            "total": 1,
            "processed": 1,
            "failed": 0,
            "skipped": 0,
            "elapsed_seconds": 0,
            "success": True,
            "throughput_files_per_second": 1.0,
        }
        mock_process_directory.return_value = summary

        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")
            Path(temp_dir, ".whisperbatch").write_text(
                json.dumps(
                    {
                        "max_workers": 0,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch.object(
                sys,
                "argv",
                [
                    "transcribe_audio.py",
                    temp_dir,
                ],
            ):
                self.assertEqual(transcribe_audio.main(), 1)

            mock_process_directory.assert_not_called()

    @patch("transcribe_audio.process_directory")
    def test_main_invalid_config_rejects(self, mock_process_directory):
        summary = {
            "total": 1,
            "processed": 1,
            "failed": 0,
            "skipped": 0,
            "elapsed_seconds": 0,
            "success": True,
            "throughput_files_per_second": 1.0,
        }
        mock_process_directory.return_value = summary

        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, dir=temp_dir) as config_file:
                config_file.write("{invalid json")
                config_path = config_file.name

            with patch.object(
                sys,
                "argv",
                [
                    "transcribe_audio.py",
                    temp_dir,
                    "--config",
                    config_path,
                ],
            ):
                self.assertEqual(transcribe_audio.main(), 1)

            mock_process_directory.assert_not_called()

    @patch("transcribe_audio.process_directory")
    def test_main_uses_resume_from_config(self, mock_process_directory):
        summary = {
            "total": 1,
            "processed": 1,
            "failed": 0,
            "skipped": 0,
            "elapsed_seconds": 0,
            "success": True,
            "throughput_files_per_second": 1.0,
        }
        mock_process_directory.return_value = summary

        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")
            Path(temp_dir, ".whisperbatch").write_text(
                json.dumps(
                    {
                        "model": "base",
                        "resume": True,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch.object(
                sys,
                "argv",
                [
                    "transcribe_audio.py",
                    temp_dir,
                ],
            ):
                self.assertEqual(transcribe_audio.main(), 0)

            call_kwargs = mock_process_directory.call_args.kwargs
            self.assertTrue(call_kwargs["resume"])

    @patch("transcribe_audio.process_directory")
    def test_main_invalid_config_value_rejects(self, mock_process_directory):
        summary = {
            "total": 1,
            "processed": 1,
            "failed": 0,
            "skipped": 0,
            "elapsed_seconds": 0,
            "success": True,
            "throughput_files_per_second": 1.0,
        }
        mock_process_directory.return_value = summary

        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, dir=temp_dir) as config_file:
                json.dump({"timestamps": "nope"}, config_file, ensure_ascii=False)
                config_path = config_file.name

            with patch.object(
                sys,
                "argv",
                [
                    "transcribe_audio.py",
                    temp_dir,
                    "--config",
                    config_path,
                ],
            ):
                self.assertEqual(transcribe_audio.main(), 1)

            mock_process_directory.assert_not_called()

    @patch("transcribe_audio.process_directory")
    def test_main_invalid_config_key_rejects(self, mock_process_directory):
        summary = {
            "total": 1,
            "processed": 1,
            "failed": 0,
            "skipped": 0,
            "elapsed_seconds": 0,
            "success": True,
            "throughput_files_per_second": 1.0,
        }
        mock_process_directory.return_value = summary

        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "speech.wav").write_text("dummy", encoding="utf-8")
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, dir=temp_dir) as config_file:
                json.dump({"unknown_key": "value"}, config_file, ensure_ascii=False)
                config_path = config_file.name

            with patch.object(
                sys,
                "argv",
                [
                    "transcribe_audio.py",
                    temp_dir,
                    "--config",
                    config_path,
                ],
            ):
                self.assertEqual(transcribe_audio.main(), 1)

            mock_process_directory.assert_not_called()

    def test_model_default_constant_is_single_source_of_truth(self):
        self.assertEqual(
            transcribe_audio.DEFAULT_CLI_OPTIONS["model_name"],
            transcribe_audio.DEFAULT_MODEL_NAME,
        )
        self.assertEqual(
            transcribe_audio.DEFAULT_CLI_OPTIONS["task"],
            transcribe_audio.DEFAULT_TASK_NAME,
        )
        self.assertEqual(
            transcribe_audio.transcribe_audio.__defaults__[0],
            transcribe_audio.DEFAULT_MODEL_NAME,
        )
        self.assertEqual(
            transcribe_audio.transcribe_audio_result.__defaults__[0],
            transcribe_audio.DEFAULT_MODEL_NAME,
        )
        self.assertEqual(
            transcribe_audio.transcribe_audio.__defaults__[3],
            transcribe_audio.DEFAULT_TASK_NAME,
        )
        self.assertEqual(
            transcribe_audio.transcribe_audio_result.__defaults__[4],
            transcribe_audio.DEFAULT_TASK_NAME,
        )
        self.assertEqual(
            transcribe_audio.process_directory.__defaults__[10],
            transcribe_audio.DEFAULT_TASK_NAME,
        )

    @patch("sys.stderr")
    @patch("sys.stdout")
    def test_cli_displays_help(self, mock_stdout, mock_stderr):
        with patch.object(sys, "argv", ["transcribe_audio.py", "--help"]):
            with self.assertRaises(SystemExit) as ctx:
                transcribe_audio.main()
            self.assertEqual(ctx.exception.code, 0)

    @patch("sys.stderr")
    @patch("sys.stdout")
    def test_cli_rejects_invalid_argument(self, mock_stdout, mock_stderr):
        with patch.object(sys, "argv", ["transcribe_audio.py", "--not-a-real-flag"]):
            with self.assertRaises(SystemExit) as ctx:
                transcribe_audio.main()
            self.assertEqual(ctx.exception.code, 2)

    def test_cli_help_mentions_default_model(self):
        with patch("sys.argv", ["transcribe_audio.py", "--help"]), patch(
            "sys.stdout", new=io.StringIO()
        ) as stdout, patch("sys.stderr", new=io.StringIO()) as stderr:
            with self.assertRaises(SystemExit):
                transcribe_audio.main()
        help_text = "\n".join((stdout.getvalue(), stderr.getvalue()))
        self.assertIn(
            f"faster-whisper model to use (default: {transcribe_audio.DEFAULT_MODEL_NAME})",
            help_text,
        )

    def test_cli_help_mentions_supported_tasks(self):
        with patch("sys.argv", ["transcribe_audio.py", "--help"]), patch(
            "sys.stdout", new=io.StringIO()
        ) as stdout, patch("sys.stderr", new=io.StringIO()) as stderr:
            with self.assertRaises(SystemExit):
                transcribe_audio.main()
        help_text = "\n".join((stdout.getvalue(), stderr.getvalue()))
        expected_supported_tasks = ", ".join(sorted(transcribe_audio.SUPPORTED_TASKS))
        self.assertIn(
            f"Whisper task to run. Supported values: {expected_supported_tasks}.",
            help_text,
        )

    def test_cli_help_mentions_supported_output_formats(self):
        with patch("sys.argv", ["transcribe_audio.py", "--help"]), patch(
            "sys.stdout", new=io.StringIO()
        ) as stdout, patch("sys.stderr", new=io.StringIO()) as stderr:
            with self.assertRaises(SystemExit):
                transcribe_audio.main()
        help_text = "\n".join((stdout.getvalue(), stderr.getvalue()))
        expected_supported_formats = ", ".join(sorted(transcribe_audio.SUPPORTED_OUTPUT_FORMATS))
        self.assertIn(
            f"Output format: {expected_supported_formats}.",
            help_text,
        )


if __name__ == "__main__":
    unittest.main()
