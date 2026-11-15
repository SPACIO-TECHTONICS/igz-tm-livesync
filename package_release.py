"""
Package the IngeTrazo Twinmotion LiveSync extension into a distributable release ZIP.
Includes plugin files, icons, compiled worker, documentation, and automated installer.
"""
import argparse
import os
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent

RELEASE_FILES = [
    "plugin.json",
    "__init__.py",
    "igz_tm_sync.py",
    "directlink_bridge.py",
    "mesh_exporter.py",
    "runtime_downloader.py",
    "DatasmithWorker.cs",
    "DatasmithWorker.exe",
    "setup_app.py",
    "setup_app.pyw",
    "setup_local.py",
    "LICENSE",
    "NOTICE.md",
    "README.md",
    ".env",
]

RELEASE_DIRS = [
    "icons",
]

EXCLUDE_EXTS = {".pyc", ".tmp", ".log", ".rhp", ".dll", ".pdb"}


def create_release_zip(output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in RELEASE_FILES:
            full = ROOT / f
            if full.is_file():
                z.write(full, arcname=f)
                print(f"Added file: {f}")

        for d in RELEASE_DIRS:
            dir_path = ROOT / d
            if dir_path.is_dir():
                for p in dir_path.rglob("*"):
                    if p.is_file() and p.suffix not in EXCLUDE_EXTS and "__pycache__" not in p.parts:
                        rel = str(p.relative_to(ROOT))
                        z.write(p, arcname=rel)
                        print(f"Added asset: {rel}")

    size_kb = output_path.stat().st_size / 1024
    print(f"\nSuccessfully packaged: {output_path} ({size_kb:.1f} KB)")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Create release ZIP for IngeTrazo Marketplace.")
    parser.add_argument("--version", default="1.0.0", help="Release version string")
    parser.add_argument("--output", default=None, help="Output ZIP file path")
    args = parser.parse_args()

    out_file = Path(args.output) if args.output else ROOT / "dist" / f"igz-tm-livesync-v{args.version}.zip"
    create_release_zip(out_file)


if __name__ == "__main__":
    main()
