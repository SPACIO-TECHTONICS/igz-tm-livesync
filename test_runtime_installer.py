"""Tests for runtime downloader discovery, verification, and setup_local."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
import runtime_downloader
import setup_local

class TestRuntimeInstaller(unittest.TestCase):

    def test_verify_empty_dir_fails(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertFalse(runtime_downloader.verify_runtime_directory(Path(td)))

    def test_verify_corrupted_file_fails(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            f = p / "DatasmithFacadeCSharp.dll"
            f.write_text("corrupted content")
            self.assertFalse(runtime_downloader.verify_runtime_directory(p))

    def test_find_existing_runtime(self):
        found = runtime_downloader.find_existing_runtime()
        if found:
            self.assertTrue(runtime_downloader.verify_runtime_directory(found))

    def test_setup_local_prerequisites_check_only(self):
        vendor = setup_local.find_or_download_runtime(auto_download=False)
        self.assertTrue(setup_local.CSC_PATH.is_file())
        self.assertTrue(runtime_downloader.verify_runtime_directory(vendor))

if __name__ == '__main__':
    unittest.main()
