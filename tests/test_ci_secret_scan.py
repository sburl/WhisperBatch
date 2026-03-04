from __future__ import annotations

import io
from contextlib import redirect_stdout
from pathlib import Path
import unittest
import tempfile

from scripts import ci_secret_scan


class TestCiSecretScan(unittest.TestCase):
    def test_should_skip_ignores_configured_paths(self):
        path_in_ignored_dir = Path("/repo/.git/config")
        path_ignored_file = Path("/repo/requirements.txt")
        path_ok = Path("/repo/src/transcribe_audio.py")

        self.assertTrue(ci_secret_scan._should_skip(path_in_ignored_dir))
        self.assertTrue(ci_secret_scan._should_skip(path_ignored_file))
        self.assertFalse(ci_secret_scan._should_skip(path_ok))

    def test_scan_file_finds_known_secret_pattern(self):
        fake_secret = "gh" + "p_" + ("A" * 36)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py") as tmp_file:
            tmp_file.write(fake_secret)
            tmp_file.flush()

            matches = ci_secret_scan._scan_file(Path(tmp_file.name))

            self.assertEqual(len(matches), 1)
            self.assertEqual(matches[0][1], "github_pat")

    def test_main_reports_no_secrets(self):
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            (root / "ok.txt").write_text("safe text", encoding="utf-8")
            (root / "nested").mkdir()
            (root / "nested" / "readme.md").write_text("no secrets here", encoding="utf-8")

            original_root = ci_secret_scan.ROOT
            ci_secret_scan.ROOT = root

            try:
                buffer = io.StringIO()
                with redirect_stdout(buffer):
                    status = ci_secret_scan.main()
                self.assertEqual(status, 0)
            finally:
                ci_secret_scan.ROOT = original_root

            self.assertIn("No secrets detected.", buffer.getvalue())

    def test_main_reports_secrets(self):
        fake_secret = "gh" + "p_" + ("A" * 36)
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            (root / "bad.py").write_text(fake_secret, encoding="utf-8")

            original_root = ci_secret_scan.ROOT
            ci_secret_scan.ROOT = root

            try:
                buffer = io.StringIO()
                with redirect_stdout(buffer):
                    status = ci_secret_scan.main()
                self.assertEqual(status, 1)
            finally:
                ci_secret_scan.ROOT = original_root

            output = buffer.getvalue()
            self.assertIn("Potential secrets found:", output)
            self.assertIn("github_pat", output)


if __name__ == "__main__":
    unittest.main()
