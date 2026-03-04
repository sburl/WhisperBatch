import json
import tempfile
from pathlib import Path
from unittest import TestCase

from sample_postprocess_plugins import redact_email_addresses, write_plugin_audit


class TestPostprocessPlugins(TestCase):
    def test_redact_email_addresses(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir, "speech_transcription.txt")
            output_path.write_text("Contact me at user@example.com by phone.", encoding="utf-8")

            redact_email_addresses(str(output_path), {})

            transformed = output_path.read_text(encoding="utf-8")
            self.assertNotIn("user@example.com", transformed)
            self.assertIn("[REDACTED_EMAIL]", transformed)

    def test_write_plugin_audit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir, "speech_transcription.txt")
            output_path.write_text("hello", encoding="utf-8")
            metadata = {
                "source_path": "/tmp/source.wav",
                "output_path": str(output_path),
                "model": "base",
                "task": "transcribe",
                "language": "en",
                "output_format": "txt",
                "processed_at": 1234.5,
            }

            write_plugin_audit(str(output_path), metadata)

            audit_path = output_path.with_suffix(output_path.suffix + ".plugin_audit.json")
            self.assertTrue(audit_path.exists())
            payload = json.loads(audit_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["plugin"], "write_plugin_audit")
            self.assertEqual(payload["model"], metadata["model"])
            self.assertEqual(payload["output_format"], "txt")
            self.assertEqual(payload["source_path"], "/tmp/source.wav")
