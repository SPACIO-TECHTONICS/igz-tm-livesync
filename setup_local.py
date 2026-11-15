"""
Local Build and Setup Helper for IngeTrazo Twinmotion LiveSync.
Automates Datasmith runtime discovery, download, compilation, and extension installation.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import runtime_downloader

CSC_PATH = Path(os.environ.get('WINDIR', 'C:\\Windows')) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
DEFAULT_INGETRAZO_PLUGINS = Path(os.environ.get('APPDATA', '')) / 'ingetrazo/plugins/igz_tm_livesync'
ROOT = Path(__file__).resolve().parent


def find_or_download_runtime(vendor_dir=None, auto_download=True):
    """Finds existing Datasmith runtime or downloads official installer automatically."""
    if vendor_dir:
        v = Path(vendor_dir).resolve()
        if runtime_downloader.verify_runtime_directory(v):
            return v
        raise ValueError(f"Specified vendor directory does not contain verified runtime: {v}")

    existing = runtime_downloader.find_existing_runtime()
    if existing:
        print(f"[Setup] Detected existing Datasmith runtime: {existing}")
        return existing

    if not auto_download:
        raise FileNotFoundError("Datasmith runtime was not found. Use --vendor-dir or allow auto-download.")

    print("[Setup] Datasmith runtime not found locally. Downloading official Epic installer...")
    def on_progress(msg, pct):
        print(f"[{int(pct*100):3d}%] {msg}")

    vendor = runtime_downloader.download_and_extract_runtime(progress_callback=on_progress)
    print(f"[Setup] Extracted runtime libraries to: {vendor}")
    return vendor


def compile_worker(source_file, output_exe):
    """Compiles the C# Datasmith worker using Windows csc.exe."""
    if not CSC_PATH.is_file():
        raise FileNotFoundError(f"C# compiler not found at: {CSC_PATH}")

    # Stop any running DatasmithWorker
    try:
        subprocess.run(["taskkill", "/F", "/IM", "DatasmithWorker.exe"], capture_output=True)
    except Exception:
        pass

    cmd = [
        str(CSC_PATH),
        "/nologo",
        "/target:exe",
        "/platform:x64",
        "/optimize+",
        f"/out:{output_exe}",
        str(source_file)
    ]

    print(f"[Setup] Compiling worker: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print("[Setup] Worker compiled successfully.")
        return True
    else:
        err_msg = result.stdout if result.stdout else result.stderr
        raise RuntimeError(f"Worker compilation failed:\n{err_msg}")


def install_plugin(vendor_dir, target_dir=DEFAULT_INGETRAZO_PLUGINS):
    """Copies all extension files and runtime DLLs into IngeTrazo plugins folder."""
    target_dir = Path(target_dir).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    # Stop any running DatasmithWorker process to release file locks
    try:
        subprocess.run(["taskkill", "/F", "/IM", "DatasmithWorker.exe"], capture_output=True)
        time.sleep(0.8)
    except Exception:
        pass

    files_to_copy = [
        "__init__.py",
        "plugin.json",
        "igz_tm_sync.py",
        "directlink_bridge.py",
        "mesh_exporter.py",
        "DatasmithWorker.exe",
        "README.md",
        "LICENSE",
        "NOTICE.md",
    ]

    for fname in files_to_copy:
        src = ROOT / fname
        if src.is_file():
            dst = target_dir / fname
            for _ in range(3):
                try:
                    shutil.copy2(src, dst)
                    print(f"[Setup] Installed: {fname}")
                    break
                except PermissionError:
                    subprocess.run(["taskkill", "/F", "/IM", "DatasmithWorker.exe"], capture_output=True)
                    time.sleep(0.5)

    # Copy runtime DLLs alongside the worker executable for direct loading
    if vendor_dir:
        v_path = Path(vendor_dir)
        for dll_name in ("DatasmithFacadeCSharp.dll", "tbbmalloc.dll"):
            dll_src = v_path / dll_name
            if dll_src.is_file():
                shutil.copy2(dll_src, target_dir / dll_name)
                print(f"[Setup] Installed Runtime Library: {dll_name}")

    # Copy icons directory
    icons_src = ROOT / "icons"
    icons_dst = target_dir / "icons"
    if icons_src.is_dir():
        icons_dst.mkdir(parents=True, exist_ok=True)
        for icon_file in icons_src.glob("*.svg"):
            shutil.copy2(icon_file, icons_dst / icon_file.name)
            print(f"[Setup] Installed Icon: {icon_file.name}")

    print(f"\n[Setup] Successfully installed extension to: {target_dir}")


def main():
    parser = argparse.ArgumentParser(description="Build and setup IngeTrazo Twinmotion LiveSync extension.")
    parser.add_argument("--vendor-dir", default=None, help="Path to Epic Datasmith runtime files")
    parser.add_argument("--install-dir", default=str(DEFAULT_INGETRAZO_PLUGINS), help="IngeTrazo plugins folder")
    parser.add_argument("--no-download", action="store_true", help="Do not auto-download Datasmith if missing")
    parser.add_argument("--build-only", action="store_true", help="Compile worker without installing")
    parser.add_argument("--check-only", action="store_true", help="Verify prerequisites without installing")
    args = parser.parse_args()

    vendor = find_or_download_runtime(args.vendor_dir, auto_download=not args.no_download)

    if args.check_only:
        print(json.dumps({
            "prerequisites_ok": True,
            "vendor_dir": str(vendor),
            "compiler": str(CSC_PATH),
            "target_dir": args.install_dir
        }, indent=2))
        return

    source_cs = ROOT / "DatasmithWorker.cs"
    output_exe = ROOT / "DatasmithWorker.exe"

    compile_worker(source_cs, output_exe)

    if not args.build_only:
        install_plugin(vendor, Path(args.install_dir))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[Error] Setup failed: {e}", file=sys.stderr)
        sys.exit(1)
