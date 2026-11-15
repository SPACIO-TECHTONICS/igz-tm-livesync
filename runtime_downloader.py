"""
Automated discovery, official download, and verification for Epic Datasmith runtime.
Extracts required DLLs to a local vendor directory without modifying system software.
"""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import urllib.request
from typing import Callable, Optional

MSI_URL = "https://unrealstudio.epicgames.com/UnrealDatasmithRhinoExporter_5_8_400.msi"
MSI_SHA256 = "7f0e3039e9c8a772b20654342854d497c16799a92077ba2a9df0e9076f1b1927"

RUNTIME_HASHES = {
    'DatasmithFacadeCSharp.dll': 'eb3e4881629244bbc3a5cb1062aa579d79f68ebb682b5140a274c7c0d1d6fc08',
    'DatasmithRhino6.rhp': '77e2073dc7bd792896f976562f97f125dd1289231338b20ef5bd8d2b6795cd1d',
    'tbbmalloc.dll': '87abcd8f7e31003ab049962a97eb645310be1ccab7ba148c46b2cde5262027bf',
}


def verify_runtime_directory(directory: Path) -> bool:
    """Returns True if the directory contains all 3 required Datasmith runtime files with exact SHA256."""
    dir_path = Path(directory).resolve()
    for name, expected_hash in RUNTIME_HASHES.items():
        file_path = dir_path / name
        if not file_path.is_file():
            return False
        try:
            actual = hashlib.sha256(file_path.read_bytes()).hexdigest()
            if actual != expected_hash:
                return False
        except Exception:
            return False
    return True


def find_existing_runtime() -> Optional[Path]:
    """Scans standard known local locations for the Datasmith runtime."""
    candidates = [
        Path(os.environ.get('LOCALAPPDATA', '')) / 'IngeTrazo' / 'twinmotion_sync' / 'vendor',
        Path(r"C:\DatasmithRuntime"),
        Path(r"C:\ProgramData\McNeel\Rhinoceros\7.0\Plug-ins\Datasmith Rhino Exporter (d1fdc795-b334-4933-b680-088119cdc6bb)"),
        Path(r"C:\ProgramData\McNeel\Rhinoceros\6.0\Plug-ins\Datasmith Rhino Exporter (d1fdc795-b334-4933-b680-088119cdc6bb)"),
        Path(r"C:\ProgramData\McNeel\Rhinoceros\8.0\Plug-ins\Datasmith Rhino Exporter (d1fdc795-b334-4933-b680-088119cdc6bb)"),
    ]
    for c in candidates:
        if c.is_dir() and verify_runtime_directory(c):
            return c.resolve()
    return None


def get_default_vendor_dir() -> Path:
    """Returns standard application vendor directory for extracted runtime files."""
    base = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'IngeTrazo' / 'twinmotion_sync' / 'vendor'
    base.mkdir(parents=True, exist_ok=True)
    return base.resolve()


def download_and_extract_runtime(
    target_dir: Optional[Path] = None,
    progress_callback: Optional[Callable[[str, float], None]] = None
) -> Path:
    """
    Downloads Epic's official Datasmith MSI, verifies checksum,
    extracts runtime files cleanly with msiexec /a, and saves to target_dir.
    """
    dest = target_dir or get_default_vendor_dir()
    dest = Path(dest).resolve()
    dest.mkdir(parents=True, exist_ok=True)

    if verify_runtime_directory(dest):
        if progress_callback:
            progress_callback("Datasmith runtime already verified in target directory.", 1.0)
        return dest

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        msi_path = temp_path / "UnrealDatasmithRhinoExporter_5_8_400.msi"
        extract_dir = temp_path / "extracted"
        extract_dir.mkdir(exist_ok=True)

        if progress_callback:
            progress_callback("Downloading official Epic Datasmith 5.8.4 installer...", 0.1)

        def report_hook(block_num, block_size, total_size):
            if total_size > 0 and progress_callback:
                downloaded = block_num * block_size
                pct = min(0.7, 0.1 + (downloaded / total_size) * 0.6)
                mb_down = downloaded / (1024 * 1024)
                mb_total = total_size / (1024 * 1024)
                progress_callback(f"Downloading Datasmith MSI: {mb_down:.1f}/{mb_total:.1f} MB", pct)

        urllib.request.urlretrieve(MSI_URL, str(msi_path), reporthook=report_hook)

        if progress_callback:
            progress_callback("Verifying installer SHA256 checksum...", 0.75)

        actual_msi_hash = hashlib.sha256(msi_path.read_bytes()).hexdigest()
        if actual_msi_hash != MSI_SHA256:
            raise ValueError(
                f"MSI hash mismatch! Expected {MSI_SHA256}, got {actual_msi_hash}."
            )

        if progress_callback:
            progress_callback("Extracting runtime files from package...", 0.85)

        cmd = [
            "msiexec.exe",
            "/a",
            str(msi_path),
            "/qn",
            f"TARGETDIR={extract_dir}",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"msiexec extraction failed with exit code {res.returncode}: {res.stderr}")

        if progress_callback:
            progress_callback("Verifying and copying runtime libraries...", 0.95)

        found_files = {}
        for p in extract_dir.rglob("*"):
            if p.is_file() and p.name in RUNTIME_HASHES:
                found_files[p.name] = p

        missing = set(RUNTIME_HASHES.keys()) - set(found_files.keys())
        if missing:
            raise FileNotFoundError(f"Could not find required files in extracted package: {missing}")

        for name, expected_hash in RUNTIME_HASHES.items():
            src_file = found_files[name]
            file_hash = hashlib.sha256(src_file.read_bytes()).hexdigest()
            if file_hash != expected_hash:
                raise ValueError(f"Checksum mismatch for {name}: expected {expected_hash}, got {file_hash}")
            shutil.copy2(src_file, dest / name)

    if not verify_runtime_directory(dest):
        raise RuntimeError("Failed to verify runtime files after copying.")

    if progress_callback:
        progress_callback("Datasmith runtime ready.", 1.0)

    return dest
