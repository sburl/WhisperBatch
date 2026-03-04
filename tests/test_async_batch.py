import tempfile
import unittest
from pathlib import Path

from whisper_batch_core.async_batch import (
    AsyncExecutionPolicy,
    TranscriptionTask,
    build_stable_task_queue,
    build_task_metadata,
    evaluate_async_execution_policy,
)
from whisper_batch_core import DEFAULT_OUTPUT_FORMAT


class TestAsyncBatchContract(unittest.TestCase):
    def test_build_stable_task_queue_orders_case_variants(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "B.MP3").touch()
            (root / "a.mp3").touch()
            (root / "A.mp3").touch()
            (root / "b.mp3").touch()

            tasks = build_stable_task_queue(
                [root / "b.mp3", root / "a.mp3", root / "B.MP3", root / "A.mp3"]
            )
            ordered = [task.source_path.name for task in tasks]

            self.assertEqual(
                ordered,
                ["A.mp3", "a.mp3", "B.MP3", "b.mp3"],
            )
            self.assertEqual([task.index for task in tasks], [0, 1, 2, 3])

    def test_build_task_metadata(self):
        task = TranscriptionTask(index=3, source_path=Path("/tmp/speech.mp3"), output_format="json")
        self.assertEqual(
            build_task_metadata(task),
            {
                "index": 3,
                "source_path": "/tmp/speech.mp3",
                "output_format": "json",
            },
        )

    def test_task_dataclass_is_immutable(self):
        task = TranscriptionTask(index=0, source_path=Path("/tmp/a.wav"))
        with self.assertRaises(AttributeError):
            task.index = 99

    def test_task_defaults_use_shared_output_format_constant(self):
        task = TranscriptionTask(index=1, source_path=Path("/tmp/sample.wav"))
        self.assertEqual(task.output_format, DEFAULT_OUTPUT_FORMAT)

    def test_evaluate_async_policy_blocks_default_parallelism(self):
        policy = evaluate_async_execution_policy(
            requested_workers=4,
            postprocess_command=None,
            postprocess_plugin=None,
        )
        self.assertFalse(policy.enabled)
        self.assertIsInstance(policy, AsyncExecutionPolicy)
        self.assertIn("reserved", policy.reason or "")

    def test_evaluate_async_policy_blocks_postprocess_command(self):
        policy = evaluate_async_execution_policy(
            requested_workers=4,
            postprocess_command="python /tmp/process.py",
            postprocess_plugin=None,
        )
        self.assertFalse(policy.enabled)
        self.assertIn("postprocess hooks", policy.reason or "")
