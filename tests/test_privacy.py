"""Behavioral tests for privacy, export and non-destructive initialization."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("pgos", Path(__file__).resolve().parents[1] / "scripts/pgos.py")
pgos = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pgos)


class PrivacyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "config").mkdir()
        self.manifest = ["README.md", pgos.MANIFEST]
        self.write("README.md", "# Synthetic fixture\n")
        self.save_manifest()

    def tearDown(self):
        self.temp.cleanup()

    def write(self, rel, value):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")

    def save_manifest(self):
        self.write(pgos.MANIFEST, json.dumps(self.manifest))

    def test_sensitive_patterns_block_export_without_echoing_values(self):
        samples = [
            "sk-" + "Z" * 30,
            "sample" + "@" + "example.org",
            "138" + "01234567",
            "110101" + "20000101" + "1234",
            "C:" + "\\" + "Users" + "\\" + "Example",
            "api_key" + "=" + "Z" * 24,
            "-----BEGIN " + "PRIVATE KEY-----",
            "我就" + "读于示例学府",
        ]
        for sample in samples:
            with self.subTest(kind=len(sample)):
                self.write("README.md", sample)
                _, findings = pgos.check(self.root)
                self.assertTrue(findings)
                self.assertNotIn(sample, repr(findings))
                with self.assertRaises(ValueError):
                    pgos.export(self.root)
                self.assertFalse((self.root / "private/release/personal-growth-os").exists())

    def test_private_data_and_git_history_never_export(self):
        self.write("private/diary.md", "PRIVATE_CONTENT")
        self.write(".git/config", "PRIVATE_REMOTE")
        target, count = pgos.export(self.root)
        actual = sorted(p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file())
        self.assertEqual(sorted(self.manifest), actual)
        self.assertEqual(count, len(self.manifest))
        for rel in self.manifest:
            self.assertEqual((target / rel).read_bytes(), (self.root / rel).read_bytes())
        with self.assertRaises(ValueError):
            pgos.export(self.root)

    def test_manifest_rejects_private_traversal_absolute_and_duplicates(self):
        for rel in ["../outside.md", "private/diary.md", "/outside.md", "config/local.yaml", "README.md"]:
            self.manifest = ["README.md", pgos.MANIFEST, rel]
            self.save_manifest()
            with self.subTest(rel=rel), self.assertRaises(ValueError):
                pgos.public_files(self.root)

    def test_unknown_files_and_binary_content_block(self):
        self.write("forgotten.md", "unreviewed")
        self.assertTrue(pgos.check(self.root)[1])
        (self.root / "forgotten.md").unlink()
        (self.root / "README.md").write_bytes(b"\x00\xff")
        self.assertTrue(pgos.check(self.root)[1])

    def test_denylist_catches_identity_in_content_and_filename(self):
        self.write("README.md", "SyntheticName")
        self.assertTrue(pgos.check(self.root, ["SyntheticName"])[1])
        self.assertTrue(pgos.check(self.root, ["readme"])[1])

    def test_init_preserves_existing_content(self):
        for name in ["goals", "learning", "knowledge", "reflection", "review", "habit", "prompt", "memory"]:
            self.write(f"templates/{name}-template.md", "<blank>")
        self.write("config/config.example.yaml", "schema_version: 1")
        self.write("private/workspace/goals/current.md", "existing user content")
        self.assertEqual(pgos.initialize(self.root), 8)
        self.assertEqual(pgos.initialize(self.root), 0)
        self.assertEqual((self.root / "private/workspace/goals/current.md").read_text(), "existing user content")

    def test_export_rejects_destination_escape(self):
        for target in ["elsewhere", "private/release/../../outside", "private/release/../escape"]:
            with self.subTest(target=target), self.assertRaises(ValueError):
                pgos.export(self.root, target)

    def test_symlink_is_rejected(self):
        target = self.root / "README.md"
        alias = self.root / "alias.md"
        try:
            alias.symlink_to(target)
        except OSError:
            self.skipTest("OS does not permit symlink creation")
        self.manifest.append("alias.md")
        self.save_manifest()
        with self.assertRaises(ValueError):
            pgos.public_files(self.root)

    @unittest.skipUnless(os.name == "nt", "Windows junction check")
    def test_windows_directory_junction_is_rejected(self):
        original = self.root / "original"
        original.mkdir()
        (original / "entry.md").write_text("synthetic", encoding="utf-8")
        alias = self.root / "alias"
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(alias), str(original)],
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, "junction setup failed")
        self.manifest.append("alias/entry.md")
        self.save_manifest()
        with self.assertRaises(ValueError):
            pgos.public_files(self.root)

    def test_manifest_and_public_directory_links_are_rejected(self):
        # Even if a linked file is not in the allowlist, export must fail closed.
        self.write("extra/entry.md", "synthetic")
        self.assertTrue(pgos.check(self.root)[1])


if __name__ == "__main__":
    unittest.main()
